from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import schemas, services
from app.database import get_db

router = APIRouter(prefix="/sms", tags=["sms"])


@router.get("/monthly-billing", response_model=schemas.SmsMonthlyBillingRead)
def get_sms_monthly_billing(month: str | None = Query(default=None)) -> schemas.SmsMonthlyBillingRead:
    return services.get_sms_monthly_billing(month=month)


@router.get("/groups")
def list_sms_groups(db: Session = Depends(get_db)) -> dict:
    items = services.list_sms_groups(db)
    return {"items": [schemas.SmsGroupRead.model_validate(item) for item in items]}


@router.post("/groups", response_model=schemas.SmsGroupRead, status_code=201)
def create_sms_group(payload: schemas.SmsGroupCreate, db: Session = Depends(get_db)) -> schemas.SmsGroupRead:
    return schemas.SmsGroupRead.model_validate(services.create_sms_group(db, payload))


@router.put("/groups/{group_id}", response_model=schemas.SmsGroupRead)
def update_sms_group(group_id: int, payload: schemas.SmsGroupUpdate, db: Session = Depends(get_db)) -> schemas.SmsGroupRead:
    return schemas.SmsGroupRead.model_validate(services.update_sms_group(db, group_id, payload))


@router.delete("/groups/{group_id}", status_code=204)
def delete_sms_group(group_id: int, db: Session = Depends(get_db)) -> Response:
    services.delete_sms_group(db, group_id)
    return Response(status_code=204)


@router.get("/templates")
def list_sms_templates(db: Session = Depends(get_db)) -> dict:
    items = services.list_sms_templates(db)
    return {"items": [schemas.SmsTemplateRead.model_validate(item) for item in items]}


@router.post("/templates", response_model=schemas.SmsTemplateRead, status_code=201)
def create_sms_template(payload: schemas.SmsTemplateCreate, db: Session = Depends(get_db)) -> schemas.SmsTemplateRead:
    return schemas.SmsTemplateRead.model_validate(services.create_sms_template(db, payload))


@router.put("/templates/{template_id}", response_model=schemas.SmsTemplateRead)
def update_sms_template(
    template_id: int, payload: schemas.SmsTemplateUpdate, db: Session = Depends(get_db)
) -> schemas.SmsTemplateRead:
    return schemas.SmsTemplateRead.model_validate(services.update_sms_template(db, template_id, payload))


@router.delete("/templates/{template_id}", status_code=204)
def delete_sms_template(template_id: int, db: Session = Depends(get_db)) -> Response:
    services.delete_sms_template(db, template_id)
    return Response(status_code=204)


@router.post("/recipients/preview", response_model=schemas.SmsPreviewResponse)
def preview_sms_recipients(payload: schemas.SmsPreviewRequest, db: Session = Depends(get_db)) -> schemas.SmsPreviewResponse:
    return services.preview_sms_recipients(db, payload)


@router.post("/send", response_model=schemas.SmsMessageRead, status_code=201)
def send_sms_message(payload: schemas.SmsSendRequest, db: Session = Depends(get_db)) -> schemas.SmsMessageRead:
    return schemas.SmsMessageRead.model_validate(services.send_sms_message(db, payload))


@router.get("/schedules")
def list_sms_schedules(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    items, total = services.query_sms_schedules(db, page, size)
    return {
        "items": [schemas.SmsMessageRead.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/schedules", response_model=schemas.SmsMessageRead, status_code=201)
def create_sms_schedule(payload: schemas.SmsScheduleRequest, db: Session = Depends(get_db)) -> schemas.SmsMessageRead:
    return schemas.SmsMessageRead.model_validate(services.create_sms_schedule(db, payload))


@router.put("/schedules/{message_id}", response_model=schemas.SmsMessageRead)
def update_sms_schedule(
    message_id: int, payload: schemas.SmsScheduleRequest, db: Session = Depends(get_db)
) -> schemas.SmsMessageRead:
    return schemas.SmsMessageRead.model_validate(services.update_sms_schedule(db, message_id, payload))


@router.delete("/schedules/{message_id}", response_model=schemas.SmsMessageRead)
def cancel_sms_schedule(message_id: int, db: Session = Depends(get_db)) -> schemas.SmsMessageRead:
    return schemas.SmsMessageRead.model_validate(services.cancel_sms_schedule(db, message_id))


@router.get("/history")
def list_sms_history(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    items, total = services.query_sms_history(db, page, size)
    return {
        "items": [schemas.SmsMessageRead.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/{message_id}/recipients")
def list_sms_message_recipients(
    message_id: int,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    message, items, total = services.query_sms_message_recipients(db, message_id, keyword, page, size)
    return {
        "message": schemas.SmsMessageRead.model_validate(message),
        "items": [schemas.SmsMessageRecipientRead.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "size": size,
    }
