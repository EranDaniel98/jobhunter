from pydantic import BaseModel


class FunnelResponse(BaseModel):
    drafted: int = 0
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    replied: int = 0
    bounced: int = 0


class OutreachStatsResponse(BaseModel):
    total_sent: int = 0
    total_opened: int = 0
    total_replied: int = 0
    open_rate: float = 0.0
    reply_rate: float = 0.0
    by_channel: dict = {}


class PipelineStatsResponse(BaseModel):
    suggested: int = 0
    approved: int = 0
    rejected: int = 0
    researched: int = 0
    contacted: int = 0


class AnalyticsInsightResponse(BaseModel):
    id: str
    insight_type: str
    title: str
    body: str
    severity: str
    data: dict | None = None
    is_read: bool = False
    created_at: str

    model_config = {"from_attributes": True}


class AnalyticsInsightListResponse(BaseModel):
    insights: list[AnalyticsInsightResponse]
    total: int


class AnalyticsDashboardResponse(BaseModel):
    funnel: FunnelResponse
    outreach: OutreachStatsResponse
    pipeline: PipelineStatsResponse
    insights: list[AnalyticsInsightResponse]
