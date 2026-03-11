# 智能文档生成器

> 让文档生成像聊天一样简单！

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://docker.com)

---

## 🎯 产品定位

**通用型智能文档生成平台**

- 🌐 **多领域支持** - ERP、CRM、电商、OA、BI、App 等任意系统
- 📱 **多端访问** - Web 端 + 移动端（iOS/Android/小程序）
- 🤖 **智能分析** - 自然语言输入，自动识别需求、补充细节
- 📄 **专业输出** - 5W2H + 测试驱动的结构化文档

---

## ✨ 核心特性

### 1. 极简输入

用户只需输入自然语言需求：
```
"我想做一个 CRM 系统，管理客户信息、销售跟进、合同管理"
"做一个类似淘宝的电商平台，支持多商家入驻"
"需要一个员工请假审批系统，支持多级审批"
```

### 2. 智能分析

系统自动识别并补充：
- ✅ **领域识别** - ERP/CRM/电商/OA/BI/App
- ✅ **业务模式** - B2B/B2C/内部管理
- ✅ **核心模块** - 自动拆解功能模块
- ✅ **功能点** - 15-30 个详细功能点
- ✅ **行业实践** - 自动融入领域最佳实践

### 3. 智能追问

检测到缺失信息时主动追问：
```
❓ 您的主要使用场景是？
❓ 需要对接哪些系统？
❓ 预计用户数量？
❓ 文档详细程度？
```

### 4. 5W2H + 测试驱动文档

每个功能点包含完整要素：
- **Why** - 业务背景
- **What** - 功能说明
- **Input** - 输入设计
- **Output** - 输出设计
- **How** - 功能流程
- **Interface** - 接口设计
- **Test** - 测试覆盖
- **Security** - 安全设计
- **Notes** - 特殊说明

---

## 🚀 快速开始

### 方式一：本地运行

```bash
# 1. 克隆项目
git clone https://github.com/zhousiyu-pc/agents.git
cd agents

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key
export LLM_API_KEY="sk-你的 APIKey"

# 4. 启动服务
./start.sh

# 5. 访问服务
# API: http://localhost:8766
# Web: http://localhost:3000 (待开发)
```

### 方式二：Docker 运行

```bash
# 1. 设置 API Key
export LLM_API_KEY="sk-你的 APIKey"

# 2. 启动容器
docker-compose up -d

# 3. 查看日志
docker-compose logs -f
```

---

## 📡 API 使用

### 智能分析并生成文档（推荐）

```bash
curl -X POST http://localhost:8766/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "我想做一个 CRM 系统，管理客户信息、销售跟进",
    "options": {
      "detail_level": "标准",
      "output_format": "markdown"
    }
  }'
```

**响应示例：**
```json
{
  "success": true,
  "task_id": "a1b2c3d4e5f6",
  "domain": "crm",
  "feature_count": 16,
  "complexity": "中等",
  "modules": ["客户管理", "销售管理", "合同管理"],
  "questions": [
    {
      "field": "scenario",
      "question": "您的主要使用场景是？",
      "options": ["销售团队管理", "客户整合", "客服支持"]
    }
  ],
  "message": "已创建任务，将生成 16 个功能点的详细需求文档"
}
```

### 查询任务进度

```bash
curl http://localhost:8766/api/tasks/a1b2c3d4e5f6
```

### 获取文档结果

```bash
curl http://localhost:8766/api/tasks/a1b2c3d4e5f6/result
```

### 导出文档

```bash
# 导出 PDF
curl -X POST http://localhost:8766/api/documents/{id}/export \
  -H "Content-Type: application/json" \
  -d '{"format": "pdf"}'

# 导出 Word
curl -X POST http://localhost:8766/api/documents/{id}/export \
  -H "Content-Type: application/json" \
  -d '{"format": "docx"}'
```

---

## 🌐 支持领域

| 领域 | 典型场景 | 核心模块 |
|------|----------|----------|
| 📊 **ERP** | 企业资源计划 | 采购、销售、库存、财务、生产 |
| 💼 **CRM** | 客户关系管理 | 客户管理、销售、市场、客服 |
| 🛒 **电商** | 电商平台/商城 | 商品、订单、支付、物流、营销 |
| 🏢 **OA** | 办公自动化 | 审批、考勤、请假、报销、公告 |
| 📈 **BI** | 数据分析看板 | 数据源、报表、可视化、预警 |
| 📱 **App** | 移动应用 | 用户中心、核心功能、消息、支付 |
| 🛡️ **保险** | 保险业务系统 | 保单、理赔、核保、精算、代理人 |
| 🎓 **教育** | 教育培训平台 | 课程、学员、教师、排课、考试 |
| 🎮 **其他** | 任意系统 | 自定义模块和功能 |

---

## 📁 项目结构

