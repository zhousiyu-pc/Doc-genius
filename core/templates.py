"""
模板市场模块
============
内置行业模板的初始化与 CRUD 操作。
"""

import uuid
import logging
from datetime import datetime, timezone

from core.db import get_db

logger = logging.getLogger("agent_skills.templates")

# ── 8 个内置行业模板 ─────────────────────────────────

BUILTIN_TEMPLATES = [
    {
        "name": "ERP系统",
        "description": "企业资源计划系统，覆盖采购、库存、生产、财务等核心业务流程，帮助企业实现资源的高效配置与管理。",
        "category": "企业管理",
        "icon": "🏭",
        "prompt": (
            "请帮我设计一套完整的ERP企业资源计划系统。系统需要包含以下核心模块：\n"
            "1. 采购管理：供应商管理、采购订单、采购审批流程、到货验收\n"
            "2. 库存管理：入库/出库、库存盘点、安全库存预警、多仓库管理\n"
            "3. 生产管理：生产计划、工单管理、BOM物料清单、产能规划\n"
            "4. 销售管理：客户订单、发货管理、退换货处理\n"
            "5. 财务管理：应收应付、总账管理、成本核算、财务报表\n"
            "6. 人力资源：员工档案、考勤管理、薪酬计算\n"
            "请详细描述每个模块的功能需求、数据流转关系和关键业务规则。"
        ),
        "mode": "free",
    },
    {
        "name": "CRM系统",
        "description": "客户关系管理系统，涵盖客户全生命周期管理、销售漏斗、营销自动化等功能，助力企业提升客户转化与留存。",
        "category": "企业管理",
        "icon": "🤝",
        "prompt": (
            "请帮我设计一套完整的CRM客户关系管理系统。系统需要包含以下核心模块：\n"
            "1. 客户管理：客户信息录入、客户分级分类、客户画像、联系人管理\n"
            "2. 销售管理：销售线索、商机跟进、销售漏斗、报价与合同管理\n"
            "3. 营销管理：营销活动管理、邮件/短信群发、营销效果分析\n"
            "4. 服务管理：工单系统、客户反馈、SLA管理、知识库\n"
            "5. 数据分析：销售报表、客户分析、业绩看板、预测分析\n"
            "6. 系统集成：与企业邮箱、电话系统、微信等渠道的集成\n"
            "请详细描述每个模块的功能需求和业务流程。"
        ),
        "mode": "free",
    },
    {
        "name": "电商平台",
        "description": "全功能电子商务平台，包含商品管理、订单处理、支付结算、物流跟踪等模块，支持B2C和B2B业务模式。",
        "category": "电商零售",
        "icon": "🛒",
        "prompt": (
            "请帮我设计一套完整的电商平台系统。系统需要包含以下核心模块：\n"
            "1. 商品管理：商品发布、SKU管理、分类管理、品牌管理、商品搜索\n"
            "2. 订单管理：购物车、下单流程、订单状态跟踪、退款/退货处理\n"
            "3. 支付结算：多支付渠道（微信/支付宝/银行卡）、对账管理、结算周期\n"
            "4. 物流管理：发货管理、物流跟踪、快递对接、运费模板\n"
            "5. 用户系统：注册登录、会员等级、积分体系、收货地址管理\n"
            "6. 营销系统：优惠券、秒杀活动、满减促销、拼团功能\n"
            "7. 商家后台：店铺管理、数据统计、评价管理\n"
            "请详细描述每个模块的功能需求、用户交互流程和关键技术方案。"
        ),
        "mode": "free",
    },
    {
        "name": "OA办公",
        "description": "办公自动化系统，集成审批流程、日程管理、公告通知、文档协作等功能，提升企业内部协作效率。",
        "category": "企业管理",
        "icon": "📋",
        "prompt": (
            "请帮我设计一套完整的OA办公自动化系统。系统需要包含以下核心模块：\n"
            "1. 审批流程：自定义审批表单、多级审批流、审批委托、催办提醒\n"
            "2. 日程管理：个人日程、团队日历、会议室预订、日程提醒\n"
            "3. 公告通知：公告发布、通知推送、已读回执、紧急通知\n"
            "4. 文档管理：在线文档编辑、版本控制、权限管理、文档共享\n"
            "5. 考勤管理：打卡签到、请假申请、加班管理、考勤统计\n"
            "6. 通讯录：组织架构、员工信息、部门管理\n"
            "7. 即时通讯：单聊群聊、文件传输、消息通知\n"
            "请详细描述每个模块的功能需求和交互设计。"
        ),
        "mode": "free",
    },
    {
        "name": "BI分析",
        "description": "商业智能分析平台，提供数据接入、可视化报表、仪表盘、自助分析等能力，帮助企业实现数据驱动决策。",
        "category": "数据分析",
        "icon": "📊",
        "prompt": (
            "请帮我设计一套完整的BI商业智能分析平台。系统需要包含以下核心模块：\n"
            "1. 数据接入：多数据源连接（MySQL/PostgreSQL/Excel/API）、数据同步、ETL处理\n"
            "2. 数据建模：数据集管理、维度/指标定义、数据关联、计算字段\n"
            "3. 可视化报表：拖拽式图表设计、20+图表类型、交叉表、地图可视化\n"
            "4. 仪表盘：大屏展示、自由布局、实时数据刷新、全屏展示\n"
            "5. 自助分析：数据探索、筛选联动、下钻分析、导出报表\n"
            "6. 权限管理：数据行列权限、报表共享、发布管理\n"
            "7. 告警监控：指标阈值监控、异常检测、告警通知\n"
            "请详细描述每个模块的功能需求和技术实现方案。"
        ),
        "mode": "free",
    },
    {
        "name": "移动App",
        "description": "移动应用开发项目，涵盖用户体系、消息推送、内容管理、社交互动等通用功能模块，适用于各类移动端产品。",
        "category": "移动开发",
        "icon": "📱",
        "prompt": (
            "请帮我设计一款移动App应用。系统需要包含以下核心模块：\n"
            "1. 用户体系：手机号/微信/Apple登录、用户资料、实名认证、隐私设置\n"
            "2. 首页信息流：个性化推荐、内容瀑布流、搜索功能、分类导航\n"
            "3. 消息系统：系统通知、互动消息、推送通知（APNs/FCM）、消息设置\n"
            "4. 内容管理：图文/视频/短视频发布、内容审核、标签管理\n"
            "5. 社交互动：关注/粉丝、点赞/评论/转发、私信聊天\n"
            "6. 个人中心：个人主页、设置、收藏夹、浏览历史、意见反馈\n"
            "7. 运营后台：用户管理、内容管理、数据统计、活动配置\n"
            "请详细描述每个模块的功能需求、UI交互和技术方案。"
        ),
        "mode": "free",
    },
    {
        "name": "保险系统",
        "description": "保险业务核心系统，覆盖产品配置、投保承保、理赔处理、精算分析等全流程，支撑保险公司数字化转型。",
        "category": "金融保险",
        "icon": "🛡️",
        "prompt": (
            "请帮我设计一套完整的保险业务系统。系统需要包含以下核心模块：\n"
            "1. 产品管理：保险产品配置、费率管理、条款管理、产品上下架\n"
            "2. 投保管理：在线投保、健康告知、核保规则、电子保单\n"
            "3. 承保管理：保单管理、批改/退保、续保管理、保全服务\n"
            "4. 理赔管理：报案登记、理赔审核、损失评估、赔付结算\n"
            "5. 客户管理：客户360视图、家庭保单、客户分群、风险评估\n"
            "6. 代理人管理：代理人招募、业绩考核、佣金计算、培训管理\n"
            "7. 精算分析：风险模型、赔付率分析、准备金计算、产品定价\n"
            "请详细描述每个模块的功能需求、业务规则和合规要求。"
        ),
        "mode": "free",
    },
    {
        "name": "教育培训",
        "description": "在线教育培训平台，包含课程管理、直播教学、考试测评、学习路径等功能，打造完整的在线学习体验。",
        "category": "教育培训",
        "icon": "🎓",
        "prompt": (
            "请帮我设计一套完整的在线教育培训平台。系统需要包含以下核心模块：\n"
            "1. 课程管理：课程创建、章节编排、视频/文档上传、课程定价\n"
            "2. 直播教学：直播课堂、屏幕共享、互动白板、课堂回放\n"
            "3. 学习管理：学习进度、学习路径、学习打卡、学习笔记\n"
            "4. 考试测评：题库管理、在线考试、自动阅卷、成绩分析\n"
            "5. 互动社区：课程讨论、问答社区、学习小组、作业提交\n"
            "6. 讲师中心：讲师入驻、课程管理、收益结算、数据统计\n"
            "7. 运营管理：用户管理、订单管理、优惠活动、数据看板\n"
            "请详细描述每个模块的功能需求和用户体验设计。"
        ),
        "mode": "free",
    },
]


