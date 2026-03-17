import { createRouter, createWebHistory } from 'vue-router'

const AUTH_REQUIRED = false  // 与后端 AUTH_REQUIRED 对应，上线时改为 true

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/share/:token',
      name: 'share',
      component: () => import('@/views/ShareView.vue'),
      meta: { guest: true },
    },
    {
      path: '/pricing',
      name: 'pricing',
      component: () => import('@/views/PricingView.vue'),
      meta: { guest: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
    },
    {
      path: '/',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
    },
    {
      path: '/chat/:sessionId?',
      name: 'chatSession',
      component: () => import('@/views/ChatView.vue'),
    },
  ],
})

// 路由守卫：AUTH_REQUIRED 时未登录跳转到登录页
router.beforeEach((to, _from, next) => {
  if (!AUTH_REQUIRED) {
    next()
    return
  }

  const token = localStorage.getItem('doc_genius_token')
  if (to.meta.guest) {
    // 已登录用户访问登录页，跳转到首页
    if (token) {
      next({ name: 'chat' })
    } else {
      next()
    }
  } else {
    // 需要认证的页面
    if (!token) {
      next({ name: 'login' })
    } else {
      next()
    }
  }
})

export default router
