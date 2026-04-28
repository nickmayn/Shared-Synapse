import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const routes = [
  {
    path: '/',
    component: () => import('../views/HomeView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/synapses',
    component: () => import('../views/SynapsesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/synapses/new',
    component: () => import('../views/SynapseEditView.vue'),
    meta: { requiresAuth: true, requiresRole: 'admin' },
  },
  {
    path: '/synapses/:name/edit',
    component: () => import('../views/SynapseEditView.vue'),
    meta: { requiresAuth: true, requiresRole: 'admin' },
  },
  {
    path: '/brainstem',
    component: () => import('../views/BrainStemView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin/users',
    component: () => import('../views/AdminUsersView.vue'),
    meta: { requiresAuth: true, requiresRole: 'admin' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const { isAuthenticated, role } = useAuth()

  if (to.meta.requiresAuth && !isAuthenticated.value) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresRole) {
    const hierarchy = { admin: 3, contributor: 2, viewer: 1 }
    const required = hierarchy[to.meta.requiresRole] || 1
    const current = hierarchy[role.value] || 0
    if (current < required) {
      return { path: '/' }
    }
  }

  return true
})

export default router
