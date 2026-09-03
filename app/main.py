import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from .database import create_db_and_tables, get_session
from .models import (
    FreezeAck,
    FreezeAckIn,
    FreezeAckOut,
    FreezeWindow,
    FreezeWindowAudit,
    FreezeWindowAuditOut,
    FreezeWindowIn,
    FreezeWindowOut,
    StatusResponse,
)

API_KEY = os.environ.get("FREEZE_API_KEY", "change-me")
UPCOMING_HORIZON = timedelta(hours=2)

# /status/ и /admin/ отдаются этим же приложением на одном origin, поэтому
# кросс-доменные запросы браузеру для них не нужны - CORS-мидлварь была
# лишней открытой поверхностью, а не рабочей необходимостью.
app = FastAPI(title="Network Freeze Notifier")


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


def _now() -> datetime:
    # naive UTC, matching how FreezeWindow.start_time/end_time are stored (see models.to_naive_utc)
    return datetime.utcnow()


def _overlaps_segment(window: FreezeWindow, segment: Optional[str]) -> bool:
    if window.scope_type == "full":
        return True
    if segment is None:
        return True
    return segment in window.segments


def _record_audit(session: Session, w: FreezeWindow, action: str, performed_by: str) -> None:
    session.add(FreezeWindowAudit(
        window_id=w.id,
        action=action,
        scope_type=w.scope_type,
        segments_raw=w.segments_raw,
        start_time=w.start_time,
        end_time=w.end_time,
        comment=w.comment,
        performed_by=performed_by,
    ))
    session.commit()


@app.get("/api/status", response_model=StatusResponse)
def get_status(segment: Optional[str] = None, session: Session = Depends(get_session)):
    now = _now()
    windows = session.exec(select(FreezeWindow)).all()

    active = [
        w for w in windows
        if w.start_time <= now <= w.end_time and _overlaps_segment(w, segment)
    ]
    upcoming = [
        w for w in windows
        if now < w.start_time <= now + UPCOMING_HORIZON and _overlaps_segment(w, segment)
    ]

    return StatusResponse(
        server_time=now.replace(tzinfo=timezone.utc),
        active=len(active) > 0,
        active_windows=[FreezeWindowOut.from_db(w) for w in active],
        upcoming_windows=[FreezeWindowOut.from_db(w) for w in upcoming],
    )


@app.get("/api/windows", response_model=list[FreezeWindowOut])
def list_windows(session: Session = Depends(get_session)):
    windows = session.exec(select(FreezeWindow).order_by(FreezeWindow.start_time.desc())).all()
    return [FreezeWindowOut.from_db(w) for w in windows]


@app.get("/api/windows/{window_id}", response_model=FreezeWindowOut)
def get_window(window_id: int, session: Session = Depends(get_session)):
    w = session.get(FreezeWindow, window_id)
    if w is None:
        raise HTTPException(status_code=404, detail="window not found")
    return FreezeWindowOut.from_db(w)


@app.post("/api/windows", response_model=FreezeWindowOut, dependencies=[Depends(require_api_key)])
def create_window(payload: FreezeWindowIn, session: Session = Depends(get_session)):
    if payload.scope_type == "partial" and not payload.segments:
        raise HTTPException(status_code=422, detail="partial freeze requires at least one segment")

    w = FreezeWindow(
        scope_type=payload.scope_type,
        segments_raw=",".join(payload.segments),
        start_time=payload.start_time,
        end_time=payload.end_time,
        comment=payload.comment,
        created_by=payload.created_by,
    )
    session.add(w)
    session.commit()
    session.refresh(w)
    _record_audit(session, w, "created", payload.created_by)
    return FreezeWindowOut.from_db(w)


@app.put("/api/windows/{window_id}", response_model=FreezeWindowOut, dependencies=[Depends(require_api_key)])
def update_window(window_id: int, payload: FreezeWindowIn, session: Session = Depends(get_session)):
    w = session.get(FreezeWindow, window_id)
    if w is None:
        raise HTTPException(status_code=404, detail="window not found")
    if payload.scope_type == "partial" and not payload.segments:
        raise HTTPException(status_code=422, detail="partial freeze requires at least one segment")

    w.scope_type = payload.scope_type
    w.segments_raw = ",".join(payload.segments)
    w.start_time = payload.start_time
    w.end_time = payload.end_time
    w.comment = payload.comment
    w.created_by = payload.created_by
    session.add(w)
    session.commit()
    session.refresh(w)
    _record_audit(session, w, "updated", payload.created_by)
    return FreezeWindowOut.from_db(w)


@app.delete("/api/windows/{window_id}", status_code=204, dependencies=[Depends(require_api_key)])
def delete_window(window_id: int, deleted_by: str = "", session: Session = Depends(get_session)):
    w = session.get(FreezeWindow, window_id)
    if w is None:
        raise HTTPException(status_code=404, detail="window not found")
    _record_audit(session, w, "deleted", deleted_by)
    session.delete(w)
    session.commit()


@app.post("/api/ack", response_model=FreezeAckOut)
def create_ack(payload: FreezeAckIn, session: Session = Depends(get_session)):
    # No API key required - this is the engineer confirming, not an admin
    # write. Still validate the window actually exists so the audit log
    # can't be filled with acks for made-up ids.
    window = session.get(FreezeWindow, payload.window_id)
    if window is None:
        raise HTTPException(status_code=404, detail="window not found")

    ack = FreezeAck(
        window_id=payload.window_id,
        segment=payload.segment,
        acknowledged_by=payload.acknowledged_by,
    )
    session.add(ack)
    session.commit()
    session.refresh(ack)
    return FreezeAckOut.from_db(ack)


@app.get("/api/acks", response_model=list[FreezeAckOut], dependencies=[Depends(require_api_key)])
def list_acks(window_id: Optional[int] = None, session: Session = Depends(get_session)):
    query = select(FreezeAck).order_by(FreezeAck.acknowledged_at.desc())
    if window_id is not None:
        query = query.where(FreezeAck.window_id == window_id)
    acks = session.exec(query).all()
    return [FreezeAckOut.from_db(a) for a in acks]


@app.get("/api/audit", response_model=list[FreezeWindowAuditOut], dependencies=[Depends(require_api_key)])
def list_audit(window_id: Optional[int] = None, session: Session = Depends(get_session)):
    query = select(FreezeWindowAudit).order_by(FreezeWindowAudit.performed_at.desc())
    if window_id is not None:
        query = query.where(FreezeWindowAudit.window_id == window_id)
    entries = session.exec(query).all()
    return [FreezeWindowAuditOut.from_db(e) for e in entries]


app.mount("/admin", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="admin")

STATUS_PAGE_DIR = os.path.join(os.path.dirname(__file__), "status_page")
app.mount("/status", StaticFiles(directory=STATUS_PAGE_DIR, html=True), name="status")
