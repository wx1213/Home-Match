"""LLM 客户端 - 统一封装（支持多 provider）。

支持的 provider:
- minimax (本项目使用，性价比高)
- deepseek
- openai
- claude (Anthropic，单独接口)

任务路由:
- 推荐解释 / 方案生成 / 链接校验 → minimax
- 评价异常检测 / 复杂语义 → claude / gpt-4o
- 任何调用都走统一接口，统一处理重试、降级、限流
"""

from __future__ import annotations

import asyncio
import json
import re
from enum import Enum
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.errors import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMTask(str, Enum):
    """LLM 任务类型 - 用于路由到不同模型。"""

    RECOMMENDATION_EXPLAIN = "recommendation_explain"  # 推荐解释
    PROPOSAL_GENERATE = "proposal_generate"  # 方案生成
    LINK_VALIDATE = "link_validate"  # 链接校验
    REVIEW_ANALYZE = "review_analyze"  # 评价异常检测
    DEMAND_SUMMARY = "demand_summary"  # 需求摘要
    GENERAL = "general"  # 通用


# ============== 月度预算控制 ==============

class LLMBudget:
    """LLM 月度预算控制（[D-008]）。"""

    def __init__(self):
        self.monthly_input_tokens = 0
        self.monthly_output_tokens = 0

    def record(self, input_tokens: int, output_tokens: int) -> None:
        self.monthly_input_tokens += input_tokens
        self.monthly_output_tokens += output_tokens

    @property
    def estimated_cost_cny(self) -> float:
        """粗略估算成本（DeepSeek-V3 定价）。"""
        # DeepSeek-V3: ¥0.001/1k input, ¥0.002/1k output
        return (
            self.monthly_input_tokens * 0.001 / 1000
            + self.monthly_output_tokens * 0.002 / 1000
        )

    def is_over_soft_cap(self) -> bool:
        return self.estimated_cost_cny >= settings.llm_soft_cap

    def is_over_hard_cap(self) -> bool:
        return self.estimated_cost_cny >= settings.llm_hard_cap


# 全局预算实例（MVP: 内存中；二期: 持久化到 Redis）
_budget = LLMBudget()


def get_budget_status() -> dict:
    """获取预算状态（用于管理接口）。"""
    return {
        "input_tokens": _budget.monthly_input_tokens,
        "output_tokens": _budget.monthly_output_tokens,
        "estimated_cost_cny": round(_budget.estimated_cost_cny, 4),
        "soft_cap_cny": settings.llm_soft_cap,
        "hard_cap_cny": settings.llm_hard_cap,
        "over_soft_cap": _budget.is_over_soft_cap(),
        "over_hard_cap": _budget.is_over_hard_cap(),
    }


# ============== LLM 客户端 ==============

