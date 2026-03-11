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

export const useTaskStore = defineStore('task', () => {
  const currentTask = ref<Task | null>(null)
  const generating = ref(false)
  const progress = ref(0)
  const questions = ref<Question[]>([])

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
      return { success: false, message: response.data.message }
    } catch (error) {
      console.error('创建任务失败:', error)
      return { success: false, message: '创建任务失败' }
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
  }

  return {
    currentTask,
    generating,
    progress,
    questions,
    createTask,
    reset,
  }
})
