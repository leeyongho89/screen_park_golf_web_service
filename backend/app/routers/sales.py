from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas, services
from app.database import get_db

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("")
def list_sales(
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    items, total = services.query_sales(db, from_date, to_date, page, size)
    return {
        "items": [schemas.SaleRead.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("", response_model=schemas.SaleRead, status_code=201)
def create_sale(payload: schemas.SaleCreate, db: Session = Depends(get_db)) -> models.Sale:
    return services.create_sale(db, payload)


@router.get("/summary", response_model=schemas.SalesSummary)
def get_sales_summary(from_date: date, to_date: date, db: Session = Depends(get_db)) -> schemas.SalesSummary:
    return services.sales_summary(db, from_date, to_date)


@router.get("/summary/daily", response_model=schemas.SalesSummary)
def get_daily_summary(target_date: date | None = None, db: Session = Depends(get_db)) -> schemas.SalesSummary:
    day = target_date or date.today()
    return services.sales_summary(db, day, day)


@router.get("/summary/monthly", response_model=schemas.SalesSummary)
def get_monthly_summary(
    year: int | None = None,
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
) -> schemas.SalesSummary:
    today = date.today()
    target_year = year or today.year
    target_month = month or today.month
    start = date(target_year, target_month, 1)
    if target_month == 12:
        end = date(target_year + 1, 1, 1)
    else:
        end = date(target_year, target_month + 1, 1)
    from datetime import timedelta

    return services.sales_summary(db, start, end - timedelta(days=1))


@router.post("/{sale_id}/refund", response_model=schemas.SaleRead, status_code=201)
def refund_sale(
    sale_id: int, payload: schemas.SaleRefundRequest, db: Session = Depends(get_db)
) -> models.Sale:
    return services.refund_sale(db, sale_id, payload)
