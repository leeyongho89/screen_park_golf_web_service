from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Member(Base, TimestampMixin):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(String(300))
    sms_agree: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text)
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sales: Mapped[list["Sale"]] = relationship(back_populates="member")
    memberships: Mapped[list["MemberMembership"]] = relationship(back_populates="member")
    sms_group_memberships: Mapped[list["SmsGroupMember"]] = relationship(back_populates="member")
    sms_recipients: Mapped[list["SmsMessageRecipient"]] = relationship(back_populates="member")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="member")


Index("ix_members_name", Member.name)
Index("ix_members_phone", Member.phone)


class MembershipProduct(Base, TimestampMixin):
    __tablename__ = "membership_products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    product_type: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    total_count: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 0), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    memberships: Mapped[list["MemberMembership"]] = relationship(back_populates="product")

    __table_args__ = (
        UniqueConstraint("name", "product_type", name="uq_membership_products_name_type"),
        Index("ix_membership_products_type", "product_type"),
    )


class MemberMembership(Base, TimestampMixin):
    __tablename__ = "member_memberships"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("membership_products.id"))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    duration_type: Mapped[str | None] = mapped_column(String(30))
    duration_days: Mapped[int | None] = mapped_column(Integer)
    total_count: Mapped[int | None] = mapped_column(Integer)
    remaining_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="사용중", nullable=False)
    sold_price: Mapped[Decimal] = mapped_column(Numeric(12, 0), default=0, nullable=False)
    source_sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales.id", use_alter=True, name="fk_member_memberships_source_sale")
    )

    member: Mapped[Member] = relationship(back_populates="memberships")
    product: Mapped[MembershipProduct | None] = relationship(back_populates="memberships")
    usage_logs: Mapped[list["MembershipUsageLog"]] = relationship(back_populates="member_membership")

    @property
    def member_name(self) -> str | None:
        return self.member.name if self.member else None

    @property
    def member_phone(self) -> str | None:
        return self.member.phone if self.member else None

    @property
    def member_memo(self) -> str | None:
        return self.member.memo if self.member else None

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def product_type(self) -> str | None:
        return self.product.product_type if self.product else None


Index("ix_member_memberships_status", MemberMembership.status)
Index("ix_member_memberships_end_date", MemberMembership.end_date)


class MembershipUsageLog(Base):
    __tablename__ = "membership_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    member_membership_id: Mapped[int] = mapped_column(ForeignKey("member_memberships.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    change_count: Mapped[int | None] = mapped_column(Integer)
    before_remaining_count: Mapped[int | None] = mapped_column(Integer)
    after_remaining_count: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    operator_name: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    member_membership: Mapped[MemberMembership] = relationship(back_populates="usage_logs")


class Sale(Base, TimestampMixin):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    member_name_snapshot: Mapped[str | None] = mapped_column(String(80))
    member_phone_snapshot: Mapped[str | None] = mapped_column(String(30))
    sale_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    related_membership_id: Mapped[int | None] = mapped_column(ForeignKey("member_memberships.id"))
    duration_type: Mapped[str | None] = mapped_column(String(30))
    duration_days: Mapped[int | None] = mapped_column(Integer)
    coupon_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="정상", nullable=False)
    original_sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"))
    note: Mapped[str | None] = mapped_column(Text)
    operator_name: Mapped[str | None] = mapped_column(String(80))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    member: Mapped[Member | None] = relationship(back_populates="sales", foreign_keys=[member_id])


Index("ix_sales_sale_type", Sale.sale_type)
Index("ix_sales_payment_method", Sale.payment_method)
Index("ix_sales_status", Sale.status)


class Reservation(Base, TimestampMixin):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bay_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="예약", nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    operator_name: Mapped[str | None] = mapped_column(String(80))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    member: Mapped[Member | None] = relationship(back_populates="reservations")

    @property
    def member_name(self) -> str | None:
        return self.member.name if self.member else None

    @property
    def member_phone(self) -> str | None:
        return self.member.phone if self.member else None


Index("ix_reservations_date_bay", Reservation.reservation_date, Reservation.bay_number)
Index("ix_reservations_date_status", Reservation.reservation_date, Reservation.status)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    actor_name: Mapped[str | None] = mapped_column(String(80))
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    target_type: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer)
    before_data: Mapped[dict | None] = mapped_column(JSON)
    after_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SmsGroup(Base, TimestampMixin):
    __tablename__ = "sms_groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(80))

    group_members: Mapped[list["SmsGroupMember"]] = relationship(back_populates="group", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("name", name="uq_sms_groups_name"),)

    @property
    def member_ids(self) -> list[int]:
        return [item.member_id for item in self.group_members]

    @property
    def member_count(self) -> int:
        return len(self.group_members)


class SmsGroupMember(Base):
    __tablename__ = "sms_group_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sms_group_id: Mapped[int] = mapped_column(ForeignKey("sms_groups.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    group: Mapped[SmsGroup] = relationship(back_populates="group_members")
    member: Mapped[Member] = relationship(back_populates="sms_group_memberships")

    __table_args__ = (UniqueConstraint("sms_group_id", "member_id", name="uq_sms_group_members_group_member"),)


class SmsTemplate(Base, TimestampMixin):
    __tablename__ = "sms_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(80))


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    target_type: Mapped[str | None] = mapped_column(String(30))
    title: Mapped[str | None] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(10), default="COMM", nullable=False)
    message_type: Mapped[str] = mapped_column(String(10), default="SMS", nullable=False)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("sms_templates.id"))
    target_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="대기", nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(40))
    provider_request_id: Mapped[str | None] = mapped_column(String(160))
    target_summary: Mapped[dict | None] = mapped_column(JSON)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    operator_name: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    recipients: Mapped[list["SmsMessageRecipient"]] = relationship(back_populates="message", cascade="all, delete-orphan")
    template: Mapped[SmsTemplate | None] = relationship()


class SmsMessageRecipient(Base):
    __tablename__ = "sms_message_recipients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sms_message_id: Mapped[int] = mapped_column(ForeignKey("sms_messages.id"), nullable=False, index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    recipient_name: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="대기", nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(160))
    fail_code: Mapped[str | None] = mapped_column(String(80))
    fail_reason: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    message: Mapped[SmsMessage] = relationship(back_populates="recipients")
    member: Mapped[Member | None] = relationship(back_populates="sms_recipients")

    @property
    def member_name(self) -> str | None:
        if self.member:
            return self.member.name
        return self.recipient_name


Index("ix_sms_groups_name", SmsGroup.name)
Index("ix_sms_templates_is_active", SmsTemplate.is_active)
Index("ix_sms_messages_created_at", SmsMessage.created_at)
Index("ix_sms_messages_status", SmsMessage.status)
Index("ix_sms_message_recipients_message", SmsMessageRecipient.sms_message_id)
Index("ix_sms_message_recipients_phone", SmsMessageRecipient.phone)
