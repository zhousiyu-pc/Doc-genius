<template>
  <div class="pricing-container">
    <div class="pricing-header">
      <h1>选择适合你的套餐</h1>
      <p class="pricing-desc">根据需求选择，随时升级或降级</p>

      <div class="billing-toggle">
        <span :class="{ active: billing === 'monthly' }" @click="billing = 'monthly'">月付</span>
        <span :class="{ active: billing === 'quarterly' }" @click="billing = 'quarterly'">季付 <em>9折</em></span>
        <span :class="{ active: billing === 'yearly' }" @click="billing = 'yearly'">年付 <em>7折</em></span>
      </div>
    </div>

    <div v-if="loading" class="pricing-loading">
      <el-icon class="loading-spin"><Loading /></el-icon>
      <p>加载套餐中...</p>
    </div>

    <div v-else class="pricing-cards">
      <div
        v-for="plan in plans"
        :key="plan.id"
        class="plan-card"
        :class="{ current: currentPlanId === plan.id, popular: plan.id === 'pro' }"
      >
        <div v-if="plan.id === 'pro'" class="plan-badge">最受欢迎</div>
        <div class="plan-icon">{{ plan.icon || '📦' }}</div>
        <h2 class="plan-name">{{ plan.display_name }}</h2>

        <div class="plan-price">
          <template v-if="getPrice(plan) === 0">
            <span class="price-amount">免费</span>
          </template>
          <template v-else>
            <span class="price-currency">¥</span>
            <span class="price-amount">{{ getMonthlyPrice(plan) }}</span>
            <span class="price-period">/月</span>
          </template>
        </div>
        <div v-if="getPrice(plan) > 0 && billing !== 'monthly'" class="plan-total">
          合计 ¥{{ (getPrice(plan) / 100).toFixed(0) }}/{{ billingLabel }}
        </div>

        <ul class="plan-features">
          <li v-for="feat in parseFeatures(plan)" :key="feat">
            <el-icon><CircleCheckFilled /></el-icon>
            {{ feat }}
          </li>
        </ul>

        <el-button
          v-if="currentPlanId === plan.id"
          type="info"
          size="large"
          disabled
          class="plan-btn"
        >当前套餐</el-button>
        <el-button
          v-else-if="plan.id === 'free'"
          type="default"
          size="large"
          class="plan-btn"
          disabled
        >免费使用</el-button>
        <el-button
          v-else
          :type="plan.id === 'pro' ? 'primary' : 'default'"
          size="large"
          class="plan-btn"
          @click="handleSubscribe(plan)"
        >
          {{ currentPlanId === 'free' ? '立即订阅' : '升级套餐' }}
        </el-button>
      </div>
    </div>

    <!-- 当前用量 -->
    <div v-if="usage" class="usage-section">
      <h3>📊 当前用量</h3>
      <div class="usage-grid">
        <div class="usage-item">
          <span class="usage-label">今日对话</span>
          <el-progress
            :percentage="usagePercent(usage.chat_used, usage.chat_limit)"
            :color="progressColor(usage.chat_used, usage.chat_limit)"
          />
          <span class="usage-text">{{ usage.chat_used }} / {{ usage.chat_limit === -1 ? '∞' : usage.chat_limit }}</span>
        </div>
        <div class="usage-item">
          <span class="usage-label">本月文档</span>
          <el-progress
            :percentage="usagePercent(usage.doc_used, usage.doc_limit)"
            :color="progressColor(usage.doc_used, usage.doc_limit)"
          />
          <span class="usage-text">{{ usage.doc_used }} / {{ usage.doc_limit === -1 ? '∞' : usage.doc_limit }}</span>
        </div>
      </div>
    </div>

    <!-- 支付对话框 -->
    <el-dialog v-model="showPayDialog" title="订阅套餐" width="480px" :close-on-click-modal="false">
      <div v-if="selectedPlan" class="pay-dialog-body">
        <h3>{{ selectedPlan.display_name }}</h3>
        <p class="pay-amount">¥{{ (getPrice(selectedPlan) / 100).toFixed(2) }} / {{ billingLabel }}</p>
        <div class="pay-methods">
          <div
            class="pay-method"
            :class="{ active: payMethod === 'wechat' }"
            @click="payMethod = 'wechat'"
          >
            <span>💚 微信支付</span>
          </div>
          <div
            class="pay-method"
            :class="{ active: payMethod === 'alipay' }"
            @click="payMethod = 'alipay'"
          >
            <span>🔵 支付宝</span>
          </div>
        </div>
        <div class="pay-placeholder">
          <el-icon :size="48" color="#ddd"><CreditCard /></el-icon>
          <p>支付功能即将上线，敬请期待</p>
          <p class="pay-hint">商户号配置完成后即可启用</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="showPayDialog = false">取消</el-button>
        <el-button type="primary" disabled>确认支付</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Loading, CircleCheckFilled, CreditCard } from '@element-plus/icons-vue'
import axios from 'axios'

interface Plan {
  id: string
  name: string
  display_name: string
  icon?: string
  price_monthly: number
  price_quarterly: number
  price_yearly: number
  daily_chat_limit: number
  monthly_doc_limit: number
  max_file_size_mb: number
  max_versions: number
  allowed_models: string
  features: string
  sort_order: number
}

