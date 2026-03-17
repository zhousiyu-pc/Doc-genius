<template>
  <div class="home-container">
    <div class="home-content">
      <!-- 标题区域 -->
      <div class="header">
        <h1 class="title">📝 AI 需求与详设生成器</h1>
        <p class="subtitle">一键生成结构化的需求文档与详细设计文档</p>
      </div>

      <!-- 输入区域 -->
      <div class="input-section">
        <el-card class="input-card">
          <template #header>
            <span class="card-title">你想创建什么文档？</span>
          </template>

          <el-input
            v-model="requirement"
            type="textarea"
            :rows="5"
            placeholder="例如：我想做一个 CRM 系统，管理客户信息、销售跟进、合同管理..."
            @keydown.ctrl.enter="handleSubmit"
          />

          <div class="input-actions">
            <el-button type="primary" size="large" :loading="generating" @click="handleSubmit">
              ✨ 开始生成
            </el-button>
            <el-button size="large" @click="handleVoiceInput">
              🎤 语音输入
            </el-button>
          </div>

          <!-- 快捷示例 -->
          <div class="quick-examples">
            <span class="examples-label">试试这些：</span>
            <el-tag
              v-for="example in examples"
              :key="example"
              class="example-tag"
              effect="plain"
              @click="selectExample(example)"
            >
              {{ example }}
            </el-tag>
          </div>
        </el-card>
      </div>

      <!-- 模板选择 -->
      <div class="templates-section">
        <h2 class="section-title">或选择模板</h2>
        <div class="templates-grid">
          <el-card
            v-for="template in templates"
            :key="template.id"
            class="template-card"
            shadow="hover"
            @click="selectTemplate(template)"
          >
            <div class="template-icon">{{ template.icon }}</div>
            <div class="template-name">{{ template.name }}</div>
            <div class="template-desc">{{ template.description }}</div>
          </el-card>
        </div>
      </div>

      <!-- 最近文档 -->
      <div class="recent-section" v-if="recentDocuments.length > 0">
        <h2 class="section-title">最近生成的文档</h2>
        <el-card class="document-card" v-for="doc in recentDocuments" :key="doc.id">
          <div class="document-info">
            <span class="document-icon">📄</span>
            <div class="document-details">
              <div class="document-title">{{ doc.title }}</div>
              <div class="document-meta">
                <span>{{ doc.domain }}</span>
                <span>•</span>
                <span>{{ doc.date }}</span>
              </div>
            </div>
          </div>
          <div class="document-actions">
            <el-button size="small" @click="viewDocument(doc.id)">查看</el-button>
            <el-button size="small" type="primary" @click="downloadDocument(doc.id)">下载</el-button>
          </div>
        </el-card>
      </div>

      <!-- 需求大纲预览弹窗 -->
      <el-dialog
        v-model="showOutline"
        title="需求大纲预览"
        width="720px"
      >
        <div v-if="analysis">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="领域">{{ analysis.domain_name }}</el-descriptions-item>
            <el-descriptions-item label="复杂度">{{ analysis.complexity }}</el-descriptions-item>
            <el-descriptions-item label="核心模块" :span="2">
              <el-tag
                v-for="m in analysis.core_modules"
                :key="m"
                class="mr-6"
                effect="plain"
              >
                {{ m }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <el-divider>功能点列表（大纲）</el-divider>
          <el-table
            :data="analysis.feature_list.map((f, idx) => ({ index: idx + 1, name: f }))"
            size="small"
            height="260"
          >
            <el-table-column prop="index" label="#" width="60" />
            <el-table-column prop="name" label="功能点" />
          </el-table>
        </div>

        <template #footer>
          <el-button @click="showOutline = false">返回修改</el-button>
          <el-button type="primary" @click="confirmGenerate">生成详细文档</el-button>
        </template>
      </el-dialog>

      <!-- 生成进度弹窗 -->
      <el-dialog
        v-model="showProgress"
        title="正在生成文档..."
        width="600px"
        :close-on-click-modal="false"
        :show-close="false"
      >
        <div class="progress-content">
          <el-progress
            :percentage="progress"
            :status="progress >= 100 ? 'success' : undefined"
            :stroke-width="20"
          />

          <div class="progress-details" v-if="currentTask">
            <div class="progress-stats">
              <el-statistic title="已完成" :value="currentTask.completed_count" />
              <el-statistic title="总数" :value="currentTask.total_count" />
              <el-statistic title="失败" :value="currentTask.failed_count" />
            </div>

            <el-divider />

            <div class="feature-status">
              <h4>✅ 已完成</h4>
              <ul class="feature-list">
                <li v-for="i in currentTask.completed_count" :key="i" class="feature-item">
                  功能点 {{ i }}
                </li>
              </ul>
            </div>
          </div>

          <div class="progress-tips">
            <el-alert
              title="💡 生成过程中可以随时关闭，下次访问时会继续"
              type="info"
              :closable="false"
              show-icon
            />
          </div>
        </div>

        <template #footer>
          <el-button @click="hideProgress">收起并后台运行</el-button>
          <el-button type="danger" @click="cancelGeneration" v-if="currentTask">
            取消生成
          </el-button>
          <el-button type="primary" @click="viewDocument(currentTask.task_id)" v-if="currentTask">
            查看详情
          </el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { useTaskStore } from '@/stores/task'

const router = useRouter()
const taskStore = useTaskStore()

const requirement = ref('')
const generating = computed(() => taskStore.generating)
const progress = computed(() => taskStore.progress)
const currentTask = computed(() => taskStore.currentTask)
const analysis = computed(() => taskStore.analysis)
const showProgress = ref(false)
const showOutline = ref(false)

const examples = [
  'CRM 系统，管理客户和销售',
  '电商平台，支持多商家入驻',
  '保险系统，包含保单和理赔管理',
  '教育培训平台，在线课程和考试',
]

const templates = [
  { id: 'erp', icon: '📊', name: 'ERP 系统', description: '企业资源计划，包含采购、销售、库存、财务' },
  { id: 'crm', icon: '💼', name: 'CRM 系统', description: '客户关系管理，线索、商机、客户管理' },
  { id: 'ecommerce', icon: '🛒', name: '电商平台', description: '多商家商城，商品、订单、支付、物流' },
  { id: 'oa', icon: '🏢', name: 'OA 办公', description: '办公自动化，审批、考勤、请假、报销' },
  { id: 'bi', icon: '📈', name: 'BI 分析', description: '数据分析看板，可视化报表、数据钻取' },
  { id: 'app', icon: '📱', name: '移动 App', description: 'iOS/Android应用，用户中心、核心功能' },
  { id: 'insurance', icon: '🛡️', name: '保险系统', description: '保单、理赔、核保、精算、代理人' },
  { id: 'education', icon: '🎓', name: '教育培训', description: '课程、学员、教师、排课、考试' },
]

const recentDocuments = ref([
  { id: '1', title: '跨境电商 ERP 需求文档', domain: 'ERP', date: '2026-03-11' },
  { id: '2', title: '健身 App 需求规格书', domain: 'App', date: '2026-03-10' },
])

const handleSubmit = async () => {
  if (!requirement.value.trim()) {
    return
  }

  // 第一步：仅生成需求大纲
  const result = await taskStore.analyze(requirement.value)
  if (result.success) {
    showOutline.value = true
  } else if (result.message) {
    ElMessage.error(result.message)
  }
}

const confirmGenerate = async () => {
  if (!requirement.value.trim()) return

  try {
    await ElMessageBox.confirm(
      '将基于当前需求大纲，为每个功能点生成详细的需求与设计文档。是否继续？',
      '确认生成详细文档',
      {
        type: 'warning',
        confirmButtonText: '开始生成',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }

  const result = await taskStore.createTask(requirement.value)
  if (result.success) {
    showOutline.value = false
    showProgress.value = true
  } else if (result.message) {
    ElMessage.error(result.message)
  }
}

const handleVoiceInput = () => {
  // TODO: 实现语音输入
  alert('语音输入功能开发中...')
}

const selectExample = (example: string) => {
  requirement.value = example
}

const selectTemplate = (template: any) => {
  requirement.value = `我想做一个${template.name}，${template.description}`
}

const viewDocument = (_id: string) => {
  router.push(`/document/${_id}`)
}

const downloadDocument = (_id: string) => {
  // TODO: 实现下载
  alert('下载功能开发中...')
}

const hideProgress = () => {
  // 不再重置 store，仅隐藏弹窗
  showProgress.value = false
  ElMessage.success('已转入后台运行，可在右下角进度条或“我的文档”中查看')
}

const cancelGeneration = async () => {
  if (!currentTask.value) return
  try {
    await ElMessageBox.confirm(
      '取消后，系统将不再继续为该任务生成后续文档。已生成的部分会保留。',
      '确认取消生成',
      {
        type: 'warning',
        confirmButtonText: '确认取消',
        cancelButtonText: '继续生成',
      },
    )
  } catch {
    return
  }

  try {
    await axios.post(`/api/tasks/${currentTask.value.task_id}/cancel`)
    taskStore.reset()
    showProgress.value = false
    ElMessage.success('已取消生成')
  } catch (e) {
    console.error('取消任务失败:', e)
    ElMessage.error('取消失败，请稍后重试')
  }
}
</script>

<style scoped lang="scss">
.home-container {
  min-height: 100vh;
  padding: 60px 20px;
  background-color: transparent;
}

.home-content {
  max-width: 800px;
  margin: 0 auto;
}

.header {
  text-align: center;
  margin-bottom: 48px;

  .title {
    font-size: 40px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 12px;
    letter-spacing: -0.02em;
  }

  .subtitle {
    font-size: 18px;
    color: #64748b;
    font-weight: 400;
  }
}

.input-section {
  margin-bottom: 48px;

  .input-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 10px;
  }

  .card-title {
    font-size: 16px;
    font-weight: 600;
    color: #1e293b;
  }

  .input-actions {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }

  .quick-examples {
    margin-top: 24px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;

    .examples-label {
      font-size: 13px;
      color: #94a3b8;
      margin-right: 4px;
    }

    .example-tag {
      cursor: pointer;
      background-color: #f1f5f9;
      border: none;
      color: #475569;
      border-radius: 6px;
      padding: 0 12px;
      height: 28px;
      line-height: 28px;
      transition: all 0.2s ease;

      &:hover {
        background-color: #e2e8f0;
        color: #0f172a;
        transform: translateY(-1px);
      }
    }
  }
}

.templates-section {
  margin-bottom: 48px;

  .section-title {
    font-size: 18px;
    font-weight: 600;
    color: #334155;
    margin-bottom: 20px;
    text-align: left;
  }

  .templates-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 16px;
  }

  .template-card {
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
    padding: 20px 16px;
    background: #ffffff;
    border: 1px solid #e2e8f0 !important;
    box-shadow: none !important;

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025) !important;
      border-color: #cbd5e1 !important;
    }

    .template-icon {
      font-size: 32px;
      margin-bottom: 16px;
    }

    .template-name {
      font-size: 16px;
      font-weight: 600;
      color: #0f172a;
      margin-bottom: 6px;
    }

    .template-desc {
      font-size: 13px;
      color: #64748b;
      line-height: 1.5;
    }
  }
}

