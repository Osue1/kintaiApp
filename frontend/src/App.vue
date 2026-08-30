<script setup lang="ts">
import Toast from 'primevue/toast'
import { computed, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useApprovalsStore } from '@/stores/approvals'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const approvals = useApprovalsStore()
const router = useRouter()
const route = useRoute()
const companyName = computed(() => auth.me?.company?.name ?? '')
const initial = computed(() => auth.me?.name?.charAt(0) ?? '')

const navItems = [
  { name: 'mypage', label: 'マイページ', icon: 'pi-home' },
  { name: 'attendance-detail', label: '勤怠明細', icon: 'pi-list' },
  { name: 'team-status', label: '出勤状況', icon: 'pi-eye' },
  { name: 'leave', label: '休暇申請', icon: 'pi-calendar' },
]
const adminNavItems = [
  { name: 'approvals', label: '勤怠承認', icon: 'pi-check-square' },
  { name: 'alerts', label: 'アラート', icon: 'pi-exclamation-triangle' },
  { name: 'employees', label: '従業員管理', icon: 'pi-users' },
  { name: 'leave-ledger', label: '有給管理簿', icon: 'pi-book' },
  { name: 'contractors', label: '外注管理', icon: 'pi-briefcase' },
  { name: 'invoices', label: '請求書発行', icon: 'pi-file-export' },
  { name: 'audit-logs', label: '監査ログ', icon: 'pi-history' },
]

// 承認待ち件数をナビの「勤怠承認」にバッジ表示する。管理者ログイン時と、
// 承認・差し戻し操作の後（各画面のストアが再取得したタイミング）に追随する。
watch(
  () => auth.me?.is_admin,
  (isAdmin) => {
    if (isAdmin) approvals.fetchApprovals()
  },
  { immediate: true },
)

async function onLogout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app">
    <header v-if="auth.me" class="bar">
      <div class="bar__inner">
        <div class="bar__left">
          <span class="brand">
            <i class="pi pi-clock brand__icon" aria-hidden="true"></i>
            <span class="brand__text">
              勤怠管理<span v-if="companyName" class="brand__company">/ {{ companyName }}</span>
            </span>
          </span>
          <nav class="nav">
            <RouterLink
              v-for="item in navItems"
              :key="item.name"
              :to="{ name: item.name }"
              class="nav__item"
              :class="{ 'nav__item--active': route.name === item.name }"
            >
              <i class="pi" :class="item.icon" aria-hidden="true"></i>
              {{ item.label }}
            </RouterLink>
          </nav>
        </div>
        <div class="bar__right">
          <span class="user">
            <span class="user__avatar">{{ initial }}</span>
            <span class="user__name">{{ auth.me.name }}</span>
          </span>
          <button type="button" class="linkbtn" @click="onLogout">ログアウト</button>
        </div>
      </div>
    </header>
    <!--
      管理者向けメニューはヘッダーには置かない。社員向け4項目だけでもヘッダーが
      窮屈になりやすい上、管理者は合計11項目になり画面幅に入りきらなかった
      （縦書き崩れの原因にもなった）。メイン画面上部の専用タブに分離し、
      どのページを見ていても管理者メニューへ常時アクセスできるようにする。
    -->
    <nav v-if="auth.me?.is_admin" class="admin-tabs" aria-label="管理者メニュー">
      <div class="admin-tabs__inner">
        <RouterLink
          v-for="item in adminNavItems"
          :key="item.name"
          :to="{ name: item.name }"
          class="admin-tab"
          :class="{ 'admin-tab--active': route.name === item.name }"
        >
          <i class="pi" :class="item.icon" aria-hidden="true"></i>
          {{ item.label }}
          <span v-if="item.name === 'approvals' && approvals.pendingCount > 0" class="nav__badge">
            {{ approvals.pendingCount }}
          </span>
        </RouterLink>
      </div>
    </nav>
    <main class="main">
      <RouterView />
    </main>
    <Toast position="top-right" />
  </div>
</template>