def init_builtin_templates():
    """初始化内置模板——仅在模板不存在时插入。"""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        for tpl in BUILTIN_TEMPLATES:
            # 按 name + is_builtin 判断是否已存在
            row = conn.execute(
                "SELECT id FROM templates WHERE name = ? AND is_builtin = 1",
                (tpl["name"],),
            ).fetchone()
            if row:
                continue
            tid = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO templates
                   (id, name, description, category, icon, prompt, mode, is_builtin, use_count, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, '', ?, ?)""",
                (
                    tid,
                    tpl["name"],
                    tpl["description"],
                    tpl["category"],
                    tpl["icon"],
                    tpl["prompt"],
                    tpl["mode"],
                    now,
                    now,
                ),
            )
        logger.info("内置模板初始化完成")


def list_templates(category: str = "") -> list[dict]:
    """列出模板，支持按 category 过滤。"""
    with get_db() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM templates WHERE category = ? ORDER BY use_count DESC, created_at ASC",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM templates ORDER BY use_count DESC, created_at ASC"
            ).fetchall()
    return [dict(r) for r in rows]


def get_template(template_id: str) -> dict | None:
    """获取单个模板。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
    return dict(row) if row else None


def increment_template_use(template_id: str) -> bool:
    """使用计数 +1，返回是否成功。"""
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE templates SET use_count = use_count + 1, updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), template_id),
        )
    return cur.rowcount > 0
