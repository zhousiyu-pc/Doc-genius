<template>
  <div class="chat-layout">
    <!-- 左侧会话列表 -->
    <aside class="chat-sidebar">
      <div class="sidebar-header">
        <h2 class="sidebar-title">AI 需求分析</h2>
        <el-button type="primary" size="small" @click="handleNewChat">
          + 新对话
        </el-button>
      </div>
      <div class="session-list">
        <div
          v-for="session in chatStore.sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: chatStore.currentSessionId === session.id }"
          @click="handleSwitchSession(session.id)"
        >
          <div class="session-title">{{ session.title || '新对话' }}</div>
          <div class="session-meta">
            <span class="session-status" :class="session.status">
              {{ statusLabel(session.status) }}
            </span>
            <el-icon
              class="session-delete"
              @click.stop="handleDeleteSession(session.id)"
            >
              <Delete />
            </el-icon>
          </div>
        </div>
        <div v-if="chatStore.sessions.length === 0" class="empty-sessions">
          暂无对话，点击上方按钮开始
        </div>
      </div>
      <!-- 底部信息 -->
      <div class="sidebar-footer">
        <span class="footer-label">AI 需求与详设生成器</span>
      </div>
    </aside>

    <!-- 右侧聊天主区域 -->
    <main class="chat-main">
      <!-- 未选择会话时的欢迎页 -->
      <div v-if="!chatStore.currentSessionId" class="welcome-screen">
        <div class="welcome-content">
          <h1 class="welcome-title">AI 需求与详设生成器</h1>
          <p class="welcome-desc">
            通过自然对话，AI 帮你精准梳理需求，自动生成需求文档、流程图、ER 图、测试用例和 API 文档
          </p>
          <el-button type="primary" size="large" @click="handleNewChat">
            开始新对话
          </el-button>
          <div class="welcome-examples">
            <p class="examples-title">试试这些：</p>
            <div class="example-chips">
              <span
                v-for="example in quickExamples"
                :key="example"
                class="example-chip"
                @click="handleQuickStart(example)"
              >
                {{ example }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 聊天消息区域 -->
      <div v-else class="chat-container">
        <div class="messages-area" ref="messagesArea">
          <div
            v-for="msg in chatStore.messages"
            :key="msg.id"
            class="message-row"
            :class="msg.role"
          >
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="message-bubble user-bubble">
              <div class="bubble-content">{{ msg.content }}</div>
            </div>

            <!-- 助手文本消息 -->
            <div
              v-else-if="msg.role === 'assistant' && msg.msg_type === 'text'"
              class="message-bubble assistant-bubble"
            >
              <div class="bubble-avatar">AI</div>
              <div class="bubble-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
            </div>

            <!-- 大纲消息 -->
            <div
              v-else-if="msg.msg_type === 'outline'"
              class="message-bubble assistant-bubble"
            >
              <div class="bubble-avatar">AI</div>
              <div class="outline-card">
                <h3 class="outline-title">
                  {{ (msg.metadata as any)?.project_name || '需求大纲' }}
                </h3>
                <div class="outline-info">
                  <el-tag effect="plain" size="small">
                    {{ (msg.metadata as any)?.domain || '未分类' }}
                  </el-tag>
                  <el-tag effect="plain" size="small" type="info">
                    {{ (msg.metadata as any)?.complexity || '中等' }}
                  </el-tag>
                </div>

                <div class="outline-section" v-if="(msg.metadata as any)?.target_users?.length">
                  <span class="outline-label">目标用户：</span>
                  <el-tag
                    v-for="u in (msg.metadata as any).target_users"
                    :key="u"
                    size="small"
                    class="outline-tag"
                  >{{ u }}</el-tag>
                </div>

                <div class="outline-section" v-if="(msg.metadata as any)?.core_modules?.length">
                  <span class="outline-label">核心模块：</span>
                  <div class="module-list">
                    <div
                      v-for="m in (msg.metadata as any).core_modules"
                      :key="typeof m === 'string' ? m : m.name"
                      class="module-item"
                    >
                      <strong>{{ typeof m === 'string' ? m : m.name }}</strong>
                      <span v-if="typeof m !== 'string' && m.description"> — {{ m.description }}</span>
                    </div>
                  </div>
                </div>

                <div class="outline-section" v-if="(msg.metadata as any)?.feature_list?.length">
                  <span class="outline-label">功能点列表 ({{ (msg.metadata as any).feature_list.length }})：</span>
                  <div class="feature-list">
                    <div
                      v-for="(f, idx) in (msg.metadata as any).feature_list"
                      :key="idx"
                      class="feature-item"
                    >
                      {{ idx + 1 }}. {{ f }}
                    </div>
                  </div>
                </div>

                <div class="outline-actions" v-if="chatStore.currentSession?.status === 'active'">
                  <el-button @click="chatStore.sendMessage('我想调整一下需求大纲')">
                    返回修改
                  </el-button>
                  <el-button
                    type="primary"
                    :loading="chatStore.confirming"
                    @click="handleConfirm"
                  >
                    确认，开始生成文档
                  </el-button>
                </div>
              </div>
            </div>

            <!-- 进度消息 -->
            <div
              v-else-if="msg.msg_type === 'progress'"
              class="message-bubble system-bubble"
            >
              <div class="progress-msg">
                <el-icon v-if="!(msg.metadata as any)?.done"><Loading /></el-icon>
                <el-icon v-else class="done-icon"><CircleCheckFilled /></el-icon>
                <span>{{ msg.content }}</span>
              </div>
            </div>

            <!-- 产出物消息 -->
            <div
              v-else-if="msg.msg_type === 'artifact'"
              class="message-bubble assistant-bubble artifact-bubble"
            >
              <div class="bubble-avatar">AI</div>
              <div class="artifact-card">
                <div class="artifact-header">
                  <el-icon><Document /></el-icon>
                  <span class="artifact-title">{{ (msg.metadata as any)?.display_name || '产出物' }}</span>
                  <el-tag size="small" effect="plain" type="info">
                    {{ (msg.metadata as any)?.output_type || 'markdown' }}
                  </el-tag>
                </div>
                <div
                  class="artifact-content markdown-body"
                  v-html="renderMarkdown(msg.content)"
                  ref="artifactRefs"
                ></div>
                <div class="artifact-footer">
                  <el-button size="small" @click="copyContent(msg.content)">
                    复制内容
                  </el-button>
                  <el-button size="small" type="primary" @click="downloadArtifact(msg)">
                    下载文件
                  </el-button>
                </div>
              </div>
            </div>

            <!-- 系统消息 -->
            <div
              v-else-if="msg.role === 'system' && msg.msg_type === 'text'"
              class="message-bubble system-bubble"
            >
              <span>{{ msg.content }}</span>
            </div>
          </div>

          <!-- 流式打字指示器 -->
          <div v-if="chatStore.streaming" class="typing-indicator">
            <div class="bubble-avatar">AI</div>
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>

        <!-- 底部输入区域 -->
        <div class="input-area">
          <div class="input-wrapper">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="1"
              :autosize="{ minRows: 1, maxRows: 6 }"
              placeholder="描述你想做的产品，或回答 AI 的问题..."
              @keydown.enter.exact.prevent="handleSend"
              :disabled="chatStore.streaming || chatStore.isGenerating"
            />
            <el-button
              type="primary"
              circle
              class="send-btn"
              :disabled="!inputText.trim() || chatStore.streaming"
              @click="handleSend"
            >
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
          <div class="input-hint">
            按 Enter 发送，Shift+Enter 换行
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
/**
 * ChatView — 全屏对话式需求分析界面
 * 左侧会话列表 + 右侧 ChatGPT 风格的聊天主区域。
 */
import { ref, onMounted, nextTick, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete, Loading, CircleCheckFilled, Document, Promotion
} from '@element-plus/icons-vue'
import mermaid from 'mermaid'
import { useChatStore } from '@/stores/chat'
import type { ChatMessage } from '@/stores/chat'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()
const inputText = ref('')
const messagesArea = ref<HTMLElement | null>(null)

const quickExamples = [
  '帮我做一个保险公司的智能培训系统',
  '设计一个 CRM 客户管理系统',
  '搭建一个在线教育平台',
  '做一个电商后台管理系统',
]

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  flowchart: { useMaxWidth: true, htmlLabels: true },
})

