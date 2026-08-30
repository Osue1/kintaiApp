<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiRequestError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const submitting = ref(false)
const errorMessage = ref('')
const fieldErrors = ref<Record<string, string[]>>({})

function goNext() {
  const next = typeof route.query.next === 'string' ? route.query.next : '/'
  router.push(next)
}

async function onSubmit() {
  submitting.value = true
  errorMessage.value = ''
  fieldErrors.value = {}
  try {
    await auth.login(email.value, password.value)
    goNext()
  } catch (e) {
    if (e instanceof ApiRequestError) {
      errorMessage.value = e.message
      fieldErrors.value = e.fieldErrors
    } else {
      errorMessage.value = '通信に失敗しました。時間をおいてお試しください。'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="login__card">
      <div class="login__brand">
        <i class="pi pi-clock" aria-hidden="true"></i>
      </div>
      <h1 class="login__title">ログイン</h1>
      <p class="login__lede">勤怠管理システムにアクセスします</p>
      <form class="login__form" @submit.prevent="onSubmit">
        <label class="field">
          <span class="field__label">メールアドレス</span>
          <input v-model="email" type="email" autocomplete="username" required />
          <span v-if="fieldErrors.email" class="field__error">{{ fieldErrors.email[0] }}</span>
        </label>
        <label class="field">
          <span class="field__label">パスワード</span>
          <input v-model="password" type="password" autocomplete="current-password" required />
          <span v-if="fieldErrors.password" class="field__error">{{ fieldErrors.password[0] }}</span>
        </label>
        <p v-if="errorMessage" class="login__error" role="alert">{{ errorMessage }}</p>
        <button type="submit" class="primary" :disabled="submitting">
          {{ submitting ? 'ログイン中…' : 'ログイン' }}
        </button>
      </form>
      <RouterLink :to="{ name: 'password-reset-request' }" class="login__forgot">パスワードをお忘れですか？</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.login {
  min-height: calc(100vh - 60px);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.login__card {
  width: 100%; max-width: 380px; background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-md); padding: 36px 32px;
}
.login__brand {
  width: 44px; height: 44px; border-radius: 12px; background: var(--accent-soft); color: var(--accent-dark);
  display: flex; align-items: center; justify-content: center; font-size: 20px; margin-bottom: 16px;
}
.login__title { font-size: 22px; margin: 0 0 4px; }
.login__lede { margin: 0 0 24px; font-size: 13px; color: var(--muted); }
.login__form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input {
  padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px;
  font: inherit; background: var(--surface);
}
.field input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.field__error, .login__error { color: var(--danger); font-size: 13px; }
.primary {
  padding: 11px 14px; background: var(--accent); color: #fff; border: 0;
  border-radius: 8px; font: inherit; font-weight: 700; cursor: pointer; margin-top: 4px;
}
.primary:hover:not(:disabled) { background: var(--accent-dark); }
.primary:disabled { opacity: 0.6; cursor: default; }
.login__forgot {
  display: block; margin-top: 18px; text-align: center; font-size: 13px;
  color: var(--muted); text-decoration: none;
}
.login__forgot:hover { color: var(--accent-dark); text-decoration: underline; }
</style>
