<template>
  <div class="pricing-container">
    <div class="pricing-header">
      <h1>升级你的套餐</h1>
      <p class="pricing-desc">根据需求选择，随时升级或降级</p>

      <!-- GPT-style pill toggle -->
      <div class="billing-toggle">
        <button
          :class="{ active: billing === 'monthly' }"
          @click="billing = 'monthly'"
        >月付</button>
        <button
          :class="{ active: billing === 'quarterly' }"
          @click="billing = 'quarterly'"
        >季付 <em>省10%</em></button>
        <button
          :class="{ active: billing === 'yearly' }"
          @click="billing = 'yearly'"
        >年付 <em>省30%</em></button>
      </div>
    </div>

    <div v-if="loading" class="pricing-loading">
      <span class="loading-spinner"></span>
      <p>加载套餐中...</p>
    </div>

    <div v-else class="pricing-cards">
      <div
        v-for="plan in plans"
        :key="plan.id"
        class="plan-card"
        :class="{
          'plan-card--current': currentPlanId === plan.id,
          'plan-card--recommended': plan.id === 'pro'
        }"
      >
        <div v-if="plan.id === 'pro'" class="plan-badge">推荐</div>
        <div v-if="currentPlanId === plan.id" class="plan-badge plan-badge--current">当前</div>

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
            <span class="check-icon">✓</span>
            <span>{{ feat }}</span>
          </li>
        </ul>

        <button
          v-if="currentPlanId === plan.id"
          class="plan-btn plan-btn--current"
          disabled
        >当前套餐</button>
        <button
          v-else-if="plan.id === 'free'"
          class="plan-btn plan-btn--outline"
          disabled
        >免费使用</button>
        <button
          v-else
          class="plan-btn"
          :class="plan.id === 'pro' ? 'plan-btn--primary' : 'plan-btn--outline'"
          @click="handleSubscribe(plan)"
        >
          {{ currentPlanId === 'free' ? '立即订阅' : '升级套餐' }}
        </button>
      </div>
    </div>

    <!-- Usage section - simplified, below cards -->
    <div v-if="usage" class="usage-section">
      <div class="usage-title">当前用量</div>
      <div class="usage-grid">
        <div class="usage-item">
          <div class="usage-item-header">
            <span class="usage-label">今日对话</span>
            <span class="usage-text">{{ usage.chat_used }} / {{ usage.chat_limit === -1 ? '∞' : usage.chat_limit }}</span>
          </div>
          <div class="usage-bar">
            <div
              class="usage-bar-fill"
              :style="{ width: usagePercent(usage.chat_used, usage.chat_limit) + '%' }"
              :class="usageBarClass(usage.chat_used, usage.chat_limit)"
            ></div>
          </div>
        </div>
        <div class="usage-item">
          <div class="usage-item-header">
            <span class="usage-label">本月文档</span>
            <span class="usage-text">{{ usage.doc_used }} / {{ usage.doc_limit === -1 ? '∞' : usage.doc_limit }}</span>
          </div>
          <div class="usage-bar">
            <div
              class="usage-bar-fill"
              :style="{ width: usagePercent(usage.doc_used, usage.doc_limit) + '%' }"
              :class="usageBarClass(usage.doc_used, usage.doc_limit)"
            ></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pay dialog - clean and minimal -->
    <el-dialog v-model="showPayDialog" width="440px" :close-on-click-modal="false" :show-close="true" class="pay-dialog">
      <div v-if="selectedPlan" class="pay-dialog-body">
        <h3 class="pay-title">订阅 {{ selectedPlan.display_name }}</h3>
        <p class="pay-amount">¥{{ (getPrice(selectedPlan) / 100).toFixed(2) }}<span class="pay-period"> / {{ billingLabel }}</span></p>

        <div class="pay-methods">
          <button
            class="pay-method"
            :class="{ active: payMethod === 'wechat' }"
            @click="payMethod = 'wechat'"
          >
            💚 微信支付
          </button>
          <button
            class="pay-method"
            :class="{ active: payMethod === 'alipay' }"
            @click="payMethod = 'alipay'"
          >
            🔵 支付宝
          </button>
        </div>

        <div class="pay-placeholder">
          <p>支付功能即将上线，敬请期待</p>
          <p class="pay-hint">商户号配置完成后即可启用</p>
        </div>

        <div class="pay-actions">
          <button class="pay-btn pay-btn--cancel" @click="showPayDialog = false">取消</button>
          <button class="pay-btn pay-btn--confirm" disabled>确认支付</button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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

function usageBarClass(used: number, limit: number): string {
  if (limit <= 0) return 'bar-normal'
  const pct = used / limit
  if (pct >= 0.9) return 'bar-danger'
  if (pct >= 0.7) return 'bar-warning'
  return 'bar-normal'
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
  padding: 48px 24px 64px;
}

