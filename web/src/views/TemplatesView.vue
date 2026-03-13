<template>
  <div class="templates-container">
    <div class="templates-header">
      <el-button :icon="ArrowLeft" @click="router.push('/')">返回首页</el-button>
      <h2 class="templates-title">文档模板</h2>
    </div>

    <div class="templates-grid">
      <el-card
        v-for="tpl in templates"
        :key="tpl.id"
        class="tpl-card"
        shadow="hover"
        @click="useTemplate(tpl)"
      >
        <div class="tpl-icon">{{ tpl.icon }}</div>
        <div class="tpl-name">{{ tpl.name }}</div>
        <div class="tpl-desc">{{ tpl.description }}</div>
        <el-button type="primary" size="small" class="tpl-btn">使用此模板</el-button>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'

const router = useRouter()

const templates = [
  { id: 'erp', icon: '📊', name: 'ERP 系统', description: '企业资源计划，包含采购、销售、库存、财务' },
  { id: 'crm', icon: '💼', name: 'CRM 系统', description: '客户关系管理，线索、商机、客户管理' },
  { id: 'ecommerce', icon: '🛒', name: '电商平台', description: '多商家商城，商品、订单、支付、物流' },
  { id: 'oa', icon: '🏢', name: 'OA 办公', description: '办公自动化，审批、考勤、请假、报销' },
  { id: 'bi', icon: '📈', name: 'BI 分析', description: '数据分析看板，可视化报表、数据钻取' },
  { id: 'app', icon: '📱', name: '移动 App', description: 'iOS/Android 应用，用户中心、核心功能' },
  { id: 'insurance', icon: '🛡️', name: '保险系统', description: '保单、理赔、核保、精算、代理人' },
  { id: 'education', icon: '🎓', name: '教育培训', description: '课程、学员、教师、排课、考试' },
]

function useTemplate(tpl: { id: string; name: string; description: string }) {
  router.push({
    path: '/',
    query: { template: tpl.id, desc: `我想做一个${tpl.name}，${tpl.description}` },
  })
}
</script>

<style scoped lang="scss">
.templates-container {
  min-height: 100vh;
  padding: 40px 20px;
  max-width: 1000px;
  margin: 0 auto;
}

.templates-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 32px;

  .templates-title {
    color: #0f172a;
    font-size: 28px;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
  }
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 20px;
}

.tpl-card {
  cursor: pointer;
  text-align: center;
  padding: 24px 16px;
  transition: all 0.2s ease;
  background: #ffffff;
  border: 1px solid #e2e8f0 !important;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
  border-radius: 16px;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025) !important;
    border-color: #cbd5e1 !important;
  }

  .tpl-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }

  .tpl-name {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
    color: #0f172a;
  }

  .tpl-desc {
    font-size: 14px;
    color: #64748b;
    margin-bottom: 24px;
    line-height: 1.5;
  }

  .tpl-btn {
    width: 100%;
    font-weight: 500;
  }
}
</style>
