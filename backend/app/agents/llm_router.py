"""LLM API 路由 - 暴露给前端的 AI 能力接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.llm_client import (
    analyze_review,
    explain_recommendation,
    generate_proposal,
    get_budget_status,
    llm_client,
)
from app.domains.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import APIResponse

router = APIRouter(prefix="/ai", tags=["AI 能力"])


# ============== 请求模型 ==============


class ProposalGenRequest(BaseModel):
    """生成合作方案请求。"""

    demand_summary: str
    property_info: dict


class RecommendExplainRequest(BaseModel):
    """推荐解释请求。"""

    demand: dict
    seller: dict


class ReviewAnalyzeRequest(BaseModel):
    """评价异常检测请求。"""

    rating: int
    comment: str | None = None


# ============== 接口 ==============


@router.post("/generate-proposal", summary="AI 生成合作方案")
async def api_generate_proposal(
    body: ProposalGenRequest,
    user: User = Depends(get_current_user),
) -> APIResponse[str]:
    """AI 辅助卖方生成合作方案。"""
    text = await generate_proposal(body.demand_summary, body.property_info)
    return APIResponse(data=text)


@router.post("/explain-recommendation", summary="AI 解释推荐理由")
async def api_explain_recommendation(
    body: RecommendExplainRequest,
    user: User = Depends(get_current_user),
) -> APIResponse[str]:
    """AI 一句话解释为什么推荐这个卖方。"""
    text = await explain_recommendation(body.demand, body.seller)
    return APIResponse(data=text)


@router.post("/analyze-review", summary="AI 评价异常检测")
async def api_analyze_review(
    body: ReviewAnalyzeRequest,
    user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    """AI 检测评价是否异常（刷分/恶意/模板化）。"""
    result = await analyze_review(body.rating, body.comment)
    return APIResponse(data=result)


@router.get("/budget", summary="LLM 月度预算状态")
async def api_budget_status(
    user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    """查看本月 LLM 用量与预算。"""
    return APIResponse(data=get_budget_status())


@router.get("/health", summary="AI 服务健康检查")
async def api_health() -> APIResponse[dict]:
    """检查 LLM 客户端是否配置好。"""
    return APIResponse(
        data={
            "configured": bool(llm_client.api_key),
            "base_url": llm_client.base_url,
            "mode": "live" if llm_client.api_key else "mock",
        }
    )