.pricing-header {
  text-align: center;
  margin-bottom: 48px;
}

.pricing-header h1 {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}

.pricing-desc {
  font-size: 16px;
  color: var(--text-muted);
  margin: 0 0 28px;
}

/* GPT-style pill toggle */
.billing-toggle {
  display: inline-flex;
  background: var(--bg-secondary);
  border-radius: 9999px;
  padding: 4px;
  border: 1px solid var(--border-primary);
}

.billing-toggle button {
  padding: 8px 20px;
  border-radius: 9999px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all 0.2s ease;
  white-space: nowrap;
}

.billing-toggle button.active {
  background: #10a37f;
  color: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.billing-toggle em {
  font-style: normal;
  font-size: 11px;
  opacity: 0.8;
  margin-left: 4px;
}

.billing-toggle button.active em {
  opacity: 1;
}

/* Loading */
.pricing-loading {
  text-align: center;
  padding: 60px;
  color: var(--text-muted);
}

.loading-spinner {
  display: inline-block;
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-primary);
  border-top-color: #10a37f;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Cards grid */
.pricing-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

.plan-card {
  position: relative;
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: 16px;
  padding: 32px 24px 24px;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s ease;
}

.plan-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.plan-card--recommended {
  border: 2px solid #10a37f;
}

.plan-card--current {
  border-color: var(--text-muted);
}

/* Badge */
.plan-badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: #10a37f;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 16px;
  border-radius: 9999px;
  white-space: nowrap;
}

.plan-badge--current {
  background: var(--text-muted);
}

.plan-name {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
}

/* Price */
.plan-price {
  margin-bottom: 4px;
  display: flex;
  align-items: baseline;
}

.price-currency {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.price-amount {
  font-size: 48px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.price-period {
  font-size: 14px;
  color: var(--text-muted);
  margin-left: 2px;
}

.plan-total {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

/* Features */
.plan-features {
  list-style: none;
  padding: 0;
  margin: 20px 0 24px;
  flex: 1;
}

.plan-features li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 5px 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.check-icon {
  color: #10a37f;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 2px;
}

/* Plan buttons */
.plan-btn {
  width: 100%;
  height: 48px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  border: none;
  margin-top: auto;
}

.plan-btn--primary {
  background: #10a37f;
  color: #fff;
}

.plan-btn--primary:hover {
  background: #0d8c6d;
}

.plan-btn--outline {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--border-primary);
}

.plan-btn--outline:hover:not(:disabled) {
  background: var(--bg-hover, var(--bg-secondary));
  border-color: var(--text-muted);
}

.plan-btn--current {
  background: var(--bg-primary);
  color: var(--text-muted);
  border: 1px solid var(--border-primary);
  cursor: default;
}

.plan-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Usage section */
.usage-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: 12px;
  padding: 20px 24px;
}

.usage-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 16px;
}

.usage-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.usage-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.usage-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.usage-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.usage-text {
  font-size: 13px;
  color: var(--text-muted);
}

.usage-bar {
  height: 6px;
  background: var(--border-primary);
  border-radius: 3px;
  overflow: hidden;
}

.usage-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.bar-normal { background: #10a37f; }
.bar-warning { background: #f59e0b; }
.bar-danger { background: #ef4444; }

/* Pay dialog */
.pay-dialog-body {
  text-align: center;
  padding: 8px 0;
}

.pay-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.pay-amount {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 24px;
}

.pay-period {
  font-size: 16px;
  font-weight: 400;
  color: var(--text-muted);
}

.pay-methods {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 24px;
}

.pay-method {
  padding: 12px 24px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-primary);
  font-size: 14px;
  color: var(--text-secondary);
}

.pay-method.active {
  border-color: #10a37f;
  color: #10a37f;
}

.pay-placeholder {
  padding: 20px;
  color: var(--text-muted);
  font-size: 14px;
}

.pay-hint {
  font-size: 12px;
  margin-top: 4px;
  color: var(--text-muted);
}

.pay-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 16px;
}

.pay-btn {
  padding: 10px 32px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
}

.pay-btn--cancel {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border-primary);
}

.pay-btn--cancel:hover {
  background: var(--bg-secondary);
}

.pay-btn--confirm {
  background: #10a37f;
  color: #fff;
}

.pay-btn--confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .pricing-cards {
    grid-template-columns: 1fr;
  }
  .usage-grid {
    grid-template-columns: 1fr;
  }
  .pricing-header h1 {
    font-size: 28px;
  }
  .billing-toggle button {
    padding: 6px 14px;
    font-size: 13px;
  }
}
</style>
