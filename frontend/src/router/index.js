import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import { ensureDemoSession, isDemoMode } from '../api/mock'

ensureDemoSession()

const routes = [
  { path: '/', redirect: isDemoMode ? '/study' : '/login' },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/study', name: 'study', component: () => import('../views/StudyView.vue'), meta: { tab: true } },
  { path: '/plan', name: 'plan', component: () => import('../views/PlanView.vue'), meta: { tab: true } },
  { path: '/ai', name: 'ai', component: () => import('../views/AiView.vue'), meta: { tab: true } },
  { path: '/stats', name: 'stats', component: () => import('../views/StatsView.vue'), meta: { tab: true } },
  { path: '/notebook', name: 'notebook', component: () => import('../views/NotebookView.vue') },
  { path: '/dict', name: 'dict', component: () => import('../views/DictView.vue') },
  { path: '/:pathMatch(.*)*', redirect: isDemoMode ? '/study' : '/login' }
]

const router = createRouter({
  history: isDemoMode ? createWebHashHistory() : createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('ct4_token')
  if (to.name !== 'login' && !token) return { name: 'login' }
  if (to.name === 'login' && token) return { name: 'study' }
  return true
})

export default router