class LLMClient:
    """统一 LLM 客户端（支持多 provider）。"""

    def __init__(self):
        self.provider = settings.llm_provider
        self.timeout = 30.0
        
        # 根据 provider 选择配置
        if self.provider == "minimax":
            self.base_url = settings.minimax_base_url
            self.api_key = settings.minimax_api_key
            self.group_id = settings.minimax_group_id
        elif self.provider == "deepseek":
            self.base_url = settings.deepseek_base_url
            self.api_key = settings.deepseek_api_key
            self.group_id = ""
        elif self.provider == "openai":
            self.base_url = settings.openai_base_url
            self.api_key = settings.openai_api_key
            self.group_id = ""
        else:
            # 默认使用 deepseek
            self.base_url = settings.deepseek_base_url
            self.api_key = settings.deepseek_api_key
            self.group_id = ""
        
        # 兼容：base_url 可能包含 /v1，也可能不包含
        self.base_url_normalized = self.base_url.rstrip('/')
        if self.base_url_normalized.endswith('/v1'):
            self.base_url_normalized = self.base_url_normalized[:-3]

    def _get_model_for_task(self, task: LLMTask) -> str:
        """根据任务类型路由到合适的模型。"""
        if self.provider == "minimax":
            return "abab5.5-chat"
        elif self.provider == "deepseek":
            return "deepseek-chat"
        elif self.provider == "openai":
            return "gpt-3.5-turbo"
        return "deepseek-chat"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[dict[str, str]],
        task: LLMTask = LLMTask.GENERAL,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        """调用 LLM 完成对话。"""
        # 硬上限检查（[D-008]）
        if _budget.is_over_hard_cap():
            logger.warning("LLM hard cap exceeded, falling back to rule-based")
            raise LLMError("AI 服务本月预算已用完，请联系管理员")

        if not self.api_key:
            # Mock 模式（无 key）：返回固定响应，方便开发
            logger.warning("LLM api_key not configured, returning mock response")
            return self._mock_response(task, messages)

        model = self._get_model_for_task(task)
        
        # 根据 provider 构建不同的请求参数
        if self.provider == "minimax":
            # Minimax API 格式
            url = f"{self.base_url_normalized}/v1/text/chatcompletion"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
                "api_key": self.api_key,
            }
            if self.group_id:
                payload["group_id"] = self.group_id
        else:
            # OpenAI/DeepSeek 格式
            url = f"{self.base_url_normalized}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    logger.error(
                        "LLM API error",
                        extra={"status": resp.status_code, "body": resp.text[:500]},
                    )
                    raise LLMError(f"LLM API error: {resp.status_code}")
                data = resp.json()
                
                # 解析响应（不同 provider 响应格式不同）
                if self.provider == "minimax":
                    content = data.get("reply", "")
                    usage = data.get("usage", {})
                else:
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})

                # 记录 token 用量
                _budget.record(
                    input_tokens=usage.get("prompt_tokens", usage.get("input_tokens", 0)),
                    output_tokens=usage.get("completion_tokens", usage.get("output_tokens", 0)),
                )
                logger.info(
                    "LLM call success",
                    extra={
                        "task": task.value,
                        "model": model,
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "cost_cny": round(_budget.estimated_cost_cny, 4),
                    },
                )
                return content
        except httpx.HTTPError as e:
            logger.error("LLM call failed", extra={"error": str(e)})
            raise LLMError(f"AI 服务调用失败: {e}")

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        task: LLMTask = LLMTask.GENERAL,
        **kwargs,
    ) -> dict[str, Any]:
        """调用 LLM 并返回 JSON 解析结果。

        自动剥离 <tool_call>... Serena: 块（minimax 等模型会附加）。
        """
        content = await self.complete(messages, task, json_mode=True, **kwargs)
        # 剥离 <tool_call>... Serena: 块
        content_clean = re.sub(r"<tool_call>.*? Serena:", "", content, flags=re.DOTALL).strip()
        # 也试试只取 ```json {...} ``` 代码块
        if not content_clean.startswith("{"):
            json_match = re.search(r"\{.*\}", content_clean, flags=re.DOTALL)
            if json_match:
                content_clean = json_match.group(0)
        try:
            return json.loads(content_clean)
        except json.JSONDecodeError as e:
            logger.error(
                "LLM JSON parse failed",
                extra={"raw_content": content[:200], "cleaned": content_clean[:200]},
            )
            raise LLMError(f"AI 响应非合法 JSON: {e}")

    def _mock_response(self, task: LLMTask, messages: list[dict[str, str]]) -> str:
        """Mock 响应（无 API key 时使用，方便本地开发）。"""
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        if task == LLMTask.PROPOSAL_GENERATE:
            return (
                "【Mock 方案】基于您的需求，我们为您匹配到合适的房源。"
                "业主诚心出售，看房时间灵活，建议尽快安排实地查看。"
                "（此为 Mock 响应，未调用真实 LLM）"
            )
        elif task == LLMTask.RECOMMENDATION_EXPLAIN:
            return (
                "【Mock 解释】该推荐基于区域、价格、户型、卖方信用分等多维匹配。\n"
                "（此为 Mock 响应，未调用真实 LLM）"
            )
        elif task == LLMTask.REVIEW_ANALYZE:
            return json.dumps({
                "is_anomaly": False,
                "reason": "Mock: 正常评价",
                "confidence": 0.95,
            })
        elif task == LLMTask.DEMAND_SUMMARY:
            return "【Mock 摘要】客户需求清晰，建议匹配同区域、相近价位的房源。"
        else:
            return f"【Mock 响应】收到消息: {last_user_msg[:50]}"


# 全局单例
llm_client = LLMClient()


# ============== 业务级便捷方法 ==============

async def generate_proposal(
    demand_summary: str,
    property_info: dict,
) -> str:
    """生成合作方案（卖方辅助）。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是 HomeMatch 平台的 AI 助手，帮助房产经纪人快速生成合作方案。"
                "输出要专业、简洁、3 段以内。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"需求摘要：{demand_summary}\n\n"
                f"匹配房源：{property_info.get('community')}，"
                f"{property_info.get('layout')}, "
                f"{property_info.get('area')}㎡, "
                f"¥{property_info.get('total_price', 0)/10000:.0f}万\n\n"
                "请生成一段 100-200 字的合作方案，包含契合点、看房建议、业主情况三段。"
            ),
        },
    ]
    return await llm_client.complete(messages, task=LLMTask.PROPOSAL_GENERATE)


async def explain_recommendation(
    demand: dict,
    seller: dict,
) -> str:
    """解释为什么推荐这个卖方。"""
    messages = [
        {
            "role": "system",
            "content": "你是 HomeMatch 平台的 AI 助手，用一句话（30 字内）解释推荐理由。",
        },
        {
            "role": "user",
            "content": (
                f"需求：{demand.get('district')} {int(demand.get('price_min', 0)/10000)}-{int(demand.get('price_max', 0)/10000)}万\n"
                f"卖方：{seller.get('display_name')}，信用分 {seller.get('credit_score')}\n"
                "为什么推荐？"
            ),
        },
    ]
    return await llm_client.complete(messages, task=LLMTask.RECOMMENDATION_EXPLAIN)


async def analyze_review(
    rating: int,
    comment: str | None,
) -> dict:
    """评价异常检测（刷分/恶意/模板化）。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是评价审核 AI。判断评价是否异常（刷分、恶意、模板化好评）。"
                "返回 JSON: {\"is_anomaly\": bool, \"reason\": str, \"confidence\": float}"
            ),
        },
        {
            "role": "user",
            "content": f"评分: {rating}/5\n评论: {comment or '(无)'}",
        },
    ]
    return await llm_client.complete_json(messages, task=LLMTask.REVIEW_ANALYZE)
