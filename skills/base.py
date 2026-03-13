"""
Skill 基类
=========
所有文档生成 Skill 的抽象基类。
每个 Skill 负责调用 LLM 生成一种类型的产出物（需求文档、流程图、ER 图等）。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from core.llm_client import call_chat

logger = logging.getLogger("agent_skills.skill_base")


@dataclass
class SkillResult:
    """Skill 执行结果。"""
    skill_name: str
    display_name: str
    output_type: str      # markdown / mermaid / yaml / json
    content: str           # 生成的文档内容
    title: str             # 产出物标题
    success: bool = True
    error: str = ""


class BaseSkill(ABC):
    """
    Skill 抽象基类。

    每个 Skill 子类需实现：
    - name: 英文标识符
    - display_name: 中文显示名
    - description: 功能描述
    - system_prompt: 发给 LLM 的 System Prompt
    - build_user_prompt(): 根据大纲构建 User Prompt
    """

    name: str = ""
    display_name: str = ""
    description: str = ""
    system_prompt: str = ""
    output_type: str = "markdown"

    def build_user_prompt(self, outline: dict, context: str = "") -> str:
        """
        根据需求大纲构建发给 LLM 的用户提示词。
        子类可覆盖此方法以定制提示内容。

        Args:
            outline: 确认后的需求大纲字典
            context: 额外的上下文信息
        """
        project_name = outline.get("project_name", "未命名项目")
        domain = outline.get("domain", "")
        target_users = ", ".join(outline.get("target_users", []))
        business_model = outline.get("business_model", "")
        complexity = outline.get("complexity", "中等")

        modules_text = ""
        for m in outline.get("core_modules", []):
            if isinstance(m, dict):
                modules_text += f"- {m.get('name', '')}: {m.get('description', '')}\n"
            else:
                modules_text += f"- {m}\n"

        features_text = "\n".join(
            f"- {f}" for f in outline.get("feature_list", [])
        )

        tech_text = "\n".join(
            f"- {t}" for t in outline.get("tech_requirements", [])
        )

        return (
            f"## 项目信息\n"
            f"- 项目名称：{project_name}\n"
            f"- 所属领域：{domain}\n"
            f"- 目标用户：{target_users}\n"
            f"- 业务模式：{business_model}\n"
            f"- 复杂度：{complexity}\n\n"
            f"## 核心模块\n{modules_text}\n"
            f"## 功能点列表\n{features_text}\n"
            f"## 技术要求\n{tech_text}\n"
        )

    def execute(self, outline: dict, context: str = "") -> SkillResult:
        """
        执行 Skill：调用 LLM 生成产出物。

        Args:
            outline: 确认后的需求大纲
            context: 额外上下文
        Returns:
            SkillResult 包含生成结果
        """
        logger.info("执行 Skill [%s]: %s", self.name, self.display_name)
        try:
            user_prompt = self.build_user_prompt(outline, context)
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            content = call_chat(messages, temperature=0.3)
            logger.info("Skill [%s] 执行完成，输出长度: %d", self.name, len(content))
            return SkillResult(
                skill_name=self.name,
                display_name=self.display_name,
                output_type=self.output_type,
                content=content,
                title=f"{outline.get('project_name', '')} - {self.display_name}",
                success=True,
            )
        except Exception as exc:
            logger.exception("Skill [%s] 执行失败: %s", self.name, exc)
            return SkillResult(
                skill_name=self.name,
                display_name=self.display_name,
                output_type=self.output_type,
                content="",
                title=self.display_name,
                success=False,
                error=str(exc),
            )
