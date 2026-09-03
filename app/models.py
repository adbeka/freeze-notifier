from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, field_validator
from sqlmodel import SQLModel, Field

SCOPE_FULL = "full"
SCOPE_PARTIAL = "partial"


def to_naive_utc(dt: datetime) -> datetime:
    """SQLite has no timezone-aware column type, so all datetimes are stored
    naive-UTC and re-tagged with tzinfo=utc on the way out."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
        dt = dt.replace(tzinfo=None)
    return dt


class FreezeWindow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scope_type: str  # "full" | "partial"
    segments_raw: str = ""  # comma-joined segment names, empty when scope_type == full
    start_time: datetime
    end_time: datetime
    comment: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def segments(self) -> list[str]:
        return [s for s in self.segments_raw.split(",") if s]


class FreezeWindowIn(BaseModel):
    scope_type: str
    segments: list[str] = []
    start_time: datetime
    end_time: datetime
    comment: str = ""
    created_by: str = ""

    @field_validator("scope_type")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        if v not in (SCOPE_FULL, SCOPE_PARTIAL):
            raise ValueError(f"scope_type must be '{SCOPE_FULL}' or '{SCOPE_PARTIAL}'")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def normalize_to_naive_utc(cls, v: datetime) -> datetime:
        return to_naive_utc(v)

    @field_validator("end_time")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info):
        start = info.data.get("start_time")
        if start is not None and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class FreezeWindowOut(BaseModel):
    id: int
    scope_type: str
    segments: list[str]
    start_time: datetime
    end_time: datetime
    comment: str
    created_by: str
    created_at: datetime

    @classmethod
    def from_db(cls, w: FreezeWindow) -> "FreezeWindowOut":
        return cls(
            id=w.id,
            scope_type=w.scope_type,
            segments=w.segments,
            start_time=w.start_time.replace(tzinfo=timezone.utc),
            end_time=w.end_time.replace(tzinfo=timezone.utc),
            comment=w.comment,
            created_by=w.created_by,
            created_at=w.created_at.replace(tzinfo=timezone.utc),
        )


class StatusResponse(BaseModel):
    server_time: datetime
    active: bool
    active_windows: list[FreezeWindowOut]
    upcoming_windows: list[FreezeWindowOut]


class FreezeAck(SQLModel, table=True):
    """Audit trail: someone clicked 'Понял(а)' on the status page while a
    window was active. Proof that the person was actually warned, not just
    that a banner was technically displayed somewhere."""
    id: Optional[int] = Field(default=None, primary_key=True)
    window_id: int
    segment: str = ""
    acknowledged_by: str = ""
    acknowledged_at: datetime = Field(default_factory=datetime.utcnow)


class FreezeAckIn(BaseModel):
    window_id: int
    segment: str = ""
    acknowledged_by: str = ""


class FreezeAckOut(BaseModel):
    id: int
    window_id: int
    segment: str
    acknowledged_by: str
    acknowledged_at: datetime

    @classmethod
    def from_db(cls, a: "FreezeAck") -> "FreezeAckOut":
        return cls(
            id=a.id,
            window_id=a.window_id,
            segment=a.segment,
            acknowledged_by=a.acknowledged_by,
            acknowledged_at=a.acknowledged_at.replace(tzinfo=timezone.utc),
        )
