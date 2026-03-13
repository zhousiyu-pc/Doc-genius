<template>
  <div class="doc-container">
    <div class="doc-header">
      <el-button :icon="ArrowLeft" @click="router.back()">返回</el-button>
      <div class="doc-title">{{ title }}</div>
      <div class="doc-actions">
        <el-button type="primary" :icon="Download" @click="handleDownload">下载文档</el-button>
        <el-button :icon="CopyDocument" @click="handleCopy">复制内容</el-button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="doc-loading">
      <el-skeleton :rows="20" animated />
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="doc-error">
      <el-result icon="error" :title="error" sub-title="请返回重试">
        <template #extra>
          <el-button type="primary" @click="router.back()">返回首页</el-button>
        </template>
      </el-result>
    </div>

    <!-- 文档内容 -->
    <div v-else class="doc-content-wrapper">
      <!-- 进度条（生成中） -->
      <el-card v-if="status === 'running'" class="progress-card">
        <div class="progress-header">
          <el-icon class="spinning"><Loading /></el-icon>
          <span>正在生成文档... {{ completedCount }}/{{ totalCount }}</span>
        </div>
        <el-progress
          :percentage="progress"
          :stroke-width="12"
          status="striped"
          striped-flow
          :duration="20"
        />
      </el-card>

      <!-- 文档预览 -->
      <el-card class="doc-preview-card">
        <template #header>
          <div class="preview-header">
            <span>文档预览</span>
            <el-tag :type="statusTagType" size="small">{{ statusText }}</el-tag>
          </div>
        </template>
        <div class="markdown-body" v-html="renderedContent"></div>
      </el-card>

      <!-- 子任务列表 -->
      <el-card v-if="subTasks.length > 0" class="subtasks-card">
        <template #header>功能点详情</template>
        <el-table :data="subTasks" stripe>
          <el-table-column prop="feature_name" label="功能点" min-width="200" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="subTaskTagType(row.status)" size="small">
                {{ subTaskStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="error" label="错误信息" min-width="200">
            <template #default="{ row }">
              <span class="error-text">{{ row.error || '—' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Download, CopyDocument, Loading } from '@element-plus/icons-vue'
import axios from 'axios'

/**
 * 简单的 Markdown 渲染（将常用语法转为 HTML）
 * 不引入 marked 等外部依赖，减少包体积
 */
function simpleMarkdown(md: string): string {
  if (!md) return ''
  return md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // 代码块
    .replace(/```[\w]*\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    // 标题
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // 粗体
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 斜体
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // 行内代码
    .replace(/`(.+?)`/g, '<code>$1</code>')
    // 水平线
    .replace(/^---$/gm, '<hr/>')
    // 表格
    .replace(/^\|(.+)\|$/gm, (line) => {
      if (/^[\|\s\-:]+$/.test(line)) return ''
      const cells = line.split('|').filter((_, i, a) => i > 0 && i < a.length - 1)
      return '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>'
    })
    // 无序列表
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    // 有序列表
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // 段落（保留换行）
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[hH\d]|<li|<pre|<hr|<tr|<\/p>|<p>)(.+)$/gm, '<p>$1</p>')
}

const route = useRoute()
const router = useRouter()
const taskId = route.params.id as string

const loading = ref(true)
const error = ref('')
const title = ref('文档详情')
const status = ref('running')
const totalCount = ref(0)
const completedCount = ref(0)
const failedCount = ref(0)
const subTasks = ref<any[]>([])
const results = ref<string[]>([])

let pollTimer: ReturnType<typeof setInterval> | null = null

const progress = computed(() =>
  totalCount.value > 0 ? Math.round((completedCount.value / totalCount.value) * 100) : 0
)

const renderedContent = computed(() => {
  const md = results.value.filter(Boolean).join('\n\n---\n\n')
  return simpleMarkdown(md)
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    running: '生成中',
    completed: '已完成',
    partial: '部分完成',
    failed: '失败',
    pending: '等待中',
  }
  return map[status.value] || status.value
})

const statusTagType = computed(() => {
  const map: Record<string, string> = {
    running: 'warning',
    completed: 'success',
    partial: 'info',
    failed: 'danger',
  }
  return map[status.value] || 'info'
})

function subTaskTagType(s: string) {
  const map: Record<string, string> = { completed: 'success', failed: 'danger', running: 'warning', pending: 'info' }
  return map[s] || 'info'
}

function subTaskStatusText(s: string) {
  const map: Record<string, string> = { completed: '已完成', failed: '失败', running: '生成中', pending: '等待' }
  return map[s] || s
}

async function fetchResult() {
  try {
    const resp = await axios.get(`/api/tasks/${taskId}/result`)
    if (resp.data.success) {
      const data = resp.data
      status.value = data.status
      totalCount.value = data.total_count
      completedCount.value = data.completed_count
      failedCount.value = data.failed_count
      results.value = data.results || []
      title.value = `文档 - ${taskId}`
    }
  } catch {
    // 静默失败，继续轮询
  }
}

async function fetchStatus() {
  try {
    const resp = await axios.get(`/api/tasks/${taskId}`)
    if (resp.data.success) {
      const data = resp.data
      status.value = data.status
      totalCount.value = data.total_count
      completedCount.value = data.completed_count
      failedCount.value = data.failed_count
      subTasks.value = data.sub_tasks || []
      loading.value = false

      if (data.completed_count > 0) {
        await fetchResult()
      }

      if (data.status === 'completed' || data.status === 'partial') {
        if (pollTimer) clearInterval(pollTimer)
      }
    } else {
      error.value = resp.data.message || '任务不存在'
      loading.value = false
      if (pollTimer) clearInterval(pollTimer)
    }
  } catch (e) {
    error.value = '加载失败，请检查网络连接'
    loading.value = false
    if (pollTimer) clearInterval(pollTimer)
  }
}

function handleDownload() {
  const md = results.value.filter(Boolean).join('\n\n---\n\n')
  if (!md) {
    ElMessage.warning('文档内容还未生成')
    return
  }
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `需求文档_${taskId}.md`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('下载成功')
}

function handleCopy() {
  const md = results.value.filter(Boolean).join('\n\n---\n\n')
  if (!md) {
    ElMessage.warning('文档内容还未生成')
    return
  }
  navigator.clipboard.writeText(md).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动选择文本')
  })
}

onMounted(() => {
  fetchStatus()
  pollTimer = setInterval(fetchStatus, 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped lang="scss">
.doc-container {
  min-height: 100vh;
  padding: 40px 20px;
  background-color: transparent;
  max-width: 900px;
  margin: 0 auto;
}

.doc-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
  background: #ffffff;
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);

  .doc-title {
    flex: 1;
    font-size: 18px;
    font-weight: 600;
    color: #0f172a;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .doc-actions {
    display: flex;
    gap: 12px;
  }
}

.doc-loading, .doc-error {
  background: #ffffff;
  border-radius: 12px;
  padding: 40px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.doc-content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.progress-card {
  border: 1px solid #e2e8f0 !important;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;

  .progress-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    font-size: 15px;
    font-weight: 500;
    color: #475569;

    .spinning {
      animation: spin 1s linear infinite;
      color: #3b82f6;
    }
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.doc-preview-card {
  border: 1px solid #e2e8f0 !important;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;

  .preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: 600;
    color: #0f172a;
  }
}

.markdown-body {
  font-size: 15px;
  color: #334155;
  line-height: 1.7;

  :deep(h1) { font-size: 1.8em; margin: 32px 0 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; color: #0f172a; }
  :deep(h2) { font-size: 1.5em; margin: 28px 0 12px; color: #1e293b; font-weight: 600; }
  :deep(h3) { font-size: 1.25em; margin: 24px 0 10px; color: #0f172a; font-weight: 600; }
  :deep(p) { margin: 12px 0; }
  :deep(code) { background: #f1f5f9; padding: 3px 6px; border-radius: 6px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.9em; color: #db2777; }
  :deep(pre) { background: #1e293b; color: #f8fafc; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 16px 0; }
  :deep(pre code) { background: none; padding: 0; color: inherit; font-size: 14px; }
  :deep(table) { width: 100%; border-collapse: collapse; margin: 20px 0; }
  :deep(td), :deep(th) { border: 1px solid #e2e8f0; padding: 10px 14px; text-align: left; }
  :deep(th) { background: #f8fafc; font-weight: 600; color: #0f172a; }
  :deep(li) { margin: 6px 0; }
  :deep(ul), :deep(ol) { padding-left: 24px; margin: 12px 0; }
  :deep(hr) { border: none; border-top: 1px solid #e2e8f0; margin: 32px 0; }
  :deep(strong) { font-weight: 600; color: #0f172a; }
}

.subtasks-card {
  border: 1px solid #e2e8f0 !important;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;

  .error-text {
    color: #ef4444;
    font-size: 13px;
  }
}
</style>
