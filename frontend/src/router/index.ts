import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/password-reset',
      name: 'password-reset-request',
      component: () => import('@/views/PasswordResetRequestView.vue'),
      meta: { public: true },
    },
    {
      path: '/password-reset/confirm',
      name: 'password-reset-confirm',
      component: () => import('@/views/PasswordResetConfirmView.vue'),
      meta: { public: true },
    },
    { path: '/', name: 'mypage', component: () => import('@/views/MyPageView.vue') },
    { path: '/attendance', name: 'attendance-detail', component: () => import('@/views/AttendanceDetailView.vue') },
    { path: '/team-status', name: 'team-status', component: () => import('@/views/TeamStatusView.vue') },
    { path: '/leave', name: 'leave', component: () => import('@/views/LeaveRequestView.vue') },
    {
      path: '/approvals',
      name: 'approvals',
      component: () => import('@/views/admin/ApprovalsView.vue'),
      meta: { adminOnly: true },
    },
    {
      path: '/alerts',
      name: 'alerts',
      component: () => import('@/views/admin/AlertsView.vue'),
      meta: { adminOnly: true },
    },
    {
      path: '/employees',
      name: 'employees',
      component: () => import('@/views/admin/EmployeesView.vue'),
      meta: { adminOnly: true },
    },
    {
      path: '/leave-ledger',
      name: 'leave-ledger',
      component: () => import('@/views/admin/LeaveLedgerView.vue'),
      meta: { adminOnly: true },
    },
    {
      path: '/contractors',
      name: 'contractors',
      component: () => import('@/views/admin/ContractorsView.vue'),
      meta: { adminOnly: true },
    },
    {
      path: '/invoices',
      name: 'invoices',
      component: () => import('@/views/admin/InvoicesView.vue'),
      meta: { adminOnly: true },
    },
    {
      path: '/audit-logs',
      name: 'audit-logs',
      component: () => import('@/views/admin/AuditLogView.vue'),
      meta: { adminOnly: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) await auth.fetchMe()

  if (!to.meta.public && !auth.me) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.adminOnly && !auth.me?.is_admin) {
    return { name: 'mypage' }
  }
  if (to.name === 'login' && auth.me) {
    return { name: 'mypage' }
  }
  return true
})

export default router
