<template>
  <div class="admin-container">
    <div class="admin-header">
      <h1>管理后台</h1>
      <el-button @click="$router.push('/')">返回首页</el-button>
    </div>

    <el-tabs v-model="activeTab">
      <!-- 数据概览 -->
      <el-tab-pane label="📊 数据概览" name="overview">
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_users }}</div>
            <div class="stat-label">总用户数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_sessions }}</div>
            <div class="stat-label">总会话数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_messages }}</div>
            <div class="stat-label">总消息数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.active_subscriptions }}</div>
            <div class="stat-label">付费用户</div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="👥 用户管理" name="users">
        <el-table :data="users" stripe style="width: 100%">
          <el-table-column prop="id" label="ID" width="140" />
          <el-table-column prop="username" label="用户名" width="160" />
          <el-table-column prop="plan_name" label="套餐" width="120">
            <template #default="{ row }">
              <el-tag :type="planTagType(row.plan_name)" size="small">{{ row.plan_name || '免费版' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="session_count" label="会话数" width="100" />
          <el-table-column prop="created_at" label="注册时间" width="180">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link size="small" type="primary" @click="viewUserDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 套餐管理 -->
      <el-tab-pane label="💰 套餐管理" name="plans">
        <el-table :data="planList" stripe style="width: 100%">
          <el-table-column prop="display_name" label="套餐名" width="140" />
          <el-table-column label="月价" width="100">
            <template #default="{ row }">¥{{ (row.price_monthly / 100).toFixed(0) }}</template>
          </el-table-column>
          <el-table-column label="对话/天" width="100">
            <template #default="{ row }">{{ row.daily_chat_limit === -1 ? '无限' : row.daily_chat_limit }}</template>
          </el-table-column>
          <el-table-column label="文档/月" width="100">
            <template #default="{ row }">{{ row.monthly_doc_limit === -1 ? '无限' : row.monthly_doc_limit }}</template>
          </el-table-column>
          <el-table-column label="订阅人数" width="100" prop="subscriber_count" />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 用户详情对话框 -->
    <el-dialog v-model="showUserDetail" :title="`用户详情 - ${userDetail?.username}`" width="520px">
      <div v-if="userDetail" class="user-detail">
        <div class="detail-row"><span>用户 ID：</span><code>{{ userDetail.id }}</code></div>
        <div class="detail-row"><span>用户名：</span>{{ userDetail.username }}</div>
        <div class="detail-row"><span>当前套餐：</span><el-tag size="small">{{ userDetail.plan_name || '免费版' }}</el-tag></div>
        <div class="detail-row"><span>今日对话：</span>{{ userDetail.today_chat || 0 }} 次</div>
        <div class="detail-row"><span>本月文档：</span>{{ userDetail.month_doc || 0 }} 次</div>
        <div class="detail-row"><span>会话总数：</span>{{ userDetail.session_count }} 个</div>
        <div class="detail-row"><span>注册时间：</span>{{ formatDate(userDetail.created_at) }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('overview')
const stats = ref({ total_users: 0, total_sessions: 0, total_messages: 0, active_subscriptions: 0 })
const users = ref<any[]>([])
const planList = ref<any[]>([])
const showUserDetail = ref(false)
const userDetail = ref<any>(null)

function formatDate(d: string): string {
  try { return new Date(d).toLocaleString('zh-CN') } catch { return d }
}

function planTagType(name: string): string {
  if (!name || name === '免费版') return 'info'
  if (name === '专业版') return ''
  if (name === '团队版') return 'warning'
  if (name === '企业版') return 'danger'
  return 'info'
}

function viewUserDetail(row: any) {
  userDetail.value = row
  showUserDetail.value = true
}

async function loadStats() {
  try {
    const { data } = await axios.get('/api/admin/stats')
    if (data.success) stats.value = data.stats
  } catch { /* ignore */ }
}

async function loadUsers() {
  try {
    const { data } = await axios.get('/api/admin/users')
    if (data.success) users.value = data.users
  } catch { /* ignore */ }
}

async function loadPlans() {
  try {
    const { data } = await axios.get('/api/plans')
    if (data.success) planList.value = data.plans
  } catch { /* ignore */ }
}

onMounted(() => {
  loadStats()
  loadUsers()
  loadPlans()
})
</script>

<style scoped>
.admin-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px 24px;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.admin-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.stat-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: 12px;
  padding: 24px;
  text-align: center;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: #409eff;
}

.stat-label {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 4px;
}

.user-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-row {
  display: flex;
  gap: 8px;
  font-size: 14px;
}

.detail-row span:first-child {
  color: var(--text-muted);
  min-width: 80px;
}

.detail-row code {
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
