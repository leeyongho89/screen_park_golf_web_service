from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas, services
from app.database import get_db

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.get("")
def list_reservations(target_date: date | None = None, db: Session = Depends(get_db)) -> dict:
    day = target_date or date.today()
    items = services.query_reservations(db, day)
    return {
        "items": [schemas.ReservationRead.model_validate(item) for item in items],
        "total": len(items),
    }


@router.post("", response_model=schemas.ReservationRead, status_code=201)
def create_reservation(payload: schemas.ReservationCreate, db: Session = Depends(get_db)) -> models.Reservation:
    return services.create_reservation(db, payload)


@router.put("/{reservation_id}", response_model=schemas.ReservationRead)
def update_reservation(
    reservation_id: int, payload: schemas.ReservationUpdate, db: Session = Depends(get_db)
) -> models.Reservation:
    return services.update_reservation(db, reservation_id, payload)


@router.patch("/{reservation_id}/cancel", response_model=schemas.ReservationRead)
def cancel_reservation(
    reservation_id: int, payload: schemas.ReservationStatusRequest, db: Session = Depends(get_db)
) -> models.Reservation:
    return services.cancel_reservation(db, reservation_id, payload)
