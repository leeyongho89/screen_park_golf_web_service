from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas, services
from app.database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=schemas.DashboardSummary)
def get_dashboard(
    new_member_days: int = Query(default=1, ge=1, le=10000),
    sales_days: int = Query(default=1, ge=1, le=10000),
    expiring_days: int = Query(default=7, ge=1, le=10000),
    low_remaining_count: int = Query(default=3, ge=0, le=10000),
    db: Session = Depends(get_db),
) -> schemas.DashboardSummary:
    return services.dashboard_summary(db, new_member_days, sales_days, expiring_days, low_remaining_count)
