<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1 class="auth-title">Doc-genius</h1>
      <p class="auth-subtitle">AI 需求与详设生成器</p>

      <div class="auth-tabs">
        <span
          class="auth-tab"
          :class="{ active: mode === 'login' }"
          @click="mode = 'login'"
        >登录</span>
        <span
          class="auth-tab"
          :class="{ active: mode === 'register' }"
          @click="mode = 'register'"
        >注册</span>
      </div>

      <form class="auth-form" @submit.prevent="handleSubmit">
        <el-input
          v-model="username"
          placeholder="用户名"
          size="large"
          clearable
          :prefix-icon="User"
        />
        <el-input
          v-model="password"
          type="password"
          placeholder="密码"
          size="large"
          show-password
          :prefix-icon="Lock"
        />
        <el-input
          v-if="mode === 'register'"
          v-model="confirmPassword"
          type="password"
          placeholder="确认密码"
          size="large"
          show-password
          :prefix-icon="Lock"
        />

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          native-type="submit"
          class="auth-btn"
        >
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </el-button>
      </form>

      <p v-if="errorMsg" class="auth-error">{{ errorMsg }}</p>

      <div class="auth-footer">
        <span v-if="mode === 'login'">
          没有账号？<a @click="mode = 'register'">立即注册</a>
        </span>
        <span v-else>
          已有账号？<a @click="mode = 'login'">去登录</a>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorMsg = ref('')

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
  background: var(--bg-secondary);
  border-radius: 16px;
  padding: 40px 32px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
}

.auth-title {
  text-align: center;
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.auth-subtitle {
  text-align: center;
  font-size: 14px;
  color: var(--text-muted);
  margin: 0 0 28px;
}

.auth-tabs {
  display: flex;
  gap: 24px;
  justify-content: center;
  margin-bottom: 24px;
}

.auth-tab {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  padding-bottom: 6px;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.auth-tab.active {
  color: #409eff;
  border-bottom-color: #409eff;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.auth-btn {
  width: 100%;
  margin-top: 8px;
  height: 44px;
  font-size: 16px;
}

.auth-error {
  text-align: center;
  color: #f56c6c;
  font-size: 13px;
  margin-top: 12px;
}

.auth-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: var(--text-muted);
}

.auth-footer a {
  color: #409eff;
  cursor: pointer;
  text-decoration: none;
}

.auth-footer a:hover {
  text-decoration: underline;
}
</style>
