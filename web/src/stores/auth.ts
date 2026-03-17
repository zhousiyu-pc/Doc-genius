/**
 * 用户认证 Store
 * ==============
 * 管理 JWT Token、用户状态、登录/注册/登出。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export interface User {
  user_id: string
  username: string
}

const TOKEN_KEY = 'doc_genius_token'
const USER_KEY = 'doc_genius_user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<User | null>(null)

  // 初始化：从 localStorage 恢复用户信息
  const savedUser = localStorage.getItem(USER_KEY)
  if (savedUser) {
    try {
      user.value = JSON.parse(savedUser)
    } catch { /* ignore */ }
  }

  const isLoggedIn = computed(() => !!token.value && !!user.value)

  // 设置 axios 全局 Authorization header
  function _setAxiosAuth(t: string | null) {
    if (t) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${t}`
    } else {
      delete axios.defaults.headers.common['Authorization']
    }
  }

  // 初始化时设置 header
  _setAxiosAuth(token.value)

  async function register(username: string, password: string): Promise<string | null> {
    try {
      const { data } = await axios.post('/api/auth/register', { username, password })
      if (data.success) {
        token.value = data.token
        user.value = { user_id: data.user_id, username: data.username }
        localStorage.setItem(TOKEN_KEY, data.token)
        localStorage.setItem(USER_KEY, JSON.stringify(user.value))
        _setAxiosAuth(data.token)
        return null
      }
      return data.message || '注册失败'
    } catch (err: any) {
      return err.response?.data?.message || '注册失败，请重试'
    }
  }

  async function login(username: string, password: string): Promise<string | null> {
    try {
      const { data } = await axios.post('/api/auth/login', { username, password })
      if (data.success) {
        token.value = data.token
        user.value = { user_id: data.user_id, username: data.username }
        localStorage.setItem(TOKEN_KEY, data.token)
        localStorage.setItem(USER_KEY, JSON.stringify(user.value))
        _setAxiosAuth(data.token)
        return null
      }
      return data.message || '登录失败'
    } catch (err: any) {
      return err.response?.data?.message || '用户名或密码错误'
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    _setAxiosAuth(null)
  }

  /** 验证当前 token 是否有效 */
  async function checkAuth(): Promise<boolean> {
    if (!token.value) return false
    try {
      const { data } = await axios.get('/api/auth/me')
      if (data.success) {
        user.value = { user_id: data.user_id, username: data.username }
        return true
      }
    } catch { /* token 无效 */ }
    logout()
    return false
  }

  return {
    token,
    user,
    isLoggedIn,
    register,
    login,
    logout,
    checkAuth,
  }
})
