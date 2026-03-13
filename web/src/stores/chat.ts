/**
 * 对话式需求分析 Store
 * ====================
 * 管理多轮对话会话、消息流、SSE 实时推送和大纲确认状态。
 * 通过 Pinia 提供响应式状态，供 ChatView 组件使用。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

/** 需求大纲中的模块信息 */
export interface OutlineModule {
  name: string
  description: string
}

/** LLM 生成的需求大纲 */
export interface OutlineData {
  project_name: string
  domain: string
  target_users: string[]
  business_model: string
  core_modules: OutlineModule[]
  feature_list: string[]
  tech_requirements: string[]
  complexity: string
}

/** 单条对话消息 */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  msg_type: 'text' | 'outline' | 'progress' | 'artifact'
  metadata?: Record<string, unknown>
  created_at: string
}

/** 对话会话 */
export interface ChatSession {
  id: string
  title: string
  status: 'active' | 'confirmed' | 'generating' | 'completed'
  outline?: OutlineData | null
  task_id?: string
  created_at: string
  updated_at: string
}

export const useChatStore = defineStore('chat', () => {
  // ── 状态 ──────────────────────────────────────────
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const streamingContent = ref('')
  const outline = ref<OutlineData | null>(null)
  const confirming = ref(false)

  // ── 计算属性 ──────────────────────────────────────
  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value) || null
  )

  const isGenerating = computed(() =>
    currentSession.value?.status === 'generating'
  )

  // ── 会话管理 ──────────────────────────────────────

  /** 加载所有会话列表 */
  async function loadSessions() {
    try {
      const { data } = await axios.get('/api/chat/sessions')
      if (data.success) {
        sessions.value = data.sessions
      }
    } catch (err) {
      console.error('加载会话列表失败:', err)
    }
  }

  /** 创建新会话 */
  async function createSession(title = ''): Promise<string | null> {
    try {
      const { data } = await axios.post('/api/chat/sessions', { title })
      if (data.success) {
        const newSession: ChatSession = {
          id: data.id,
          title: data.title || '',
          status: 'active',
          created_at: data.created_at,
          updated_at: data.created_at,
        }
        sessions.value.unshift(newSession)
        return data.id
      }
    } catch (err) {
      console.error('创建会话失败:', err)
    }
    return null
  }

  /** 切换到指定会话并加载消息 */
  async function switchSession(sessionId: string) {
    currentSessionId.value = sessionId
    messages.value = []
    outline.value = null
    streamingContent.value = ''
    streaming.value = false

    try {
      const { data } = await axios.get(`/api/chat/sessions/${sessionId}`)
      if (data.success) {
        messages.value = data.messages || []
        if (data.session?.outline) {
          outline.value = data.session.outline
        }
        // 更新会话列表中对应条目的状态
        const idx = sessions.value.findIndex(s => s.id === sessionId)
        if (idx !== -1) {
          sessions.value[idx] = { ...sessions.value[idx], ...data.session }
        }
      }
    } catch (err) {
      console.error('加载会话详情失败:', err)
    }
  }

  /** 删除会话 */
  async function deleteSession(sessionId: string) {
    try {
      await axios.delete(`/api/chat/sessions/${sessionId}`)
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = null
        messages.value = []
        outline.value = null
      }
    } catch (err) {
      console.error('删除会话失败:', err)
    }
  }

  // ── 消息发送（SSE 流式）──────────────────────────

  /** 发送消息并通过 SSE 接收流式响应 */
  async function sendMessage(content: string) {
    if (!currentSessionId.value || streaming.value) return

    // 立即将用户消息添加到本地列表
    const userMsg: ChatMessage = {
      id: `local_${Date.now()}`,
      role: 'user',
      content,
      msg_type: 'text',
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // 预添加一条空的 assistant 消息，用于流式填充
    const assistantMsg: ChatMessage = {
      id: `streaming_${Date.now()}`,
      role: 'assistant',
      content: '',
      msg_type: 'text',
      created_at: new Date().toISOString(),
    }
    messages.value.push(assistantMsg)

    streaming.value = true
    streamingContent.value = ''

    try {
      const response = await fetch(
        `/api/chat/sessions/${currentSessionId.value}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
        }
      )

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // 按双换行分割 SSE 事件
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.trim()) continue

          const lines = part.split('\n')
          let eventType = 'text'
          let eventData = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6)
            }
          }

          if (!eventData) continue

          if (eventType === 'text') {
            try {
              const parsed = JSON.parse(eventData)
              streamingContent.value += parsed.content || ''
              // 实时更新 assistant 消息内容
              const lastMsg = messages.value[messages.value.length - 1]
              if (lastMsg && lastMsg.role === 'assistant') {
                lastMsg.content = streamingContent.value
              }
            } catch { /* 忽略解析失败的 chunk */ }
          } else if (eventType === 'outline') {
            try {
              const outlineData = JSON.parse(eventData) as OutlineData
              outline.value = outlineData
              // 添加大纲消息
              messages.value.push({
                id: `outline_${Date.now()}`,
                role: 'assistant',
                content: '',
                msg_type: 'outline',
                metadata: outlineData as unknown as Record<string, unknown>,
                created_at: new Date().toISOString(),
              })
            } catch { /* 忽略解析失败 */ }
          } else if (eventType === 'done') {
            // 流结束
          }
        }
      }

      // 更新会话标题（使用第一条消息的内容）
      const session = sessions.value.find(s => s.id === currentSessionId.value)
      if (session && !session.title) {
        session.title = content.slice(0, 30)
      }
    } catch (err) {
      console.error('发送消息失败:', err)
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.role === 'assistant' && !lastMsg.content) {
        lastMsg.content = '抱歉，消息发送失败，请重试。'
      }
    } finally {
      streaming.value = false
      streamingContent.value = ''
    }
  }

  // ── 确认大纲 ──────────────────────────────────────

  /** 确认需求大纲，启动 Skill 流水线 */
  async function confirmOutline(): Promise<boolean> {
    if (!currentSessionId.value || !outline.value) return false

    confirming.value = true
    try {
      const { data } = await axios.post(
        `/api/chat/sessions/${currentSessionId.value}/confirm`
      )
      if (data.success) {
        // 更新会话状态
        const session = sessions.value.find(s => s.id === currentSessionId.value)
        if (session) {
          session.status = 'generating'
        }
        // 开始轮询新消息（产出物通过 artifact 消息推送）
        startPolling()
        return true
      }
    } catch (err) {
      console.error('确认大纲失败:', err)
    } finally {
      confirming.value = false
    }
    return false
  }

  // ── 轮询产出物消息 ──────────────────────────────────

  let pollTimer: ReturnType<typeof setInterval> | null = null

  /** 开始轮询会话消息（获取 Skill 生成的产出物） */
  function startPolling() {
    stopPolling()
    pollTimer = setInterval(async () => {
      if (!currentSessionId.value) return
      try {
        const { data } = await axios.get(
          `/api/chat/sessions/${currentSessionId.value}`
        )
        if (data.success) {
          messages.value = data.messages || []
          const session = sessions.value.find(s => s.id === currentSessionId.value)
          if (session && data.session) {
            session.status = data.session.status
          }
          // 如果已完成，停止轮询
          if (data.session?.status === 'completed') {
            stopPolling()
          }
        }
      } catch { /* 静默忽略轮询错误 */ }
    }, 3000)
  }

  /** 停止轮询 */
  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  // ── 重置 ──────────────────────────────────────────

  function reset() {
    stopPolling()
    currentSessionId.value = null
    messages.value = []
    outline.value = null
    streaming.value = false
    streamingContent.value = ''
    confirming.value = false
  }

  return {
    sessions,
    currentSessionId,
    messages,
    streaming,
    streamingContent,
    outline,
    confirming,
    currentSession,
    isGenerating,
    loadSessions,
    createSession,
    switchSession,
    deleteSession,
    sendMessage,
    confirmOutline,
    startPolling,
    stopPolling,
    reset,
  }
})