/** 渲染页面中所有未渲染的 Mermaid 代码块 */
async function renderMermaidBlocks() {
  await nextTick()
  const blocks = document.querySelectorAll('.mermaid-source:not(.mermaid-rendered)')
  for (let i = 0; i < blocks.length; i++) {
    const el = blocks[i] as HTMLElement
    const code = el.textContent?.trim() || ''
    if (!code) continue
    try {
      const id = `mermaid-${Date.now()}-${i}`
      const { svg } = await mermaid.render(id, code)
      const container = el.parentElement
      if (container) {
        container.innerHTML = svg
        container.classList.add('mermaid-rendered-container')
      }
    } catch (err) {
      el.classList.add('mermaid-rendered')
      console.warn('Mermaid 渲染失败:', err)
    }
  }
}

onMounted(async () => {
  await chatStore.loadSessions()
  const sessionId = route.params.sessionId as string
  if (sessionId) {
    await chatStore.switchSession(sessionId)
  }
})

onUnmounted(() => {
  chatStore.stopPolling()
})

/** 滚动到消息底部 */
function scrollToBottom() {
  nextTick(() => {
    if (messagesArea.value) {
      messagesArea.value.scrollTop = messagesArea.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
  renderMermaidBlocks()
})
watch(() => chatStore.streaming, scrollToBottom)

/** 简单的 Markdown 渲染（将关键标记转为 HTML） */
function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Mermaid 代码块：保留原始内容，由后续逻辑渲染
  html = html.replace(
    /```mermaid\n([\s\S]*?)```/g,
    '<div class="mermaid-block"><pre class="mermaid-source">$1</pre></div>'
  )
  // 普通代码块
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    '<pre class="code-block"><code>$2</code></pre>'
  )
  // 行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  // 表格
  html = renderTables(html)
  // 标题
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // 粗体和斜体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // 列表
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
  // 分割线
  html = html.replace(/^---$/gm, '<hr/>')
  // 换行
  html = html.replace(/\n/g, '<br/>')
  // 修复列表包裹
  html = html.replace(/(<li>.*?<\/li>(<br\/>)?)+/g, (match) => {
    return '<ul>' + match.replace(/<br\/>/g, '') + '</ul>'
  })
  return html
}

