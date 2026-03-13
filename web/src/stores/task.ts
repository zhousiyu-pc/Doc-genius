import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export interface Task {
  task_id: string
  status: string
  domain?: string
  domain_name?: string
  feature_count: number
  completed_count: number
  failed_count: number
  total_count: number
  created_at: string
  result_file?: string
}

export interface Question {
  field: string
  question: string
  options: string[]
}

export interface AnalysisPreview {
  domain: string
  domain_name: string
  feature_count: number
  complexity: string
  core_modules: string[]
  feature_list: string[]
  questions: Question[]
}

export const useTaskStore = defineStore('task', () => {
  const currentTask = ref<Task | null>(null)
  const generating = ref(false)
  const progress = ref(0)
  const questions = ref<Question[]>([])
  const analysis = ref<AnalysisPreview | null>(null)
  const lastRequirement = ref('')

  async function analyze(requirement: string) {
    analysis.value = null
    lastRequirement.value = requirement
    try {
      const response = await axios.post('/api/analyze', {
        requirement,
        preview_only: true,
      })
      if (response.data.success) {
        analysis.value = {
          domain: response.data.domain,
          domain_name: response.data.domain_name,
          feature_count: response.data.feature_count,
          complexity: response.data.complexity,
          core_modules: response.data.core_modules || [],
          feature_list: response.data.feature_list || [],
          questions: response.data.questions || [],
        }
        return { success: true, data: response.data }
      }
      return { success: false, message: response.data.message || '分析失败' }
    } catch (error) {
      console.error('需求分析失败:', error)
      return { success: false, message: '需求分析失败，请稍后重试' }
    }
  }

  async function createTask(requirement: string) {
    try {
      generating.value = true
      const response = await axios.post('/api/analyze', {
        requirement,
      })

      if (response.data.success) {
        currentTask.value = {
          task_id: response.data.task_id,
          status: 'pending',
          domain: response.data.domain,
          domain_name: response.data.domain_name,
          feature_count: response.data.feature_count,
          completed_count: 0,
          failed_count: 0,
          total_count: response.data.feature_count,
          created_at: new Date().toISOString(),
        }
        questions.value = response.data.questions || []
        pollProgress(response.data.task_id)
        return { success: true, data: response.data }
      }
      generating.value = false
      return { success: false, message: response.data.message || '未知错误' }
    } catch (error: unknown) {
      console.error('创建任务失败:', error)
      // 提取后端返回的具体错误信息（500 时 response.data.message 包含原因）
      const msg =
        axios.isAxiosError(error) && error.response?.data?.message
          ? error.response.data.message
          : axios.isAxiosError(error) && error.response?.status === 500
            ? '服务端处理失败，请检查后端日志或稍后重试'
            : axios.isAxiosError(error) && error.code === 'ECONNREFUSED'
              ? '无法连接后端服务，请确认后端已启动（默认端口 8766）'
              : '创建任务失败，请稍后重试'
      generating.value = false
      return { success: false, message: msg }
    }
  }

  function pollProgress(taskId: string) {
    const timer = setInterval(async () => {
      try {
        const response = await axios.get(`/api/tasks/${taskId}`)
        if (response.data.success) {
          const data = response.data
          progress.value = Math.round(
            (data.completed_count / data.total_count) * 100
          )

          if (currentTask.value) {
            currentTask.value = {
              ...currentTask.value,
              status: data.status,
              completed_count: data.completed_count,
              failed_count: data.failed_count,
              result_file: data.result_file,
            }
          }

          if (data.status === 'completed' || data.status === 'partial') {
            clearInterval(timer)
            generating.value = false
          }
        }
      } catch (error) {
        console.error('轮询进度失败:', error)
      }
    }, 2000)
  }

  function reset() {
    currentTask.value = null
    generating.value = false
    progress.value = 0
    questions.value = []
    analysis.value = null
    lastRequirement.value = ''
  }

  return {
    currentTask,
    generating,
    progress,
    questions,
    analysis,
    lastRequirement,
    analyze,
    createTask,
    reset,
  }
})
