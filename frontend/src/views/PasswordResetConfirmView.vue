<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiRequestError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// トークンはメール内リンクの ?token= から受け取る。無いままこの画面を開いた場合
// （URLを直接編集した等）はサーバー側でどのみち invalid_token として弾かれる。
const token = typeof route.query.token === 'string' ? route.query.token : ''

const password = ref('')
const passwordConfirm = ref('')
const submitting = ref(false)
const errorMessage = ref('')
const done = ref(false)

async function onSubmit() {
  errorMessage.value = ''
  if (password.value !== passwordConfirm.value) {
    errorMessage.value = '新しいパスワードが一致しません。'
    return
  }
  submitting.value = true
  try {
    await auth.confirmPasswordReset(token, password.value)
    done.value = true
    setTimeout(() => router.push({ name: 'login' }), 2500)
  } catch (e) {
    errorMessage.value = e instanceof ApiRequestError ? e.message : '通信に失敗しました。時間をおいてお試しください。'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="login__card">
      <div class="login__brand">
        <i class="pi pi-key" aria-hidden="true"></i>
      </div>
      <h1 class="login__title">新しいパスワードの設定</h1>

      <template v-if="done">
        <p class="login__done">パスワードを再設定しました。ログイン画面に移動します…</p>
      </template>
      <template v-else-if="!token">
        <p class="login__error" role="alert">
          リンクが正しくありません。お手数ですが、パスワード再設定を最初からやり直してください。
        </p>
        <RouterLink :to="{ name: 'password-reset-request' }" class="login__forgot">パスワード再設定をやり直す</RouterLink>
      </template>
      <form v-else class="login__form" @submit.prevent="onSubmit">
        <label class="field">
          <span class="field__label">新しいパスワード（12文字以上）</span>
          <input v-model="password" type="password" autocomplete="new-password" required />
        </label>
        <label class="field">
          <span class="field__label">新しいパスワード（確認）</span>
          <input v-model="passwordConfirm" type="password" autocomplete="new-password" required />
        </label>
        <p v-if="errorMessage" class="login__error" role="alert">{{ errorMessage }}</p>
        <button type="submit" class="primary" :disabled="submitting">
          {{ submitting ? '設定中…' : 'パスワードを設定する' }}
        </button>
      </form>
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
.login__title { font-size: 22px; margin: 0 0 20px; }
.login__form { display: flex; flex-direction: column; gap: 16px; }
.login__done { font-size: 14px; color: var(--ink); line-height: 1.8; margin: 0; }
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
