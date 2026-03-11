"""
需求分析引擎
============
智能识别用户意图，评估复杂度，自动补充行业最佳实践。
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

class BusinessModel(str, Enum):
    """业务模式"""
    B2C = "B2C 零售"
    B2B = "B2B 批发"
    MIXED = "混合模式"
    UNKNOWN = "未知"


class ComplexityLevel(str, Enum):
    """复杂度等级"""
    SIMPLE = "简单"
    MEDIUM = "中等"
    COMPLEX = "复杂"


# ── 数据结构 ──────────────────────────────────────

@dataclass
class PlatformInfo:
    """平台信息"""
    name: str
    api_type: str  # SP-API, API v2, etc.
    integrations: list[str] = field(default_factory=list)


@dataclass
class AnalyzedRequirement:
    """分析后的需求"""
    # 基础信息
    business_model: BusinessModel
    target_market: str
    platforms: list[str]
    
    # 功能模块
    core_modules: list[str]
    feature_list: list[str]
    
    # 复杂度评估
    complexity: ComplexityLevel
    estimated_features: int
    
    # 智能补充
    cross_border_features: list[str]
    compliance_requirements: list[str]
    
    # 追问列表（如有缺失信息）
    questions: list[dict[str, str]]
    
    # 原始输入
    raw_input: str


# ── 知识库 ──────────────────────────────────────

PLATFORM_KNOWLEDGE = {
    "amazon": PlatformInfo(
        name="Amazon",
        api_type="SP-API",
        integrations=["FBA 库存同步", "自动定价", "广告数据", "订单拉取", "Feedback 管理"],
    ),
    "亚马逊": PlatformInfo(
        name="Amazon",
        api_type="SP-API",
        integrations=["FBA 库存同步", "自动定价", "广告数据", "订单拉取", "Feedback 管理"],
    ),
    "tiktok": PlatformInfo(
        name="TikTok Shop",
        api_type="TikTok Shop API",
        integrations=["商品同步", "订单管理", "物流追踪", "达人带货", "直播数据"],
    ),
    "ebay": PlatformInfo(
        name="eBay",
        api_type="eBay API",
        integrations=["刊登管理", "订单处理", "支付管理", "纠纷处理"],
    ),
    "shopee": PlatformInfo(
        name="Shopee",
        api_type="Shopee Open Platform",
        integrations=["商品管理", "订单处理", "物流对接", "营销活动"],
    ),
    "lazada": PlatformInfo(
        name="Lazada",
        api_type="Lazada Open Platform",
        integrations=["商品同步", "订单管理", "物流追踪"],
    ),
    "独立站": PlatformInfo(
        name="独立站",
        api_type="REST API",
        integrations=["Shopify 对接", "WooCommerce 对接", "支付网关", "物流 API"],
    ),
}

MODULE_KNOWLEDGE = {
    "商品": ["商品录入", "商品同步", "库存管理", "价格管理", "图片管理", "分类管理"],
    "订单": ["订单拉取", "订单处理", "订单审核", "订单拆分", "订单合并", "退换货"],
    "物流": ["物流商管理", "运费计算", "运单生成", "物流追踪", "海外仓管理"],
    "采购": ["智能采购", "采购建议", "供应商管理", "采购订单", "入库管理"],
    "财务": ["利润核算", "成本计算", "对账管理", "多币种", "税务计算"],
    "客服": ["消息聚合", "自动回复", "工单管理", "评价管理", "纠纷处理"],
    "仓储": ["多仓库", "库存调拨", "盘点管理", "批次管理", "效期管理"],
    "报表": ["销售报表", "利润报表", "库存报表", "绩效分析", "数据导出"],
}

CROSS_BORDER_DEFAULTS = [
    "多币种支持（USD/EUR/GBP/JPY 等）",
    "多语言支持（英文/德文/法文/日文等）",
    "时区自动转换",
    "关税/VAT 计算",
    "合规检查（CE/FCC/RoHS 等）",
    "尺寸单位转换（公制/英制）",
]


# ── 分析引擎 ──────────────────────────────────────

class RequirementAnalyzer:
    """需求分析引擎"""
    
    def __init__(self):
        self.platform_knowledge = PLATFORM_KNOWLEDGE
        self.module_knowledge = MODULE_KNOWLEDGE
    
    def analyze(self, raw_input: str) -> AnalyzedRequirement:
        """
        分析用户需求，提取关键信息并智能补充。
        
        Args:
            raw_input: 用户原始输入
        
        Returns:
            分析后的需求对象
        """
        # 1. 业务模式识别
        business_model = self._identify_business_model(raw_input)
        
        # 2. 目标市场识别
        target_market = self._identify_target_market(raw_input)
        
        # 3. 平台识别
        platforms = self._identify_platforms(raw_input)
        
        # 4. 核心模块识别
        core_modules = self._identify_modules(raw_input)
        
        # 5. 功能点拆解
        feature_list = self._generate_features(core_modules, platforms)
        
        # 6. 复杂度评估
        complexity = self._evaluate_complexity(feature_list, raw_input)
        
        # 7. 跨境电商特性补充
        cross_border_features = self._add_cross_border_features(
            business_model, target_market
        )
        
        # 8. 合规要求补充
        compliance_requirements = self._add_compliance_requirements(target_market)
        
        # 9. 智能追问（检测缺失信息）
        questions = self._generate_questions(
            business_model, platforms, core_modules, raw_input
        )
        
        return AnalyzedRequirement(
            business_model=business_model,
            target_market=target_market,
            platforms=platforms,
            core_modules=core_modules,
            feature_list=feature_list,
            complexity=complexity,
            estimated_features=len(feature_list) + len(cross_border_features),
            cross_border_features=cross_border_features,
            compliance_requirements=compliance_requirements,
            questions=questions,
            raw_input=raw_input,
        )
    
    def _identify_business_model(self, text: str) -> BusinessModel:
        """识别业务模式"""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ["批发", "b2b", "企业采购", "大宗"]):
            return BusinessModel.B2B
        elif any(kw in text_lower for kw in ["零售", "b2c", "个人", "消费者"]):
            return BusinessModel.B2C
        elif any(kw in text_lower for kw in ["混合", "both", "b2b2c"]):
            return BusinessModel.MIXED
        else:
            # 默认根据平台推断
            return BusinessModel.B2C
    
    def _identify_target_market(self, text: str) -> str:
        """识别目标市场"""
        text_lower = text.lower()
        
        markets = {
            "北美": ["北美", "美国", "加拿大", "美利坚", "usa", "us"],
            "欧洲": ["欧洲", "英国", "德国", "法国", "意大利", "西班牙", "eu"],
            "东南亚": ["东南亚", "泰国", "越南", "印尼", "马来西亚", "菲律宾"],
            "日本": ["日本", "日亚", "jp"],
            "中东": ["中东", "沙特", "阿联酋", "迪拜"],
            "全球": ["全球", "全世界", "worldwide", "global"],
        }
        
        for market, keywords in markets.items():
            if any(kw in text_lower for kw in keywords):
                return market
        
        return "全球"  # 默认
    
    def _identify_platforms(self, text: str) -> list[str]:
        """识别销售平台"""
        text_lower = text.lower()
        platforms = []
        
        for key, info in self.platform_knowledge.items():
            if key in text_lower:
                if info.name not in platforms:
                    platforms.append(info.name)
        
        # 智能推断
        if not platforms:
            # 提到"跨境"但未指定平台，默认包含主流平台
            if any(kw in text_lower for kw in ["跨境", "电商", "erp"]):
                platforms = ["Amazon", "TikTok Shop"]
        
        return platforms if platforms else ["未指定"]
    
    def _identify_modules(self, text: str) -> list[str]:
        """识别核心功能模块"""
        text_lower = text.lower()
        modules = []
        
        for module, features in self.module_knowledge.items():
            # 直接匹配模块名
            if module in text_lower:
                modules.append(module)
                continue
            
            # 匹配模块下的功能关键词
            for feature in features:
                if feature in text_lower:
                    if module not in modules:
                        modules.append(module)
                    break
        
        # 智能推断
        if not modules:
            # 提到"erp"默认包含核心模块
            if "erp" in text_lower:
                modules = ["商品", "订单", "物流", "财务"]
        
        # 至少要有核心模块
        if not modules:
            modules = ["商品", "订单"]
        
        return modules
    
    def _generate_features(
        self, modules: list[str], platforms: list[str]
    ) -> list[str]:
        """根据模块和平台生成详细功能点列表"""
        features = []
        
        # 1. 添加模块下的核心功能
        for module in modules:
            module_features = self.module_knowledge.get(module, [])
            # 根据模块重要性选择功能数量
            if module in ["商品", "订单"]:
                # 核心模块，包含所有功能
                features.extend(module_features[:4])
            else:
                # 其他模块，选 2-3 个核心功能
                features.extend(module_features[:3])
        
        # 2. 添加平台特有功能
        for platform in platforms:
            platform_info = self.platform_knowledge.get(platform)
            if platform_info:
                features.extend(platform_info.integrations[:3])
        
        # 去重
        seen = set()
        unique_features = []
        for f in features:
            if f not in seen:
                seen.add(f)
                unique_features.append(f)
        
        return unique_features
    
    def _evaluate_complexity(
        self, features: list[str], raw_input: str
    ) -> ComplexityLevel:
        """评估需求复杂度"""
        feature_count = len(features)
        text_length = len(raw_input)
        
        # 检测高级关键词
        advanced_keywords = [
            "智能", "自动", "ai", "算法", "预测",
            "多仓库", "海外仓", "fba",
            "财务", "核算", "税务",
            "定制", "私有化", "源码",
        ]
        
        advanced_count = sum(
            1 for kw in advanced_keywords if kw in raw_input.lower()
        )
        
        # 复杂度判定
        if feature_count <= 5 and advanced_count <= 1:
            return ComplexityLevel.SIMPLE
        elif feature_count <= 15 and advanced_count <= 3:
            return ComplexityLevel.MEDIUM
        else:
            return ComplexityLevel.COMPLEX
    
    def _add_cross_border_features(
        self, business_model: BusinessModel, target_market: str
    ) -> list[str]:
        """添加跨境电商特有功能"""
        # 只有跨境电商才需要这些
        if target_market == "全球" or business_model in [BusinessModel.B2C, BusinessModel.MIXED]:
            return CROSS_BORDER_DEFAULTS[:4]  # 选 4 个核心的
        return []
    
    def _add_compliance_requirements(self, target_market: str) -> list[str]:
        """添加合规要求"""
        compliance = []
        
        if target_market in ["北美", "全球"]:
            compliance.extend(["FCC 认证", "FDA 注册（如适用）"])
        if target_market in ["欧洲", "全球"]:
            compliance.extend(["CE 认证", "VAT 税务合规", "GDPR 数据保护"])
        if target_market in ["日本", "全球"]:
            compliance.extend(["PSE 认证", "日本消费税"])
        
        return compliance if compliance else ["基础合规检查"]
    
    def _generate_questions(
        self,
        business_model: BusinessModel,
        platforms: list[str],
        modules: list[str],
        raw_input: str,
    ) -> list[dict[str, str]]:
        """生成智能追问列表"""
        questions = []
        text_lower = raw_input.lower()
        
        # 检测多仓库但未说明位置
        if ("仓库" in text_lower or "仓储" in text_lower) and "海外仓" not in text_lower:
            questions.append({
                "field": "warehouse_locations",
                "question": "您的仓库分布在哪些地区？（如：国内仓、美国仓、欧洲仓）",
                "options": ["仅国内仓", "国内 + 海外仓", "纯海外仓", "暂不确定"],
            })
        
        # 检测自动采购但未说明策略
        if ("自动采购" in text_lower or "智能采购" in text_lower) and "采购" in modules:
            questions.append({
                "field": "purchase_strategy",
                "question": "自动采购的触发规则是？",
                "options": ["库存低于安全值", "基于销售预测", "定期补货", "手动配置"],
            })
        
        # 检测财务但未说明币种
        if "财务" in modules and "币种" not in text_lower and "货币" not in text_lower:
            questions.append({
                "field": "base_currency",
                "question": "您的本位币是？",
                "options": ["人民币 CNY", "美元 USD", "欧元 EUR", "多币种"],
            })
        
        # 检测物流但未说明物流商
        if "物流" in modules and "物流商" not in text_lower and "快递" not in text_lower:
            questions.append({
                "field": "logistics_providers",
                "question": "您主要使用哪些物流商？",
                "options": ["国际快递（DHL/FedEx/UPS）", "专线物流", "海外仓配", "平台物流（FBA 等）"],
            })
        
        # 平台特定追问
        if "Amazon" in platforms and "fba" not in text_lower:
            questions.append({
                "field": "fba_usage",
                "question": "是否使用 FBA 服务？",
                "options": ["是，主要用 FBA", "部分使用", "不用，自发货"],
            })
        
        return questions
    
    def to_context_dict(self, analyzed: AnalyzedRequirement) -> dict:
        """
        将分析结果转换为 LLM 上下文格式。
        用于传递给文档生成引擎。
        """
        return {
            "project_name": f"{analyzed.business_model.value}跨境电商 ERP 系统",
            "project_summary": (
                f"面向{analyzed.target_market}市场的{analyzed.business_model.value}跨境电商 ERP，"
                f"支持{', '.join(analyzed.platforms)}平台，"
                f"涵盖{', '.join(analyzed.core_modules)}等核心模块。"
            ),
            "business_model": analyzed.business_model.value,
            "target_market": analyzed.target_market,
            "platforms": ", ".join(analyzed.platforms),
            "core_modules": analyzed.core_modules,
            "feature_list": analyzed.feature_list,
            "cross_border_notes": "\n".join(
                f"- {item}" for item in analyzed.cross_border_features
            ),
            "compliance_notes": "\n".join(
                f"- {item}" for item in analyzed.compliance_requirements
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
