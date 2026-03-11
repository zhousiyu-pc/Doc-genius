<template>
  <div class="home-container">
    <div class="home-content">
      <!-- 标题区域 -->
      <div class="header">
        <h1 class="title">📝 智能文档生成器</h1>
        <p class="subtitle">让文档生成像聊天一样简单</p>
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
            <el-button @click="handleVoiceInput">
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
          <el-button @click="cancelGeneration">取消生成</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'

const router = useRouter()
const taskStore = useTaskStore()

const requirement = ref('')
const generating = computed(() => taskStore.generating)
const progress = computed(() => taskStore.progress)
const currentTask = computed(() => taskStore.currentTask)
const showProgress = ref(false)

const examples = [
  'CRM 系统，管理客户和销售',
  '电商平台，支持多商家入驻',
  'OA 办公系统，包含审批和考勤',
  '数据看板，展示销售和库存',
]

const templates = [
  { id: 'erp', icon: '📊', name: 'ERP 系统', description: '企业资源计划，包含采购、销售、库存、财务' },
  { id: 'crm', icon: '💼', name: 'CRM 系统', description: '客户关系管理，线索、商机、客户管理' },
  { id: 'ecommerce', icon: '🛒', name: '电商平台', description: '多商家商城，商品、订单、支付、物流' },
  { id: 'oa', icon: '🏢', name: 'OA 办公', description: '办公自动化，审批、考勤、请假、报销' },
  { id: 'bi', icon: '📈', name: 'BI 分析', description: '数据分析看板，可视化报表、数据钻取' },
  { id: 'app', icon: '📱', name: '移动 App', description: 'iOS/Android应用，用户中心、核心功能' },
]

const recentDocuments = ref([
  { id: '1', title: '跨境电商 ERP 需求文档', domain: 'ERP', date: '2026-03-11' },
  { id: '2', title: '健身 App 需求规格书', domain: 'App', date: '2026-03-10' },
])

const handleSubmit = async () => {
  if (!requirement.value.trim()) {
    return
  }

  const result = await taskStore.createTask(requirement.value)
  if (result.success) {
    showProgress.value = true
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

const viewDocument = (id: string) => {
  router.push(`/document/${id}`)
}

const downloadDocument = (id: string) => {
  // TODO: 实现下载
  alert('下载功能开发中...')
}

const cancelGeneration = () => {
  taskStore.reset()
  showProgress.value = false
}
</script>

<style scoped lang="scss">
.home-container {
  min-height: 100vh;
  padding: 40px 20px;
}

.home-content {
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  text-align: center;
  margin-bottom: 40px;

  .title {
    font-size: 48px;
    color: white;
    margin-bottom: 10px;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
  }

  .subtitle {
    font-size: 20px;
    color: rgba(255, 255, 255, 0.9);
  }
}

.input-section {
  margin-bottom: 40px;

  .input-card {
    backdrop-filter: blur(10px);
    background: rgba(255, 255, 255, 0.95);
  }

  .card-title {
    font-size: 18px;
    font-weight: 600;
  }

  .input-actions {
    margin-top: 20px;
    display: flex;
    gap: 10px;
  }

  .quick-examples {
    margin-top: 20px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;

    .examples-label {
      font-size: 14px;
      color: #666;
    }

    .example-tag {
      cursor: pointer;
      transition: all 0.3s;

      &:hover {
        transform: translateY(-2px);
      }
    }
  }
}

.templates-section {
  margin-bottom: 40px;

  .section-title {
    font-size: 24px;
    color: white;
    margin-bottom: 20px;
    text-align: center;
  }

  .templates-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 20px;
  }

  .template-card {
    cursor: pointer;
    transition: all 0.3s;
    text-align: center;
    padding: 20px 10px;

    &:hover {
      transform: translateY(-5px);
    }

    .template-icon {
      font-size: 48px;
      margin-bottom: 10px;
    }

    .template-name {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 5px;
    }

    .template-desc {
      font-size: 13px;
      color: #666;
    }
  }
}

.recent-section {
  .section-title {
    font-size: 24px;
    color: white;
    margin-bottom: 20px;
    text-align: center;
  }

  .document-card {
    margin-bottom: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .document-info {
      display: flex;
      align-items: center;
      gap: 15px;

      .document-icon {
        font-size: 32px;
      }

      .document-details {
        .document-title {
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 5px;
        }

        .document-meta {
          font-size: 13px;
          color: #666;
          display: flex;
          gap: 8px;
        }
      }
    }

    .document-actions {
      display: flex;
      gap: 10px;
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
      color: #67c23a;
    }

    .feature-list {
      list-style: none;
      max-height: 200px;
      overflow-y: auto;

      .feature-item {
        padding: 5px 0;
        font-size: 14px;
        color: #666;
      }
    }
  }

  .progress-tips {
    margin-top: 20px;
  }
}
</style>
