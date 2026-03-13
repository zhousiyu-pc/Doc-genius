import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
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

export default router
