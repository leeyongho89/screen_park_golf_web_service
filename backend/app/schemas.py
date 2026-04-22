from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.utils import normalize_phone


KST = timezone(timedelta(hours=9))


class ErrorResponse(BaseModel):
    code: str
    message: str


class ListResponse(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    size: int = 20


class MemberBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=8, max_length=30)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=300)
    sms_agree: bool = True
    memo: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = normalize_phone(value)
        if not normalized or len(normalized) < 8:
            raise ValueError("휴대전화 번호를 확인해 주세요.")
        return normalized


class MemberCreate(MemberBase):
    operator_name: str | None = None


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    phone: str | None = Field(default=None, min_length=8, max_length=30)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=300)
    sms_agree: bool | None = None
    memo: str | None = None
    is_active: bool | None = None
    operator_name: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = normalize_phone(value)
        if not normalized or len(normalized) < 8:
            raise ValueError("휴대전화 번호를 확인해 주세요.")
        return normalized


class MemberRead(BaseModel):
    id: int
    name: str
    phone: str
    birth_date: date | None = None
    gender: str | None = None
    email: str | None = None
    address: str | None = None
    sms_agree: bool
    memo: str | None = None
    last_visit_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemberListRead(MemberRead):
    total_sales_amount: Decimal = Decimal("0")
    recent_30_days_sales_amount: Decimal = Decimal("0")


class MembershipProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    product_type: str = Field(pattern="^(기간제|횟수|판매)$")
    duration_days: int | None = Field(default=None, ge=1)
    total_count: int | None = Field(default=None, ge=1)
    price: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_product_policy(self) -> "MembershipProductBase":
        if self.product_type in {"기간제", "횟수"} and self.duration_days is None:
            raise ValueError("기간제와 횟수 상품은 유효 일수를 입력해 주세요.")
        if self.product_type == "횟수" and self.total_count is None:
            raise ValueError("횟수 상품은 횟수를 입력해 주세요.")
        if self.product_type == "기간제" and self.total_count is not None:
            raise ValueError("기간제 상품에는 횟수를 입력할 수 없습니다.")
        if self.product_type == "판매" and (self.duration_days is not None or self.total_count is not None):
            raise ValueError("판매 상품에는 유효 일수나 횟수를 입력할 수 없습니다.")
        return self


class MembershipProductCreate(MembershipProductBase):
    operator_name: str | None = None


class MembershipProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    product_type: str | None = Field(default=None, pattern="^(기간제|횟수|판매)$")
    duration_days: int | None = Field(default=None, ge=1)
    total_count: int | None = Field(default=None, ge=1)
    price: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None
    operator_name: str | None = None


class MembershipProductRead(BaseModel):
    id: int
    name: str
    product_type: str
    duration_days: int | None
    total_count: int | None
    price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemberMembershipCreate(BaseModel):
    member_id: int
    product_id: int | None = None
    start_date: date = Field(default_factory=date.today)
    end_date: date | None = None
    duration_type: str | None = Field(default=None, pattern="^(한달|지정일수)$")
    duration_days: int | None = Field(default=None, ge=1)
    total_count: int | None = Field(default=None, ge=1)
    sold_price: Decimal = Field(default=Decimal("0"), ge=0)
    note: str | None = None
    operator_name: str | None = None


class MemberMembershipRead(BaseModel):
    id: int
    member_id: int
    member_name: str | None = None
    member_phone: str | None = None
    member_memo: str | None = None
    product_id: int | None
    product_name: str | None = None
    product_type: str | None = None
    start_date: date
    end_date: date | None
    duration_type: str | None
    duration_days: int | None
    total_count: int | None
    remaining_count: int | None
    status: str
    sold_price: Decimal
    source_sale_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipActionRequest(BaseModel):
    count: int = Field(default=1, ge=1)
    note: str | None = None
    operator_name: str | None = None


class MembershipAdjustRequest(BaseModel):
    remaining_count: int = Field(ge=0)
    note: str | None = None
    operator_name: str | None = None


class MembershipPeriodAdjustRequest(BaseModel):
    start_date: date
    end_date: date | None = None
    note: str | None = None
    operator_name: str | None = None


