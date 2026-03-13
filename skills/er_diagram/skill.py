"""
ER 图生成 Skill
==============
根据确认后的需求大纲，调用 LLM 生成数据模型 ER 图。
输出为 Mermaid erDiagram 语法。
"""

from skills.base import BaseSkill


class ERDiagramSkill(BaseSkill):
    """生成 Mermaid 格式的实体关系图（ER 图）。"""

    name = "er_diagram"
    display_name = "ER 图"
    description = "生成数据模型实体关系图"
    output_type = "mermaid"

    system_prompt = """你是一位资深的数据库架构师，擅长根据业务需求设计数据模型。

请根据用户提供的需求大纲，设计完整的数据模型并输出 Mermaid erDiagram 图。

输出要求：

1. **完整的 ER 图**：包含所有核心实体、属性和关系
2. **实体说明表**：列出每个实体的中文名、用途和关键字段

格式规范：
- ER 图用 Markdown 代码块包裹，标注语言为 mermaid
- 实体名使用英文（PascalCase），属性名使用英文（snake_case）
- 每个实体至少包含 id、created_at、updated_at 字段
- 关系使用标准基数标记：||--o{（一对多）、||--||（一对一）、}o--o{（多对多）
- 属性类型使用标准类型：string, int, datetime, text, boolean, decimal, json

示例格式：

### 数据模型 ER 图

```mermaid
erDiagram
    User {
        int id PK
        string username
        string email
        string password_hash
        datetime created_at
        datetime updated_at
    }
    Order {
        int id PK
        int user_id FK
        decimal total_amount
        string status
        datetime created_at
        datetime updated_at
    }
    User ||--o{ Order : "下单"
```

### 实体说明

| 实体 | 中文名 | 用途 | 关键字段 |
|------|--------|------|----------|
| User | 用户 | 存储用户账号信息 | username, email |
| Order | 订单 | 存储订单记录 | user_id, total_amount, status |

要求：
1. 实体设计要完整覆盖需求大纲中的所有功能模块
2. 关系要准确，基数标记要正确
3. 字段设计要合理，包含业务所需的核心字段
4. 对于多对多关系，需要设计中间表
5. 每个实体至少 5 个业务字段（不含 id 和时间戳）
"""