.recent-section {
  .section-title {
    font-size: 18px;
    font-weight: 600;
    color: #334155;
    margin-bottom: 20px;
    text-align: left;
  }

  .document-card {
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #ffffff;
    border: 1px solid #e2e8f0 !important;
    box-shadow: none !important;
    transition: all 0.2s;

    &:hover {
      border-color: #cbd5e1 !important;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
    }

    .document-info {
      display: flex;
      align-items: center;
      gap: 16px;

      .document-icon {
        font-size: 24px;
      }

      .document-details {
        .document-title {
          font-size: 15px;
          font-weight: 500;
          color: #0f172a;
          margin-bottom: 4px;
        }

        .document-meta {
          font-size: 13px;
          color: #64748b;
          display: flex;
          gap: 8px;
        }
      }
    }

    .document-actions {
      display: flex;
      gap: 8px;
    }
  }
}

.progress-content {
  .progress-details {
    margin-top: 30px;
  }

  .progress-stats {
    display: flex;
    justify-content: space-around;
  }

  .feature-status {
    h4 {
      margin-bottom: 10px;
      color: #10b981;
      font-weight: 600;
    }

    .feature-list {
      list-style: none;
      max-height: 200px;
      overflow-y: auto;

      .feature-item {
        padding: 6px 0;
        font-size: 14px;
        color: #475569;
        border-bottom: 1px solid #f1f5f9;
        
        &:last-child {
          border-bottom: none;
        }
      }
    }
  }

  .progress-tips {
    margin-top: 24px;
  }
}
</style>
