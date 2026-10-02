from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["daily_log", "snag", "variation"]
Severity = Literal["Low", "Medium", "High", "Critical"]


class IngestResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: Category
    summary_english: str = Field(min_length=1, max_length=10_000)
    weather_summary: str = Field(default="Unknown", max_length=120)
    headcount: int = Field(default=0, ge=0, le=100_000)
    trade_assigned: str = Field(default="General", max_length=120)
    severity: Severity = "Low"
    delay_hours: float = Field(default=0.0, ge=0, le=100_000)
    cost_impact_flag: bool = False
    estimated_cost: float = Field(default=0.0, ge=0, le=1_000_000_000)


class IngestResponse(BaseModel):
    status: Literal["success"] = "success"
    category: Category
    result: IngestResult
    title: str | None = None
    source: str | None = None