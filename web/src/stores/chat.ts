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
  msg_type: 'text' | 'outline' | 'progress' | 'artifact' | 'file' | 'milestone'
  metadata?: Record<string, unknown>
  created_at: string
}

/** 对话会话 */
export interface ChatSession {
  id: string
  title: string
  status: 'active' | 'confirmed' | 'generating' | 'completed'
  mode: 'free' | 'agile'
  current_stage: string
  model?: string | null
  outline?: OutlineData | null
  task_id?: string
  created_at: string
  updated_at: string
}

/** 可选的文档类型 */
export type DocType = 'outline' | 'detail' | 'proposal_ppt'

export const useChatStore = defineStore('chat', () => {
  // ── 状态 ──────────────────────────────────────────
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  let _abortController: AbortController | null = null
  const streaming = ref(false)
  const streamingContent = ref('')
  const outline = ref<OutlineData | null>(null)
  const confirming = ref(false)

  /** 文件上传状态 */
  const uploading = ref(false)

  /** 消息选择导出模式 */
  const selectMode = ref(false)
  const selectedMessageIds = ref<Set<string>>(new Set())
  const exportFormat = ref<string>('docx')
  const exporting = ref(false)

  /** 敏捷模式：环节大纲摘要（各环节成果） */
  const stageSummaries = ref<Array<{ stage: string; label: string; title: string; content: string; msg_id?: string }>>([])

  /** 敏捷模式：待确认的环节完成询问（AI 输出 [STAGE_READY] 时设置） */
  const stageReady = ref<{ stage: string; summary?: string } | null>(null)

  /** 可用模型列表 */
  const availableModels = ref<Array<{id: string, name: string, provider: string, tier: string, cost_multiplier: number}>>([])

  // ── 计算属性 ──────────────────────────────────────
  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value) || null
  )

  const currentModel = computed(() =>
    currentSession.value?.model || null
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

  /** 搜索会话 */
  async function searchSessions(query: string) {
    try {
      const { data } = await axios.get('/api/chat/sessions', { params: { q: query } })
      if (data.success) {
        sessions.value = data.sessions
      }
    } catch (err) {
      console.error('搜索会话失败:', err)
    }
  }

  /** 创建新会话 */
  async function createSession(title = '', mode = 'free', model: string | null = null): Promise<string | null> {
    try {
      const { data } = await axios.post('/api/chat/sessions', { title, mode, model })
      if (data.success) {
        const newSession: ChatSession = {
          id: data.id,
          title: data.title || '',
          status: 'active',
          mode: data.mode || 'free',
          current_stage: data.current_stage || 'discovery',
          model: data.model || null,
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

  /** 加载环节大纲摘要（敏捷模式） */
  async function loadStageSummaries(sessionId: string) {
    try {
      const { data } = await axios.get(`/api/chat/sessions/${sessionId}/stage_summaries`)
      if (data.success) {
        stageSummaries.value = data.summaries || []
      }
    } catch (err) {
      console.error('加载环节摘要失败:', err)
    }
  }

  /** 用户确认进入下一环节 */
  async function advanceStage(sessionId: string): Promise<boolean> {
    try {
      const { data } = await axios.post(`/api/chat/sessions/${sessionId}/advance_stage`)
      if (data.success) {
        const session = sessions.value.find(s => s.id === sessionId)
        if (session) {
          session.current_stage = data.next_stage
        }
        stageReady.value = null
        await loadStageSummaries(sessionId)
        return true
      }
    } catch (err) {
      console.error('进入下一环节失败:', err)
    }
    return false
  }

  /** 按环节导出附件 */
  async function exportStage(sessionId: string, stageId: string, format: string): Promise<boolean> {
    try {
      const { data } = await axios.post(`/api/chat/sessions/${sessionId}/export_stage`, {
        stage: stageId,
        format,
      })
      if (data.success) {
        startPolling()
        return true
      }
    } catch (err) {
      console.error('环节导出失败:', err)
    }
    return false
  }

  /** 清除环节完成询问状态 */
  function clearStageReady() {
    stageReady.value = null
  }

  /** 手动切换会话阶段 */
  async function updateStage(sessionId: string, stage: string) {
    try {
      const { data } = await axios.post(`/api/chat/sessions/${sessionId}/stage`, { stage })
      if (data.success) {
        const session = sessions.value.find(s => s.id === sessionId)
        if (session) {
          session.current_stage = stage
        }
      }
    } catch (err) {
      console.error('更新阶段失败:', err)
    }
  }

  /**
   * 重命名会话标题。
   * @param sessionId 会话 ID
   * @param newTitle 新标题
   */
  async function renameSession(sessionId: string, newTitle: string): Promise<boolean> {
    try {
      const { data } = await axios.put(`/api/chat/sessions/${sessionId}/rename`, { title: newTitle })
      if (data.success) {
        const session = sessions.value.find(s => s.id === sessionId)
        if (session) {
          session.title = data.title
        }
        return true
      }
    } catch (err) {
      console.error('重命名会话失败:', err)
    }
    return false
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
        // 敏捷模式：加载环节大纲
        if (data.session?.mode === 'agile') {
          await loadStageSummaries(sessionId)
        } else {
          stageSummaries.value = []
          stageReady.value = null
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

  /** 停止当前流式对话 */
  function stopStreaming() {
    if (_abortController) {
      _abortController.abort()
      _abortController = null
    }
    streaming.value = false
    streamingContent.value = ''
  }

  /** 发送消息并通过 SSE 接收流式响应 */
  async function sendMessage(content: string) {
    if (!currentSessionId.value || streaming.value) return

    const userMsg: ChatMessage = {
      id: `local_${Date.now()}`,
      role: 'user',
      content,
      msg_type: 'text',
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMsg)

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
    _abortController = new AbortController()

    try {
      const response = await fetch(
        `/api/chat/sessions/${currentSessionId.value}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
          signal: _abortController.signal,
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
              messages.value.push({
                id: `outline_${Date.now()}`,
                role: 'assistant',
                content: '',
                msg_type: 'outline',
                metadata: outlineData as unknown as Record<string, unknown>,
                created_at: new Date().toISOString(),
              })
            } catch { /* 忽略解析失败 */ }
          } else if (eventType === 'stage_update') {
            try {
              const stageData = JSON.parse(eventData)
              const session = sessions.value.find(s => s.id === currentSessionId.value)
              if (session) {
                session.current_stage = stageData.next_stage
              }
            } catch { /* 忽略 */ }
          } else if (eventType === 'stage_ready') {
            try {
              const stageData = JSON.parse(eventData)
              stageReady.value = { stage: stageData.stage, summary: stageData.summary }
            } catch { /* 忽略 */ }
          } else if (eventType === 'stage_advance') {
            try {
              const stageData = JSON.parse(eventData)
              const session = sessions.value.find(s => s.id === currentSessionId.value)
              if (session) {
                session.current_stage = stageData.next_stage
              }
              stageReady.value = null
              if (currentSessionId.value) {
                loadStageSummaries(currentSessionId.value)
              }
            } catch { /* 忽略 */ }
          } else if (eventType === 'milestone') {
            try {
              const milestoneData = JSON.parse(eventData)
              messages.value.push({
                id: `milestone_${Date.now()}`,
                role: 'assistant',
                content: milestoneData.content || '',
                msg_type: 'milestone',
                metadata: milestoneData,
                created_at: new Date().toISOString(),
              })
              if (currentSessionId.value) {
                loadStageSummaries(currentSessionId.value)
              }
            } catch { /* 忽略 */ }
          } else if (eventType === 'export') {
            try {
              const exportInfo = JSON.parse(eventData)
              if (exportInfo.content_type === 'chat') {
                // chat 类型：进入消息选择模式，让用户勾选要导出的消息
                exportFormat.value = exportInfo.format || 'docx'
                enterSelectMode()
              } else {
                // 标准文档类型：直接轮询获取结果
                startPolling()
              }
            } catch {
              startPolling()
            }
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

  /** 确认需求大纲，启动 Skill 流水线。docConfigs 指定每个文档类型要导出的格式。 */
  async function confirmOutline(docConfigs: Record<string, string[]>): Promise<boolean> {
    if (!currentSessionId.value || !outline.value) return false

    confirming.value = true
    try {
      const { data } = await axios.post(
        `/api/chat/sessions/${currentSessionId.value}/confirm`,
        { doc_configs: docConfigs }
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

  /** 开始轮询会话消息（获取 Skill 生成的产出物或即时导出结果） */
  function startPolling() {
    stopPolling()
    let pollCount = 0
    const maxPolls = 60
    pollTimer = setInterval(async () => {
      if (!currentSessionId.value) return
      pollCount++
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
          // Pipeline 完成时停止
          if (data.session?.status === 'completed') {
            stopPolling()
            return
          }
          // 即时导出完成时停止（检测最后的 progress 消息是否有 done 标记）
          const msgs = data.messages as ChatMessage[] || []
          const lastProgress = [...msgs].reverse().find(
            (m: ChatMessage) => m.msg_type === 'progress' && m.metadata
          )
          if (lastProgress?.metadata && (lastProgress.metadata as Record<string, unknown>).done === true) {
            stopPolling()
            return
          }
        }
      } catch { /* 静默忽略轮询错误 */ }
      if (pollCount >= maxPolls) {
        stopPolling()
      }
    }, 3000)
  }

  /** 停止轮询 */
  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  // ── 消息选择导出模式 ──────────────────────────────

  /** 进入消息选择模式，默认不选中任何消息 */
  function enterSelectMode() {
    selectedMessageIds.value = new Set()
    selectMode.value = true
  }

  /** 全选所有 AI 文本消息 */
  function selectAllMessages() {
    const newSet = new Set<string>()
    for (const msg of messages.value) {
      if (msg.role === 'assistant' && msg.msg_type === 'text' && msg.content) {
        newSet.add(msg.id)
      }
    }
    selectedMessageIds.value = newSet
  }

  /** 全不选所有消息 */
  function deselectAllMessages() {
    selectedMessageIds.value = new Set()
  }

  /** 退出消息选择模式 */
  function exitSelectMode() {
    selectMode.value = false
    selectedMessageIds.value = new Set()
  }

  /** 切换某条消息的选中状态 */
  function toggleMessageSelection(msgId: string) {
    const newSet = new Set(selectedMessageIds.value)
    if (newSet.has(msgId)) {
      newSet.delete(msgId)
    } else {
      newSet.add(msgId)
    }
    selectedMessageIds.value = newSet
  }

  /** 提交选中的消息进行导出 */
  async function exportSelectedMessages(format?: string): Promise<boolean> {
    if (!currentSessionId.value || selectedMessageIds.value.size === 0) return false

    const fmt = format || exportFormat.value
    exporting.value = true
    try {
      const { data } = await axios.post(
        `/api/chat/sessions/${currentSessionId.value}/export`,
        {
          format: fmt,
          message_ids: Array.from(selectedMessageIds.value),
        }
      )
      if (data.success) {
        exitSelectMode()
        startPolling()
        return true
      }
    } catch (err) {
      console.error('导出失败:', err)
    } finally {
      exporting.value = false
    }
    return false
  }

  // ── 文件上传 ──────────────────────────────────────

  /**
   * 上传文件到当前会话，系统提取文件文本后保存为 file 类型消息。
   * 上传成功后自动在对话中显示文件消息气泡。
   * 注意：文件上传只保存文件内容，用户的指令文字由 sendMessage 单独处理。
   *
   * @param file 用户选择的文件
   * @returns 上传结果对象，失败时返回 null
   */
  async function uploadFile(file: File): Promise<Record<string, unknown> | null> {
    if (!currentSessionId.value || uploading.value) return null

    uploading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(
        `/api/chat/sessions/${currentSessionId.value}/upload`,
        { method: 'POST', body: formData }
      )

      const result = await response.json()
      if (!result.success) {
        console.error('文件上传失败:', result.message)
        return null
      }

      const fileMsg: ChatMessage = {
        id: result.file_msg_id,
        role: 'user',
        content: result.preview || '',
        msg_type: 'file',
        metadata: {
          filename: result.filename,
          file_size: result.file_size,
          file_type: result.file_type,
          char_count: result.char_count,
        },
        created_at: new Date().toISOString(),
      }
      messages.value.push(fileMsg)

      const session = sessions.value.find(s => s.id === currentSessionId.value)
      if (session && !session.title) {
        session.title = `上传: ${result.filename}`.slice(0, 30)
      }

      return result
    } catch (err) {
      console.error('文件上传失败:', err)
      return null
    } finally {
      uploading.value = false
    }
  }

  // ── 重置 ──────────────────────────────────────────

  function reset() {
    stopPolling()
    exitSelectMode()
    currentSessionId.value = null
    messages.value = []
    outline.value = null
    streaming.value = false
    streamingContent.value = ''
    confirming.value = false
    stageSummaries.value = []
    stageReady.value = null
  }

  /** 加载可用模型列表 */
  async function loadAvailableModels() {
    try {
      const { data } = await axios.get('/api/models')
      if (data.success) {
        availableModels.value = data.models
      }
    } catch (err) {
      console.error('加载模型列表失败:', err)
    }
  }

  /** 切换会话模型 */
  async function switchModel(modelId: string): Promise<boolean> {
    if (!currentSessionId.value) return false
    try {
      const { data } = await axios.put(`/api/chat/sessions/${currentSessionId.value}/model`, { model: modelId })
      if (data.success) {
        const session = sessions.value.find(s => s.id === currentSessionId.value)
        if (session) {
          session.model = modelId
        }
        return true
      }
    } catch (err) {
      console.error('切换模型失败:', err)
    }
    return false
  }

  return {
    sessions,
    currentSessionId,
    messages,
    streaming,
    streamingContent,
    outline,
    confirming,
    uploading,
    selectMode,
    stageSummaries,
    stageReady,
    selectedMessageIds,
    exportFormat,
    availableModels,
    currentModel,
    exporting,
    currentSession,
    isGenerating,
    loadSessions,
    searchSessions,
    createSession,
    renameSession,
    loadStageSummaries,
    advanceStage,
    exportStage,
    clearStageReady,
    updateStage,
    switchSession,
    deleteSession,
    sendMessage,
    stopStreaming,
    confirmOutline,
    enterSelectMode,
    exitSelectMode,
    selectAllMessages,
    deselectAllMessages,
    toggleMessageSelection,
    exportSelectedMessages,
    uploadFile,
    startPolling,
    stopPolling,
    reset,
    loadAvailableModels,
    switchModel,
  }
})
