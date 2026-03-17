<template>
  <div class="auth-container">
    <div class="auth-card">
      <div class="auth-logo">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="8" fill="#10a37f"/>
          <path d="M20 10L28 16V28L20 34L12 28V16L20 10Z" stroke="white" stroke-width="2" fill="none"/>
          <circle cx="20" cy="22" r="4" fill="white"/>
        </svg>
      </div>
      <h1 class="auth-title">Doc-genius</h1>
      <p class="auth-subtitle">AI 需求与详设生成器</p>

      <!-- Initial choice buttons (shown when no mode selected yet) -->
      <div v-if="!showForm" class="auth-choices">
        <button class="choice-btn choice-btn--primary" @click="selectMode('login')">
          登录
        </button>
        <button class="choice-btn choice-btn--secondary" @click="selectMode('register')">
          注册
        </button>
      </div>

      <!-- Form (shown after choosing login or register) -->
      <div v-else class="auth-form-wrapper">
        <div class="auth-tabs">
          <button
            class="auth-tab"
            :class="{ active: mode === 'login' }"
            @click="mode = 'login'"
          >登录</button>
          <button
            class="auth-tab"
            :class="{ active: mode === 'register' }"
            @click="mode = 'register'"
          >注册</button>
        </div>

        <form class="auth-form" @submit.prevent="handleSubmit">
          <div class="input-group">
            <input
              v-model="username"
              type="text"
              class="auth-input"
              placeholder="用户名"
              autocomplete="username"
            />
          </div>
          <div class="input-group">
            <input
              v-model="password"
              :type="showPwd ? 'text' : 'password'"
              class="auth-input"
              placeholder="密码"
              autocomplete="current-password"
            />
            <button type="button" class="pwd-toggle" @click="showPwd = !showPwd">
              {{ showPwd ? '隐藏' : '显示' }}
            </button>
          </div>
          <div v-if="mode === 'register'" class="input-group">
            <input
              v-model="confirmPassword"
              :type="showConfirmPwd ? 'text' : 'password'"
              class="auth-input"
              placeholder="确认密码"
              autocomplete="new-password"
            />
            <button type="button" class="pwd-toggle" @click="showConfirmPwd = !showConfirmPwd">
              {{ showConfirmPwd ? '隐藏' : '显示' }}
            </button>
          </div>

          <p v-if="errorMsg" class="auth-error">{{ errorMsg }}</p>

          <button
            type="submit"
            class="submit-btn"
            :disabled="loading"
          >
            <span v-if="loading" class="spinner"></span>
            {{ mode === 'login' ? '继续' : '注册' }}
          </button>
        </form>

        <div class="auth-footer">
          <span v-if="mode === 'login'">
            没有账号？<a class="auth-link" @click="mode = 'register'">注册</a>
          </span>
          <span v-else>
            已有账号？<a class="auth-link" @click="mode = 'login'">登录</a>
          </span>
        </div>
      </div>

      <p class="auth-terms">
        继续即表示你同意我们的<a href="javascript:void(0)">服务条款</a>和<a href="javascript:void(0)">隐私政策</a>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const showForm = ref(false)
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorMsg = ref('')
const showPwd = ref(false)
const showConfirmPwd = ref(false)

function selectMode(m: 'login' | 'register') {
  mode.value = m
  showForm.value = true
}

async function handleSubmit() {
  errorMsg.value = ''

  if (!username.value.trim()) {
    errorMsg.value = '请输入用户名'
    return
  }
  if (!password.value) {
    errorMsg.value = '请输入密码'
    return
  }

  if (mode.value === 'register') {
    if (password.value.length < 6) {
      errorMsg.value = '密码长度至少 6 位'
      return
    }
    if (password.value !== confirmPassword.value) {
      errorMsg.value = '两次输入的密码不一致'
      return
    }
  }

  loading.value = true
  try {
    let err: string | null
    if (mode.value === 'login') {
      err = await authStore.login(username.value.trim(), password.value)
    } else {
      err = await authStore.register(username.value.trim(), password.value)
    }

    if (err) {
      errorMsg.value = err
    } else {
      ElMessage.success(mode.value === 'login' ? '登录成功' : '注册成功')
      router.replace({ name: 'chat' })
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  padding: 20px;
}

.auth-card {
  width: 400px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 32px 32px;
}

.auth-logo {
  margin-bottom: 20px;
}

.auth-title {
  text-align: center;
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}

.auth-subtitle {
  text-align: center;
  font-size: 15px;
  color: var(--text-muted);
  margin: 0 0 36px;
}

/* Initial choice buttons - ChatGPT style */
.auth-choices {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.choice-btn {
  width: 100%;
  height: 52px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  border: none;
  outline: none;
}

.choice-btn--primary {
  background: #10a37f;
  color: #fff;
}

.choice-btn--primary:hover {
  background: #0d8c6d;
}

.choice-btn--secondary {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--border-primary);
}

.choice-btn--secondary:hover {
  background: var(--bg-secondary);
}

/* Tabs */
.auth-form-wrapper {
  width: 100%;
}

.auth-tabs {
  display: flex;
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 24px;
  border: 1px solid var(--border-primary);
}

.auth-tab {
  flex: 1;
  padding: 10px 0;
  text-align: center;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.auth-tab.active {
  background: var(--bg-primary);
  color: var(--text-primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* Form */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input-group {
  position: relative;
}

.auth-input {
  width: 100%;
  height: 52px;
  padding: 0 56px 0 16px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  font-size: 16px;
  color: var(--text-primary);
  background: var(--bg-primary);
  outline: none;
  transition: border-color 0.2s ease;
  box-sizing: border-box;
}

.auth-input::placeholder {
  color: var(--text-muted);
}

.auth-input:focus {
  border-color: #10a37f;
}

.pwd-toggle {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
}

.pwd-toggle:hover {
  color: var(--text-secondary);
}

.auth-error {
  text-align: center;
  color: #ef4444;
  font-size: 14px;
  margin: 0;
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 8px;
}

.submit-btn {
  width: 100%;
  height: 52px;
  border-radius: 8px;
  border: none;
  background: #10a37f;
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.submit-btn:hover:not(:disabled) {
  background: #0d8c6d;
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Footer */
.auth-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: var(--text-muted);
}

.auth-link {
  color: #10a37f;
  cursor: pointer;
  text-decoration: none;
  font-weight: 500;
}

.auth-link:hover {
  text-decoration: underline;
}

.auth-terms {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 32px;
  line-height: 1.6;
}

.auth-terms a {
  color: var(--text-secondary);
  text-decoration: underline;
}

.auth-terms a:hover {
  color: var(--text-primary);
}

@media (max-width: 480px) {
  .auth-card {
    padding: 32px 20px 24px;
  }

  .auth-title {
    font-size: 28px;
  }
}
</style>
