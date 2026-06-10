"""业务域 Pydantic schema（请求/响应）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ============== Property（房源） ==============


class PropertyCreate(BaseModel):
    """创建房源请求。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "community": "望京西园",
            "layout": "3室1厅",
            "area": 95.5,
            "total_price": 4200000,
            "tags": ["满五唯一", "近地铁"],
            "images": ["https://..."],
            "viewing_time": "工作日晚上+周末",
            "source_url": None,
            "is_verified": True,
        }
    })

    community: str = Field(..., min_length=1, max_length=128)
    layout: str = Field(..., min_length=1, max_length=32)
    area: float = Field(..., gt=0)
    total_price: float = Field(..., gt=0)
    tags: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    viewing_time: str = Field(..., min_length=1)
    source_url: str | None = None
    is_verified: bool = False


class PropertyUpdate(BaseModel):
    """更新房源请求（所有字段可选）。"""

    community: str | None = None
    layout: str | None = None
    area: float | None = Field(default=None, gt=0)
    total_price: float | None = Field(default=None, gt=0)
    tags: list[str] | None = None
    images: list[str] | None = None
    viewing_time: str | None = None
    is_verified: bool | None = None


class PropertyResponse(BaseModel):
    """房源响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    seller_id: int
    community: str
    layout: str
    area: float
    total_price: float
    tags: list[str]
    images: list[str]
    viewing_time: str
    source_url: str | None
    is_verified: bool
    status: str
    created_at: datetime


# ============== Demand（需求） ==============


class DemandCreate(BaseModel):
    """发布需求请求。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "district": "朝阳区",
            "price_min": 3500000,
            "price_max": 4500000,
            "layouts": ["2室1厅", "3室1厅"],
            "qualification": "首套",
            "viewing_time": ["工作日晚上", "周末"],
            "source_url": None,
        }
    })

    district: str = Field(..., min_length=1, max_length=64)
    price_min: float = Field(..., gt=0)
    price_max: float = Field(..., gt=0)
    layouts: list[str] = Field(default_factory=list)
    qualification: str = Field(default="不限")
    viewing_time: list[str] = Field(default_factory=list)
    source_url: str | None = None


class DemandResponse(BaseModel):
    """需求响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    buyer_id: int
    district: str
    price_min: float
    price_max: float
    layouts: list[str]
    qualification: str
    viewing_time: list[str]
    source_url: str | None
    status: str
    summary: str | None
    created_at: datetime


# ============== Recommendation（推荐） ==============


class SellerMatch(BaseModel):
    """单个卖方匹配结果。"""

    rank: int
    match_score: float
    seller: dict  # 脱敏用户信息
    matched_properties: list[dict]  # 简化字段（id/community/layout/area/total_price/tags/images）


class RecommendationResponse(BaseModel):
    """推荐响应。"""

    demand_id: int
    sellers: list[SellerMatch]


# ============== Invitation（邀请） ==============


class InvitationCreate(BaseModel):
    """发起邀请请求。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {"demand_id": 20001, "seller_id": 10001, "note": "客户总价 400-450w"}
    })

    demand_id: int
    seller_id: int
    note: str | None = None


class InvitationResponse(BaseModel):
    """邀请响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    demand_id: int
    buyer_id: int
    seller_id: int
    status: str
    expired_at: datetime
    responded_at: datetime | None
    proposal_deadline: datetime | None
    reject_reason: str | None
    note: str | None
    created_at: datetime


class InvitationAcceptResponse(BaseModel):
    """邀请接单响应（含方案截止时间）。"""

    invitation_id: int
    status: str
    proposal_deadline: datetime


# ============== Proposal（方案） ==============


class ProposalCreate(BaseModel):
    """提交合作方案请求。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "content": "契合点：1) 总价匹配 2) 业主诚心 3) 业主配合度高",
            "fit_points": "总价 420w 在客户预算 400-450w 范围内",
            "viewing_suggestion": "建议周五晚 8 点看房",
            "owner_situation": "业主自住，新房已购 3 月，急售",
        }
    })

    content: str = Field(..., min_length=20)
    fit_points: str | None = None
    viewing_suggestion: str | None = None
    owner_situation: str | None = None


class ProposalResponse(BaseModel):
    """方案响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    invitation_id: int
    content: str
    fit_points: str | None
    viewing_suggestion: str | None
    owner_situation: str | None
    submitted_at: datetime
    confirmed_at: datetime | None
    declined_at: datetime | None
    decline_reason: str | None


# ============== Cooperation（合作） ==============


class CooperationResponse(BaseModel):
    """合作响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    invitation_id: int
    buyer_id: int
    seller_id: int
    status: str
    memo_content: str
    signed_at: datetime
    closed_at: datetime | None
    close_reason: str | None
    buyer_reviewed: bool
    seller_reviewed: bool


# ============== Review（评价） ==============


class ReviewCreate(BaseModel):
    """评价请求。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "rating": 5,
            "comment": "响应快，方案专业",
            "tags": ["响应及时", "流程规范"],
            "is_anonymous": False,
        }
    })

    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None
    tags: list[str] | None = None
    is_anonymous: bool = False


class ReviewResponse(BaseModel):
    """评价响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cooperation_id: int
    reviewer_id: int
    reviewee_id: int
    rating: int
    comment: str | None
    tags: list[str] = Field(default_factory=list)
    is_anonymous: bool
    created_at: datetime


# ============== User（用户） ==============


class UserResponse(BaseModel):
    """当前用户完整信息（含信用分统计）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str | None
    avatar_url: str | None
    credit_score: float
    rating_avg: float
    rating_count: int
    activity_count_30d: int
    completed_count: int
    is_verified: bool
    status: str
    credit_score_updated_at: datetime | None = None


class UserStatsResponse(BaseModel):
    """用户业务数据统计（个人中心展示用）。"""

    model_config = ConfigDict(from_attributes=True)

    # 业务数据
    demand_count: int        # 发布的有效需求数
    property_count: int      # 发布的有效房源数
    cooperation_count: int   # 进行中合作数（handshaked / in_progress）
    completed_count: int     # 已完成合作数
    review_given_count: int  # 我发出的评价数
    review_received_count: int  # 我收到的评价数

    # 信用分
    credit_score: float
    rating_avg: float
    rating_count: int
    activity_count_30d: int
