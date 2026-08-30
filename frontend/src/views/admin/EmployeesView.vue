<script setup lang="ts">
import dayjs from 'dayjs'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { computed, onMounted, ref } from 'vue'
import { ApiRequestError } from '@/api/client'
import { useEmployeesStore } from '@/stores/employees'
import type { Employee, EmployeeRole } from '@/types/domain'

const store = useEmployeesStore()
const toast = useToast()

onMounted(() => {
  store.fetchEmployees()
})

const roleOptions: { label: string; value: EmployeeRole }[] = [
  { label: '正社員', value: 'employee' },
  { label: '管理者', value: 'admin' },
]

const search = ref('')
const filteredEmployees = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return store.employees
  return store.employees.filter(
    (e) => e.name.toLowerCase().includes(q) || e.email.toLowerCase().includes(q),
  )
})

const optionOrNull = (list: { id: string; name: string }[]) => [{ label: '未設定', value: null }, ...list.map((o) => ({ label: o.name, value: o.id }))]

// --- 新規登録 ---
const showAddDialog = ref(false)
const addForm = ref({
  email: '',
  name: '',
  password: '',
  role: 'employee' as EmployeeRole,
  hireDate: '',
  teamId: null as string | null,
  workPatternId: null as string | null,
  leavePolicyId: null as string | null,
})
const addError = ref('')

function openAddDialog() {
  addForm.value = {
    email: '',
    name: '',
    password: '',
    role: 'employee',
    hireDate: '',
    teamId: null,
    workPatternId: null,
    leavePolicyId: null,
  }
  addError.value = ''
  showAddDialog.value = true
}

async function onSubmitAdd() {
  addError.value = ''
  try {
    await store.createEmployee({
      email: addForm.value.email,
      name: addForm.value.name,
      password: addForm.value.password,
      role: addForm.value.role,
      hireDate: addForm.value.hireDate || null,
      teamId: addForm.value.teamId,
      workPatternId: addForm.value.workPatternId,
      leavePolicyId: addForm.value.leavePolicyId,
    })
    showAddDialog.value = false
    toast.add({ severity: 'success', summary: `${addForm.value.name}さんを登録しました`, life: 2500 })
  } catch (e) {
    addError.value = e instanceof ApiRequestError ? e.message : '登録に失敗しました。'
  }
}

// --- 編集 ---
const showEditDialog = ref(false)
const editTarget = ref<Employee | null>(null)
const editForm = ref({
  name: '',
  role: 'employee' as EmployeeRole,
  hireDate: '' as string | null,
  retiredAt: '' as string | null,
  isActive: true,
  teamId: null as string | null,
  workPatternId: null as string | null,
  leavePolicyId: null as string | null,
  password: '',
})
const editError = ref('')

function openEditDialog(employee: Employee) {
  editTarget.value = employee
  editForm.value = {
    name: employee.name,
    role: employee.role,
    hireDate: employee.hireDate,
    retiredAt: employee.retiredAt,
    isActive: employee.isActive,
    teamId: employee.teamId,
    workPatternId: employee.workPatternId,
    leavePolicyId: employee.leavePolicyId,
    password: '',
  }
  editError.value = ''
  showEditDialog.value = true
}

