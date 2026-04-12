from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas, services
from app.database import get_db

router = APIRouter(prefix="/membership-products", tags=["membership-products"])


@router.get("")
def list_products(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(models.MembershipProduct)
    if not include_inactive:
        stmt = stmt.where(models.MembershipProduct.is_active.is_(True))
    items = db.scalars(
        stmt.order_by(models.MembershipProduct.is_active.desc(), models.MembershipProduct.product_type, models.MembershipProduct.name)
    ).all()
    return {"items": [schemas.MembershipProductRead.model_validate(item) for item in items]}


@router.post("", response_model=schemas.MembershipProductRead, status_code=201)
def create_product(payload: schemas.MembershipProductCreate, db: Session = Depends(get_db)) -> models.MembershipProduct:
    return services.create_product(db, payload)


@router.put("/{product_id}", response_model=schemas.MembershipProductRead)
def update_product(
    product_id: int, payload: schemas.MembershipProductUpdate, db: Session = Depends(get_db)
) -> models.MembershipProduct:
    return services.update_product(db, product_id, payload)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> None:
    services.delete_product(db, product_id)
