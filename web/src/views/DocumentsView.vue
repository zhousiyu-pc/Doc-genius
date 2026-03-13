<template>
  <div class="docs-container">
    <div class="docs-header">
      <el-button :icon="ArrowLeft" @click="router.push('/')">返回首页</el-button>
      <h2 class="docs-title">我的文档</h2>
    </div>

    <el-card class="docs-card">
      <div v-if="tasks.length === 0" class="empty-state">
        <el-empty description="暂无文档，去首页生成吧">
          <el-button type="primary" @click="router.push('/')">立即生成</el-button>
        </el-empty>
      </div>

      <el-table v-else :data="tasks" stripe style="width: 100%">
        <el-table-column label="任务 ID" prop="id" width="160" />
        <el-table-column label="功能点数" prop="total_count" width="100" align="center" />
        <el-table-column label="完成数" prop="completed_count" width="100" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="tagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" prop="created_at" min-width="180" />
        <el-table-column label="操作" width="160" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="viewDoc(row.id)">查看</el-button>
            <el-button size="small" type="danger" @click="deleteTask(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const tasks = ref<any[]>([])

/** 获取任务列表（通过健康检查接口确认服务在线后读 localStorage 备份） */
async function loadTasks() {
  try {
    // 尝试从后端获取任务列表（如有该接口）
    const resp = await axios.get('/api/tasks')
    if (resp.data.success && Array.isArray(resp.data.tasks)) {
      tasks.value = resp.data.tasks
      return
    }
  } catch {
    // 接口不存在或出错，读取本地缓存
  }
  // 从 localStorage 读取曾经创建的 task_id 列表
  const saved = localStorage.getItem('doc_task_ids')
  if (!saved) return
  const ids: string[] = JSON.parse(saved)
  const results = await Promise.allSettled(
    ids.map(id => axios.get(`/api/tasks/${id}`))
  )
  tasks.value = results
    .filter(r => r.status === 'fulfilled' && r.value.data.success)
    .map(r => (r as PromiseFulfilledResult<any>).value.data)
}

function tagType(status: string) {
  const map: Record<string, string> = {
    running: 'warning', completed: 'success', partial: 'info', failed: 'danger', pending: 'info',
  }
  return map[status] || 'info'
}

function statusText(status: string) {
  const map: Record<string, string> = {
    running: '生成中', completed: '已完成', partial: '部分完成', failed: '失败', pending: '等待中',
  }
  return map[status] || status
}

function viewDoc(id: string) {
  router.push(`/document/${id}`)
}

async function deleteTask(id: string) {
  try {
    await ElMessageBox.confirm('确认删除该任务记录？', '提示', { type: 'warning' })
    // 从本地缓存移除
    const saved = localStorage.getItem('doc_task_ids')
    if (saved) {
      const ids: string[] = JSON.parse(saved)
      localStorage.setItem('doc_task_ids', JSON.stringify(ids.filter(i => i !== id)))
    }
    tasks.value = tasks.value.filter(t => t.id !== id)
    ElMessage.success('已删除')
  } catch {
    // 用户取消
  }
}

onMounted(loadTasks)
</script>

<style scoped lang="scss">
.docs-container {
  min-height: 100vh;
  padding: 40px 20px;
  max-width: 1000px;
  margin: 0 auto;
}

.docs-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 32px;

  .docs-title {
    color: #0f172a;
    font-size: 28px;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
  }
}

.docs-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0 !important;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
}

.empty-state {
  padding: 60px 20px;
  text-align: center;
}
</style>