class MembershipStatusRequest(BaseModel):
    note: str | None = None
    operator_name: str | None = None


class MembershipUsageLogRead(BaseModel):
    id: int
    member_membership_id: int
    member_id: int
    action_type: str
    change_count: int | None
    before_remaining_count: int | None
    after_remaining_count: int | None
    note: str | None
    operator_name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SaleCreate(BaseModel):
    member_id: int | None = None
    member_name: str | None = Field(default=None, max_length=80)
    member_phone: str | None = Field(default=None, max_length=30)
    product_id: int
    payment_method: str = Field(pattern="^(현금|카드|계좌이체|기타)$")
    amount: Decimal = Field(gt=0)
    start_date: date | None = None
    end_date: date | None = None
    total_count: int | None = Field(default=None, ge=1)
    note: str | None = None
    operator_name: str | None = None

    @field_validator("member_phone")
    @classmethod
    def validate_member_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = normalize_phone(value)
        if not normalized or len(normalized) < 8:
            raise ValueError("휴대전화 번호를 확인해 주세요.")
        return normalized


class SaleRead(BaseModel):
    id: int
    member_id: int | None
    member_name_snapshot: str | None
    member_phone_snapshot: str | None
    sale_type: str
    payment_method: str
    amount: Decimal
    sale_date: date
    related_membership_id: int | None
    duration_type: str | None
    duration_days: int | None
    coupon_count: int | None
    status: str
    original_sale_id: int | None
    note: str | None
    operator_name: str | None
    created_at: datetime
    refunded_at: datetime | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SaleRefundRequest(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    note: str | None = None
    operator_name: str | None = None


class ReservationCreate(BaseModel):
    bay_number: int = Field(ge=1, le=6)
    member_id: int | None = None
    customer_name: str | None = Field(default=None, max_length=80)
    customer_phone: str | None = Field(default=None, max_length=30)
    reservation_date: date
    start_time: time
    end_time: time
    note: str | None = None
    operator_name: str | None = None

    @field_validator("customer_phone")
    @classmethod
    def validate_customer_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = normalize_phone(value)
        if not normalized or len(normalized) < 8:
            raise ValueError("휴대전화 번호를 확인해 주세요.")
        return normalized


class ReservationUpdate(BaseModel):
    bay_number: int | None = Field(default=None, ge=1, le=6)
    member_id: int | None = None
    customer_name: str | None = Field(default=None, max_length=80)
    customer_phone: str | None = Field(default=None, max_length=30)
    reservation_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    note: str | None = None
    operator_name: str | None = None

    @field_validator("customer_phone")
    @classmethod
    def validate_customer_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = normalize_phone(value)
        if not normalized or len(normalized) < 8:
            raise ValueError("휴대전화 번호를 확인해 주세요.")
        return normalized


class ReservationStatusRequest(BaseModel):
    note: str | None = None
    operator_name: str | None = None


class ReservationRead(BaseModel):
    id: int
    bay_number: int
    member_id: int | None
    member_name: str | None = None
    member_phone: str | None = None
    customer_name: str
    customer_phone: str
    reservation_date: date
    start_time: time
    end_time: time
    status: str
    note: str | None
    operator_name: str | None
    canceled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SalesBreakdownItem(BaseModel):
    label: str
    amount: Decimal
    count: int


class SalesDailyItem(BaseModel):
    sale_date: date
    amount: Decimal
    count: int


class SalesSummary(BaseModel):
    from_date: date
    to_date: date
    total_amount: Decimal
    total_count: int
    refund_count: int
    by_payment_method: dict[str, Decimal]
    by_sale_type: dict[str, Decimal]
    by_member: list[SalesBreakdownItem] = Field(default_factory=list)
    by_day: list[SalesDailyItem] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    current_member_count: int
    today_new_members: int
    today_sales: Decimal
    month_sales: Decimal
    expiring_memberships: int
    low_remaining_memberships: int
    recent_sales: list[SaleRead]


class SmsGroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class SmsGroupCreate(SmsGroupBase):
    member_ids: list[int] = Field(default_factory=list)
    operator_name: str | None = None


class SmsGroupUpdate(SmsGroupBase):
    member_ids: list[int] = Field(default_factory=list)
    is_active: bool = True
    operator_name: str | None = None


class SmsGroupRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_active: bool
    operator_name: str | None = None
    member_ids: list[int] = Field(default_factory=list)
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SmsTemplateBase(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1)


class SmsTemplateCreate(SmsTemplateBase):
    is_active: bool = True
    operator_name: str | None = None


class SmsTemplateUpdate(SmsTemplateBase):
    is_active: bool = True
    operator_name: str | None = None


class SmsTemplateRead(BaseModel):
    id: int
    title: str
    content: str
    is_active: bool
    operator_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SmsTargetSelection(BaseModel):
    include_all_members: bool = False
    include_expiring_memberships: bool = False
    expiring_days: int = Field(default=7, ge=1)
    include_low_remaining_memberships: bool = False
    low_remaining_count: int = Field(default=3, ge=0)
    include_birthdays: bool = False
    birthday_days: int = Field(default=0, ge=0)
    group_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target_selection(self) -> "SmsTargetSelection":
        if not any(
            [
                self.include_all_members,
                self.include_expiring_memberships,
                self.include_low_remaining_memberships,
                self.include_birthdays,
                self.group_ids,
            ]
        ):
            raise ValueError("발송 대상을 하나 이상 선택해 주세요.")
        return self


class SmsPreviewRequest(SmsTargetSelection):
    content_type: Literal["COMM", "AD"] = "COMM"


class SmsPreviewRecipientRead(BaseModel):
    member_id: int | None = None
    recipient_name: str
    phone: str
    sms_agree: bool
    source_labels: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class SmsPreviewSummary(BaseModel):
    total_candidates: int
    eligible_count: int
    blocked_count: int
    excluded_count: int = 0


class SmsPreviewResponse(BaseModel):
    summary: SmsPreviewSummary
    eligible_recipients: list[SmsPreviewRecipientRead] = Field(default_factory=list)
    blocked_recipients: list[SmsPreviewRecipientRead] = Field(default_factory=list)


class SmsSendRequest(SmsTargetSelection):
    content_type: Literal["COMM", "AD"] = "COMM"
    title: str | None = Field(default=None, max_length=40)
    content: str = Field(min_length=1)
    template_id: int | None = None
    excluded_member_ids: list[int] = Field(default_factory=list)
    excluded_phones: list[str] = Field(default_factory=list)
    operator_name: str | None = None

    @field_validator("excluded_phones")
    @classmethod
    def validate_excluded_phones(cls, value: list[str]) -> list[str]:
        phones: list[str] = []
        for item in value:
            normalized = normalize_phone(item)
            if normalized:
                phones.append(normalized)
        return phones


class SmsScheduleRequest(SmsSendRequest):
    scheduled_at: datetime

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=KST)
        return value


