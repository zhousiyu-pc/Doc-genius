"""
需求分析引擎（通用版）
====================
智能识别用户意图，评估复杂度，自动补充行业最佳实践。
支持多领域：ERP、CRM、电商、OA、BI、App 等。
目标：让用户输入最少，系统输出最多。
"""

import json
import re
import logging
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("agent_skills.analyzer")


# ── 枚举定义 ──────────────────────────────────────

class Domain(str, Enum):
    """文档领域"""
    ERP = "erp"
    CRM = "crm"
    ECOMMERCE = "ecommerce"
    OA = "oa"
    BI = "bi"
    APP = "app"
    GENERAL = "general"


class BusinessModel(str, Enum):
    """业务模式"""
    B2C = "B2C 零售"
    B2B = "B2B 批发"
    INTERNAL = "内部管理"
    PLATFORM = "平台服务"
    UNKNOWN = "未知"


class ComplexityLevel(str, Enum):
    """复杂度等级"""
    SIMPLE = "简单"
    MEDIUM = "中等"
    COMPLEX = "复杂"


# ── 数据结构 ──────────────────────────────────────

@dataclass
class DomainInfo:
    """领域信息"""
    name: str
    modules: list[str]
    common_features: list[str]
    special_considerations: list[str]


@dataclass
class AnalyzedRequirement:
    """分析后的需求"""
    # 基础信息
    domain: Domain
    domain_name: str
    business_model: BusinessModel
    target_users: str
    
    # 功能模块
    core_modules: list[str]
    feature_list: list[str]
    
    # 复杂度评估
    complexity: ComplexityLevel
    estimated_features: int
    
    # 智能补充
    common_features: list[str]
    special_considerations: list[str]
    
    # 追问列表（如有缺失信息）
    questions: list[dict[str, str]]
    
    # 原始输入
    raw_input: str


# ── 领域知识库 ──────────────────────────────────────

DOMAIN_KNOWLEDGE = {
    Domain.ERP: DomainInfo(
        name="ERP 系统",
        modules=["采购管理", "销售管理", "库存管理", "财务管理", "生产管理", "质量管理"],
        common_features=["多组织架构", "多币种支持", "审批流程", "权限管理", "报表中心"],
        special_considerations=[
            "财务合规性（会计准则）",
            "库存准确性（实时同步）",
            "业务流程完整性",
        ],
    ),
    Domain.CRM: DomainInfo(
        name="CRM 系统",
        modules=["客户管理", "销售管理", "市场活动", "客服支持", "数据分析"],
        common_features=["线索管理", "商机跟进", "客户画像", "销售漏斗", "跟进记录"],
        special_considerations=[
            "客户数据隐私保护",
            "销售流程标准化",
            "多渠道客户整合",
        ],
    ),
    Domain.ECOMMERCE: DomainInfo(
        name="电商平台",
        modules=["商品管理", "订单管理", "支付结算", "物流管理", "营销推广", "售后服务"],
        common_features=["多商家入驻", "库存同步", "促销规则", "评价系统", "退换货"],
        special_considerations=[
            "高并发订单处理",
            "支付安全",
            "物流配送时效",
            "售后纠纷处理",
        ],
    ),
    Domain.OA: DomainInfo(
        name="OA 办公系统",
        modules=["审批流程", "考勤管理", "请假管理", "报销管理", "公告通知", "日程管理"],
        common_features=["多级审批", "消息通知", "移动端支持", "集成 IM", "数据导出"],
        special_considerations=[
            "审批流程灵活性",
            "消息及时送达",
            "与现有系统集成",
        ],
    ),
    Domain.BI: DomainInfo(
        name="BI 数据分析平台",
        modules=["数据源管理", "报表设计", "数据看板", "预警通知", "数据导出"],
        common_features=["可视化图表", "定时刷新", "权限控制", "数据钻取", "多维分析"],
        special_considerations=[
            "数据安全性",
            "查询性能优化",
            "数据准确性校验",
        ],
    ),
    Domain.APP: DomainInfo(
        name="移动 App",
        modules=["用户中心", "核心功能", "消息通知", "设置", "支付"],
        common_features=["iOS/Android", "推送通知", "离线缓存", "版本更新", "第三方登录"],
        special_considerations=[
            "移动端性能优化",
            "网络不稳定处理",
            "应用商店审核规范",
        ],
    ),
}

