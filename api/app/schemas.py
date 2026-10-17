from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class FactoryReportRequest(BaseModel):
    plant: Optional[str] = Field(None, description="Plant name; omit for all plants")
    days: int = Field(7, ge=1, le=90)
    background: bool = Field(False, description="Return immediately with a run_id")


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    max_sources: int = Field(5, ge=1, le=10)
    background: bool = False


class RunAccepted(BaseModel):
    run_id: str
    status: str


class MetricIn(BaseModel):
    plant: str
    line_name: str
    shift_date: date
    shift: Literal["A", "B", "C"]
    units_produced: int = Field(..., ge=0)
    units_defective: int = Field(0, ge=0)
    downtime_minutes: int = Field(0, ge=0)
    downtime_reason: Optional[str] = None


class MetricsBatch(BaseModel):
    metrics: list[MetricIn] = Field(..., min_length=1, max_length=1000)


class DocumentIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