<style>
:root {
  --ink: #101828;
  --muted: #667085;
  --line: #e4e7ec;
  --paper: #f7f8fa;
  --surface: #ffffff;
  --accent: #0f8a63;
  --accent-dark: #0d6f51;
  --accent-soft: #eafcf4;
  --danger: #d92d20;
  --danger-soft: #fef3f2;
  --warning: #b54708;
  --warning-soft: #fffaeb;
  --radius-lg: 16px;
  --radius-md: 10px;
  --shadow-sm: 0 1px 2px rgba(16, 24, 40, 0.06);
  --shadow-md: 0 4px 16px rgba(16, 24, 40, 0.07);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: 'Hiragino Sans', 'Noto Sans JP', system-ui, sans-serif;
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  /* 金額・時間・日数などの数字を揃える。DataTable の数値列を桁で読み比べやすくする */
  font-variant-numeric: tabular-nums;
}
.bar {
  position: sticky; top: 0; z-index: 10;
  background: var(--surface); border-bottom: 1px solid var(--line);
  box-shadow: var(--shadow-sm);
}
.bar__inner {
  max-width: 1200px; margin: 0 auto; padding: 0 24px;
  display: flex; align-items: center; justify-content: space-between; height: 60px;
}
.bar__left { display: flex; align-items: center; gap: 28px; height: 100%; min-width: 0; }
.brand { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; white-space: nowrap; }
.brand__icon { color: var(--accent); font-size: 16px; }
.brand__company { color: var(--muted); font-weight: 500; }
.nav { display: flex; align-items: center; gap: 0; height: 100%; overflow-x: auto; }
.nav__item {
  display: flex; align-items: center; gap: 6px; height: 100%; flex: 0 0 auto;
  padding: 0 4px; color: var(--muted); text-decoration: none; font-size: 14px; font-weight: 600;
  border-bottom: 2px solid transparent; transition: color 0.15s, border-color 0.15s;
}
.nav__item + .nav__item { margin-left: 20px; }
.nav__item:hover { color: var(--ink); }
.nav__item--active { color: var(--accent-dark); border-bottom-color: var(--accent); }
.nav__badge {
  display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px;
  padding: 0 5px; border-radius: 999px; background: var(--danger); color: #fff; font-size: 11px; font-weight: 700;
}
/*
 * bar__left（ロゴ＋ナビ）は横幅が足りないとき .nav の overflow-x: auto で
 * 内部スクロールさせる想定だが、bar__right 側に flex-shrink を止める指定が
 * 無かったため、画面（特に管理者はナビ項目が多く圧迫されやすい）が狭いと
 * flexboxがこちら側を圧縮対象にしてしまっていた。日本語テキストは
 * スペース無しでも文字間で改行できてしまうため、圧縮されると
 * 「管理者」「ログアウト」が1文字ずつ縦に積まれ、縦書きのように見えていた。
 * flex-shrink: 0 と white-space: nowrap で、ここが縮む前にナビの方が
 * 先にスクロールするようにする。
 */
.bar__right { display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
.user { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.user__avatar {
  width: 28px; height: 28px; border-radius: 50%; background: var(--accent-soft); color: var(--accent-dark);
  display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
  flex-shrink: 0;
}
.user__name { font-size: 13px; color: var(--muted); white-space: nowrap; }
.linkbtn {
  background: none; border: 0; color: var(--accent-dark); cursor: pointer;
  font: inherit; font-size: 13px; padding: 6px 10px; border-radius: 6px; white-space: nowrap; flex-shrink: 0;
}
.linkbtn:hover { background: var(--paper); }
.linkbtn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

/* 管理者専用のタブバー。ヘッダー（60px）の直下に張り付けて、
   スクロールしてもヘッダーと一緒に見え続けるようにする。 */
.admin-tabs {
  position: sticky; top: 60px; z-index: 9;
  background: var(--warning-soft); border-bottom: 1px solid #f4dfb8;
}
.admin-tabs__inner {
  max-width: 1200px; margin: 0 auto; padding: 0 24px;
  display: flex; align-items: center; height: 44px; overflow-x: auto;
}
.admin-tab {
  display: flex; align-items: center; gap: 6px; height: 100%; flex: 0 0 auto;
  padding: 0 4px; color: var(--warning); text-decoration: none; font-size: 13px; font-weight: 600;
  white-space: nowrap; border-bottom: 2px solid transparent; opacity: 0.75;
  transition: opacity 0.15s, border-color 0.15s;
}
.admin-tab + .admin-tab { margin-left: 22px; }
.admin-tab:hover { opacity: 1; }
.admin-tab--active { opacity: 1; border-bottom-color: var(--warning); }

.main { max-width: 1200px; margin: 0 auto; padding: 32px 24px 96px; }
</style>