# 领域识别关键词
DOMAIN_KEYWORDS = {
    Domain.ERP: ["erp", "企业资源计划", "采购", "库存", "生产", "物料", "bom", "工单"],
    Domain.CRM: ["crm", "客户关系", "销售", "线索", "商机", "客户管理", "跟进"],
    Domain.ECOMMERCE: ["电商", "商城", "店铺", "商品", "订单", "卖家", "买家", "入驻"],
    Domain.OA: ["oa", "办公", "审批", "考勤", "请假", "报销", "行政", "后勤"],
    Domain.BI: ["bi", "数据看板", "报表", "分析", "可视化", "图表", " dashboard"],
    Domain.APP: ["app", "移动应用", "ios", "android", "小程序", "手机"],
}

# 业务模式识别关键词
BUSINESS_MODEL_KEYWORDS = {
    BusinessModel.B2C: ["零售", "个人", "消费者", "c 端", "买家"],
    BusinessModel.B2B: ["批发", "企业", "供应商", "b 端", "采购"],
    BusinessModel.INTERNAL: ["内部", "管理", "员工", "办公", "行政"],
    BusinessModel.PLATFORM: ["平台", "多商家", "入驻", "开放", "生态"],
}


# ── 分析引擎 ──────────────────────────────────────

class RequirementAnalyzer:
    """需求分析引擎（通用版）"""
    
    def __init__(self):
        self.domain_knowledge = DOMAIN_KNOWLEDGE
    
    def analyze(self, raw_input: str) -> AnalyzedRequirement:
        """
        分析用户需求，提取关键信息并智能补充。
        
        Args:
            raw_input: 用户原始输入
        
        Returns:
            分析后的需求对象
        """
        # 1. 领域识别
        domain = self._identify_domain(raw_input)
        
        # 2. 业务模式识别
        business_model = self._identify_business_model(raw_input)
        
        # 3. 目标用户识别
        target_users = self._identify_target_users(raw_input)
        
        # 4. 核心模块识别
        core_modules = self._identify_modules(raw_input, domain)
        
        # 5. 功能点拆解
        feature_list = self._generate_features(raw_input, domain, core_modules)
        
        # 6. 复杂度评估
        complexity = self._evaluate_complexity(feature_list, raw_input)
        
        # 7. 通用特性补充
        domain_info = self.domain_knowledge.get(domain, DOMAIN_KNOWLEDGE[Domain.GENERAL])
        common_features = domain_info.common_features[:5]
        special_considerations = domain_info.special_considerations
        
        # 8. 智能追问（检测缺失信息）
        questions = self._generate_questions(domain, core_modules, raw_input)
        
        return AnalyzedRequirement(
            domain=domain,
            domain_name=domain_info.name,
            business_model=business_model,
            target_users=target_users,
            core_modules=core_modules,
            feature_list=feature_list,
            complexity=complexity,
            estimated_features=len(feature_list) + len(common_features),
            common_features=common_features,
            special_considerations=special_considerations,
            questions=questions,
            raw_input=raw_input,
        )
    
    def _identify_domain(self, text: str) -> Domain:
        """识别文档所属领域"""
        text_lower = text.lower()
        scores = {}
        
        for domain, keywords in DOMAIN_KEYWORDS.items():
            scores[domain] = sum(1 for kw in keywords if kw in text_lower)
        
        # 返回得分最高的领域
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        return Domain.GENERAL
    
    def _identify_business_model(self, text: str) -> BusinessModel:
        """识别业务模式"""
        text_lower = text.lower()
        scores = {}
        
        for model, keywords in BUSINESS_MODEL_KEYWORDS.items():
            scores[model] = sum(1 for kw in keywords if kw in text_lower)
        
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        return BusinessModel.UNKNOWN
    
    def _identify_target_users(self, text: str) -> str:
        """识别目标用户"""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ["中小", "小微企业", "初创"]):
            return "中小企业"
        elif any(kw in text_lower for kw in ["大型", "集团", "企业"]):
            return "大型企业"
        elif any(kw in text_lower for kw in ["个人", "消费者"]):
            return "个人用户"
        elif any(kw in text_lower for kw in ["内部", "员工"]):
            return "内部员工"
        else:
            return "通用"
    
    def _identify_modules(self, text: str, domain: Domain) -> list[str]:
        """识别核心功能模块"""
        text_lower = text.lower()
        modules = []
        
        domain_info = self.domain_knowledge.get(domain)
        if not domain_info:
            return ["核心功能"]
        
        for module in domain_info.modules:
            # 直接匹配模块名
            if any(kw in text_lower for kw in module.lower()):
                modules.append(module)
                continue
            
            # 匹配模块关键词
            for kw in ["管理", "功能", "模块"]:
                if module.replace("管理", "") in text_lower:
                    if module not in modules:
                        modules.append(module)
                    break
        
        # 智能推断
        if not modules:
            # 如果未指定模块，返回领域的前 3 个核心模块
            modules = domain_info.modules[:3]
        
        return modules
    
    def _generate_features(
        self, raw_input: str, domain: Domain, modules: list[str]
    ) -> list[str]:
        """根据领域和模块生成详细功能点列表"""
        features = []
        domain_info = self.domain_knowledge.get(domain)
        
        if not domain_info:
            # 通用领域，根据模块名生成
            for module in modules:
                features.extend([
                    f"{module} - 基础功能",
                    f"{module} - 列表查看",
                    f"{module} - 新增/编辑",
                    f"{module} - 删除",
                ])
            return features
        
        # 为每个模块生成 3-5 个功能点
        for module in modules:
            # 查找模块在知识库中的索引
            module_idx = -1
            for i, m in enumerate(domain_info.modules):
                if module in m or m in module:
                    module_idx = i
                    break
            
            if module_idx >= 0:
                # 根据模块重要性选择功能数量
                if module_idx < 2:
                    # 核心模块，生成 5 个功能点
                    features.extend([
                        f"{module} - 基础设置",
                        f"{module} - 列表查看",
                        f"{module} - 新增/导入",
                        f"{module} - 编辑/更新",
                        f"{module} - 删除/归档",
                    ])
                else:
                    # 其他模块，生成 3 个功能点
                    features.extend([
                        f"{module} - 基础功能",
                        f"{module} - 核心操作",
                        f"{module} - 查询统计",
                    ])
        
        # 添加通用功能
        features.extend([
            "系统管理 - 用户管理",
            "系统管理 - 角色权限",
            "系统管理 - 操作日志",
        ])
        
        return features
    
    def _evaluate_complexity(
        self, features: list[str], raw_input: str
    ) -> ComplexityLevel:
        """评估需求复杂度"""
        feature_count = len(features)
        text_length = len(raw_input)
        
        # 检测高级关键词
        advanced_keywords = [
            "智能", "自动", "ai", "算法", "预测",
            "多组织", "多租户", "saas",
            "高并发", "分布式", "微服务",
            "集成", "对接", "api",
            "定制", "私有化", "源码",
        ]
        
        advanced_count = sum(
            1 for kw in advanced_keywords if kw in raw_input.lower()
        )
        
        # 复杂度判定
        if feature_count <= 8 and advanced_count <= 1:
            return ComplexityLevel.SIMPLE
        elif feature_count <= 20 and advanced_count <= 3:
            return ComplexityLevel.MEDIUM
        else:
            return ComplexityLevel.COMPLEX
    
    def _generate_questions(
        self,
        domain: Domain,
        modules: list[str],
        raw_input: str,
    ) -> list[dict[str, str]]:
        """生成智能追问列表"""
        questions = []
        text_lower = raw_input.lower()
        
        # 通用追问（所有领域都适用）
        if "用户" not in text_lower and "人" not in text_lower:
            questions.append({
                "field": "user_scale",
                "question": "预计用户数量？",
                "options": ["<50 人", "50-200 人", "200-500 人", "500+ 人"],
            })
        
        # 领域特定追问
        if domain == Domain.ERP:
            if "财务" in modules and "币种" not in text_lower:
                questions.append({
                    "field": "currency",
                    "question": "是否需要多币种支持？",
                    "options": ["单币种（人民币）", "多币种（USD/EUR 等）"],
                })
            if "库存" in modules and "仓库" not in text_lower:
                questions.append({
                    "field": "warehouse",
                    "question": "仓库分布情况？",
                    "options": ["单仓库", "多仓库", "多地仓库"],
                })
        
        elif domain == Domain.CRM:
            if "销售" in modules and "线索" not in text_lower:
                questions.append({
                    "field": "lead_source",
                    "question": "线索来源渠道？",
                    "options": ["线上渠道", "线下渠道", "多渠道整合"],
                })
        
        elif domain == Domain.ECOMMERCE:
            if "支付" not in text_lower:
                questions.append({
                    "field": "payment",
                    "question": "需要对接哪些支付方式？",
                    "options": ["微信支付", "支付宝", "银行卡", "全都要"],
                })
            if "物流" in modules and "快递" not in text_lower:
                questions.append({
                    "field": "logistics",
                    "question": "主要合作的物流公司？",
                    "options": ["顺丰", "三通一达", "京东物流", "多家混合"],
                })
        
        elif domain == Domain.OA:
            if "审批" in modules:
                questions.append({
                    "field": "approval_levels",
                    "question": "审批流程复杂度？",
                    "options": ["单级审批", "多级审批", "动态审批流"],
                })
        
        elif domain == Domain.BI:
            if "数据" in text_lower and "源" not in text_lower:
                questions.append({
                    "field": "data_source",
                    "question": "数据来源？",
                    "options": ["现有数据库", "API 接口", "Excel 导入", "混合来源"],
                })
        
        elif domain == Domain.APP:
            if "ios" not in text_lower and "android" not in text_lower:
                questions.append({
                    "field": "platform",
                    "question": "目标平台？",
                    "options": ["iOS", "Android", "双平台", "小程序"],
                })
        
        return questions
    
    def to_context_dict(self, analyzed: AnalyzedRequirement) -> dict:
        """
        将分析结果转换为 LLM 上下文格式。
        用于传递给文档生成引擎。
        """
        return {
            "project_name": f"{analyzed.domain_name}需求规格说明书",
            "project_summary": (
                f"面向{analyzed.target_users}的{analyzed.domain_name}，"
                f"业务模式：{analyzed.business_model.value}，"
                f"涵盖{', '.join(analyzed.core_modules)}等核心模块。"
            ),
            "domain": analyzed.domain.value,
            "domain_name": analyzed.domain_name,
            "business_model": analyzed.business_model.value,
            "target_users": analyzed.target_users,
            "core_modules": analyzed.core_modules,
            "feature_list": analyzed.feature_list,
            "common_features": analyzed.common_features,
            "special_considerations": "\n".join(
                f"- {item}" for item in analyzed.special_considerations
            ),
            "complexity": analyzed.complexity.value,
            "estimated_features": analyzed.estimated_features,
            "questions": analyzed.questions,
        }


# ── 快捷函数 ──────────────────────────────────────

def analyze_requirement(raw_input: str) -> dict:
    """
    快捷函数：分析用户需求并返回上下文字典。
    
    Args:
        raw_input: 用户原始输入
    
    Returns:
        LLM 上下文字典
    """
    analyzer = RequirementAnalyzer()
    analyzed = analyzer.analyze(raw_input)
    return analyzer.to_context_dict(analyzed)