const loading = ref(true)
const plans = ref<Plan[]>([])
const currentPlanId = ref('free')
const billing = ref<'monthly' | 'quarterly' | 'yearly'>('monthly')
const showPayDialog = ref(false)
const selectedPlan = ref<Plan | null>(null)
const payMethod = ref<'wechat' | 'alipay'>('wechat')
const usage = ref<any>(null)

const billingLabel = computed(() => ({
  monthly: '月', quarterly: '季', yearly: '年'
}[billing.value]))

function getPrice(plan: Plan): number {
  return plan[`price_${billing.value}` as keyof Plan] as number || 0
}

function getMonthlyPrice(plan: Plan): string {
  const total = getPrice(plan)
  if (total === 0) return '0'
  const months = { monthly: 1, quarterly: 3, yearly: 12 }[billing.value]
  return (total / 100 / months).toFixed(0)
}

function parseFeatures(plan: Plan): string[] {
  try {
    return JSON.parse(plan.features || '[]')
  } catch { return [] }
}

function usagePercent(used: number, limit: number): number {
  if (limit <= 0) return 0
  return Math.min(100, Math.round((used / limit) * 100))
}

function progressColor(used: number, limit: number): string {
  if (limit <= 0) return '#67c23a'
  const pct = used / limit
  if (pct >= 0.9) return '#f56c6c'
  if (pct >= 0.7) return '#e6a23c'
  return '#409eff'
}

function handleSubscribe(plan: Plan) {
  selectedPlan.value = plan
  showPayDialog.value = true
}

async function loadPlans() {
  try {
    const { data } = await axios.get('/api/plans')
    if (data.success) {
      plans.value = data.plans
    }
  } catch { /* ignore */ }
}

async function loadUserPlan() {
  try {
    const { data } = await axios.get('/api/user/plan')
    if (data.success) {
      currentPlanId.value = data.plan?.id || 'free'
      // 把后端格式转换成前端需要的格式
      if (data.usage && data.plan) {
        usage.value = {
          chat_used: data.usage.today?.chat_count || 0,
          chat_limit: data.plan.daily_chat_limit,
          doc_used: data.usage.month?.doc_count || 0,
          doc_limit: data.plan.monthly_doc_limit,
        }
      }
    }
  } catch { /* anonymous */ }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([loadPlans(), loadUserPlan()])
  loading.value = false
})
</script>

<style scoped>
.pricing-container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 24px 60px;
}

.pricing-header {
  text-align: center;
  margin-bottom: 40px;
}

.pricing-header h1 {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.pricing-desc {
  font-size: 16px;
  color: var(--text-muted);
  margin: 0 0 24px;
}

.billing-toggle {
  display: inline-flex;
  gap: 4px;
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 4px;
  border: 1px solid var(--border-primary);
}

.billing-toggle span {
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.billing-toggle span.active {
  background: #409eff;
  color: #fff;
}

.billing-toggle em {
  font-style: normal;
  font-size: 11px;
  color: #67c23a;
  margin-left: 2px;
}

.billing-toggle span.active em {
  color: #a0f0a0;
}

.pricing-loading {
  text-align: center;
  padding: 60px;
}

.loading-spin {
  font-size: 32px;
  color: #409eff;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.pricing-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 40px;
}

.plan-card {
  position: relative;
  background: var(--bg-secondary);
  border: 2px solid var(--border-primary);
  border-radius: 16px;
  padding: 28px 20px;
  text-align: center;
  transition: all 0.2s;
}

.plan-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.plan-card.popular {
  border-color: #409eff;
}

.plan-card.current {
  border-color: #67c23a;
}

.plan-badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: #409eff;
  color: #fff;
  font-size: 12px;
  padding: 2px 16px;
  border-radius: 12px;
}

.plan-icon {
  font-size: 36px;
  margin-bottom: 8px;
}

.plan-name {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
}

.plan-price {
  margin-bottom: 4px;
}

.price-currency {
  font-size: 18px;
  color: var(--text-primary);
  vertical-align: top;
  line-height: 1.8;
}

.price-amount {
  font-size: 40px;
  font-weight: 700;
  color: var(--text-primary);
}

.price-period {
  font-size: 14px;
  color: var(--text-muted);
}

.plan-total {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.plan-features {
  list-style: none;
  padding: 0;
  margin: 20px 0;
  text-align: left;
}

.plan-features li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.plan-features li .el-icon {
  color: #67c23a;
  flex-shrink: 0;
}

.plan-btn {
  width: 100%;
}

.usage-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: 12px;
  padding: 24px;
}

.usage-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
  color: var(--text-primary);
}

.usage-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.usage-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.usage-label {
  font-size: 13px;
  color: var(--text-muted);
}

.usage-text {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: right;
}

.pay-dialog-body {
  text-align: center;
}

.pay-dialog-body h3 {
  margin: 0 0 8px;
}

.pay-amount {
  font-size: 24px;
  font-weight: 700;
  color: #409eff;
  margin-bottom: 20px;
}

.pay-methods {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 24px;
}

.pay-method {
  padding: 12px 24px;
  border: 2px solid var(--border-primary);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.pay-method.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.pay-placeholder {
  padding: 24px;
  color: var(--text-muted);
}

.pay-hint {
  font-size: 12px;
  margin-top: 8px;
}

@media (max-width: 768px) {
  .pricing-cards {
    grid-template-columns: 1fr;
  }
  .usage-grid {
    grid-template-columns: 1fr;
  }
  .pricing-header h1 {
    font-size: 24px;
  }
}
</style>