async function onSubmitEdit() {
  if (!editTarget.value) return
  editError.value = ''
  try {
    await store.updateEmployee(editTarget.value.id, {
      name: editForm.value.name,
      role: editForm.value.role,
      hireDate: editForm.value.hireDate || null,
      retiredAt: editForm.value.retiredAt || null,
      isActive: editForm.value.isActive,
      teamId: editForm.value.teamId,
      workPatternId: editForm.value.workPatternId,
      leavePolicyId: editForm.value.leavePolicyId,
      ...(editForm.value.password ? { password: editForm.value.password } : {}),
    })
    showEditDialog.value = false
    toast.add({ severity: 'success', summary: '更新しました', life: 2000 })
  } catch (e) {
    editError.value = e instanceof ApiRequestError ? e.message : '更新に失敗しました。'
  }
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">管理者</p>
      <h1 class="page__title">従業員管理</h1>
    </header>

    <Card>
      <template #content>
        <div class="toolbar">
          <IconField>
            <InputIcon class="pi pi-search" />
            <InputText v-model="search" placeholder="名前・メールで検索" />
          </IconField>
          <Button label="従業員を登録" icon="pi pi-user-plus" @click="openAddDialog" />
        </div>

        <DataTable :value="filteredEmployees" size="small" :loading="store.loading" paginator :rows="10">
          <Column field="name" header="氏名" style="width: 140px" />
          <Column field="email" header="メールアドレス" />
          <Column header="区分" style="width: 90px">
            <template #body="{ data }">
              <Tag :value="data.isAdmin ? '管理者' : '正社員'" :severity="data.isAdmin ? 'warn' : 'info'" />
            </template>
          </Column>
          <Column header="グループ" style="width: 120px">
            <template #body="{ data }">{{ data.teamName ?? '未設定' }}</template>
          </Column>
          <Column header="勤務体系" style="width: 160px">
            <template #body="{ data }">{{ data.workPatternName ?? '未設定' }}</template>
          </Column>
          <Column header="有給ポリシー" style="width: 140px">
            <template #body="{ data }">{{ data.leavePolicyName ?? '未設定' }}</template>
          </Column>
          <Column field="hireDate" header="入社日" style="width: 110px">
            <template #body="{ data }">{{ data.hireDate ? dayjs(data.hireDate).format('YYYY/M/D') : '—' }}</template>
          </Column>
          <Column header="状態" style="width: 90px">
            <template #body="{ data }">
              <Tag :value="data.isActive ? '在籍中' : '退職済み'" :severity="data.isActive ? 'success' : 'secondary'" />
            </template>
          </Column>
          <Column header="操作" style="width: 70px">
            <template #body="{ data }">
              <Button
                icon="pi pi-pencil"
                size="small"
                severity="secondary"
                text
                aria-label="編集"
                title="編集"
                @click="openEditDialog(data)"
              />
            </template>
          </Column>
          <template #empty>該当する従業員はいません。</template>
        </DataTable>
      </template>
    </Card>

    <Dialog v-model:visible="showAddDialog" header="従業員を登録" modal :style="{ width: '440px' }">
      <form class="form" @submit.prevent="onSubmitAdd">
        <label class="field">
          <span class="field__label">氏名</span>
          <InputText v-model="addForm.name" required />
        </label>
        <label class="field">
          <span class="field__label">メールアドレス</span>
          <InputText v-model="addForm.email" type="email" required />
        </label>
        <label class="field">
          <span class="field__label">初期パスワード（12文字以上）</span>
          <InputText v-model="addForm.password" type="password" required />
        </label>
        <label class="field">
          <span class="field__label">区分</span>
          <Select v-model="addForm.role" :options="roleOptions" option-label="label" option-value="value" />
        </label>
        <label class="field">
          <span class="field__label">入社日</span>
          <input v-model="addForm.hireDate" type="date" />
        </label>
        <label class="field">
          <span class="field__label">グループ</span>
          <Select v-model="addForm.teamId" :options="optionOrNull(store.teams)" option-label="label" option-value="value" />
        </label>
        <label class="field">
          <span class="field__label">勤務体系</span>
          <Select v-model="addForm.workPatternId" :options="optionOrNull(store.workPatterns)" option-label="label" option-value="value" />
        </label>
        <label class="field">
          <span class="field__label">有給ポリシー</span>
          <Select v-model="addForm.leavePolicyId" :options="optionOrNull(store.leavePolicies)" option-label="label" option-value="value" />
        </label>
        <p v-if="addError" class="form__error">{{ addError }}</p>
        <div class="form__actions">
          <Button type="button" label="キャンセル" severity="secondary" text @click="showAddDialog = false" />
          <Button type="submit" label="登録する" :loading="store.saving" />
        </div>
      </form>
    </Dialog>

    <Dialog v-model:visible="showEditDialog" header="従業員を編集" modal :style="{ width: '440px' }">
      <form v-if="editTarget" class="form" @submit.prevent="onSubmitEdit">
        <p class="form__target">{{ editTarget.email }}</p>
        <label class="field">
          <span class="field__label">氏名</span>
          <InputText v-model="editForm.name" required />
        </label>
        <label class="field">
          <span class="field__label">区分</span>
          <Select v-model="editForm.role" :options="roleOptions" option-label="label" option-value="value" />
        </label>
        <label class="field">
          <span class="field__label">入社日</span>
          <input v-model="editForm.hireDate" type="date" />
        </label>
        <label class="field">
          <span class="field__label">グループ</span>
          <Select v-model="editForm.teamId" :options="optionOrNull(store.teams)" option-label="label" option-value="value" />
        </label>
        <label class="field">
          <span class="field__label">勤務体系</span>
          <Select v-model="editForm.workPatternId" :options="optionOrNull(store.workPatterns)" option-label="label" option-value="value" />
        </label>
        <label class="field">
          <span class="field__label">有給ポリシー</span>
          <Select v-model="editForm.leavePolicyId" :options="optionOrNull(store.leavePolicies)" option-label="label" option-value="value" />
        </label>
        <label class="toggle">
          <input v-model="editForm.isActive" type="checkbox" />
          在籍中
        </label>
        <label class="field" v-if="!editForm.isActive">
          <span class="field__label">退職日</span>
          <input v-model="editForm.retiredAt" type="date" />
        </label>
        <label class="field">
          <span class="field__label">パスワードを再設定（任意）</span>
          <InputText v-model="editForm.password" type="password" placeholder="変更しない場合は空欄" />
        </label>
        <p v-if="editError" class="form__error">{{ editError }}</p>
        <div class="form__actions">
          <Button type="button" label="キャンセル" severity="secondary" text @click="showEditDialog = false" />
          <Button type="submit" label="保存する" :loading="store.saving" />
        </div>
      </form>
    </Dialog>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 24px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; gap: 12px; }

.form { display: flex; flex-direction: column; gap: 14px; }
.form__target { margin: -6px 0 0; font-size: 12px; color: var(--muted); }
.field { display: flex; flex-direction: column; gap: 6px; }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input[type='date'] {
  padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; font: inherit; background: var(--surface);
}
.toggle { display: flex; align-items: center; gap: 8px; font-size: 13.5px; }
.form__error { color: var(--danger); font-size: 13px; margin: 0; }
.form__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
</style>
