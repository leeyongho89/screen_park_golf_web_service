from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.config import get_settings
from app.sms_provider import NaverSensSmsProvider, NcloudBillingClient
from app.utils import calculate_end_date, normalize_phone


LEGACY_PRODUCT_TYPES = {"정기권": "기간제", "쿠폰": "횟수", "묶음티켓": "횟수"}
MEMBERSHIP_PRODUCT_TYPES = {"기간제", "횟수"}
KST = timezone(timedelta(hours=9))
RESERVATION_OPEN_TIME = time(9, 0)
RESERVATION_CLOSE_TIME = time(23, 0)
RESERVATION_SLOT_MINUTES = 30
RESERVATION_STATUSES = {"예약", "취소"}
SMS_SCHEDULE_LIST_STATUSES = {"예약", "예약취소"}
SMS_SCHEDULE_SYNC_STATUSES = {"예약", "발송중"}
SMS_HISTORY_EXCLUDED_STATUSES = {"예약", "예약취소"}


def fail(status_code: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def model_snapshot(obj: Any, fields: list[str]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for field in fields:
        value = getattr(obj, field)
        if isinstance(value, (date, datetime, time)):
            snapshot[field] = value.isoformat()
        elif isinstance(value, Decimal):
            snapshot[field] = str(value)
        else:
            snapshot[field] = value
    return snapshot


def add_audit_log(
    db: Session,
    action_type: str,
    target_type: str,
    target_id: int | None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    actor_name: str | None = None,
) -> None:
    db.add(
        models.AuditLog(
            actor_name=actor_name or get_settings().operator_name,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            before_data=before_data,
            after_data=after_data,
        )
    )


def canonical_product_type(product_type: str | None) -> str | None:
    if product_type is None:
        return None
    return LEGACY_PRODUCT_TYPES.get(product_type, product_type)


def normalized_product_fields(product_type: str, duration_days: int | None, total_count: int | None) -> tuple[int | None, int | None]:
    if product_type == "판매":
        return None, None
    if product_type == "기간제":
        return duration_days, None
    return duration_days, total_count


def validate_product_policy(product_type: str, duration_days: int | None, total_count: int | None) -> None:
    if product_type in {"기간제", "횟수"} and duration_days is None:
        fail(400, "invalid_product_policy", "기간제와 횟수 상품은 유효 일수를 입력해 주세요.")
    if product_type == "횟수" and total_count is None:
        fail(400, "invalid_product_policy", "횟수 상품은 횟수를 입력해 주세요.")


def calculate_membership_end_date(start_date: date, duration_days: int | None, explicit_end_date: date | None = None) -> date | None:
    end_date = explicit_end_date or calculate_end_date(start_date, None, duration_days)
    if end_date is not None and end_date < start_date:
        fail(400, "invalid_membership_period", "종료일은 시작일보다 빠를 수 없습니다.")
    return end_date


def kst_date_range_bounds_utc(start_date: date, end_date: date | None = None) -> tuple[datetime, datetime]:
    utc_start = datetime.combine(start_date, time.min, tzinfo=KST).astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = datetime.combine((end_date or start_date) + timedelta(days=1), time.min, tzinfo=KST).astimezone(timezone.utc)
    return utc_start, utc_end.replace(tzinfo=None)


def migrate_legacy_products(db: Session) -> None:
    products = db.scalars(select(models.MembershipProduct)).all()
    changed = False
    for product in products:
        legacy_type = canonical_product_type(product.product_type)
        if legacy_type != product.product_type:
            product.product_type = legacy_type
            changed = True
        duration_days, total_count = normalized_product_fields(
            product.product_type,
            product.duration_days or (30 if product.product_type in MEMBERSHIP_PRODUCT_TYPES else None),
            product.total_count or (10 if product.product_type == "횟수" else None),
        )
        if product.duration_days != duration_days:
            product.duration_days = duration_days
            changed = True
        if product.total_count != total_count:
            product.total_count = total_count
            changed = True
    if changed:
        db.flush()


def get_member_or_404(db: Session, member_id: int) -> models.Member:
    member = db.get(models.Member, member_id)
    if not member:
        fail(404, "member_not_found", "회원을 찾을 수 없습니다.")
    return member


def get_active_member_by_phone(db: Session, phone: str | None) -> models.Member | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    return db.scalar(select(models.Member).where(models.Member.phone == normalized, models.Member.is_active.is_(True)))


def ensure_unique_active_phone(db: Session, phone: str, exclude_member_id: int | None = None) -> None:
    stmt = select(models.Member).where(models.Member.phone == phone, models.Member.is_active.is_(True))
    if exclude_member_id:
        stmt = stmt.where(models.Member.id != exclude_member_id)
    if db.scalar(stmt):
        fail(409, "duplicate_phone", "이미 등록된 휴대전화 번호입니다.")


def create_member(db: Session, payload: schemas.MemberCreate) -> models.Member:
    ensure_unique_active_phone(db, payload.phone)
    now = datetime.now(KST)
    member = models.Member(**payload.model_dump(exclude={"operator_name"}), created_at=now, updated_at=now)
    db.add(member)
    db.flush()
    add_audit_log(
        db,
        action_type="회원 등록",
        target_type="member",
        target_id=member.id,
        after_data=model_snapshot(member, ["id", "name", "phone", "sms_agree", "is_active"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(member)
    return member


def update_member(db: Session, member_id: int, payload: schemas.MemberUpdate) -> models.Member:
    member = get_member_or_404(db, member_id)
    before = model_snapshot(member, ["name", "phone", "sms_agree", "memo", "is_active"])
    data = payload.model_dump(exclude_unset=True, exclude={"operator_name"})
    if "phone" in data and data["phone"] and data["phone"] != member.phone:
        ensure_unique_active_phone(db, data["phone"], exclude_member_id=member.id)
    for key, value in data.items():
        setattr(member, key, value)
    db.flush()
    add_audit_log(
        db,
        action_type="회원 수정",
        target_type="member",
        target_id=member.id,
        before_data=before,
        after_data=model_snapshot(member, ["name", "phone", "sms_agree", "memo", "is_active"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(member)
    return member


def restore_member(db: Session, member_id: int, payload: schemas.MembershipStatusRequest) -> models.Member:
    member = get_member_or_404(db, member_id)
    ensure_unique_active_phone(db, member.phone, exclude_member_id=member.id)
    before = model_snapshot(member, ["name", "phone", "is_active"])
    member.is_active = True
    db.flush()
    add_audit_log(
        db,
        action_type="회원 복구",
        target_type="member",
        target_id=member.id,
        before_data=before,
        after_data=model_snapshot(member, ["name", "phone", "is_active"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(member)
    return member


def permanently_delete_member(db: Session, member_id: int, payload: schemas.MembershipStatusRequest) -> None:
    member = get_member_or_404(db, member_id)
    if member.is_active:
        fail(400, "member_must_be_inactive", "삭제 처리된 회원만 영구삭제할 수 있습니다.")

    sale_exists = db.scalar(select(models.Sale.id).where(models.Sale.member_id == member.id).limit(1))
    membership_exists = db.scalar(
        select(models.MemberMembership.id).where(models.MemberMembership.member_id == member.id).limit(1)
    )
    if sale_exists or membership_exists:
        fail(400, "member_has_history", "매출 또는 보유 상품 이력이 있는 회원은 영구삭제할 수 없습니다.")

    before = model_snapshot(member, ["id", "name", "phone", "sms_agree", "memo", "is_active"])
    db.delete(member)
    db.flush()
    add_audit_log(
        db,
        action_type="회원 영구삭제",
        target_type="member",
        target_id=member_id,
        before_data=before,
        actor_name=payload.operator_name,
    )
    db.commit()


def create_product(db: Session, payload: schemas.MembershipProductCreate) -> models.MembershipProduct:
    data = payload.model_dump(exclude={"operator_name"})
    data["product_type"] = canonical_product_type(data["product_type"])
    data["duration_days"], data["total_count"] = normalized_product_fields(
        data["product_type"], data.get("duration_days"), data.get("total_count")
    )
    validate_product_policy(data["product_type"], data.get("duration_days"), data.get("total_count"))
    product = models.MembershipProduct(**data)
    db.add(product)
    db.flush()
    add_audit_log(
        db,
        action_type="상품 등록",
        target_type="membership_product",
        target_id=product.id,
        after_data=model_snapshot(product, ["id", "name", "product_type", "price", "is_active"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(product)
    return product


def update_product(
    db: Session, product_id: int, payload: schemas.MembershipProductUpdate
) -> models.MembershipProduct:
    product = db.get(models.MembershipProduct, product_id)
    if not product:
        fail(404, "product_not_found", "상품을 찾을 수 없습니다.")
    before = model_snapshot(product, ["name", "product_type", "duration_days", "total_count", "price", "is_active"])
    update_data = payload.model_dump(exclude_unset=True, exclude={"operator_name"})
    next_product_type = canonical_product_type(update_data.get("product_type", product.product_type))
    next_duration_days = update_data.get("duration_days", product.duration_days)
    next_total_count = update_data.get("total_count", product.total_count)
    next_duration_days, next_total_count = normalized_product_fields(next_product_type, next_duration_days, next_total_count)
    validate_product_policy(next_product_type, next_duration_days, next_total_count)
    update_data["product_type"] = next_product_type
    update_data["duration_days"] = next_duration_days
    update_data["total_count"] = next_total_count
    for key, value in update_data.items():
        setattr(product, key, value)
    db.flush()
    add_audit_log(
        db,
        action_type="상품 수정",
        target_type="membership_product",
        target_id=product.id,
        before_data=before,
        after_data=model_snapshot(product, ["name", "product_type", "duration_days", "total_count", "price", "is_active"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    product = db.get(models.MembershipProduct, product_id)
    if not product:
        fail(404, "product_not_found", "상품을 찾을 수 없습니다.")

    membership_exists = db.scalar(
        select(models.MemberMembership.id).where(models.MemberMembership.product_id == product.id).limit(1)
    )
    if membership_exists:
        fail(400, "product_in_use", "사용 이력이 있는 상품은 삭제할 수 없습니다. 판매 비활성으로 전환해 주세요.")

    before = model_snapshot(product, ["name", "product_type", "duration_days", "total_count", "price", "is_active"])
    db.delete(product)
    db.flush()
    add_audit_log(
        db,
        action_type="상품 삭제",
        target_type="membership_product",
        target_id=product_id,
        before_data=before,
    )
    db.commit()


def normalize_legacy_reservation_statuses(db: Session) -> None:
    result = db.execute(
        update(models.Reservation)
        .where(models.Reservation.status.not_in(RESERVATION_STATUSES))
        .values(status="예약", updated_at=datetime.now(timezone.utc))
    )
    if result.rowcount:
        db.commit()
    else:
        db.rollback()


def create_member_membership(
    db: Session,
    payload: schemas.MemberMembershipCreate,
    source_sale_id: int | None = None,
    commit: bool = True,
) -> models.MemberMembership:
    member = get_member_or_404(db, payload.member_id)
    product = db.get(models.MembershipProduct, payload.product_id) if payload.product_id else None
    if payload.product_id and not product:
        fail(404, "product_not_found", "상품을 찾을 수 없습니다.")

    product_type = canonical_product_type(product.product_type) if product else None
    duration_type = payload.duration_type
    duration_days = payload.duration_days
    total_count = payload.total_count

    if product:
        if product_type == "판매":
            fail(400, "invalid_product_type", "판매 상품은 보유 상품으로 만들 수 없습니다.")
        duration_days = duration_days or product.duration_days
        total_count = total_count or product.total_count
        duration_days, total_count = normalized_product_fields(product_type, duration_days, total_count)
        validate_product_policy(product_type, duration_days, total_count)
        if product_type == "기간제":
            duration_type = duration_type or ("지정일수" if duration_days else "한달")

    if total_count and payload.end_date is None:
        end_date = calculate_membership_end_date(payload.start_date, duration_days)
    elif payload.end_date is not None:
        end_date = calculate_membership_end_date(payload.start_date, duration_days, payload.end_date)
    else:
        end_date = calculate_end_date(payload.start_date, duration_type, duration_days)

    membership = models.MemberMembership(
        member_id=member.id,
        product_id=product.id if product else None,
        start_date=payload.start_date,
        end_date=end_date,
        duration_type=duration_type,
        duration_days=duration_days,
        total_count=total_count,
        remaining_count=total_count,
        status="사용중",
        sold_price=payload.sold_price,
        source_sale_id=source_sale_id,
    )
    db.add(membership)
    db.flush()
    add_audit_log(
        db,
        action_type="보유 상품 생성",
        target_type="member_membership",
        target_id=membership.id,
        after_data=model_snapshot(
            membership,
            ["id", "member_id", "product_id", "start_date", "end_date", "total_count", "remaining_count", "status"],
        ),
        actor_name=payload.operator_name,
    )
    if commit:
        db.commit()
        db.refresh(membership)
    return membership


def resolve_sale_member(db: Session, payload: schemas.SaleCreate) -> models.Member | None:
    if payload.member_id:
        member = get_member_or_404(db, payload.member_id)
        if not member.is_active:
            fail(400, "inactive_member", "비활성 회원에는 매출을 연결할 수 없습니다.")
        return member

    member = get_active_member_by_phone(db, payload.member_phone)
    if member:
        return member

    return None


def require_sale_member_details(payload: schemas.SaleCreate) -> tuple[str, str]:
    name = (payload.member_name or "").strip()
    phone = normalize_phone(payload.member_phone)
    if not name or not phone:
        fail(400, "member_details_required", "기간제 또는 횟수 상품은 회원명과 휴대전화를 입력해 주세요.")
    return name, phone


def create_auto_member_for_sale(
    db: Session, name: str, phone: str, operator_name: str | None = None
) -> models.Member:
    ensure_unique_active_phone(db, phone)
    member = models.Member(name=name, phone=phone, sms_agree=True, memo="매출 등록 중 자동 생성")
    db.add(member)
    db.flush()
    add_audit_log(
        db,
        action_type="회원 자동 등록",
        target_type="member",
        target_id=member.id,
        after_data=model_snapshot(member, ["id", "name", "phone", "sms_agree", "is_active"]),
        actor_name=operator_name,
    )
    return member


def create_sale(db: Session, payload: schemas.SaleCreate) -> models.Sale:
    product = db.get(models.MembershipProduct, payload.product_id)
    if not product:
        fail(404, "product_not_found", "상품을 찾을 수 없습니다.")
    product_type = canonical_product_type(product.product_type)
    duration_days, default_total_count = normalized_product_fields(product_type, product.duration_days, product.total_count)
    validate_product_policy(product_type, duration_days, default_total_count)
    sale_date = date.today()

    if product_type in MEMBERSHIP_PRODUCT_TYPES and not payload.member_id:
        name, phone = require_sale_member_details(payload)
        member = get_active_member_by_phone(db, phone)
        if not member:
            member = create_auto_member_for_sale(db, name, phone, payload.operator_name)
    else:
        member = resolve_sale_member(db, payload)

    start_date = payload.start_date or sale_date
    total_count = None if product_type != "횟수" else payload.total_count or default_total_count
    if product_type == "횟수" and total_count is None:
        fail(400, "invalid_sale_count", "횟수 상품은 횟수를 입력해 주세요.")
    end_date = None if product_type == "판매" else calculate_membership_end_date(start_date, duration_days, payload.end_date)

    sale = models.Sale(
        member_id=member.id if member else None,
        member_name_snapshot=member.name if member else payload.member_name,
        member_phone_snapshot=member.phone if member else payload.member_phone,
        sale_type=product.name,
        payment_method=payload.payment_method,
        amount=payload.amount,
        sale_date=sale_date,
        duration_days=duration_days if product_type in MEMBERSHIP_PRODUCT_TYPES else None,
        coupon_count=total_count,
        status="정상",
        note=payload.note,
        operator_name=payload.operator_name,
    )
    db.add(sale)
    db.flush()

    if member:
        member.last_visit_at = datetime.combine(sale_date, datetime.min.time(), tzinfo=timezone.utc)

    if product_type in MEMBERSHIP_PRODUCT_TYPES and member:
        membership_payload = schemas.MemberMembershipCreate(
            member_id=member.id,
            product_id=product.id,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            total_count=total_count,
            sold_price=payload.amount,
            note=payload.note,
            operator_name=payload.operator_name,
        )
        membership = create_member_membership(db, membership_payload, source_sale_id=sale.id, commit=False)
        sale.related_membership_id = membership.id

    add_audit_log(
        db,
        action_type="매출 등록",
        target_type="sale",
        target_id=sale.id,
        after_data=model_snapshot(
            sale,
            ["id", "member_id", "sale_type", "payment_method", "amount", "sale_date", "status", "related_membership_id"],
        ),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(sale)
    return sale


def refund_sale(db: Session, sale_id: int, payload: schemas.SaleRefundRequest) -> models.Sale:
    original = db.get(models.Sale, sale_id)
    if not original:
        fail(404, "sale_not_found", "매출을 찾을 수 없습니다.")
    if original.status == "환불":
        fail(400, "already_refunded", "이미 환불 처리된 매출입니다.")
    if original.amount <= 0:
        fail(400, "invalid_refund_target", "환불 매출은 다시 환불할 수 없습니다.")

    refund_amount = payload.amount or original.amount
    if refund_amount > original.amount:
        fail(400, "invalid_refund_amount", "환불 금액은 원매출 금액보다 클 수 없습니다.")

    before = model_snapshot(original, ["status", "refunded_at"])
    now = datetime.now(timezone.utc)
    original.status = "환불" if refund_amount == original.amount else "부분환불"
    original.refunded_at = now

    refund = models.Sale(
        member_id=original.member_id,
        member_name_snapshot=original.member_name_snapshot,
        member_phone_snapshot=original.member_phone_snapshot,
        sale_type=original.sale_type,
        payment_method=original.payment_method,
        amount=-refund_amount,
        sale_date=original.sale_date,
        related_membership_id=original.related_membership_id,
        duration_type=original.duration_type,
        duration_days=original.duration_days,
        coupon_count=original.coupon_count,
        status="환불",
        original_sale_id=original.id,
        note=payload.note or "환불 처리",
        operator_name=payload.operator_name,
        refunded_at=now,
    )
    db.add(refund)

    if original.related_membership_id:
        membership = db.get(models.MemberMembership, original.related_membership_id)
        if membership:
            membership.status = "환불"

    db.flush()
    add_audit_log(
        db,
        action_type="매출 환불",
        target_type="sale",
        target_id=original.id,
        before_data=before,
        after_data=model_snapshot(original, ["status", "refunded_at"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(refund)
    return refund


def change_membership_status(
    db: Session, membership_id: int, status: str, payload: schemas.MembershipStatusRequest
) -> models.MemberMembership:
    membership = db.get(models.MemberMembership, membership_id)
    if not membership:
        fail(404, "membership_not_found", "보유 상품을 찾을 수 없습니다.")
    before = model_snapshot(membership, ["status"])
    membership.status = status
    db.flush()
    add_audit_log(
        db,
        action_type=f"보유 상품 {status}",
        target_type="member_membership",
        target_id=membership.id,
        before_data=before,
        after_data=model_snapshot(membership, ["status"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(membership)
    return membership


def deduct_membership(
    db: Session, membership_id: int, payload: schemas.MembershipActionRequest
) -> models.MemberMembership:
    membership = db.get(models.MemberMembership, membership_id)
    if not membership:
        fail(404, "membership_not_found", "보유 상품을 찾을 수 없습니다.")
    if membership.status != "사용중":
        fail(400, "membership_not_active", "사용중인 보유 상품만 차감할 수 있습니다.")
    if membership.remaining_count is None:
        log = models.MembershipUsageLog(
            member_membership_id=membership.id,
            member_id=membership.member_id,
            action_type="사용",
            change_count=None,
            before_remaining_count=None,
            after_remaining_count=None,
            note=payload.note,
            operator_name=payload.operator_name,
        )
        db.add(log)
    else:
        if membership.remaining_count < payload.count:
            fail(400, "not_enough_count", "잔여 횟수가 부족합니다.")
        before = membership.remaining_count
        membership.remaining_count -= payload.count
        log = models.MembershipUsageLog(
            member_membership_id=membership.id,
            member_id=membership.member_id,
            action_type="사용",
            change_count=-payload.count,
            before_remaining_count=before,
            after_remaining_count=membership.remaining_count,
            note=payload.note,
            operator_name=payload.operator_name,
        )
        db.add(log)
        if membership.remaining_count == 0:
            membership.status = "만료"
    db.flush()
    add_audit_log(
        db,
        action_type="보유 상품 차감",
        target_type="member_membership",
        target_id=membership.id,
        after_data=model_snapshot(membership, ["remaining_count", "status"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(membership)
    return membership


def adjust_membership(
    db: Session, membership_id: int, payload: schemas.MembershipAdjustRequest
) -> models.MemberMembership:
    membership = db.get(models.MemberMembership, membership_id)
    if not membership:
        fail(404, "membership_not_found", "보유 상품을 찾을 수 없습니다.")
    before = membership.remaining_count
    membership.remaining_count = payload.remaining_count
    if membership.remaining_count == 0:
        membership.status = "만료"
    elif membership.status == "만료":
        membership.status = "사용중"
    db.add(
        models.MembershipUsageLog(
            member_membership_id=membership.id,
            member_id=membership.member_id,
            action_type="보정",
            change_count=None if before is None else payload.remaining_count - before,
            before_remaining_count=before,
            after_remaining_count=payload.remaining_count,
            note=payload.note,
            operator_name=payload.operator_name,
        )
    )
    db.flush()
    add_audit_log(
        db,
        action_type="보유 상품 보정",
        target_type="member_membership",
        target_id=membership.id,
        before_data={"remaining_count": before},
        after_data=model_snapshot(membership, ["remaining_count", "status"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(membership)
    return membership


def adjust_membership_period(
    db: Session, membership_id: int, payload: schemas.MembershipPeriodAdjustRequest
) -> models.MemberMembership:
    membership = db.get(models.MemberMembership, membership_id)
    if not membership:
        fail(404, "membership_not_found", "보유 상품을 찾을 수 없습니다.")
    if payload.end_date is not None and payload.end_date < payload.start_date:
        fail(400, "invalid_membership_period", "종료일은 시작일보다 빠를 수 없습니다.")
    before = model_snapshot(membership, ["start_date", "end_date", "status"])
    membership.start_date = payload.start_date
    membership.end_date = payload.end_date
    db.add(
        models.MembershipUsageLog(
            member_membership_id=membership.id,
            member_id=membership.member_id,
            action_type="기간 보정",
            change_count=None,
            before_remaining_count=None,
            after_remaining_count=None,
            note=payload.note,
            operator_name=payload.operator_name,
        )
    )
    db.flush()
    add_audit_log(
        db,
        action_type="보유 상품 기간 보정",
        target_type="member_membership",
        target_id=membership.id,
        before_data=before,
        after_data=model_snapshot(membership, ["start_date", "end_date", "status"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(membership)
    return membership


def seed_default_products(db: Session) -> None:
    migrate_legacy_products(db)
    defaults = [
        {"name": "1개월 정기권", "product_type": "기간제", "duration_days": 30, "total_count": None, "price": 0},
        {"name": "10회 쿠폰", "product_type": "횟수", "duration_days": 30, "total_count": 10, "price": 0},
        {"name": "타석 이용료", "product_type": "판매", "duration_days": None, "total_count": None, "price": 0},
    ]
    for item in defaults:
        exists = db.scalar(
            select(models.MembershipProduct).where(
                models.MembershipProduct.name == item["name"],
                models.MembershipProduct.product_type == item["product_type"],
            )
        )
        if not exists:
            db.add(models.MembershipProduct(**item))
    db.commit()


def query_members(
    db: Session,
    keyword: str | None,
    include_inactive: bool,
    inactive_only: bool,
    created_from: date | None,
    created_to: date | None,
    page: int,
    size: int,
) -> tuple[list[models.Member], int]:
    stmt = select(models.Member)
    if inactive_only:
        stmt = stmt.where(models.Member.is_active.is_(False))
    elif not include_inactive:
        stmt = stmt.where(models.Member.is_active.is_(True))
    if keyword:
        normalized = normalize_phone(keyword)
        like = f"%{keyword}%"
        conditions = [models.Member.name.ilike(like), models.Member.memo.ilike(like)]
        if normalized:
            conditions.append(models.Member.phone.ilike(f"%{normalized}%"))
        stmt = stmt.where(or_(*conditions))
    if created_from:
        created_from_utc, _ = kst_date_range_bounds_utc(created_from)
        stmt = stmt.where(models.Member.created_at >= created_from_utc)
    if created_to:
        _, created_to_utc = kst_date_range_bounds_utc(created_to)
        stmt = stmt.where(models.Member.created_at < created_to_utc)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(models.Member.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    return list(items), total


def member_sales_amounts(db: Session, member_ids: list[int], recent_to_date: date | None = None) -> dict[int, dict[str, Decimal]]:
    if not member_ids:
        return {}

    empty_summary = {
        member_id: {
            "total_sales_amount": Decimal("0"),
            "recent_30_days_sales_amount": Decimal("0"),
        }
        for member_id in member_ids
    }

    total_rows = db.execute(
        select(models.Sale.member_id, func.coalesce(func.sum(models.Sale.amount), 0))
        .where(models.Sale.member_id.in_(member_ids))
        .group_by(models.Sale.member_id)
    ).all()
    for member_id, amount in total_rows:
        if member_id is not None:
            empty_summary[member_id]["total_sales_amount"] = Decimal(amount or 0)

    recent_end = recent_to_date or date.today()
    recent_start = recent_end - timedelta(days=29)
    recent_rows = db.execute(
        select(models.Sale.member_id, func.coalesce(func.sum(models.Sale.amount), 0))
        .where(
            models.Sale.member_id.in_(member_ids),
            models.Sale.sale_date >= recent_start,
            models.Sale.sale_date <= recent_end,
        )
        .group_by(models.Sale.member_id)
    ).all()
    for member_id, amount in recent_rows:
        if member_id is not None:
            empty_summary[member_id]["recent_30_days_sales_amount"] = Decimal(amount or 0)

    return empty_summary


def query_sales(
    db: Session, from_date: date | None, to_date: date | None, page: int, size: int
) -> tuple[list[models.Sale], int]:
    stmt = select(models.Sale)
    if from_date:
        stmt = stmt.where(models.Sale.sale_date >= from_date)
    if to_date:
        stmt = stmt.where(models.Sale.sale_date <= to_date)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(models.Sale.created_at.desc(), models.Sale.id.desc()).offset((page - 1) * size).limit(size)).all()
    return list(items), total


def validate_reservation_window(start_time: time | None, end_time: time | None) -> None:
    if start_time is None or end_time is None:
        fail(400, "invalid_reservation_time", "예약 시작 시간과 종료 시간을 입력해 주세요.")
    if start_time >= end_time:
        fail(400, "invalid_reservation_time", "예약 종료 시간은 시작 시간보다 늦어야 합니다.")
    if start_time < RESERVATION_OPEN_TIME or end_time > RESERVATION_CLOSE_TIME:
        fail(400, "invalid_reservation_hours", "예약 가능 시간은 09:00부터 23:00까지입니다.")
    for value in (start_time, end_time):
        if value.second or value.microsecond or value.minute % RESERVATION_SLOT_MINUTES != 0:
            fail(400, "invalid_reservation_slot", "예약 시간은 30분 단위로 입력해 주세요.")


def resolve_reservation_customer(
    db: Session,
    member_id: int | None,
    customer_name: str | None,
    customer_phone: str | None,
) -> tuple[models.Member | None, str, str]:
    member = None
    if member_id:
        member = get_member_or_404(db, member_id)
        if not member.is_active:
            fail(400, "inactive_member", "비활성 회원은 예약에 연결할 수 없습니다.")
        return member, member.name, member.phone

    name = (customer_name or "").strip()
    phone = normalize_phone(customer_phone)
    if not name or not phone:
        fail(400, "reservation_customer_required", "예약자 이름과 연락처를 입력해 주세요.")
    return None, name, phone


def ensure_reservation_not_conflicting(
    db: Session,
    reservation_date: date,
    bay_number: int,
    start_time: time,
    end_time: time,
    exclude_reservation_id: int | None = None,
) -> None:
    stmt = select(models.Reservation.id).where(
        models.Reservation.reservation_date == reservation_date,
        models.Reservation.bay_number == bay_number,
        models.Reservation.status != "취소",
        models.Reservation.start_time < end_time,
        models.Reservation.end_time > start_time,
    )
    if exclude_reservation_id:
        stmt = stmt.where(models.Reservation.id != exclude_reservation_id)
    if db.scalar(stmt.limit(1)):
        fail(409, "reservation_conflict", "같은 타석에 겹치는 예약이 있습니다.")


def query_reservations(db: Session, target_date: date) -> list[models.Reservation]:
    return list(
        db.scalars(
            select(models.Reservation)
            .options(joinedload(models.Reservation.member))
            .where(models.Reservation.reservation_date == target_date)
            .order_by(models.Reservation.bay_number.asc(), models.Reservation.start_time.asc(), models.Reservation.id.asc())
        ).all()
    )


def get_reservation_or_404(db: Session, reservation_id: int) -> models.Reservation:
    reservation = db.scalars(
        select(models.Reservation)
        .options(joinedload(models.Reservation.member))
        .where(models.Reservation.id == reservation_id)
    ).first()
    if not reservation:
        fail(404, "reservation_not_found", "예약을 찾을 수 없습니다.")
    return reservation


def create_reservation(db: Session, payload: schemas.ReservationCreate) -> models.Reservation:
    validate_reservation_window(payload.start_time, payload.end_time)
    member, customer_name, customer_phone = resolve_reservation_customer(
        db, payload.member_id, payload.customer_name, payload.customer_phone
    )
    ensure_reservation_not_conflicting(db, payload.reservation_date, payload.bay_number, payload.start_time, payload.end_time)
    reservation = models.Reservation(
        bay_number=payload.bay_number,
        member_id=member.id if member else None,
        customer_name=customer_name,
        customer_phone=customer_phone,
        reservation_date=payload.reservation_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status="예약",
        note=payload.note,
        operator_name=payload.operator_name,
    )
    db.add(reservation)
    db.flush()
    add_audit_log(
        db,
        action_type="예약 등록",
        target_type="reservation",
        target_id=reservation.id,
        after_data=model_snapshot(
            reservation,
            ["id", "bay_number", "member_id", "customer_name", "customer_phone", "reservation_date", "start_time", "end_time", "status"],
        ),
        actor_name=payload.operator_name,
    )
    db.commit()
    return get_reservation_or_404(db, reservation.id)


def update_reservation(db: Session, reservation_id: int, payload: schemas.ReservationUpdate) -> models.Reservation:
    reservation = get_reservation_or_404(db, reservation_id)
    if reservation.status == "취소":
        fail(400, "reservation_canceled", "취소된 예약은 수정할 수 없습니다.")
    before = model_snapshot(
        reservation,
        ["bay_number", "member_id", "customer_name", "customer_phone", "reservation_date", "start_time", "end_time", "status", "note"],
    )
    data = payload.model_dump(exclude_unset=True, exclude={"operator_name"})
    next_member_id = data.get("member_id", reservation.member_id)
    next_name = data.get("customer_name", reservation.customer_name)
    next_phone = data.get("customer_phone", reservation.customer_phone)
    member, customer_name, customer_phone = resolve_reservation_customer(db, next_member_id, next_name, next_phone)
    next_bay_number = data.get("bay_number", reservation.bay_number)
    next_date = data.get("reservation_date", reservation.reservation_date)
    next_start_time = data.get("start_time", reservation.start_time)
    next_end_time = data.get("end_time", reservation.end_time)
    validate_reservation_window(next_start_time, next_end_time)
    ensure_reservation_not_conflicting(db, next_date, next_bay_number, next_start_time, next_end_time, reservation.id)

    reservation.bay_number = next_bay_number
    reservation.member_id = member.id if member else None
    reservation.customer_name = customer_name
    reservation.customer_phone = customer_phone
    reservation.reservation_date = next_date
    reservation.start_time = next_start_time
    reservation.end_time = next_end_time
    if "note" in data:
        reservation.note = data["note"]
    db.flush()
    add_audit_log(
        db,
        action_type="예약 수정",
        target_type="reservation",
        target_id=reservation.id,
        before_data=before,
        after_data=model_snapshot(
            reservation,
            ["bay_number", "member_id", "customer_name", "customer_phone", "reservation_date", "start_time", "end_time", "status", "note"],
        ),
        actor_name=payload.operator_name,
    )
    db.commit()
    return get_reservation_or_404(db, reservation.id)


def cancel_reservation(db: Session, reservation_id: int, payload: schemas.ReservationStatusRequest) -> models.Reservation:
    reservation = get_reservation_or_404(db, reservation_id)
    before = model_snapshot(reservation, ["status", "canceled_at"])
    reservation.status = "취소"
    reservation.canceled_at = datetime.now(timezone.utc)
    if payload.note:
        reservation.note = payload.note
    db.flush()
    add_audit_log(
        db,
        action_type="예약 취소",
        target_type="reservation",
        target_id=reservation.id,
        before_data=before,
        after_data=model_snapshot(reservation, ["status", "canceled_at", "note"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    return get_reservation_or_404(db, reservation.id)


def query_member_memberships(
    db: Session,
    member_id: int | None,
    statuses: list[str] | None,
    keyword: str | None,
    expiring_days: int | None,
    remaining_count_lte: int | None,
    page: int,
    size: int,
) -> tuple[list[models.MemberMembership], int]:
    stmt = (
        select(models.MemberMembership)
        .join(models.Member)
        .outerjoin(models.MembershipProduct)
        .options(joinedload(models.MemberMembership.member), joinedload(models.MemberMembership.product))
    )
    if member_id:
        stmt = stmt.where(models.MemberMembership.member_id == member_id)
    if statuses:
        stmt = stmt.where(models.MemberMembership.status.in_(statuses))
    if keyword:
        normalized = normalize_phone(keyword)
        like = f"%{keyword}%"
        conditions = [
            models.Member.name.ilike(like),
            models.Member.memo.ilike(like),
            models.MembershipProduct.name.ilike(like),
        ]
        if normalized:
            conditions.append(models.Member.phone.ilike(f"%{normalized}%"))
        stmt = stmt.where(or_(*conditions))
    if expiring_days:
        today = date.today()
        stmt = stmt.where(
            models.MemberMembership.end_date.is_not(None),
            models.MemberMembership.end_date >= today,
            models.MemberMembership.end_date <= today + timedelta(days=expiring_days),
        )
    if remaining_count_lte is not None:
        stmt = stmt.where(
            models.MemberMembership.remaining_count.is_not(None),
            models.MemberMembership.remaining_count <= remaining_count_lte,
        )
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(
        stmt.order_by(models.MemberMembership.end_date.asc().nullslast(), models.MemberMembership.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(items), total


def sales_summary(db: Session, from_date: date, to_date: date) -> schemas.SalesSummary:
    if to_date < from_date:
        fail(400, "invalid_date_range", "종료일은 시작일보다 빠를 수 없습니다.")
    rows = db.execute(
        select(models.Sale.payment_method, func.coalesce(func.sum(models.Sale.amount), 0))
        .where(models.Sale.sale_date >= from_date, models.Sale.sale_date <= to_date)
        .group_by(models.Sale.payment_method)
    ).all()
    by_payment = {row[0]: Decimal(row[1] or 0) for row in rows}
    type_rows = db.execute(
        select(models.Sale.sale_type, func.coalesce(func.sum(models.Sale.amount), 0))
        .where(models.Sale.sale_date >= from_date, models.Sale.sale_date <= to_date)
        .group_by(models.Sale.sale_type)
    ).all()
    by_type = {row[0]: Decimal(row[1] or 0) for row in type_rows}
    total_amount = sum(by_payment.values(), Decimal("0"))
    total_count = db.scalar(
        select(func.count()).where(models.Sale.sale_date >= from_date, models.Sale.sale_date <= to_date)
    ) or 0
    refund_count = db.scalar(
        select(func.count()).where(
            models.Sale.sale_date >= from_date,
            models.Sale.sale_date <= to_date,
            models.Sale.amount < 0,
        )
    ) or 0
    member_label = func.coalesce(func.nullif(models.Sale.member_name_snapshot, ""), "비회원")
    member_rows = db.execute(
        select(member_label, func.coalesce(func.sum(models.Sale.amount), 0), func.count())
        .where(models.Sale.sale_date >= from_date, models.Sale.sale_date <= to_date)
        .group_by(member_label)
    ).all()
    by_member = sorted(
        [
            schemas.SalesBreakdownItem(label=row[0] or "비회원", amount=Decimal(row[1] or 0), count=int(row[2] or 0))
            for row in member_rows
        ],
        key=lambda item: item.amount,
        reverse=True,
    )
    day_rows = db.execute(
        select(models.Sale.sale_date, func.coalesce(func.sum(models.Sale.amount), 0), func.count())
        .where(models.Sale.sale_date >= from_date, models.Sale.sale_date <= to_date)
        .group_by(models.Sale.sale_date)
    ).all()
    day_map = {row[0]: (Decimal(row[1] or 0), int(row[2] or 0)) for row in day_rows}
    by_day = []
    for offset in range((to_date - from_date).days + 1):
        target_date = from_date + timedelta(days=offset)
        amount, count = day_map.get(target_date, (Decimal("0"), 0))
        by_day.append(schemas.SalesDailyItem(sale_date=target_date, amount=amount, count=count))
    return schemas.SalesSummary(
        from_date=from_date,
        to_date=to_date,
        total_amount=total_amount,
        total_count=total_count,
        refund_count=refund_count,
        by_payment_method=by_payment,
        by_sale_type=by_type,
        by_member=by_member,
        by_day=by_day,
    )


def dashboard_summary(
    db: Session,
    new_member_days: int = 1,
    sales_days: int = 1,
    expiring_days: int = 7,
    low_remaining_count: int = 3,
) -> schemas.DashboardSummary:
    today = date.today()
    new_member_start = today - timedelta(days=max(1, new_member_days) - 1)
    sales_start = today - timedelta(days=max(1, sales_days) - 1)
    new_member_start_utc, tomorrow_start_utc = kst_date_range_bounds_utc(new_member_start, today)
    current_member_count = db.scalar(select(func.count()).where(models.Member.is_active.is_(True))) or 0
    today_new_members = db.scalar(
        select(func.count()).where(
            models.Member.created_at >= new_member_start_utc,
            models.Member.created_at < tomorrow_start_utc,
        )
    ) or 0
    today_sales = db.scalar(
        select(func.coalesce(func.sum(models.Sale.amount), 0)).where(
            models.Sale.sale_date >= sales_start,
            models.Sale.sale_date <= today,
        )
    ) or 0
    expiring_until = today + timedelta(days=expiring_days)
    expiring_memberships = db.scalar(
        select(func.count()).where(
            models.MemberMembership.status == "사용중",
            models.MemberMembership.end_date.is_not(None),
            models.MemberMembership.end_date >= today,
            models.MemberMembership.end_date <= expiring_until,
        )
    ) or 0
    low_remaining_memberships = db.scalar(
        select(func.count()).where(
            models.MemberMembership.status == "사용중",
            models.MemberMembership.remaining_count.is_not(None),
            models.MemberMembership.remaining_count <= low_remaining_count,
        )
    ) or 0
    recent_sales = db.scalars(select(models.Sale).order_by(models.Sale.created_at.desc()).limit(5)).all()
    return schemas.DashboardSummary(
        current_member_count=current_member_count,
        today_new_members=today_new_members,
        today_sales=Decimal(today_sales or 0),
        month_sales=Decimal(today_sales or 0),
        expiring_memberships=expiring_memberships,
        low_remaining_memberships=low_remaining_memberships,
        recent_sales=list(recent_sales),
    )


def get_sms_group_or_404(db: Session, group_id: int) -> models.SmsGroup:
    stmt = (
        select(models.SmsGroup)
        .options(joinedload(models.SmsGroup.group_members))
        .where(models.SmsGroup.id == group_id)
    )
    group = db.scalars(stmt).unique().first()
    if not group:
        fail(404, "sms_group_not_found", "문자 그룹을 찾을 수 없습니다.")
    return group


def get_sms_template_or_404(db: Session, template_id: int) -> models.SmsTemplate:
    template = db.get(models.SmsTemplate, template_id)
    if not template:
        fail(404, "sms_template_not_found", "문자 템플릿을 찾을 수 없습니다.")
    return template


def get_sms_message_or_404(db: Session, message_id: int) -> models.SmsMessage:
    stmt = (
        select(models.SmsMessage)
        .options(joinedload(models.SmsMessage.recipients))
        .where(models.SmsMessage.id == message_id)
    )
    message = db.scalars(stmt).unique().first()
    if not message:
        fail(404, "sms_message_not_found", "문자 발송 이력을 찾을 수 없습니다.")
    return message


def get_sms_schedule_or_404(db: Session, message_id: int) -> models.SmsMessage:
    message = get_sms_message_or_404(db, message_id)
    if message.scheduled_at is None:
        fail(404, "sms_schedule_not_found", "문자 예약 정보를 찾을 수 없습니다.")
    return message


def normalize_sms_schedule_datetime(value: datetime) -> datetime:
    localized = value if value.tzinfo is not None else value.replace(tzinfo=KST)
    localized = localized.astimezone(KST).replace(second=0, microsecond=0)
    return localized.astimezone(timezone.utc)


def format_sms_reserve_time(value: datetime) -> tuple[str, str]:
    localized = normalize_sms_schedule_datetime(value).astimezone(KST)
    return localized.strftime("%Y-%m-%d %H:%M"), "Asia/Seoul"


def validate_sms_schedule_datetime(value: datetime) -> datetime:
    normalized = normalize_sms_schedule_datetime(value)
    if normalized <= datetime.now(timezone.utc):
        fail(400, "invalid_sms_schedule_time", "예약 발송 시각은 현재 시각보다 늦어야 합니다.")
    return normalized


def normalized_sms_target_config(
    payload: schemas.SmsTargetSelection,
    *,
    content_type: str,
    excluded_member_ids: list[int] | None = None,
    excluded_phones: list[str] | None = None,
) -> dict[str, Any]:
    unique_excluded_phones = sorted(
        {
            normalized
            for phone in (excluded_phones or [])
            if (normalized := normalize_phone(phone))
        }
    )
    return {
        "group_ids": sorted(set(payload.group_ids)),
        "include_all_members": payload.include_all_members,
        "include_expiring_memberships": payload.include_expiring_memberships,
        "expiring_days": payload.expiring_days,
        "include_low_remaining_memberships": payload.include_low_remaining_memberships,
        "low_remaining_count": payload.low_remaining_count,
        "include_birthdays": payload.include_birthdays,
        "birthday_days": payload.birthday_days,
        "content_type": content_type,
        "excluded_member_ids": sorted(set(excluded_member_ids or [])),
        "excluded_phones": unique_excluded_phones,
    }


def sms_target_config_matches_summary(
    summary: dict[str, Any] | None,
    *,
    payload: schemas.SmsTargetSelection,
    content_type: str,
    excluded_member_ids: list[int] | None = None,
    excluded_phones: list[str] | None = None,
) -> bool:
    if not isinstance(summary, dict):
        return False
    current = normalized_sms_target_config(
        payload,
        content_type=content_type,
        excluded_member_ids=excluded_member_ids,
        excluded_phones=excluded_phones,
    )
    saved = {
        key: summary.get(key)
        for key in (
            "group_ids",
            "include_all_members",
            "include_expiring_memberships",
            "expiring_days",
            "include_low_remaining_memberships",
            "low_remaining_count",
            "include_birthdays",
            "birthday_days",
            "content_type",
            "excluded_member_ids",
            "excluded_phones",
        )
    }
    return current == saved


def build_sms_target_summary(
    payload: schemas.SmsTargetSelection,
    *,
    content_type: str,
    labels: list[str],
    groups: list[models.SmsGroup],
    eligible_count: int,
    blocked_count: int,
    excluded_count: int,
    excluded_member_ids: list[int] | None = None,
    excluded_phones: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "labels": labels,
        "group_ids": sorted(set(payload.group_ids)),
        "group_names": [group.name for group in groups],
        "include_all_members": payload.include_all_members,
        "include_expiring_memberships": payload.include_expiring_memberships,
        "expiring_days": payload.expiring_days,
        "include_low_remaining_memberships": payload.include_low_remaining_memberships,
        "low_remaining_count": payload.low_remaining_count,
        "include_birthdays": payload.include_birthdays,
        "birthday_days": payload.birthday_days,
        "content_type": content_type,
        "eligible_count": eligible_count,
        "blocked_count": blocked_count,
        "excluded_count": excluded_count,
        "excluded_member_ids": sorted(set(excluded_member_ids or [])),
        "excluded_phones": sorted(
            {
                normalized
                for phone in (excluded_phones or [])
                if (normalized := normalize_phone(phone))
            }
        ),
    }


def get_active_members_by_ids(db: Session, member_ids: list[int]) -> list[models.Member]:
    if not member_ids:
        return []
    unique_member_ids = sorted(set(member_ids))
    items = db.scalars(
        select(models.Member)
        .where(models.Member.id.in_(unique_member_ids), models.Member.is_active.is_(True))
        .order_by(models.Member.name.asc(), models.Member.id.asc())
    ).all()
    if len(items) != len(unique_member_ids):
        fail(400, "invalid_group_members", "그룹에 포함할 활성 회원을 다시 확인해 주세요.")
    return list(items)


def list_sms_groups(db: Session) -> list[models.SmsGroup]:
    stmt = (
        select(models.SmsGroup)
        .options(joinedload(models.SmsGroup.group_members))
        .order_by(models.SmsGroup.updated_at.desc(), models.SmsGroup.id.desc())
    )
    return list(db.scalars(stmt).unique().all())


def create_sms_group(db: Session, payload: schemas.SmsGroupCreate) -> models.SmsGroup:
    exists = db.scalar(select(models.SmsGroup.id).where(models.SmsGroup.name == payload.name).limit(1))
    if exists:
        fail(409, "duplicate_sms_group", "같은 이름의 문자 그룹이 이미 있습니다.")
    members = get_active_members_by_ids(db, payload.member_ids)
    group = models.SmsGroup(name=payload.name.strip(), description=(payload.description or "").strip() or None, operator_name=payload.operator_name)
    db.add(group)
    db.flush()
    group.group_members = [models.SmsGroupMember(member_id=member.id) for member in members]
    db.flush()
    add_audit_log(
        db,
        action_type="문자 그룹 생성",
        target_type="sms_group",
        target_id=group.id,
        after_data={"name": group.name, "member_ids": group.member_ids},
        actor_name=payload.operator_name,
    )
    db.commit()
    return get_sms_group_or_404(db, group.id)


def update_sms_group(db: Session, group_id: int, payload: schemas.SmsGroupUpdate) -> models.SmsGroup:
    group = get_sms_group_or_404(db, group_id)
    exists = db.scalar(
        select(models.SmsGroup.id).where(models.SmsGroup.name == payload.name, models.SmsGroup.id != group_id).limit(1)
    )
    if exists:
        fail(409, "duplicate_sms_group", "같은 이름의 문자 그룹이 이미 있습니다.")
    before = {"name": group.name, "description": group.description, "member_ids": group.member_ids, "is_active": group.is_active}
    members = get_active_members_by_ids(db, payload.member_ids)
    group.name = payload.name.strip()
    group.description = (payload.description or "").strip() or None
    group.is_active = payload.is_active
    group.operator_name = payload.operator_name
    group.group_members.clear()
    db.flush()
    group.group_members = [models.SmsGroupMember(member_id=member.id) for member in members]
    db.flush()
    add_audit_log(
        db,
        action_type="문자 그룹 수정",
        target_type="sms_group",
        target_id=group.id,
        before_data=before,
        after_data={"name": group.name, "description": group.description, "member_ids": group.member_ids, "is_active": group.is_active},
        actor_name=payload.operator_name,
    )
    db.commit()
    return get_sms_group_or_404(db, group.id)


def delete_sms_group(db: Session, group_id: int) -> None:
    group = get_sms_group_or_404(db, group_id)
    before = {"name": group.name, "member_ids": group.member_ids}
    db.delete(group)
    db.flush()
    add_audit_log(
        db,
        action_type="문자 그룹 삭제",
        target_type="sms_group",
        target_id=group_id,
        before_data=before,
    )
    db.commit()


def list_sms_templates(db: Session) -> list[models.SmsTemplate]:
    return list(
        db.scalars(
            select(models.SmsTemplate).order_by(models.SmsTemplate.is_active.desc(), models.SmsTemplate.updated_at.desc())
        ).all()
    )


def create_sms_template(db: Session, payload: schemas.SmsTemplateCreate) -> models.SmsTemplate:
    template = models.SmsTemplate(
        title=payload.title.strip(),
        content=payload.content.strip(),
        is_active=payload.is_active,
        operator_name=payload.operator_name,
    )
    db.add(template)
    db.flush()
    add_audit_log(
        db,
        action_type="문자 템플릿 생성",
        target_type="sms_template",
        target_id=template.id,
        after_data={"title": template.title, "is_active": template.is_active},
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(template)
    return template


def update_sms_template(db: Session, template_id: int, payload: schemas.SmsTemplateUpdate) -> models.SmsTemplate:
    template = get_sms_template_or_404(db, template_id)
    before = {"title": template.title, "content": template.content, "is_active": template.is_active}
    template.title = payload.title.strip()
    template.content = payload.content.strip()
    template.is_active = payload.is_active
    template.operator_name = payload.operator_name
    db.flush()
    add_audit_log(
        db,
        action_type="문자 템플릿 수정",
        target_type="sms_template",
        target_id=template.id,
        before_data=before,
        after_data={"title": template.title, "content": template.content, "is_active": template.is_active},
        actor_name=payload.operator_name,
    )
    db.commit()
    db.refresh(template)
    return template


def delete_sms_template(db: Session, template_id: int) -> None:
    template = get_sms_template_or_404(db, template_id)
    before = {"title": template.title, "content": template.content, "is_active": template.is_active}
    db.execute(update(models.SmsMessage).where(models.SmsMessage.template_id == template.id).values(template_id=None))
    db.delete(template)
    db.flush()
    add_audit_log(
        db,
        action_type="문자 템플릿 삭제",
        target_type="sms_template",
        target_id=template_id,
        before_data=before,
    )
    db.commit()


def get_sms_provider() -> NaverSensSmsProvider:
    settings = get_settings()
    if not settings.sms_provider_configured:
        fail(400, "sms_provider_not_configured", "NAVER Cloud SENS 설정이 필요합니다.")
    return NaverSensSmsProvider(
        service_id=(settings.ncp_sms_service_id or "").strip(),
        access_key=(settings.ncp_access_key or "").strip(),
        secret_key=(settings.ncp_secret_key or "").strip(),
        from_number=normalize_phone(settings.ncp_sms_from_number) or "",
    )


def get_ncloud_billing_client() -> NcloudBillingClient:
    settings = get_settings()
    if not (settings.ncp_access_key or "").strip() or not (settings.ncp_secret_key or "").strip():
        fail(400, "ncloud_billing_not_configured", "NAVER Cloud Billing 조회를 위해 Access Key와 Secret Key 설정이 필요합니다.")
    return NcloudBillingClient(
        access_key=(settings.ncp_access_key or "").strip(),
        secret_key=(settings.ncp_secret_key or "").strip(),
    )


def current_billing_month(now: datetime | None = None) -> str:
    reference = now.astimezone(KST) if now else datetime.now(KST)
    return reference.strftime("%Y%m")


def normalize_billing_month(month: str | None) -> str:
    if not month:
        return current_billing_month()
    normalized = month.strip()
    if re.fullmatch(r"\d{6}", normalized):
        year = int(normalized[:4])
        month_value = int(normalized[4:])
    else:
        match = re.fullmatch(r"(\d{4})-(\d{2})", normalized)
        if not match:
            fail(400, "invalid_billing_month", "조회 월 형식은 YYYY-MM 또는 YYYYMM만 사용할 수 있습니다.")
        year = int(match.group(1))
        month_value = int(match.group(2))
        normalized = f"{year:04d}{month_value:02d}"
    if month_value < 1 or month_value > 12:
        fail(400, "invalid_billing_month", "조회 월 형식을 확인해 주세요.")
    return normalized


def normalize_billing_text(value: str | None) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z가-힣]+", " ", (value or "").lower())
    return " ".join(cleaned.split())


def billing_amount_to_decimal(value: Any) -> Decimal:
    if value == "" or value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def billing_amount_to_text(value: Any) -> str:
    return str(billing_amount_to_decimal(value))


def collect_billing_search_terms(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        terms: list[str] = []
        for item in value.values():
            terms.extend(collect_billing_search_terms(item))
        return terms
    if isinstance(value, list):
        terms: list[str] = []
        for item in value:
            terms.extend(collect_billing_search_terms(item))
        return terms
    return []


def is_sms_billing_item(item: dict[str, Any], keywords: list[str]) -> bool:
    searchable_text = normalize_billing_text(" ".join(collect_billing_search_terms(item)))
    if not any(keyword in searchable_text for keyword in keywords):
        return False
    excluded_terms = [
        "alim",
        "알림톡",
        "brand message",
        "브랜드 메시지",
        "friendtalk",
        "친구톡",
        "kakao",
    ]
    if "sms" in searchable_text:
        return True
    return "simple easy notification service" in searchable_text and not any(term in searchable_text for term in excluded_terms)


def get_sms_monthly_billing(
    client: NcloudBillingClient | None = None,
    month: str | None = None,
) -> schemas.SmsMonthlyBillingRead:
    target_month = normalize_billing_month(month)
    keywords = [normalize_billing_text(item) for item in get_settings().sms_billing_keyword_list if normalize_billing_text(item)]
    client = client or get_ncloud_billing_client()
    try:
        result = client.get_product_demand_cost_list(start_month=target_month, end_month=target_month)
    except RuntimeError as exc:
        fail(502, "ncloud_billing_error", f"네이버 클라우드 이달 청구금액을 조회하지 못했습니다. {exc}")

    response = result.get("getProductDemandCostListResponse") if isinstance(result, dict) else None
    if not isinstance(response, dict):
        fail(502, "ncloud_billing_error", "네이버 클라우드 Billing 응답 형식을 확인할 수 없습니다.")

    items = response.get("productDemandCostList") or []
    if not isinstance(items, list):
        fail(502, "ncloud_billing_error", "네이버 클라우드 Billing 항목을 해석할 수 없습니다.")

    currency_code: str | None = None
    currency_name: str | None = None
    total_demand_amount = Decimal("0")
    last_write_date: datetime | None = None
    matched_items: list[schemas.SmsMonthlyBillingItemRead] = []

    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        pay_currency = raw_item.get("payCurrency") if isinstance(raw_item.get("payCurrency"), dict) else {}
        if not currency_code:
            currency_code = pay_currency.get("code")
            currency_name = pay_currency.get("codeName")
        if not is_sms_billing_item(raw_item, keywords):
            continue
        product_demand_type = raw_item.get("productDemandType") if isinstance(raw_item.get("productDemandType"), dict) else {}
        write_date = parse_provider_datetime(raw_item.get("writeDate"))
        demand_amount = billing_amount_to_decimal(raw_item.get("demandAmount"))
        total_demand_amount += demand_amount
        if write_date and (last_write_date is None or write_date > last_write_date):
            last_write_date = write_date
        matched_items.append(
            schemas.SmsMonthlyBillingItemRead(
                product_demand_type_code=product_demand_type.get("code"),
                product_demand_type_name=product_demand_type.get("codeName"),
                demand_amount=str(demand_amount),
                use_amount=billing_amount_to_text(raw_item.get("useAmount")),
                write_date=write_date,
            )
        )

    matched_items.sort(key=lambda item: billing_amount_to_decimal(item.demand_amount), reverse=True)
    return schemas.SmsMonthlyBillingRead(
        month=target_month,
        currency_code=currency_code,
        currency_name=currency_name,
        total_demand_amount=str(total_demand_amount),
        last_write_date=last_write_date,
        matched_items=matched_items,
    )


def parse_provider_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=KST)
            return parsed
        except ValueError:
            continue
    return None


def determine_sms_message_type(title: str | None, content: str) -> str:
    if (title or "").strip():
        return "LMS"
    return "SMS" if len(content.encode("utf-8")) <= 90 else "LMS"


def load_sms_target_groups(db: Session, group_ids: list[int]) -> list[models.SmsGroup]:
    unique_group_ids = sorted(set(group_ids))
    if not unique_group_ids:
        return []
    stmt = (
        select(models.SmsGroup)
        .options(joinedload(models.SmsGroup.group_members).joinedload(models.SmsGroupMember.member))
        .where(models.SmsGroup.id.in_(unique_group_ids), models.SmsGroup.is_active.is_(True))
    )
    groups = list(db.scalars(stmt).unique().all())
    if len(groups) != len(unique_group_ids):
        fail(404, "sms_group_not_found", "선택한 문자 그룹을 다시 확인해 주세요.")
    return groups


def add_sms_candidate(
    candidates: dict[str, dict[str, Any]],
    *,
    member: models.Member,
    source_label: str,
) -> None:
    phone = normalize_phone(member.phone)
    if not phone:
        return
    key = f"member:{member.id}" if member.id else f"phone:{phone}"
    if key not in candidates:
        candidates[key] = {
            "member_id": member.id,
            "recipient_name": member.name,
            "phone": phone,
            "sms_agree": member.sms_agree,
            "source_labels": set(),
        }
    candidates[key]["source_labels"].add(source_label)


def birthday_within_days(birth_date: date | None, today_date: date, days: int) -> bool:
    if birth_date is None:
        return False
    try:
        next_birthday = birth_date.replace(year=today_date.year)
    except ValueError:
        next_birthday = date(today_date.year, 2, 28)
    if next_birthday < today_date:
        try:
            next_birthday = birth_date.replace(year=today_date.year + 1)
        except ValueError:
            next_birthday = date(today_date.year + 1, 2, 28)
    return 0 <= (next_birthday - today_date).days <= days


def collect_sms_target_candidates(
    db: Session, payload: schemas.SmsTargetSelection
) -> tuple[list[dict[str, Any]], list[str], list[models.SmsGroup]]:
    candidates: dict[str, dict[str, Any]] = {}
    labels: list[str] = []

    if payload.include_all_members:
        label = "전체 회원"
        labels.append(label)
        members = db.scalars(
            select(models.Member)
            .where(models.Member.is_active.is_(True))
            .order_by(models.Member.name.asc(), models.Member.id.asc())
        ).all()
        for member in members:
            add_sms_candidate(candidates, member=member, source_label=label)

    if payload.include_expiring_memberships:
        label = f"기간제 만료 예정 {payload.expiring_days}일"
        labels.append(label)
        today_date = date.today()
        memberships = db.scalars(
            select(models.MemberMembership)
            .join(models.Member)
            .options(joinedload(models.MemberMembership.member))
            .where(
                models.MemberMembership.status == "사용중",
                models.MemberMembership.end_date.is_not(None),
                models.MemberMembership.end_date >= today_date,
                models.MemberMembership.end_date <= today_date + timedelta(days=payload.expiring_days),
                models.Member.is_active.is_(True),
            )
        ).all()
        for membership in memberships:
            if membership.member:
                add_sms_candidate(candidates, member=membership.member, source_label=label)

    if payload.include_low_remaining_memberships:
        label = f"횟수 만료 예정 {payload.low_remaining_count}회 이하"
        labels.append(label)
        memberships = db.scalars(
            select(models.MemberMembership)
            .join(models.Member)
            .options(joinedload(models.MemberMembership.member))
            .where(
                models.MemberMembership.status == "사용중",
                models.MemberMembership.remaining_count.is_not(None),
                models.MemberMembership.remaining_count <= payload.low_remaining_count,
                models.Member.is_active.is_(True),
            )
        ).all()
        for membership in memberships:
            if membership.member:
                add_sms_candidate(candidates, member=membership.member, source_label=label)

    if payload.include_birthdays:
        label = "오늘 생일자" if payload.birthday_days == 0 else f"{payload.birthday_days}일 안 생일자"
        labels.append(label)
        today_date = date.today()
        members = db.scalars(
            select(models.Member)
            .where(models.Member.is_active.is_(True), models.Member.birth_date.is_not(None))
            .order_by(models.Member.name.asc(), models.Member.id.asc())
        ).all()
        for member in members:
            if birthday_within_days(member.birth_date, today_date, payload.birthday_days):
                add_sms_candidate(candidates, member=member, source_label=label)

    groups = load_sms_target_groups(db, payload.group_ids)
    for group in groups:
        label = f"그룹 {group.name}"
        labels.append(label)
        for item in group.group_members:
            if item.member and item.member.is_active:
                add_sms_candidate(candidates, member=item.member, source_label=label)

    items = []
    for item in candidates.values():
        items.append(
            {
                "member_id": item["member_id"],
                "recipient_name": item["recipient_name"],
                "phone": item["phone"],
                "sms_agree": item["sms_agree"],
                "source_labels": sorted(item["source_labels"]),
            }
        )
    items.sort(key=lambda item: (item["recipient_name"], item["phone"]))
    return items, labels, groups


def split_sms_preview_candidates(
    items: list[dict[str, Any]], content_type: str
) -> tuple[list[schemas.SmsPreviewRecipientRead], list[schemas.SmsPreviewRecipientRead]]:
    eligible: list[schemas.SmsPreviewRecipientRead] = []
    blocked: list[schemas.SmsPreviewRecipientRead] = []
    for item in items:
        blocked_reason = None
        if not item["phone"]:
            blocked_reason = "휴대전화 번호 없음"
        elif content_type == "AD" and not item["sms_agree"]:
            blocked_reason = "문자 수신 미동의"
        recipient = schemas.SmsPreviewRecipientRead(
            member_id=item["member_id"],
            recipient_name=item["recipient_name"],
            phone=item["phone"],
            sms_agree=item["sms_agree"],
            source_labels=item["source_labels"],
            blocked_reason=blocked_reason,
        )
        if blocked_reason:
            blocked.append(recipient)
        else:
            eligible.append(recipient)
    return eligible, blocked


def preview_sms_recipients(db: Session, payload: schemas.SmsPreviewRequest) -> schemas.SmsPreviewResponse:
    items, _, _ = collect_sms_target_candidates(db, payload)
    eligible, blocked = split_sms_preview_candidates(items, payload.content_type)
    return schemas.SmsPreviewResponse(
        summary=schemas.SmsPreviewSummary(
            total_candidates=len(items),
            eligible_count=len(eligible),
            blocked_count=len(blocked),
            excluded_count=0,
        ),
        eligible_recipients=eligible,
        blocked_recipients=blocked,
    )


def filter_sms_final_recipients(
    eligible: list[schemas.SmsPreviewRecipientRead],
    *,
    excluded_member_ids: list[int],
    excluded_phones: list[str],
) -> tuple[list[schemas.SmsPreviewRecipientRead], int]:
    excluded_member_id_set = set(excluded_member_ids)
    excluded_phone_set = {
        normalized
        for phone in excluded_phones
        if (normalized := normalize_phone(phone))
    }
    final_recipients: list[schemas.SmsPreviewRecipientRead] = []
    excluded_count = 0
    for item in eligible:
        if (item.member_id is not None and item.member_id in excluded_member_id_set) or item.phone in excluded_phone_set:
            excluded_count += 1
            continue
        final_recipients.append(item)
    return final_recipients, excluded_count


def build_sms_message_recipients(
    message_id: int,
    recipients: list[schemas.SmsPreviewRecipientRead],
) -> list[models.SmsMessageRecipient]:
    return [
        models.SmsMessageRecipient(
            sms_message_id=message_id,
            member_id=item.member_id,
            recipient_name=item.recipient_name,
            phone=item.phone,
            sms_agree=item.sms_agree,
            source_labels=item.source_labels,
            status="대기",
        )
        for item in recipients
    ]


def replace_sms_message_recipients(
    message: models.SmsMessage,
    recipients: list[schemas.SmsPreviewRecipientRead],
) -> None:
    message.recipients = [
        models.SmsMessageRecipient(
            member_id=item.member_id,
            recipient_name=item.recipient_name,
            phone=item.phone,
            sms_agree=item.sms_agree,
            source_labels=item.source_labels,
            status="대기",
        )
        for item in recipients
    ]


def mark_sms_message_failed(message: models.SmsMessage, *, reason: str, status: str = "실패", fail_code: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    message.status = status
    message.sent_at = message.sent_at or now
    message.success_count = 0
    message.fail_count = len(message.recipients)
    message.sync_completed_at = now
    for recipient in message.recipients:
        recipient.status = "실패"
        recipient.fail_code = fail_code or recipient.fail_code
        recipient.fail_reason = reason
        recipient.sent_at = recipient.sent_at or now


def build_sms_message(
    payload: schemas.SmsTargetSelection,
    *,
    content: str,
    title: str | None,
    content_type: str,
    template_id: int | None,
    message_type: str,
    target_count: int,
    operator_name: str | None,
    labels: list[str],
    groups: list[models.SmsGroup],
    eligible_count: int,
    blocked_count: int,
    excluded_count: int,
    excluded_member_ids: list[int] | None = None,
    excluded_phones: list[str] | None = None,
    scheduled_at: datetime | None = None,
) -> models.SmsMessage:
    return models.SmsMessage(
        target_type=labels[0] if len(labels) == 1 else "복합",
        title=title,
        content=content,
        content_type=content_type,
        message_type=message_type,
        template_id=template_id,
        target_count=target_count,
        success_count=0,
        fail_count=0,
        status="예약" if scheduled_at else "대기",
        provider_name="NAVER_SENS",
        operator_name=operator_name,
        target_summary=build_sms_target_summary(
            payload,
            content_type=content_type,
            labels=labels,
            groups=groups,
            eligible_count=eligible_count,
            blocked_count=blocked_count,
            excluded_count=excluded_count,
            excluded_member_ids=excluded_member_ids,
            excluded_phones=excluded_phones,
        ),
        scheduled_at=scheduled_at,
    )


def apply_sms_delivery_result(recipient: models.SmsMessageRecipient, payload: dict[str, Any]) -> None:
    recipient.provider_message_id = payload.get("messageId") or recipient.provider_message_id
    recipient.sent_at = parse_provider_datetime(payload.get("completeTime") or payload.get("requestTime")) or recipient.sent_at
    request_status = str(payload.get("status") or "").upper()
    receipt_status = str(payload.get("statusName") or "").lower()
    receipt_code = str(payload.get("statusCode") or "")
    status_message = str(payload.get("statusMessage") or "").strip() or None

    if request_status in {"READY", "PROCESSING"}:
        recipient.status = "발송중"
        return
    if request_status == "COMPLETED":
        if receipt_status == "success" or receipt_code == "0":
            recipient.status = "성공"
            recipient.fail_code = None
            recipient.fail_reason = None
        elif receipt_status == "fail" or receipt_code:
            recipient.status = "실패"
            recipient.fail_code = receipt_code or recipient.fail_code
            recipient.fail_reason = status_message or recipient.fail_reason
        else:
            recipient.status = "발송중"


def update_sms_message_counts(message: models.SmsMessage) -> None:
    message.success_count = sum(1 for item in message.recipients if item.status == "성공")
    message.fail_count = sum(1 for item in message.recipients if item.status == "실패")
    sent_times = [item.sent_at for item in message.recipients if item.sent_at]
    if sent_times:
        message.sent_at = min(sent_times)
    if not message.recipients:
        message.status = "실패"
        message.sync_completed_at = datetime.now(timezone.utc)
        return
    if message.success_count + message.fail_count == len(message.recipients):
        message.status = "실패" if message.fail_count == len(message.recipients) else "완료"
        message.sync_completed_at = datetime.now(timezone.utc)
    elif message.success_count or any(item.status == "발송중" for item in message.recipients):
        message.status = "발송중"


def sync_sms_schedule_status(
    db: Session, message_id: int, provider: NaverSensSmsProvider | None = None
) -> models.SmsMessage:
    message = get_sms_schedule_or_404(db, message_id)
    if not message.provider_request_id or message.status not in SMS_SCHEDULE_SYNC_STATUSES:
        return message

    provider = provider or get_sms_provider()
    result = provider.get_reservation_status(reserve_id=message.provider_request_id)
    reserve_status = str(result.get("reserveStatus") or "").upper()
    reserve_time = parse_provider_datetime(result.get("reserveTime"))
    if reserve_time:
        message.scheduled_at = reserve_time

    if reserve_status == "READY":
        message.status = "예약"
        db.commit()
        return get_sms_message_or_404(db, message.id)

    if reserve_status == "CANCELED":
        message.status = "예약취소"
        message.canceled_at = message.canceled_at or datetime.now(timezone.utc)
        message.sync_completed_at = message.sync_completed_at or datetime.now(timezone.utc)
        db.commit()
        return get_sms_message_or_404(db, message.id)

    if reserve_status in {"FAIL", "STALE", "SKIP"}:
        mark_sms_message_failed(
            message,
            reason="예약 발송에 실패했습니다.",
            fail_code=reserve_status,
        )
        db.commit()
        return get_sms_message_or_404(db, message.id)

    if reserve_status in {"PROCESSING", "DONE"}:
        message.status = "발송중"
        if reserve_time and not message.sent_at:
            message.sent_at = reserve_time
        db.flush()
        return sync_sms_message_delivery(db, message.id, provider)

    db.commit()
    return get_sms_message_or_404(db, message.id)


def sync_sms_message_delivery(
    db: Session, message_id: int, provider: NaverSensSmsProvider | None = None
) -> models.SmsMessage:
    message = get_sms_message_or_404(db, message_id)
    if not message.provider_request_id:
        return message

    provider = provider or get_sms_provider()
    recipients_by_phone: dict[str, models.SmsMessageRecipient] = {}
    for recipient in message.recipients:
        phone = normalize_phone(recipient.phone)
        if phone and phone not in recipients_by_phone:
            recipients_by_phone[phone] = recipient

    next_token: str | None = None
    while True:
        result = provider.list_messages(request_id=message.provider_request_id, page_size=100, page_index=0, next_token=next_token)
        for item in result.get("messages", []):
            phone = normalize_phone(item.get("to"))
            recipient = recipients_by_phone.get(phone or "")
            if not recipient and item.get("messageId"):
                recipient = next((target for target in message.recipients if target.provider_message_id == item.get("messageId")), None)
            if not recipient:
                continue
            apply_sms_delivery_result(recipient, item)
        next_token = result.get("nextToken")
        if not result.get("hasMore") or not next_token:
            break

    for recipient in message.recipients:
        if recipient.provider_message_id and recipient.status == "발송중":
            detail = provider.get_message(message_id=recipient.provider_message_id)
            detail_items = detail.get("messages") or []
            if detail_items:
                apply_sms_delivery_result(recipient, detail_items[0])

    update_sms_message_counts(message)
    db.commit()
    return get_sms_message_or_404(db, message.id)


def sync_sms_message_runtime_state(
    db: Session, message_id: int, provider: NaverSensSmsProvider | None = None
) -> models.SmsMessage:
    message = get_sms_message_or_404(db, message_id)
    if not message.provider_request_id:
        return message
    if message.scheduled_at and message.status == "예약":
        return sync_sms_schedule_status(db, message_id, provider)
    if message.status == "발송중":
        return sync_sms_message_delivery(db, message_id, provider)
    return message


def prepare_sms_dispatch_request(
    db: Session,
    payload: schemas.SmsSendRequest | schemas.SmsScheduleRequest,
) -> tuple[
    str,
    str | None,
    str,
    list[str],
    list[models.SmsGroup],
    list[schemas.SmsPreviewRecipientRead],
    list[schemas.SmsPreviewRecipientRead],
    list[schemas.SmsPreviewRecipientRead],
    int,
]:
    content = payload.content.strip()
    if not content:
        fail(400, "empty_sms_content", "문자 내용을 입력해 주세요.")
    if payload.template_id is not None:
        get_sms_template_or_404(db, payload.template_id)

    items, labels, groups = collect_sms_target_candidates(db, payload)
    eligible, blocked = split_sms_preview_candidates(items, payload.content_type)
    final_recipients, excluded_count = filter_sms_final_recipients(
        eligible,
        excluded_member_ids=payload.excluded_member_ids,
        excluded_phones=payload.excluded_phones,
    )
    if not final_recipients:
        fail(400, "no_sms_recipients", "발송 가능한 대상이 없습니다.")
    title = (payload.title or "").strip() or None
    message_type = determine_sms_message_type(title, content)
    return content, title, message_type, labels, groups, eligible, blocked, final_recipients, excluded_count


def send_sms_message(
    db: Session, payload: schemas.SmsSendRequest, provider: NaverSensSmsProvider | None = None
) -> models.SmsMessage:
    content, title, message_type, labels, groups, eligible, blocked, final_recipients, excluded_count = prepare_sms_dispatch_request(
        db, payload
    )
    message = build_sms_message(
        payload,
        content=content,
        title=title,
        content_type=payload.content_type,
        template_id=payload.template_id,
        message_type=message_type,
        target_count=len(final_recipients),
        operator_name=payload.operator_name,
        labels=labels,
        groups=groups,
        eligible_count=len(eligible),
        blocked_count=len(blocked),
        excluded_count=excluded_count,
        excluded_member_ids=payload.excluded_member_ids,
        excluded_phones=payload.excluded_phones,
    )
    db.add(message)
    db.flush()
    db.add_all(build_sms_message_recipients(message.id, final_recipients))
    db.commit()

    provider = provider or get_sms_provider()
    try:
        response = provider.send_messages(
            recipients=[item.phone for item in final_recipients],
            content=content,
            title=title,
            content_type=payload.content_type,
            message_type=message_type,
        )
        request_id = str(response.get("requestId") or "").strip()
        request_time = parse_provider_datetime(response.get("requestTime")) or datetime.now(timezone.utc)
        if not request_id:
            raise RuntimeError("문자 발송 요청 ID를 받지 못했습니다.")
        message = get_sms_message_or_404(db, message.id)
        message.provider_request_id = request_id
        message.status = "발송중"
        message.sent_at = request_time
        for recipient in message.recipients:
            recipient.status = "발송중"
            recipient.sent_at = request_time
        db.flush()
        add_audit_log(
            db,
            action_type="문자 발송",
            target_type="sms_message",
            target_id=message.id,
            after_data={"target_count": message.target_count, "content_type": message.content_type, "status": message.status},
            actor_name=payload.operator_name,
        )
        db.commit()
        try:
            return sync_sms_message_delivery(db, message.id, provider)
        except Exception:
            db.rollback()
            return get_sms_message_or_404(db, message.id)
    except Exception as exc:
        db.rollback()
        message = get_sms_message_or_404(db, message.id)
        failure_reason = str(exc) or "문자 발송 요청이 실패했습니다."
        mark_sms_message_failed(message, reason=failure_reason)
        add_audit_log(
            db,
            action_type="문자 발송 실패",
            target_type="sms_message",
            target_id=message.id,
            after_data={"target_count": message.target_count, "status": message.status, "fail_reason": failure_reason},
            actor_name=payload.operator_name,
        )
        db.commit()
        return get_sms_message_or_404(db, message.id)


def create_sms_schedule(
    db: Session, payload: schemas.SmsScheduleRequest, provider: NaverSensSmsProvider | None = None
) -> models.SmsMessage:
    scheduled_at = validate_sms_schedule_datetime(payload.scheduled_at)
    content, title, message_type, labels, groups, eligible, blocked, final_recipients, excluded_count = prepare_sms_dispatch_request(
        db, payload
    )
    message = build_sms_message(
        payload,
        content=content,
        title=title,
        content_type=payload.content_type,
        template_id=payload.template_id,
        message_type=message_type,
        target_count=len(final_recipients),
        operator_name=payload.operator_name,
        labels=labels,
        groups=groups,
        eligible_count=len(eligible),
        blocked_count=len(blocked),
        excluded_count=excluded_count,
        excluded_member_ids=payload.excluded_member_ids,
        excluded_phones=payload.excluded_phones,
        scheduled_at=scheduled_at,
    )
    db.add(message)
    db.flush()
    db.add_all(build_sms_message_recipients(message.id, final_recipients))
    db.commit()

    provider = provider or get_sms_provider()
    reserve_time, reserve_time_zone = format_sms_reserve_time(scheduled_at)
    try:
        response = provider.send_messages(
            recipients=[item.phone for item in final_recipients],
            content=content,
            title=title,
            content_type=payload.content_type,
            message_type=message_type,
            reserve_time=reserve_time,
            reserve_time_zone=reserve_time_zone,
        )
        request_id = str(response.get("requestId") or "").strip()
        if not request_id:
            raise RuntimeError("문자 예약 요청 ID를 받지 못했습니다.")
        message = get_sms_schedule_or_404(db, message.id)
        message.provider_request_id = request_id
        message.status = "예약"
        message.sent_at = None
        message.canceled_at = None
        db.flush()
        add_audit_log(
            db,
            action_type="문자 예약 등록",
            target_type="sms_message",
            target_id=message.id,
            after_data={
                "target_count": message.target_count,
                "content_type": message.content_type,
                "status": message.status,
                "scheduled_at": message.scheduled_at.isoformat() if message.scheduled_at else None,
            },
            actor_name=payload.operator_name,
        )
        db.commit()
        return get_sms_schedule_or_404(db, message.id)
    except Exception as exc:
        db.rollback()
        message = get_sms_schedule_or_404(db, message.id)
        failure_reason = str(exc) or "문자 예약 요청이 실패했습니다."
        mark_sms_message_failed(message, reason=failure_reason)
        add_audit_log(
            db,
            action_type="문자 예약 실패",
            target_type="sms_message",
            target_id=message.id,
            after_data={
                "target_count": message.target_count,
                "status": message.status,
                "scheduled_at": message.scheduled_at.isoformat() if message.scheduled_at else None,
                "fail_reason": failure_reason,
            },
            actor_name=payload.operator_name,
        )
        db.commit()
        return get_sms_schedule_or_404(db, message.id)


def update_sms_schedule(
    db: Session, message_id: int, payload: schemas.SmsScheduleRequest, provider: NaverSensSmsProvider | None = None
) -> models.SmsMessage:
    message = sync_sms_message_runtime_state(db, message_id, provider)
    message = get_sms_schedule_or_404(db, message.id)
    if message.status != "예약":
        fail(400, "sms_schedule_not_editable", "발송 전 예약만 수정할 수 있습니다.")
    if not message.provider_request_id:
        fail(400, "sms_schedule_invalid_state", "예약 요청 정보를 다시 확인해 주세요.")

    scheduled_at = validate_sms_schedule_datetime(payload.scheduled_at)
    preserve_existing_recipients = sms_target_config_matches_summary(
        message.target_summary,
        payload=payload,
        content_type=payload.content_type,
        excluded_member_ids=payload.excluded_member_ids,
        excluded_phones=payload.excluded_phones,
    )

    title = (payload.title or "").strip() or None
    content = payload.content.strip()
    if not content:
        fail(400, "empty_sms_content", "문자 내용을 입력해 주세요.")
    if payload.template_id is not None:
        get_sms_template_or_404(db, payload.template_id)
    message_type = determine_sms_message_type(title, content)

    if preserve_existing_recipients:
        final_recipients = [
            schemas.SmsPreviewRecipientRead(
                member_id=item.member_id,
                recipient_name=item.recipient_name or item.member_name or "",
                phone=item.phone,
                sms_agree=item.sms_agree,
                source_labels=item.source_labels or [],
            )
            for item in message.recipients
        ]
        if not final_recipients:
            fail(400, "no_sms_recipients", "발송 가능한 대상이 없습니다.")
        target_summary = dict(message.target_summary or {})
    else:
        _, _, _, labels, groups, eligible, blocked, final_recipients, excluded_count = prepare_sms_dispatch_request(db, payload)
        target_summary = build_sms_target_summary(
            payload,
            content_type=payload.content_type,
            labels=labels,
            groups=groups,
            eligible_count=len(eligible),
            blocked_count=len(blocked),
            excluded_count=excluded_count,
            excluded_member_ids=payload.excluded_member_ids,
            excluded_phones=payload.excluded_phones,
        )

    provider = provider or get_sms_provider()
    try:
        reserve_time, reserve_time_zone = format_sms_reserve_time(scheduled_at)
        response = provider.send_messages(
            recipients=[item.phone for item in final_recipients],
            content=content,
            title=title,
            content_type=payload.content_type,
            message_type=message_type,
            reserve_time=reserve_time,
            reserve_time_zone=reserve_time_zone,
        )
        new_request_id = str(response.get("requestId") or "").strip()
        if not new_request_id:
            raise RuntimeError("문자 예약 요청 ID를 받지 못했습니다.")

        try:
            provider.cancel_reservation(reserve_id=message.provider_request_id)
        except Exception:
            try:
                provider.cancel_reservation(reserve_id=new_request_id)
            except Exception:
                pass
            raise RuntimeError("기존 예약을 취소하지 못했습니다.")
    except Exception as exc:
        fail(502, "sms_schedule_update_failed", str(exc) or "문자 예약 수정에 실패했습니다.")

    before = model_snapshot(message, ["title", "content", "content_type", "message_type", "target_count", "status", "scheduled_at"])
    message.target_type = target_summary.get("labels", [message.target_type])[0] if len(target_summary.get("labels", [])) == 1 else "복합"
    message.title = title
    message.content = content
    message.content_type = payload.content_type
    message.message_type = message_type
    message.template_id = payload.template_id
    message.target_count = len(final_recipients)
    message.success_count = 0
    message.fail_count = 0
    message.status = "예약"
    message.provider_name = "NAVER_SENS"
    message.provider_request_id = new_request_id
    message.target_summary = target_summary
    message.scheduled_at = scheduled_at
    message.sent_at = None
    message.canceled_at = None
    message.sync_completed_at = None
    if payload.operator_name is not None:
        message.operator_name = payload.operator_name
    if preserve_existing_recipients:
        for recipient in message.recipients:
            recipient.status = "대기"
            recipient.provider_message_id = None
            recipient.fail_code = None
            recipient.fail_reason = None
            recipient.sent_at = None
    else:
        replace_sms_message_recipients(message, final_recipients)
    db.flush()
    add_audit_log(
        db,
        action_type="문자 예약 수정",
        target_type="sms_message",
        target_id=message.id,
        before_data=before,
        after_data=model_snapshot(message, ["title", "content", "content_type", "message_type", "target_count", "status", "scheduled_at"]),
        actor_name=payload.operator_name,
    )
    db.commit()
    return get_sms_schedule_or_404(db, message.id)


def cancel_sms_schedule(
    db: Session, message_id: int, provider: NaverSensSmsProvider | None = None, operator_name: str | None = None
) -> models.SmsMessage:
    message = sync_sms_message_runtime_state(db, message_id, provider)
    message = get_sms_schedule_or_404(db, message.id)
    if message.status != "예약":
        fail(400, "sms_schedule_not_cancelable", "발송 전 예약만 삭제할 수 있습니다.")
    if not message.provider_request_id:
        fail(400, "sms_schedule_invalid_state", "예약 요청 정보를 다시 확인해 주세요.")

    provider = provider or get_sms_provider()
    try:
        provider.cancel_reservation(reserve_id=message.provider_request_id)
    except Exception as exc:
        fail(502, "sms_schedule_cancel_failed", str(exc) or "문자 예약 삭제에 실패했습니다.")
    before = model_snapshot(message, ["status", "canceled_at"])
    message.status = "예약취소"
    message.canceled_at = datetime.now(timezone.utc)
    message.sync_completed_at = message.sync_completed_at or message.canceled_at
    db.flush()
    add_audit_log(
        db,
        action_type="문자 예약 취소",
        target_type="sms_message",
        target_id=message.id,
        before_data=before,
        after_data=model_snapshot(message, ["status", "canceled_at"]),
        actor_name=operator_name or message.operator_name,
    )
    db.commit()
    return get_sms_schedule_or_404(db, message.id)


def query_sms_schedules(db: Session, page: int, size: int) -> tuple[list[models.SmsMessage], int]:
    pending_ids = db.scalars(
        select(models.SmsMessage.id).where(
            models.SmsMessage.scheduled_at.is_not(None),
            models.SmsMessage.status == "예약",
            models.SmsMessage.provider_request_id.is_not(None),
        )
    ).all()
    for message_id in pending_ids:
        try:
            sync_sms_schedule_status(db, message_id)
        except Exception:
            db.rollback()

    stmt = select(models.SmsMessage).where(
        models.SmsMessage.scheduled_at.is_not(None),
        models.SmsMessage.status.in_(SMS_SCHEDULE_LIST_STATUSES),
    )
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(
        stmt.order_by(models.SmsMessage.scheduled_at.desc(), models.SmsMessage.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(items), total


def query_sms_history(db: Session, page: int, size: int) -> tuple[list[models.SmsMessage], int]:
    pending_ids = db.scalars(
        select(models.SmsMessage.id).where(
            models.SmsMessage.provider_request_id.is_not(None),
            models.SmsMessage.status.in_(SMS_SCHEDULE_SYNC_STATUSES),
        )
    ).all()
    for message_id in pending_ids:
        try:
            sync_sms_message_runtime_state(db, message_id)
        except Exception:
            db.rollback()

    stmt = select(models.SmsMessage).where(models.SmsMessage.status.not_in(SMS_HISTORY_EXCLUDED_STATUSES))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(
        stmt.order_by(models.SmsMessage.created_at.desc(), models.SmsMessage.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(items), total


def query_sms_message_recipients(
    db: Session, message_id: int, keyword: str | None, page: int, size: int
) -> tuple[models.SmsMessage, list[models.SmsMessageRecipient], int]:
    message = get_sms_message_or_404(db, message_id)
    if message.provider_request_id and message.status in SMS_SCHEDULE_SYNC_STATUSES:
        try:
            message = sync_sms_message_runtime_state(db, message_id)
        except Exception:
            db.rollback()
            message = get_sms_message_or_404(db, message_id)

    stmt = (
        select(models.SmsMessageRecipient)
        .outerjoin(models.Member)
        .options(joinedload(models.SmsMessageRecipient.member))
        .where(models.SmsMessageRecipient.sms_message_id == message_id)
    )
    if keyword:
        like = f"%{keyword}%"
        normalized = normalize_phone(keyword)
        conditions = [
            models.SmsMessageRecipient.recipient_name.ilike(like),
            models.Member.name.ilike(like),
            models.SmsMessageRecipient.fail_reason.ilike(like),
            models.SmsMessageRecipient.status.ilike(like),
        ]
        if normalized:
            conditions.append(models.SmsMessageRecipient.phone.ilike(f"%{normalized}%"))
        stmt = stmt.where(or_(*conditions))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(
        stmt.order_by(models.SmsMessageRecipient.id.asc()).offset((page - 1) * size).limit(size)
    ).all()
    return message, list(items), total
