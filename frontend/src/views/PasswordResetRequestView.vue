<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const email = ref('')
const submitting = ref(false)
// バックエンドはメールアドレスの在不在に関わらず常に成功を返す（列挙攻撃対策）ため、
// 画面側でも「送信した/しなかった」を区別せず、常に同じ案内文だけを出す。
const submitted = ref(false)

async function onSubmit() {
  submitting.value = true
  try {
    await auth.requestPasswordReset(email.value)
  } catch {
    // 通信エラー時もメールアドレスの在不在を推測させないため、あえてエラー内容は出さず
    // 同じ案内文にとどめる（もし本当に通信できていなければ、ユーザーは再送すればよい）。
  } finally {
    submitting.value = false
    submitted.value = true
  }
}
</script>

<template>
  <div class="login">
    <div class="login__card">
      <div class="login__brand">
        <i class="pi pi-key" aria-hidden="true"></i>
      </div>
      <h1 class="login__title">パスワード再設定</h1>
      <p class="login__lede">登録済みのメールアドレスに再設定用のリンクをお送りします</p>

      <template v-if="submitted">
        <p class="login__done">
          ご入力いただいたメールアドレス宛に、パスワード再設定用のリンクを送信しました
          （該当するアカウントが存在する場合）。メールが届かない場合は、迷惑メールフォルダも
          ご確認のうえ、時間をおいて再度お試しください。
        </p>
        <RouterLink :to="{ name: 'login' }" class="login__forgot">ログイン画面に戻る</RouterLink>
      </template>
      <form v-else class="login__form" @submit.prevent="onSubmit">
        <label class="field">
          <span class="field__label">メールアドレス</span>
          <input v-model="email" type="email" autocomplete="username" required />
        </label>
        <button type="submit" class="primary" :disabled="submitting">
          {{ submitting ? '送信中…' : '再設定用リンクを送信' }}
        </button>
        <RouterLink :to="{ name: 'login' }" class="login__forgot">ログイン画面に戻る</RouterLink>
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
.login__title { font-size: 22px; margin: 0 0 4px; }
.login__lede { margin: 0 0 24px; font-size: 13px; color: var(--muted); }
.login__form { display: flex; flex-direction: column; gap: 16px; }
.login__done { font-size: 14px; color: var(--ink); line-height: 1.8; margin: 0 0 20px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input {
  padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px;
  font: inherit; background: var(--surface);
}
.field input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
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
