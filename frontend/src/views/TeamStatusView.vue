<script setup lang="ts">
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'
import { computed, onMounted, ref } from 'vue'
import { useTeamStatusStore } from '@/stores/teamStatus'
import type { PunchState, TeamStatusScope } from '@/types/domain'

const store = useTeamStatusStore()

const scope = ref<TeamStatusScope>('team')

onMounted(() => {
  store.fetchStatus(scope.value)
})

function onSelectScope(next: TeamStatusScope) {
  scope.value = next
  store.fetchStatus(next)
}

const stateMeta: Record<PunchState, { label: string; severity: 'secondary' | 'warn' | 'success' }> = {
  not_started: { label: '未出勤', severity: 'secondary' },
  working: { label: '出勤中', severity: 'warn' },
  finished: { label: '退勤済み', severity: 'success' },
}

const workingCount = computed(() => store.result?.members.filter((m) => m.state === 'working').length ?? 0)
const totalCount = computed(() => store.result?.members.length ?? 0)

const heading = computed(() => {
  if (!store.result) return ''
  if (store.result.scope === 'all') return '全社員'
  return store.result.teamName ? `${store.result.teamName}のメンバー` : 'グループのメンバー'
})
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">勤怠</p>
      <h1 class="page__title">出勤状況</h1>
    </header>

    <div class="controls">
      <button
        type="button"
        class="chip"
        :class="{ 'chip--active': scope === 'team' }"
        @click="onSelectScope('team')"
      >
        <i class="pi pi-users" aria-hidden="true" /> 自分のグループ
      </button>
      <button
        type="button"
        class="chip"
        :class="{ 'chip--active': scope === 'all' }"
        @click="onSelectScope('all')"
      >
        <i class="pi pi-building" aria-hidden="true" /> 全社員
      </button>
      <span v-if="store.result" class="controls__count">{{ heading }} ・ 出勤中 {{ workingCount }} / {{ totalCount }}名</span>
    </div>

    <p v-if="store.result?.fallbackToAll" class="fallback-note">
      <i class="pi pi-info-circle" aria-hidden="true" /> グループが未設定のため、全社員を表示しています。
    </p>

    <Card>
      <template #content>
        <DataTable :value="store.result?.members ?? []" size="small" :loading="store.loading">
          <Column field="name" header="氏名" style="width: 140px" sortable />
          <Column v-if="scope === 'all'" header="グループ" style="width: 120px">
            <template #body="{ data }">{{ data.teamName ?? '未設定' }}</template>
          </Column>
          <Column header="区分" style="width: 90px">
            <template #body="{ data }">
              <Tag :value="data.isAdmin ? '管理者' : '正社員'" :severity="data.isAdmin ? 'warn' : 'info'" />
            </template>
          </Column>
          <Column header="状態" style="width: 100px">
            <template #body="{ data }">
              <Tag
                :value="data.onLeave ? '休暇中' : stateMeta[data.state as PunchState].label"
                :severity="data.onLeave ? 'info' : stateMeta[data.state as PunchState].severity"
              />
            </template>
          </Column>
          <Column header="出勤" style="width: 90px" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ data.clockInAt ?? '—' }}</template>
          </Column>
          <Column header="退勤" style="width: 90px" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ data.clockOutAt ?? '—' }}</template>
          </Column>
          <template #empty>表示できるメンバーがいません。</template>
        </DataTable>
      </template>
    </Card>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 24px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.controls { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.controls__count { font-size: 12.5px; color: var(--muted); margin-left: 4px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  border: 1px solid var(--line); background: var(--surface); color: var(--muted);
  border-radius: 999px; padding: 6px 14px; font: inherit; font-size: 13px; cursor: pointer;
}
.chip--active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent-dark); font-weight: 600; }

.fallback-note {
  display: flex; align-items: center; gap: 6px; margin: 0 0 16px; font-size: 12.5px; color: var(--warning);
}
</style>