class SmsMessageRead(BaseModel):
    id: int
    target_type: str | None = None
    title: str | None = None
    content: str
    content_type: Literal["COMM", "AD"]
    message_type: Literal["SMS", "LMS"]
    template_id: int | None = None
    target_count: int
    success_count: int
    fail_count: int
    status: str
    provider_name: str | None = None
    provider_request_id: str | None = None
    target_summary: dict[str, Any] | None = None
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    canceled_at: datetime | None = None
    sync_completed_at: datetime | None = None
    operator_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SmsMessageRecipientRead(BaseModel):
    id: int
    sms_message_id: int
    member_id: int | None = None
    member_name: str | None = None
    recipient_name: str | None = None
    phone: str
    sms_agree: bool
    source_labels: list[str] = Field(default_factory=list)
    status: str
    provider_message_id: str | None = None
    fail_code: str | None = None
    fail_reason: str | None = None
    sent_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SmsMonthlyBillingItemRead(BaseModel):
    product_demand_type_code: str | None = None
    product_demand_type_name: str | None = None
    demand_amount: str
    use_amount: str
    write_date: datetime | None = None


class SmsMonthlyBillingRead(BaseModel):
    month: str
    currency_code: str | None = None
    currency_name: str | None = None
    total_demand_amount: str
    last_write_date: datetime | None = None
    matched_items: list[SmsMonthlyBillingItemRead] = Field(default_factory=list)
