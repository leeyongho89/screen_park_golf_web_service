from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.config import get_settings
from app.sms_provider import NaverSensSmsProvider
from app.utils import calculate_end_date, normalize_phone


LEGACY_PRODUCT_TYPES = {"정기권": "기간제", "쿠폰": "횟수", "묶음티켓": "횟수"}
MEMBERSHIP_PRODUCT_TYPES = {"기간제", "횟수"}
KST = timezone(timedelta(hours=9))


def fail(status_code: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def model_snapshot(obj: Any, fields: list[str]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for field in fields:
        value = getattr(obj, field)
        if isinstance(value, (date, datetime)):
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
    member = models.Member(**payload.model_dump(exclude={"operator_name"}))
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
        stmt = stmt.where(models.Member.created_at >= datetime.combine(created_from, time.min))
    if created_to:
        stmt = stmt.where(models.Member.created_at < datetime.combine(created_to + timedelta(days=1), time.min))
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
    today_start = datetime.combine(today, time.min)
    tomorrow_start = today_start + timedelta(days=1)
    today_new_members = db.scalar(
        select(func.count()).where(
            models.Member.created_at >= datetime.combine(new_member_start, time.min),
            models.Member.created_at < tomorrow_start,
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
    if not message.recipients:
        message.status = "실패"
        message.sync_completed_at = datetime.now(timezone.utc)
        return
    if message.success_count + message.fail_count == len(message.recipients):
        message.status = "실패" if message.fail_count == len(message.recipients) else "완료"
        message.sync_completed_at = datetime.now(timezone.utc)
    elif message.success_count or any(item.status == "발송중" for item in message.recipients):
        message.status = "발송중"


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
        result = provider.list_messages(request_id=message.provider_request_id, page_size=100, page_index=1, next_token=next_token)
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


def send_sms_message(
    db: Session, payload: schemas.SmsSendRequest, provider: NaverSensSmsProvider | None = None
) -> models.SmsMessage:
    content = payload.content.strip()
    if not content:
        fail(400, "empty_sms_content", "문자 내용을 입력해 주세요.")
    if payload.template_id is not None:
        get_sms_template_or_404(db, payload.template_id)

    items, labels, groups = collect_sms_target_candidates(db, payload)
    eligible, blocked = split_sms_preview_candidates(items, payload.content_type)
    excluded_member_ids = set(payload.excluded_member_ids)
    excluded_phones = {normalize_phone(phone) for phone in payload.excluded_phones if normalize_phone(phone)}

    final_recipients: list[schemas.SmsPreviewRecipientRead] = []
    excluded_count = 0
    for item in eligible:
        if (item.member_id is not None and item.member_id in excluded_member_ids) or item.phone in excluded_phones:
            excluded_count += 1
            continue
        final_recipients.append(item)
    if not final_recipients:
        fail(400, "no_sms_recipients", "발송 가능한 대상이 없습니다.")

    message_type = determine_sms_message_type(payload.title, content)
    title = (payload.title or "").strip() or None
    message = models.SmsMessage(
        target_type=labels[0] if len(labels) == 1 else "복합",
        title=title,
        content=content,
        content_type=payload.content_type,
        message_type=message_type,
        template_id=payload.template_id,
        target_count=len(final_recipients),
        success_count=0,
        fail_count=0,
        status="대기",
        provider_name="NAVER_SENS",
        operator_name=payload.operator_name,
        target_summary={
            "labels": labels,
            "group_ids": sorted(set(payload.group_ids)),
            "group_names": [group.name for group in groups],
            "include_all_members": payload.include_all_members,
            "include_expiring_memberships": payload.include_expiring_memberships,
            "expiring_days": payload.expiring_days,
            "include_low_remaining_memberships": payload.include_low_remaining_memberships,
            "low_remaining_count": payload.low_remaining_count,
            "eligible_count": len(eligible),
            "blocked_count": len(blocked),
            "excluded_count": excluded_count,
        },
    )
    db.add(message)
    db.flush()
    recipients = [
        models.SmsMessageRecipient(
            sms_message_id=message.id,
            member_id=item.member_id,
            recipient_name=item.recipient_name,
            phone=item.phone,
            status="대기",
        )
        for item in final_recipients
    ]
    db.add_all(recipients)
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
        message.status = "실패"
        message.sent_at = datetime.now(timezone.utc)
        message.fail_count = message.target_count
        message.sync_completed_at = datetime.now(timezone.utc)
        for recipient in message.recipients:
            recipient.status = "실패"
            recipient.fail_reason = failure_reason
            recipient.sent_at = message.sent_at
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


def query_sms_history(db: Session, page: int, size: int) -> tuple[list[models.SmsMessage], int]:
    stmt = select(models.SmsMessage)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(models.SmsMessage.created_at.desc(), models.SmsMessage.id.desc()).offset((page - 1) * size).limit(size)).all()
    return list(items), total


def query_sms_message_recipients(
    db: Session, message_id: int, keyword: str | None, page: int, size: int
) -> tuple[models.SmsMessage, list[models.SmsMessageRecipient], int]:
    message = get_sms_message_or_404(db, message_id)
    if message.status == "발송중" and message.provider_request_id:
        try:
            message = sync_sms_message_delivery(db, message_id)
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
