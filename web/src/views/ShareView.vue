<template>
  <div class="share-container">
    <!-- 需要密码 -->
    <div v-if="needPassword" class="share-password-card">
      <h2>🔒 该文档需要密码访问</h2>
      <el-input
        v-model="password"
        type="password"
        placeholder="请输入访问密码"
        size="large"
        show-password
        @keydown.enter="submitPassword"
      />
      <el-button type="primary" size="large" @click="submitPassword" :loading="loading">
        访问
      </el-button>
      <p v-if="errorMsg" class="share-error">{{ errorMsg }}</p>
    </div>

    <!-- 加载中 -->
    <div v-else-if="loading" class="share-loading">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <p>加载分享内容中...</p>
    </div>

    <!-- 错误 -->
    <div v-else-if="errorMsg && !shareData" class="share-error-card">
      <h2>😕 无法访问</h2>
      <p>{{ errorMsg }}</p>
    </div>

    <!-- 分享内容 -->
    <div v-else-if="shareData" class="share-content">
      <div class="share-header">
        <h1 class="share-title">{{ shareData.session.title || '需求文档' }}</h1>
        <div class="share-meta">
          <el-tag size="small" effect="plain">{{ shareData.session.mode === 'agile' ? '敏捷模式' : '自由对话' }}</el-tag>
          <span class="share-date">{{ formatDate(shareData.session.created_at) }}</span>
          <span class="share-views">👁 {{ shareData.share.view_count }} 次查看</span>
        </div>
      </div>

      <div class="share-messages">
        <div
          v-for="msg in shareData.messages"
          :key="msg.id"
          class="share-msg"
          :class="msg.role"
        >
          <div v-if="msg.role === 'user' && msg.msg_type !== 'file'" class="msg-user">
            <div class="msg-role">用户</div>
            <div class="msg-text">{{ msg.content }}</div>
          </div>

          <div v-else-if="msg.role === 'assistant' && msg.msg_type === 'text'" class="msg-assistant">
            <div class="msg-role">AI</div>
            <div class="msg-text markdown-body" v-html="renderMd(msg.content)"></div>
          </div>

          <div v-else-if="msg.msg_type === 'artifact'" class="msg-artifact">
            <div class="msg-role">📄 {{ getMetaField(msg, 'display_name') || '产出物' }}</div>
            <div class="msg-text markdown-body" v-html="renderMd(msg.content)"></div>
          </div>

          <div v-else-if="msg.msg_type === 'milestone'" class="msg-milestone">
            <div class="msg-role">🎯 {{ getMetaField(msg, 'title') || '阶段成果' }}</div>
            <div class="msg-text markdown-body" v-html="renderMd(msg.content)"></div>
          </div>
        </div>
      </div>

      <div class="share-footer">
        <p>由 <strong>Doc-genius</strong> 生成 · AI 需求与详设生成器</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'
import axios from 'axios'

const route = useRoute()
const loading = ref(true)
const needPassword = ref(false)
const password = ref('')
const errorMsg = ref('')
const shareData = ref<any>(null)

function renderMd(text: string): string {
  return renderMarkdown(text || '')
}

function getMetaField(msg: any, field: string): string {
  try {
    const meta = typeof msg.metadata === 'string' ? JSON.parse(msg.metadata) : msg.metadata
    return meta?.[field] || ''
  } catch { return '' }
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('zh-CN')
  } catch { return dateStr }
}

async function loadShare(pwd: string = '') {
  const token = route.params.token as string
  if (!token) {
    errorMsg.value = '无效的分享链接'
    loading.value = false
    return
  }

  loading.value = true
  errorMsg.value = ''

  try {
    const url = `/api/share/${token}`
    let resp
    if (pwd) {
      resp = await axios.post(url, { password: pwd })
    } else {
      resp = await axios.get(url)
    }

    if (resp.data.success) {
      shareData.value = resp.data
      needPassword.value = false
    }
  } catch (err: any) {
    const data = err.response?.data
    if (data?.need_password) {
      needPassword.value = true
    } else {
      errorMsg.value = data?.message || data?.reason || '加载失败'
    }
  } finally {
    loading.value = false
  }
}

function submitPassword() {
  if (!password.value.trim()) {
    errorMsg.value = '请输入密码'
    return
  }
  loadShare(password.value.trim())
}

onMounted(() => {
  loadShare()
})
</script>

<style scoped>
.share-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 24px;
  min-height: 100vh;
  background: var(--bg-primary);
}

.share-password-card,
.share-error-card,
.share-loading {
  text-align: center;
  padding: 60px 24px;
}

.share-password-card h2,
.share-error-card h2 {
  margin-bottom: 20px;
  color: var(--text-primary);
}

.share-password-card .el-input {
  max-width: 300px;
  margin: 0 auto 16px;
}

.share-password-card .el-button {
  min-width: 120px;
}

.share-error {
  color: #f56c6c;
  margin-top: 8px;
  font-size: 13px;
}

.loading-icon {
  font-size: 32px;
  color: #409eff;
  animation: spin 1s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.share-header {
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-primary);
}

.share-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.share-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--text-muted);
}

.share-messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.share-msg {
  padding: 16px;
  border-radius: 12px;
}

.msg-user {
  background: #e8f0fe;
  border-radius: 12px;
  padding: 12px 16px;
}

.msg-assistant,
.msg-artifact,
.msg-milestone {
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: 12px;
  padding: 16px;
}

.msg-milestone {
  border-color: #e1f3d8;
  background: #f0f9eb;
}

.msg-role {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.msg-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.share-footer {
  text-align: center;
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border-primary);
  font-size: 13px;
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .share-container {
    padding: 16px 12px;
  }
  .share-title {
    font-size: 20px;
  }
}
</style>
