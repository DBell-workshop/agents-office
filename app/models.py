from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


TaskStatus = Literal["pending", "running", "succeeded", "failed"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


class CourseCreateRequest(BaseModel):
    product_id: str
    product_name: str
    objective: str
    required_points: list[str] = Field(default_factory=list)
    product_facts: dict[str, str] = Field(default_factory=dict)


class GenerateContentRequest(BaseModel):
    script_style: str = "natural"
    scene: str = "in_store"
    language: str = "zh-CN"


class TrainingAttemptCreateRequest(BaseModel):
    course_id: str
    user_id: str
    audio_url: Optional[str] = None
    mock_transcript: Optional[str] = None


class EvaluateAttemptRequest(BaseModel):
    rubric_version: str = "v1"


class ComparisonTarget(BaseModel):
    platform: str
    url: str


class ComparisonTaskCreateRequest(BaseModel):
    source_product_id: str
    source_product_name: str
    targets: list[ComparisonTarget]


class ComparisonRunRequest(BaseModel):
    template_version: str = "default_v1"


class TaskRecord(BaseModel):
    task_id: str
    trace_id: str
    task_type: str
    status: TaskStatus = "pending"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    input: dict[str, Any] = Field(default_factory=dict)
    output: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class CourseRecord(BaseModel):
    course_id: str
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    product_id: str
    product_name: str
    objective: str
    required_points: list[str] = Field(default_factory=list)
    product_facts: dict[str, str] = Field(default_factory=dict)
    content_version: int = 0
    latest_content: Optional[dict[str, Any]] = None


class TrainingAttemptRecord(BaseModel):
    attempt_id: str
    course_id: str
    user_id: str
    created_at: str = Field(default_factory=now_iso)
    audio_url: Optional[str] = None
    mock_transcript: Optional[str] = None


class ComparisonTaskRecord(BaseModel):
    comparison_task_id: str
    source_product_id: str
    source_product_name: str
    targets: list[dict[str, str]]
    created_at: str = Field(default_factory=now_iso)


class ApiEnvelope(BaseModel):
    trace_id: str
    request_id: str
    data: dict[str, Any]
    error: Optional[str] = None


# ================================================================
# 商品数据接入（外部采集系统 → 本系统）
# ================================================================


class ProductImage(BaseModel):
    """商品图片。"""
    url: str
    type: str = "main"  # main / detail / sku / video_cover


class ProductSpec(BaseModel):
    """商品规格项。"""
    name: str
    value: str


class ProductImportItem(BaseModel):
    """单个商品的标准化数据结构 — 外部采集系统按此格式推送。"""
    product_id: str = Field(description="平台侧商品ID")
    platform: str = Field(description="来源平台：京东/淘宝/拼多多/抖音/其他")
    name: str = Field(description="商品标题")
    brand: Optional[str] = None
    price: Optional[float] = Field(default=None, description="当前售价")
    original_price: Optional[float] = Field(default=None, description="原价/划线价")
    url: Optional[str] = Field(default=None, description="商品详情页链接")
    shop_name: Optional[str] = None
    category: Optional[str] = Field(default=None, description="商品类目")
    images: list[ProductImage] = Field(default_factory=list)
    video_url: Optional[str] = Field(default=None, description="商品主视频链接")
    specs: list[ProductSpec] = Field(default_factory=list, description="规格参数")
    description: Optional[str] = Field(default=None, description="商品描述文本")
    promotions: list[str] = Field(default_factory=list, description="促销信息")
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    review_count: Optional[int] = Field(default=None, ge=0)
    sales_count: Optional[int] = Field(default=None, ge=0, description="销量")
    extra: dict[str, Any] = Field(default_factory=dict, description="扩展字段，按需传入")


class ProductImportRequest(BaseModel):
    """批量商品数据导入请求。"""
    source: str = Field(description="数据来源标识，如 'jd_crawler', 'manual', 'api_partner'")
    products: list[ProductImportItem] = Field(min_length=1)
    batch_id: Optional[str] = Field(default=None, description="外部批次号，用于去重/追溯")