/** Markdown 表格渲染 */
function renderTables(text: string): string {
  const tableRegex = /(\|.+\|[\r\n]+\|[-| :]+\|[\r\n]+((\|.+\|[\r\n]*)+))/g
  return text.replace(tableRegex, (match) => {
    const rows = match.trim().split('\n').filter(r => r.trim())
    if (rows.length < 2) return match

    const headerCells = rows[0].split('|').filter(c => c.trim())
    const dataRows = rows.slice(2)

    let table = '<table class="md-table"><thead><tr>'
    for (const cell of headerCells) {
      table += `<th>${cell.trim()}</th>`
    }
    table += '</tr></thead><tbody>'
    for (const row of dataRows) {
      const cells = row.split('|').filter(c => c.trim())
      table += '<tr>'
      for (const cell of cells) {
        table += `<td>${cell.trim()}</td>`
      }
      table += '</tr>'
    }
    table += '</tbody></table>'
    return table
  })
}

/** 会话状态中文标签 */
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    active: '对话中',
    confirmed: '已确认',
    generating: '生成中',
    completed: '已完成',
  }
  return map[status] || status
}

/** 创建新对话 */
async function handleNewChat() {
  const sessionId = await chatStore.createSession()
  if (sessionId) {
    await chatStore.switchSession(sessionId)
    router.replace({ name: 'chatSession', params: { sessionId } })
  }
}

/** 快捷示例：创建新对话并发送 */
async function handleQuickStart(example: string) {
  const sessionId = await chatStore.createSession()
  if (sessionId) {
    await chatStore.switchSession(sessionId)
    router.replace({ name: 'chatSession', params: { sessionId } })
    await nextTick()
    await chatStore.sendMessage(example)
  }
}

/** 切换会话 */
async function handleSwitchSession(sessionId: string) {
  await chatStore.switchSession(sessionId)
  router.replace({ name: 'chatSession', params: { sessionId } })
  // 如果正在生成中，恢复轮询
  if (chatStore.currentSession?.status === 'generating') {
    chatStore.startPolling()
  }
}

