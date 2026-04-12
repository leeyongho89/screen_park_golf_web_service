from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas, services
from app.database import get_db

router = APIRouter(prefix="/members", tags=["members"])


@router.get("")
def list_members(
    keyword: str | None = None,
    include_inactive: bool = False,
    inactive_only: bool = False,
    sale_date: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    items, total = services.query_members(db, keyword, include_inactive, inactive_only, created_from, created_to, page, size)
    sales_amounts = services.member_sales_amounts(db, [item.id for item in items], sale_date)
    return {
        "items": [
            schemas.MemberListRead(
                **schemas.MemberRead.model_validate(item).model_dump(),
                **sales_amounts.get(item.id, {}),
            )
            for item in items
        ],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("", response_model=schemas.MemberRead, status_code=201)
def create_member(payload: schemas.MemberCreate, db: Session = Depends(get_db)) -> models.Member:
    return services.create_member(db, payload)


@router.get("/{member_id}", response_model=schemas.MemberRead)
def get_member(member_id: int, db: Session = Depends(get_db)) -> models.Member:
    return services.get_member_or_404(db, member_id)


@router.put("/{member_id}", response_model=schemas.MemberRead)
def update_member(member_id: int, payload: schemas.MemberUpdate, db: Session = Depends(get_db)) -> models.Member:
    return services.update_member(db, member_id, payload)


@router.patch("/{member_id}/deactivate", response_model=schemas.MemberRead)
def deactivate_member(member_id: int, payload: schemas.MembershipStatusRequest, db: Session = Depends(get_db)) -> models.Member:
    return services.update_member(
        db,
        member_id,
        schemas.MemberUpdate(is_active=False, operator_name=payload.operator_name),
    )


@router.patch("/{member_id}/restore", response_model=schemas.MemberRead)
def restore_member(member_id: int, payload: schemas.MembershipStatusRequest, db: Session = Depends(get_db)) -> models.Member:
    return services.restore_member(db, member_id, payload)


@router.delete("/{member_id}", status_code=204)
def permanently_delete_member(
    member_id: int, payload: schemas.MembershipStatusRequest | None = None, db: Session = Depends(get_db)
) -> Response:
    services.permanently_delete_member(db, member_id, payload or schemas.MembershipStatusRequest())
    return Response(status_code=204)


@router.get("/{member_id}/sales")
def get_member_sales(
    member_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    services.get_member_or_404(db, member_id)
    stmt = select(models.Sale).where(models.Sale.member_id == member_id).order_by(models.Sale.sale_date.desc())
    all_items = list(db.scalars(stmt).all())
    start = (page - 1) * size
    items = all_items[start : start + size]
    return {
        "items": [schemas.SaleRead.model_validate(item) for item in items],
        "total": len(all_items),
        "page": page,
        "size": size,
    }


@router.get("/{member_id}/memberships")
def get_member_memberships(member_id: int, db: Session = Depends(get_db)) -> dict:
    services.get_member_or_404(db, member_id)
    items = db.scalars(
        select(models.MemberMembership)
        .where(models.MemberMembership.member_id == member_id)
        .order_by(models.MemberMembership.created_at.desc())
    ).all()
    return {"items": [schemas.MemberMembershipRead.model_validate(item) for item in items]}
