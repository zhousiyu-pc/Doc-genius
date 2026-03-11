"""
测试需求分析引擎
================
验证领域识别、功能点拆解、智能追问等核心功能。
"""

import pytest
from core.analyzer import RequirementAnalyzer, Domain, BusinessModel, ComplexityLevel


class TestRequirementAnalyzer:
    """需求分析引擎测试"""

    def setup_method(self):
        """每个测试前的初始化"""
        self.analyzer = RequirementAnalyzer()

    def test_identify_domain_erp(self):
        """测试 ERP 领域识别"""
        text = "我想做一个 ERP 系统，管理采购、库存和财务"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.ERP

    def test_identify_domain_crm(self):
        """测试 CRM 领域识别"""
        text = "需要一个 CRM 系统来管理客户和销售线索"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.CRM

    def test_identify_domain_ecommerce(self):
        """测试电商领域识别"""
        text = "做一个电商平台，支持多商家入驻"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.ECOMMERCE

    def test_identify_domain_oa(self):
        """测试 OA 领域识别"""
        text = "OA 办公系统，包含审批流程和考勤管理"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.OA

    def test_identify_domain_bi(self):
        """测试 BI 领域识别"""
        text = "搭建一个 BI 数据看板，展示销售报表"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.BI

    def test_identify_domain_app(self):
        """测试 App 领域识别"""
        text = "开发一个移动 App，支持 iOS 和 Android"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.APP

    def test_identify_domain_insurance(self):
        """测试保险领域识别"""
        text = "保险系统，管理保单、理赔和代理人"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.INSURANCE

    def test_identify_domain_education(self):
        """测试教育领域识别"""
        text = "教育培训平台，包含课程、学员和在线考试"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.EDUCATION

    def test_identify_domain_general(self):
        """测试通用领域识别（无关键词）"""
        text = "我想做一个管理系统"
        result = self.analyzer._identify_domain(text)
        assert result == Domain.GENERAL

    def test_identify_business_model_b2c(self):
        """测试 B2C 业务模式识别"""
        text = "做一个零售电商，面向个人消费者"
        result = self.analyzer._identify_business_model(text)
        assert result == BusinessModel.B2C

    def test_identify_business_model_b2b(self):
        """测试 B2B 业务模式识别"""
        text = "企业级批发平台，服务供应商"
        result = self.analyzer._identify_business_model(text)
        assert result == BusinessModel.B2B

    def test_identify_business_model_internal(self):
        """测试内部管理业务模式识别"""
        text = "内部员工管理系统"
        result = self.analyzer._identify_business_model(text)
        assert result == BusinessModel.INTERNAL

    def test_generate_features_crm(self):
        """测试 CRM 功能点生成"""
        modules = ["客户管理", "销售管理"]
        features = self.analyzer._generate_features("", Domain.CRM, modules)
        
        assert len(features) > 0
        assert any("客户管理" in f for f in features)
        assert any("销售管理" in f for f in features)

    def test_generate_features_ecommerce(self):
        """测试电商功能点生成"""
        modules = ["商品管理", "订单管理"]
        features = self.analyzer._generate_features("", Domain.ECOMMERCE, modules)
        
        assert len(features) > 0
        assert any("商品" in f for f in features)
        assert any("订单" in f for f in features)

    def test_evaluate_complexity_simple(self):
        """测试简单复杂度评估"""
        features = ["功能 1", "功能 2", "功能 3"]
        text = "简单的管理系统"
        result = self.analyzer._evaluate_complexity(features, text)
        assert result == ComplexityLevel.SIMPLE

    def test_evaluate_complexity_medium(self):
        """测试中等复杂度评估"""
        features = [f"功能{i}" for i in range(15)]
        text = "需要智能算法和自动化的系统"
        result = self.analyzer._evaluate_complexity(features, text)
        assert result == ComplexityLevel.MEDIUM

    def test_evaluate_complexity_complex(self):
        """测试复杂复杂度评估"""
        features = [f"功能{i}" for i in range(25)]
        text = "多租户 SaaS 平台，支持高并发分布式架构"
        result = self.analyzer._evaluate_complexity(features, text)
        assert result == ComplexityLevel.COMPLEX

    def test_generate_questions_erp(self):
        """测试 ERP 智能追问生成"""
        modules = ["财务管理", "库存管理"]
        text = "ERP 系统"
        questions = self.analyzer._generate_questions(Domain.ERP, modules, text)
        
        assert len(questions) > 0
        assert any("币种" in q["question"] or "仓库" in q["question"] for q in questions)

    def test_generate_questions_ecommerce(self):
        """测试电商智能追问生成"""
        modules = ["支付", "物流"]
        text = "电商平台"
        questions = self.analyzer._generate_questions(Domain.ECOMMERCE, modules, text)
        
        assert len(questions) > 0
        assert any("支付" in q["question"] or "物流" in q["question"] for q in questions)

    def test_analyze_full_crm(self):
        """测试完整的 CRM 需求分析"""
        text = "我想做一个 CRM 系统，管理客户信息、销售跟进、合同管理，预计 200 人使用"
        result = self.analyzer.analyze(text)
        
        assert result.domain == Domain.CRM
        assert result.domain_name == "CRM 系统"
        assert len(result.core_modules) > 0
        assert len(result.feature_list) > 0
        assert result.complexity in [ComplexityLevel.SIMPLE, ComplexityLevel.MEDIUM, ComplexityLevel.COMPLEX]
        assert len(result.questions) > 0

    def test_analyze_full_ecommerce(self):
        """测试完整的电商需求分析"""
        text = "做一个类似淘宝的电商平台，支持多商家入驻，需要商品、订单、支付、物流功能"
        result = self.analyzer.analyze(text)
        
        assert result.domain == Domain.ECOMMERCE
        assert result.domain_name == "电商平台"
        assert len(result.feature_list) > 10

    def test_analyze_full_insurance(self):
        """测试完整的保险需求分析"""
        text = "保险系统，管理保单生命周期、理赔流程、代理人佣金，支持车险和寿险"
        result = self.analyzer.analyze(text)
        
        assert result.domain == Domain.INSURANCE
        assert result.domain_name == "保险系统"
        assert len(result.feature_list) > 8
        assert any("保单" in f for f in result.feature_list)

    def test_analyze_full_education(self):
        """测试完整的教育需求分析"""
        text = "教育培训平台，学员管理、课程排课、在线学习和考试测评"
        result = self.analyzer.analyze(text)
        
        assert result.domain == Domain.EDUCATION
        assert result.domain_name == "教育培训系统"
        assert len(result.feature_list) > 8
        assert any("课程" in f or "学员" in f for f in result.feature_list)

    def test_to_context_dict(self):
        """测试上下文转换"""
        text = "CRM 系统"
        analyzed = self.analyzer.analyze(text)
        context = self.analyzer.to_context_dict(analyzed)
        
        assert "project_name" in context
        assert "domain" in context
        assert "core_modules" in context
        assert "feature_list" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