/** 删除会话 */
async function handleDeleteSession(sessionId: string) {
  try {
    await ElMessageBox.confirm('确定删除这个对话？', '删除确认', {
      type: 'warning',
    })
    await chatStore.deleteSession(sessionId)
  } catch { /* 用户取消 */ }
}

/** 发送消息 */
async function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.streaming) return
  inputText.value = ''
  await chatStore.sendMessage(text)
}

/** 确认大纲 */
async function handleConfirm() {
  try {
    await ElMessageBox.confirm(
      '将基于当前需求大纲，并行生成需求文档、流程图、ER 图、测试用例和 API 文档。是否继续？',
      '确认生成',
      { type: 'info', confirmButtonText: '开始生成', cancelButtonText: '再想想' },
    )
    const ok = await chatStore.confirmOutline()
    if (ok) {
      ElMessage.success('文档生成已启动，请稍候...')
    } else {
      ElMessage.error('启动失败，请重试')
    }
  } catch { /* 用户取消 */ }
}

/** 复制内容到剪贴板 */
async function copyContent(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

/** 下载产出物为文件 */
function downloadArtifact(msg: ChatMessage) {
  const meta = msg.metadata as Record<string, unknown> | undefined
  const skillName = (meta?.skill_name as string) || 'document'
  const outputType = (meta?.output_type as string) || 'markdown'
  const ext = outputType === 'yaml' ? 'yaml' : 'md'
  const filename = `${skillName}.${ext}`

  const blob = new Blob([msg.content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: #f8fafc;
}

/* ── 左侧会话列表 ────────────────────────── */
.chat-sidebar {
  width: 260px;
  background: #ffffff;
  border-right: 1px solid #e8ecf1;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e8ecf1;
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.2s;
}

.session-item:hover {
  background: #f0f4ff;
}

.session-item.active {
  background: #e8f0fe;
}

.session-title {
  font-size: 13px;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.session-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.session-status {
  font-size: 11px;
  color: #999;
}

.session-status.active { color: #409eff; }
.session-status.confirmed { color: #e6a23c; }
.session-status.generating { color: #f56c6c; }
.session-status.completed { color: #67c23a; }

.session-delete {
  font-size: 14px;
  color: #ccc;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-delete {
  opacity: 1;
}

.session-delete:hover {
  color: #f56c6c;
}

.empty-sessions {
  text-align: center;
  color: #999;
  font-size: 13px;
  padding: 40px 16px;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid #e8ecf1;
  text-align: center;
}

.footer-label {
  font-size: 11px;
  color: #bbb;
}

/* ── 右侧主区域 ──────────────────────────── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ── 欢迎页 ──────────────────────────────── */
.welcome-screen {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.welcome-content {
  text-align: center;
  max-width: 560px;
  padding: 40px;
}

.welcome-title {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 12px;
}

.welcome-desc {
  font-size: 15px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 24px;
}

.welcome-examples {
  margin-top: 32px;
}

.examples-title {
  font-size: 13px;
  color: #999;
  margin-bottom: 12px;
}

.example-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.example-chip {
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 20px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.example-chip:hover {
  border-color: #409eff;
  color: #409eff;
  background: #f0f7ff;
}

/* ── 聊天容器 ────────────────────────────── */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  scroll-behavior: smooth;
}

/* ── 消息气泡 ────────────────────────────── */
.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant,
.message-row.system {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 75%;
  display: flex;
  gap: 10px;
}

.user-bubble {
  flex-direction: row-reverse;
}

.user-bubble .bubble-content {
  background: #409eff;
  color: #fff;
  border-radius: 16px 16px 4px 16px;
  padding: 10px 16px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.assistant-bubble .bubble-content {
  background: #fff;
  border: 1px solid #e8ecf1;
  border-radius: 4px 16px 16px 16px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.7;
  color: #333;
  word-break: break-word;
}

.system-bubble {
  justify-content: center;
  max-width: 100%;
}

.progress-msg {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #999;
  padding: 6px 16px;
  background: #f5f5f5;
  border-radius: 12px;
}

.done-icon {
  color: #67c23a;
}

/* ── 大纲卡片 ────────────────────────────── */
.outline-card {
  background: #fff;
  border: 1px solid #e0e7ff;
  border-radius: 12px;
  padding: 20px;
  min-width: 400px;
}

.outline-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 12px 0;
}

.outline-info {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.outline-section {
  margin-bottom: 14px;
}

.outline-label {
  font-size: 13px;
  font-weight: 600;
  color: #555;
  display: block;
  margin-bottom: 6px;
}

.outline-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}

.module-list {
  padding-left: 4px;
}

.module-item {
  font-size: 13px;
  color: #444;
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
}

.module-item:last-child {
  border-bottom: none;
}

.feature-list {
  max-height: 200px;
  overflow-y: auto;
  padding-left: 4px;
}

.feature-item {
  font-size: 13px;
  color: #555;
  padding: 3px 0;
}

.outline-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

/* ── 产出物卡片 ──────────────────────────── */
.artifact-bubble {
  max-width: 90%;
}

.artifact-card {
  background: #fff;
  border: 1px solid #e0e7ff;
  border-radius: 12px;
  overflow: hidden;
}

.artifact-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f8f9fe;
  border-bottom: 1px solid #e8ecf1;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.artifact-title {
  flex: 1;
}

.artifact-content {
  padding: 16px;
  max-height: 500px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.7;
}

.artifact-footer {
  padding: 10px 16px;
  border-top: 1px solid #e8ecf1;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

/* ── 打字指示器 ──────────────────────────── */
.typing-indicator {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.typing-dots {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e8ecf1;
  border-radius: 4px 16px 16px 16px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  background: #999;
  border-radius: 50%;
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* ── 底部输入区域 ────────────────────────── */
.input-area {
  padding: 12px 24px 16px;
  background: #fff;
  border-top: 1px solid #e8ecf1;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  max-width: 800px;
  margin: 0 auto;
}

.input-wrapper :deep(.el-textarea__inner) {
  border-radius: 12px;
  padding: 10px 16px;
  font-size: 14px;
  resize: none;
  border: 1px solid #dcdfe6;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

.input-wrapper :deep(.el-textarea__inner:focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
}

.send-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
}

.input-hint {
  text-align: center;
  font-size: 11px;
  color: #bbb;
  margin-top: 6px;
}

/* ── Markdown 渲染样式 ───────────────────── */
.markdown-body :deep(h1) { font-size: 20px; font-weight: 700; margin: 16px 0 8px; color: #1a1a2e; }
.markdown-body :deep(h2) { font-size: 17px; font-weight: 600; margin: 14px 0 6px; color: #1a1a2e; }
.markdown-body :deep(h3) { font-size: 15px; font-weight: 600; margin: 12px 0 4px; color: #333; }
.markdown-body :deep(h4) { font-size: 14px; font-weight: 600; margin: 10px 0 4px; color: #444; }
.markdown-body :deep(strong) { font-weight: 600; }

.markdown-body :deep(.code-block) {
  background: #f6f8fa;
  border-radius: 8px;
  padding: 12px 16px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  margin: 8px 0;
}

.markdown-body :deep(.inline-code) {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: #c7254e;
}

.markdown-body :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
}

.markdown-body :deep(.md-table th) {
  background: #f8f9fa;
  padding: 6px 10px;
  text-align: left;
  border: 1px solid #e0e0e0;
  font-weight: 600;
}

.markdown-body :deep(.md-table td) {
  padding: 6px 10px;
  border: 1px solid #e0e0e0;
}

.markdown-body :deep(ul) {
  padding-left: 20px;
  margin: 4px 0;
}

.markdown-body :deep(li) {
  margin-bottom: 2px;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 12px 0;
}

.markdown-body :deep(.mermaid-block) {
  background: #f8f9fe;
  border: 1px solid #e0e7ff;
  border-radius: 8px;
  padding: 16px;
  margin: 8px 0;
  overflow-x: auto;
}

/* ── 响应式 ──────────────────────────────── */
@media (max-width: 768px) {
  .chat-sidebar {
    display: none;
  }
  .message-bubble {
    max-width: 90%;
  }
  .outline-card {
    min-width: auto;
  }
}
</style>
