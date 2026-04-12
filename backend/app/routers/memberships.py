from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas, services
from app.database import get_db

router = APIRouter(prefix="/member-memberships", tags=["member-memberships"])


@router.get("")
def list_member_memberships(
    member_id: int | None = None,
    status: list[str] | None = Query(default=None),
    keyword: str | None = None,
    expiring_days: int | None = Query(default=None, ge=1, le=10000),
    remaining_count_lte: int | None = Query(default=None, ge=0, le=10000),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    items, total = services.query_member_memberships(
        db, member_id, status, keyword, expiring_days, remaining_count_lte, page, size
    )
    return {
        "items": [schemas.MemberMembershipRead.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("", response_model=schemas.MemberMembershipRead, status_code=201)
def create_member_membership(
    payload: schemas.MemberMembershipCreate, db: Session = Depends(get_db)
) -> models.MemberMembership:
    return services.create_member_membership(db, payload)


@router.patch("/{membership_id}/pause", response_model=schemas.MemberMembershipRead)
def pause_membership(
    membership_id: int, payload: schemas.MembershipStatusRequest, db: Session = Depends(get_db)
) -> models.MemberMembership:
    return services.change_membership_status(db, membership_id, "정지", payload)


@router.patch("/{membership_id}/resume", response_model=schemas.MemberMembershipRead)
def resume_membership(
    membership_id: int, payload: schemas.MembershipStatusRequest, db: Session = Depends(get_db)
) -> models.MemberMembership:
    return services.change_membership_status(db, membership_id, "사용중", payload)


@router.post("/{membership_id}/deduct", response_model=schemas.MemberMembershipRead)
def deduct_membership(
    membership_id: int, payload: schemas.MembershipActionRequest, db: Session = Depends(get_db)
) -> models.MemberMembership:
    return services.deduct_membership(db, membership_id, payload)


@router.post("/{membership_id}/adjust", response_model=schemas.MemberMembershipRead)
def adjust_membership(
    membership_id: int, payload: schemas.MembershipAdjustRequest, db: Session = Depends(get_db)
) -> models.MemberMembership:
    return services.adjust_membership(db, membership_id, payload)


@router.patch("/{membership_id}/period", response_model=schemas.MemberMembershipRead)
def adjust_membership_period(
    membership_id: int, payload: schemas.MembershipPeriodAdjustRequest, db: Session = Depends(get_db)
) -> models.MemberMembership:
    return services.adjust_membership_period(db, membership_id, payload)


@router.get("/{membership_id}/usage-logs")
def get_usage_logs(membership_id: int, db: Session = Depends(get_db)) -> dict:
    if not db.get(models.MemberMembership, membership_id):
        services.fail(404, "membership_not_found", "보유 상품을 찾을 수 없습니다.")
    items = db.scalars(
        select(models.MembershipUsageLog)
        .where(models.MembershipUsageLog.member_membership_id == membership_id)
        .order_by(models.MembershipUsageLog.created_at.desc())
    ).all()
    return {"items": [schemas.MembershipUsageLogRead.model_validate(item) for item in items]}