```
agents/
├── core/                       # 核心基础设施
│   ├── config.py               # 全局配置
│   ├── db.py                   # 数据库管理
│   ├── llm_client.py           # LLM API 客户端
│   ├── logger.py               # 日志管理
│   └── analyzer.py             # 需求分析引擎
├── skills/                     # 技能模块
│   ├── file_saver/             # 文件保存
│   └── task_manager/           # 任务管理
├── web/                        # Web 前端（待开发）
│   ├── src/
│   ├── public/
│   └── package.json
├── mobile/                     # 移动端（待开发）
│   ├── src/
│   └── manifest.json
├── Dockerfile                  # Docker 镜像
├── docker-compose.yml          # Docker Compose
├── requirements.txt            # Python 依赖
├── DESIGN.md                   # 产品设计方案
├── README.md                   # 使用说明
├── start.sh                    # 启动脚本
├── stop.sh                     # 停止脚本
└── main.py                     # 统一入口
```

---

## 🔧 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | (必填) | 通义千问 API Key |
| `LLM_MODEL` | qwen-plus | 模型名称 |
| `SERVER_PORT` | 8766 | 服务端口 |
| `TASK_WORKERS` | 3 | 并发 Worker 数量 |
| `DATA_DIR` | ~/.doc_generator | 数据存储目录 |
| `DEFAULT_OUTPUT_FORMAT` | markdown | 默认输出格式 |
| `DEBUG` | false | 调试模式 |

---

## 🎨 前端集成示例

### Web 端（Vue 3）

```vue
<template>
  <div class="doc-generator">
    <h1>📝 智能文档生成器</h1>
    
    <!-- 输入区域 -->
    <el-input
      v-model="requirement"
      type="textarea"
      :rows="4"
      placeholder="你想创建什么文档？例如：我想做一个 CRM 系统..."
    />
    
    <el-button type="primary" @click="generate">
      ✨ 开始生成
    </el-button>
    
    <!-- 进度显示 -->
    <el-progress 
      v-if="generating" 
      :percentage="progress" 
      :status="status"
    />
    
    <!-- 结果预览 -->
    <markdown-preview v-if="document" :content="document" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const requirement = ref('')
const generating = ref(false)
const progress = ref(0)
const document = ref(null)

const generate = async () => {
  generating.value = true
  
  // 创建任务
  const { data } = await axios.post('/api/analyze', {
    requirement: requirement.value
  })
  
  // 轮询进度
  pollProgress(data.task_id)
}

const pollProgress = async (taskId) => {
  const timer = setInterval(async () => {
    const { data } = await axios.get(`/api/tasks/${taskId}`)
    
    progress.value = Math.round(
      (data.completed_count / data.total_count) * 100
    )
    
    if (data.status === 'completed') {
      clearInterval(timer)
      // 获取结果
      const result = await axios.get(`/api/tasks/${taskId}/result`)
      document.value = result.data.content
      generating.value = false
    }
  }, 2000)
}
</script>
```

### 移动端（UniApp）

```vue
<template>
  <view class="container">
    <text class="title">📝 智能文档生成器</text>
    
    <!-- 语音输入 -->
    <button @click="startVoiceInput">
      🎤 语音输入
    </button>
    
    <!-- 文本输入 -->
    <textarea 
      v-model="requirement" 
      placeholder="你想创建什么文档？"
    />
    
    <button type="primary" @click="generate">
      ✨ 开始生成
    </button>
    
    <!-- 进度显示 -->
    <progress 
      v-if="generating" 
      :percent="progress" 
    />
  </view>
</template>

<script>
export default {
  data() {
    return {
      requirement: '',
      generating: false,
      progress: 0
    }
  },
  methods: {
    async generate() {
      this.generating = true
      
      // 调用 API
      const res = await uni.request({
        url: 'http://localhost:8766/api/analyze',
        method: 'POST',
        data: { requirement: this.requirement }
      })
      
      // 轮询进度
      this.pollProgress(res.data.task_id)
    },
    
    startVoiceInput() {
      // 语音识别
      uni.startRecord({
        success: (res) => {
          // 语音转文字（可集成讯飞/百度语音）
          this.requirement = res.tempFilePath
        }
      })
    }
  }
}
</script>
```

---

## 🧪 测试

```bash
# 运行测试
pytest tests/ -v --cov=core

# 运行单个测试
pytest tests/test_analyzer.py -v
```

---

## 🛠️ 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 代码格式化
black core/ skills/

# 类型检查
mypy core/ skills/

# 代码检查
flake8 core/ skills/
```

---

## 📊 API 端点总览

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/analyze` | POST | 智能分析需求 |
| `/api/tasks` | POST | 创建任务 |
| `/api/tasks/{id}` | GET | 查询进度 |
| `/api/tasks/{id}/result` | GET | 获取结果 |
| `/api/documents` | GET | 文档列表 |
| `/api/documents/{id}` | GET | 文档详情 |
| `/api/documents/{id}/export` | POST | 导出文档 |
| `/api/templates` | GET | 模板列表 |
| `/api/health` | GET | 健康检查 |

---

## 🚧 路线图

### 已完成 ✅
- [x] 需求分析引擎（通用化）
- [x] 领域知识库框架
- [x] 5W2H 文档模板
- [x] 核心 API 服务
- [x] Docker 部署支持

### 进行中 🚧
- [ ] Web 前端开发
- [ ] 移动端开发
- [ ] PDF/Word 导出

### 计划中 📋
- [ ] 用户认证系统
- [ ] 文档分享功能
- [ ] 团队协作
- [ ] 模板市场
- [ ] API 开放平台

---

## 📄 License

MIT License

---

_让每一份需求文档都专业、完整、高效！_
