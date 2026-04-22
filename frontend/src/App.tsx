import { ChangeEvent, Fragment, FormEvent, useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

type TabKey = "dashboard" | "memberInfo" | "reservations" | "sales" | "salesSummary" | "memberships" | "products" | "sms";
type MembershipStatusFilter = "사용중" | "정지" | "만료" | "환불";
type SalesSummaryRange = "하루" | "1주" | "2주" | "3주" | "4주" | "한달";
type SalesSummaryModalKey = "payment" | "product" | "member" | "day" | "totalAmount" | "totalCount";
type DashboardMembershipModalKey = "expiring" | "lowCount";
type SmsContentType = "COMM" | "AD";
type SmsDispatchMode = "immediate" | "scheduled";
type SmsSendStep = "target" | "content" | "review" | "done";
type SmsPreviewMode = "live" | "scheduleSnapshot";
type SmsMonthlyBillingStatus = "idle" | "loading" | "ready" | "error";

interface ListResult<T> {
  items: T[];
  total?: number;
  page?: number;
  size?: number;
}

interface Member {
  id: number;
  name: string;
  phone: string;
  birth_date?: string | null;
  gender?: string | null;
  email?: string | null;
  address?: string | null;
  sms_agree: boolean;
  memo?: string | null;
  last_visit_at?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  total_sales_amount?: string;
  recent_30_days_sales_amount?: string;
}

interface MembershipProduct {
  id: number;
  name: string;
  product_type: "기간제" | "횟수" | "판매";
  duration_days?: number | null;
  total_count?: number | null;
  price: string;
  is_active: boolean;
}

interface MemberMembership {
  id: number;
  member_id: number;
  member_name?: string | null;
  member_phone?: string | null;
  member_memo?: string | null;
  product_id?: number | null;
  product_name?: string | null;
  product_type?: string | null;
  start_date: string;
  end_date?: string | null;
  duration_type?: string | null;
  duration_days?: number | null;
  total_count?: number | null;
  remaining_count?: number | null;
  status: string;
  sold_price: string;
}

interface MembershipUsageLog {
  id: number;
  member_membership_id: number;
  member_id: number;
  action_type: string;
  change_count?: number | null;
  before_remaining_count?: number | null;
  after_remaining_count?: number | null;
  note?: string | null;
  operator_name?: string | null;
  created_at: string;
}

interface Sale {
  id: number;
  member_id?: number | null;
  member_name_snapshot?: string | null;
  member_phone_snapshot?: string | null;
  sale_type: string;
  payment_method: string;
  amount: string;
  sale_date: string;
  related_membership_id?: number | null;
  status: string;
  original_sale_id?: number | null;
  note?: string | null;
  created_at: string;
}

interface Reservation {
  id: number;
  bay_number: number;
  member_id?: number | null;
  member_name?: string | null;
  member_phone?: string | null;
  customer_name: string;
  customer_phone: string;
  reservation_date: string;
  start_time: string;
  end_time: string;
  status: "예약" | "취소";
  note?: string | null;
  operator_name?: string | null;
  canceled_at?: string | null;
  created_at: string;
  updated_at: string;
}

interface DashboardSummary {
  current_member_count: number;
  today_new_members: number;
  today_sales: string;
  month_sales: string;
  expiring_memberships: number;
  low_remaining_memberships: number;
  recent_sales: Sale[];
}

interface SalesBreakdownItem {
  label: string;
  amount: string;
  count: number;
}

interface SalesDailyItem {
  sale_date: string;
  amount: string;
  count: number;
}

interface SalesSummary {
  from_date: string;
  to_date: string;
  total_amount: string;
  total_count: number;
  by_payment_method: Record<string, string>;
  by_sale_type: Record<string, string>;
  by_member: SalesBreakdownItem[];
  by_day: SalesDailyItem[];
}

interface SmsGroup {
  id: number;
  name: string;
  description?: string | null;
  is_active: boolean;
  operator_name?: string | null;
  member_ids: number[];
  member_count: number;
  created_at: string;
  updated_at: string;
}

interface SmsTemplate {
  id: number;
  title: string;
  content: string;
  is_active: boolean;
  operator_name?: string | null;
  created_at: string;
  updated_at: string;
}

interface SmsPreviewRecipient {
  member_id?: number | null;
  recipient_name: string;
  phone: string;
  sms_agree: boolean;
  source_labels: string[];
  blocked_reason?: string | null;
}

interface SmsPreviewSummary {
  total_candidates: number;
  eligible_count: number;
  blocked_count: number;
  excluded_count: number;
}

interface SmsPreviewResult {
  summary: SmsPreviewSummary;
  eligible_recipients: SmsPreviewRecipient[];
  blocked_recipients: SmsPreviewRecipient[];
}

interface SmsMessage {
  id: number;
  target_type?: string | null;
  title?: string | null;
  content: string;
  content_type: SmsContentType;
  message_type: "SMS" | "LMS";
  template_id?: number | null;
  target_count: number;
  success_count: number;
  fail_count: number;
  status: string;
  provider_name?: string | null;
  provider_request_id?: string | null;
  target_summary?: Record<string, unknown> | null;
  scheduled_at?: string | null;
  sent_at?: string | null;
  canceled_at?: string | null;
  sync_completed_at?: string | null;
  operator_name?: string | null;
  created_at: string;
  updated_at?: string | null;
}

interface SmsMessageRecipient {
  id: number;
  sms_message_id: number;
  member_id?: number | null;
  member_name?: string | null;
  recipient_name?: string | null;
  phone: string;
  sms_agree: boolean;
  source_labels: string[];
  status: string;
  provider_message_id?: string | null;
  fail_code?: string | null;
  fail_reason?: string | null;
  sent_at?: string | null;
}

interface SmsMonthlyBillingItem {
  product_demand_type_code?: string | null;
  product_demand_type_name?: string | null;
  demand_amount: string;
  use_amount: string;
  write_date?: string | null;
}

interface SmsMonthlyBillingSummary {
  month: string;
  currency_code?: string | null;
  currency_name?: string | null;
  total_demand_amount: string;
  last_write_date?: string | null;
  matched_items: SmsMonthlyBillingItem[];
}

interface MemberForm {
  name: string;
  phone: string;
  birth_date: string;
  gender: string;
  email: string;
  address: string;
  sms_agree: boolean;
  memo: string;
}

interface ProductForm {
  name: string;
  product_type: "기간제" | "횟수" | "판매";
  duration_days: string;
  total_count: string;
  price: string;
}

interface SaleForm {
  member_id: string;
  member_name: string;
  member_phone: string;
  product_id: string;
  payment_method: string;
  amount: string;
  start_date: string;
  end_date: string;
  total_count: string;
  note: string;
}

interface ReservationForm {
  bay_number: string;
  member_id: string;
  customer_name: string;
  customer_phone: string;
  reservation_date: string;
  start_time: string;
  end_time: string;
  note: string;
}

interface MembershipPeriodForm {
  start_date: string;
  end_date: string;
  note: string;
}

interface MembershipCountForm {
  remaining_count: string;
  note: string;
}

interface SmsComposeForm {
  include_all_members: boolean;
  include_expiring_memberships: boolean;
  expiring_days: string;
  include_low_remaining_memberships: boolean;
  low_remaining_count: string;
  include_birthdays: boolean;
  birthday_days: string;
  group_ids: string[];
  content_type: SmsContentType;
  send_mode: SmsDispatchMode;
  scheduled_at: string;
  template_id: string;
  title: string;
  content: string;
}

interface SmsGroupForm {
  name: string;
  description: string;
  member_ids: string[];
}

interface SmsTemplateForm {
  title: string;
  content: string;
  is_active: boolean;
}

function pad2(value: number) {
  return String(value).padStart(2, "0");
}

function formatDateValue(value: Date) {
  return `${value.getFullYear()}-${pad2(value.getMonth() + 1)}-${pad2(value.getDate())}`;
}

function parseDateValue(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() + 1 !== month || date.getUTCDate() !== day) {
    return null;
  }
  return date;
}

function formatUtcDateValue(value: Date) {
  return `${value.getUTCFullYear()}-${pad2(value.getUTCMonth() + 1)}-${pad2(value.getUTCDate())}`;
}

const today = () => {
  const date = new Date();
  return formatDateValue(date);
};

function formatCurrentDateTime(value: Date) {
  return `${value.getFullYear()}-${pad2(value.getMonth() + 1)}-${pad2(value.getDate())} ${pad2(value.getHours())}:${pad2(
    value.getMinutes()
  )}:${pad2(value.getSeconds())}`;
}

const MEMBERSHIP_STATUS_FILTERS: MembershipStatusFilter[] = ["사용중", "정지", "만료", "환불"];
const MEMBERSHIP_PAGE_SIZE = 500;
const SALES_SUMMARY_RANGES: SalesSummaryRange[] = ["하루", "1주", "2주", "3주", "4주", "한달"];
const CHART_COLORS = ["#1f8a70", "#d08418", "#2557a7", "#b42318", "#6f5cc2", "#008a9a", "#8a5a1f", "#56635f"];
const SMS_FEATURE_VISIBLE = true;
const SMS_SEND_STEPS: Array<{ key: SmsSendStep; label: string }> = [
  { key: "target", label: "받는 사람" },
  { key: "content", label: "내용 입력" },
  { key: "review", label: "확인" },
  { key: "done", label: "결과" }
];
const RESERVATION_BAYS = [1, 2, 3, 4, 5, 6];
const RESERVATION_OPEN_TIME = "09:00";
const RESERVATION_CLOSE_TIME = "23:00";
const RESERVATION_SLOT_MINUTES = 30;

const emptyMemberForm: MemberForm = {
  name: "",
  phone: "",
  birth_date: "",
  gender: "",
  email: "",
  address: "",
  sms_agree: true,
  memo: ""
};

const emptySaleForm: SaleForm = {
  member_id: "",
  member_name: "",
  member_phone: "",
  product_id: "",
  payment_method: "카드",
  amount: "",
  start_date: "",
  end_date: "",
  total_count: "",
  note: ""
};

const emptyReservationForm: ReservationForm = {
  bay_number: "1",
  member_id: "",
  customer_name: "",
  customer_phone: "",
  reservation_date: today(),
  start_time: RESERVATION_OPEN_TIME,
  end_time: "09:30",
  note: ""
};

const emptyMembershipPeriodForm: MembershipPeriodForm = {
  start_date: "",
  end_date: "",
  note: ""
};

const emptyMembershipCountForm: MembershipCountForm = {
  remaining_count: "",
  note: ""
};

const emptySmsComposeForm: SmsComposeForm = {
  include_all_members: false,
  include_expiring_memberships: false,
  expiring_days: "7",
  include_low_remaining_memberships: false,
  low_remaining_count: "3",
  include_birthdays: false,
  birthday_days: "0",
  group_ids: [],
  content_type: "COMM",
  send_mode: "immediate",
  scheduled_at: "",
  template_id: "",
  title: "",
  content: ""
};

const emptySmsGroupForm: SmsGroupForm = {
  name: "",
  description: "",
  member_ids: []
};

const emptySmsTemplateForm: SmsTemplateForm = {
  title: "",
  content: "",
  is_active: true
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.message || "요청 처리 중 오류가 발생했습니다.");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

function compactPayload<T extends object>(values: T) {
  return Object.fromEntries(
    Object.entries(values as Record<string, unknown>).filter(([, value]) => value !== "" && value !== null && value !== undefined)
  );
}

function money(value: string | number | null | undefined) {
  const numberValue = Number(value || 0);
  return `${numberValue.toLocaleString("ko-KR")}원`;
}

function isRefundSale(sale: Sale) {
  return sale.status.includes("환불") || Number(sale.amount || 0) < 0 || Boolean(sale.original_sale_id);
}

function displayPhone(value: string | null | undefined) {
  if (!value) return "-";
  if (value.length === 11) return `${value.slice(0, 3)}-${value.slice(3, 7)}-${value.slice(7)}`;
  return value;
}

function smsMemberOptionLabel(member: Member) {
  return [
    member.name,
    displayPhone(member.phone),
    member.gender || "성별 없음",
    member.birth_date || "생년월일 없음"
  ].join(" / ");
}

function digitsOnly(value: string | null | undefined) {
  return (value || "").replace(/\D/g, "");
}

function selectedValues(event: ChangeEvent<HTMLSelectElement>) {
  return Array.from(event.target.selectedOptions).map((option) => option.value);
}

function smsTargetSummaryText(targetSummary: Record<string, unknown> | null | undefined) {
  const labels = Array.isArray(targetSummary?.labels) ? targetSummary?.labels : [];
  return labels.length > 0 ? labels.join(", ") : "-";
}

function smsTargetSummaryNumber(targetSummary: Record<string, unknown> | null | undefined, key: string, fallback = 0) {
  const value = Number(targetSummary?.[key]);
  return Number.isFinite(value) ? value : fallback;
}

function smsTargetSummaryBoolean(targetSummary: Record<string, unknown> | null | undefined, key: string) {
  return targetSummary?.[key] === true;
}

function smsTargetSummaryStringArray(targetSummary: Record<string, unknown> | null | undefined, key: string) {
  const value = targetSummary?.[key];
  return Array.isArray(value) ? value.map(String) : [];
}

function formatDateTimeLocalInput(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}T${pad2(date.getHours())}:${pad2(
    date.getMinutes()
  )}`;
}

function localDateTimeInputToIso(value: string) {
  const [datePart, timePart] = value.split("T");
  if (!datePart || !timePart) return "";
  const [year, month, day] = datePart.split("-").map(Number);
  const [hour, minute] = timePart.split(":").map(Number);
  if (!year || !month || !day || Number.isNaN(hour) || Number.isNaN(minute)) return "";
  return new Date(year, month - 1, day, hour, minute, 0, 0).toISOString();
}

function smsExcludedKeysFromSummary(targetSummary: Record<string, unknown> | null | undefined) {
  const memberKeys = smsTargetSummaryStringArray(targetSummary, "excluded_member_ids")
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value))
    .map((value) => `member:${value}`);
  const phoneKeys = smsTargetSummaryStringArray(targetSummary, "excluded_phones").map((value) => `phone:${digitsOnly(value)}`);
  return Array.from(new Set([...memberKeys, ...phoneKeys]));
}

function smsExcludedKeysToPayload(keys: string[]) {
  const excludedMemberIds = new Set<number>();
  const excludedPhones = new Set<string>();
  keys.forEach((key) => {
    if (key.startsWith("member:")) {
      const memberId = Number(key.slice(7));
      if (Number.isFinite(memberId)) {
        excludedMemberIds.add(memberId);
      }
      return;
    }
    if (key.startsWith("phone:")) {
      const phone = digitsOnly(key.slice(6));
      if (phone) {
        excludedPhones.add(phone);
      }
    }
  });
  return {
    excluded_member_ids: Array.from(excludedMemberIds),
    excluded_phones: Array.from(excludedPhones)
  };
}

function smsTargetConfigSignature(form: SmsComposeForm, excludedKeys: string[]) {
  return JSON.stringify({
    include_all_members: form.include_all_members,
    include_expiring_memberships: form.include_expiring_memberships,
    expiring_days: Math.max(1, Number(form.expiring_days || 7)),
    include_low_remaining_memberships: form.include_low_remaining_memberships,
    low_remaining_count: Math.max(0, Number(form.low_remaining_count || 3)),
    include_birthdays: form.include_birthdays,
    birthday_days: Math.max(0, Number(form.birthday_days || 0)),
    group_ids: [...form.group_ids].map(Number).sort((left, right) => left - right),
    content_type: form.content_type,
    ...smsExcludedKeysToPayload(excludedKeys)
  });
}

function smsTargetSummarySignature(message: SmsMessage | null) {
  if (!message) return "";
  const summary = message.target_summary || null;
  return JSON.stringify({
    include_all_members: smsTargetSummaryBoolean(summary, "include_all_members"),
    include_expiring_memberships: smsTargetSummaryBoolean(summary, "include_expiring_memberships"),
    expiring_days: smsTargetSummaryNumber(summary, "expiring_days", 7),
    include_low_remaining_memberships: smsTargetSummaryBoolean(summary, "include_low_remaining_memberships"),
    low_remaining_count: smsTargetSummaryNumber(summary, "low_remaining_count", 3),
    include_birthdays: smsTargetSummaryBoolean(summary, "include_birthdays"),
    birthday_days: smsTargetSummaryNumber(summary, "birthday_days", 0),
    group_ids: smsTargetSummaryStringArray(summary, "group_ids").map(Number).sort((left, right) => left - right),
    content_type: message.content_type,
    ...smsExcludedKeysToPayload(smsExcludedKeysFromSummary(summary))
  });
}

function smsScheduleToComposeForm(message: SmsMessage): SmsComposeForm {
  const summary = message.target_summary || null;
  return {
    include_all_members: smsTargetSummaryBoolean(summary, "include_all_members"),
    include_expiring_memberships: smsTargetSummaryBoolean(summary, "include_expiring_memberships"),
    expiring_days: String(smsTargetSummaryNumber(summary, "expiring_days", 7)),
    include_low_remaining_memberships: smsTargetSummaryBoolean(summary, "include_low_remaining_memberships"),
    low_remaining_count: String(smsTargetSummaryNumber(summary, "low_remaining_count", 3)),
    include_birthdays: smsTargetSummaryBoolean(summary, "include_birthdays"),
    birthday_days: String(smsTargetSummaryNumber(summary, "birthday_days", 0)),
    group_ids: smsTargetSummaryStringArray(summary, "group_ids"),
    content_type: message.content_type,
    send_mode: "scheduled",
    scheduled_at: formatDateTimeLocalInput(message.scheduled_at),
    template_id: message.template_id ? String(message.template_id) : "",
    title: message.title || "",
    content: message.content
  };
}

function smsPreviewFromSchedule(message: SmsMessage, recipients: SmsMessageRecipient[]): SmsPreviewResult {
  const targetSummary = message.target_summary || null;
  const blockedCount = smsTargetSummaryNumber(targetSummary, "blocked_count", 0);
  const excludedCount = smsTargetSummaryNumber(targetSummary, "excluded_count", 0);
  return {
    summary: {
      total_candidates: recipients.length + blockedCount + excludedCount,
      eligible_count: recipients.length,
      blocked_count: blockedCount,
      excluded_count: 0
    },
    eligible_recipients: recipients.map((item) => ({
      member_id: item.member_id,
      recipient_name: item.recipient_name || item.member_name || "-",
      phone: item.phone,
      sms_agree: item.sms_agree,
      source_labels: item.source_labels || []
    })),
    blocked_recipients: []
  };
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatTime(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatBillingMonth(value: string | null | undefined) {
  if (!value) return "-";
  const match = /^(\d{4})(\d{2})$/.exec(value);
  if (!match) return value;
  return `${match[1]}년 ${Number(match[2])}월`;
}

function currentMonthValue() {
  const date = new Date();
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`;
}

function normalizeMonthValue(value: string | null | undefined) {
  return /^\d{4}-\d{2}$/.test(value || "") ? String(value) : currentMonthValue();
}

function billingMonthQueryValue(value: string | null | undefined) {
  return normalizeMonthValue(value).replace("-", "");
}

function formatCurrencyAmount(value: string | number | null | undefined, currencyCode: string | null | undefined) {
  const amountText = Number(value || 0).toLocaleString("ko-KR");
  if (!currencyCode || currencyCode === "KRW") return `${amountText}원`;
  return `${amountText} ${currencyCode}`;
}

function addDays(startDate: string, durationDays?: number | null) {
  if (!startDate || !durationDays) return "";
  const date = parseDateValue(startDate);
  if (!date) return "";
  date.setUTCDate(date.getUTCDate() + durationDays - 1);
  return formatUtcDateValue(date);
}

function shiftDate(value: string, days: number) {
  const date = parseDateValue(value);
  if (!date) return value;
  date.setUTCDate(date.getUTCDate() + days);
  return formatUtcDateValue(date);
}

function formatDateWithWeekday(value: string) {
  const date = parseDateValue(value);
  if (!date) return value || "-";
  const weekdays = ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"];
  return `${value}-${weekdays[date.getUTCDay()]}`;
}

function normalizeTimeValue(value: string | null | undefined) {
  return (value || "").slice(0, 5);
}

function timeToMinutes(value: string) {
  const [hour, minute] = normalizeTimeValue(value).split(":").map(Number);
  return (hour || 0) * 60 + (minute || 0);
}

function minutesToTime(totalMinutes: number) {
  const hour = Math.floor(totalMinutes / 60);
  const minute = totalMinutes % 60;
  return `${pad2(hour)}:${pad2(minute)}`;
}

function addMinutesToTime(value: string, minutes: number) {
  return minutesToTime(timeToMinutes(value) + minutes);
}

function buildReservationTimeSlots() {
  const slots: string[] = [];
  for (
    let minutes = timeToMinutes(RESERVATION_OPEN_TIME);
    minutes < timeToMinutes(RESERVATION_CLOSE_TIME);
    minutes += RESERVATION_SLOT_MINUTES
  ) {
    slots.push(minutesToTime(minutes));
  }
  return slots;
}

function reservationCoversSlot(reservation: Reservation, slot: string) {
  const slotMinutes = timeToMinutes(slot);
  return timeToMinutes(reservation.start_time) <= slotMinutes && slotMinutes < timeToMinutes(reservation.end_time);
}

function reservationStartsAt(reservation: Reservation, slot: string) {
  return normalizeTimeValue(reservation.start_time) === normalizeTimeValue(slot);
}

function salesSummaryDays(range: SalesSummaryRange) {
  if (range === "하루") return 1;
  if (range === "1주") return 7;
  if (range === "2주") return 14;
  if (range === "3주") return 21;
  if (range === "4주") return 28;
  return 30;
}

function salesSummaryStartDate(toDate: string, range: SalesSummaryRange) {
  return shiftDate(toDate, -(salesSummaryDays(range) - 1));
}

function parseLocalDate(value: string) {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

function daysBetweenInclusive(startDate: string | null | undefined, endDate: string | null | undefined) {
  const start = parseLocalDate(startDate || "");
  const end = parseLocalDate(endDate || "");
  if (!start || !end) return null;
  const dayMs = 24 * 60 * 60 * 1000;
  return Math.floor((end.getTime() - start.getTime()) / dayMs) + 1;
}

function remainingDays(endDate: string | null | undefined) {
  const end = parseLocalDate(endDate || "");
  if (!end) return null;
  const now = new Date();
  const todayDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dayMs = 24 * 60 * 60 * 1000;
  return Math.max(0, Math.floor((end.getTime() - todayDate.getTime()) / dayMs) + 1);
}

function memberToForm(member: Member): MemberForm {
  return {
    name: member.name || "",
    phone: member.phone || "",
    birth_date: member.birth_date || "",
    gender: member.gender || "",
    email: member.email || "",
    address: member.address || "",
    sms_agree: member.sms_agree,
    memo: member.memo || ""
  };
}

function memberUpdatePayload(form: MemberForm) {
  return {
    name: form.name,
    phone: form.phone,
    birth_date: form.birth_date || null,
    gender: form.gender || null,
    email: form.email || null,
    address: form.address || null,
    sms_agree: form.sms_agree,
    memo: form.memo || null
  };
}

function productToForm(product: MembershipProduct): ProductForm {
  return {
    name: product.name,
    product_type: product.product_type,
    duration_days: product.duration_days ? String(product.duration_days) : "",
    total_count: product.total_count ? String(product.total_count) : "",
    price: String(Number(product.price || 0))
  };
}

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [dashboardNewMemberDays, setDashboardNewMemberDays] = useState("1");
  const [dashboardSalesDays, setDashboardSalesDays] = useState("1");
  const [dashboardExpiringDays, setDashboardExpiringDays] = useState("7");
  const [dashboardLowCount, setDashboardLowCount] = useState("3");
  const [dashboardMembershipModal, setDashboardMembershipModal] = useState<DashboardMembershipModalKey | null>(null);
  const [dashboardMembershipItems, setDashboardMembershipItems] = useState<MemberMembership[]>([]);
  const [dashboardNewMembersOpen, setDashboardNewMembersOpen] = useState(false);
  const [dashboardNewMemberItems, setDashboardNewMemberItems] = useState<Member[]>([]);
  const [dashboardSalesOpen, setDashboardSalesOpen] = useState(false);
  const [dashboardSalesItems, setDashboardSalesItems] = useState<Sale[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberResults, setMemberResults] = useState<Member[]>([]);
  const [deletedMembers, setDeletedMembers] = useState<Member[]>([]);
  const [products, setProducts] = useState<MembershipProduct[]>([]);
  const [memberships, setMemberships] = useState<MemberMembership[]>([]);
  const [membershipResults, setMembershipResults] = useState<MemberMembership[]>([]);
  const [membershipStatusFilters, setMembershipStatusFilters] = useState<MembershipStatusFilter[]>(["사용중"]);
  const [membershipKeyword, setMembershipKeyword] = useState("");
  const [membershipPage, setMembershipPage] = useState(1);
  const [membershipTotal, setMembershipTotal] = useState(0);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [reservationDate, setReservationDate] = useState(today());
  const [reservationForm, setReservationForm] = useState<ReservationForm>(emptyReservationForm);
  const [reservationModalOpen, setReservationModalOpen] = useState(false);
  const [reservationCanceledModalOpen, setReservationCanceledModalOpen] = useState(false);
  const [editingReservation, setEditingReservation] = useState<Reservation | null>(null);
  const [reservationMemberMatches, setReservationMemberMatches] = useState<Member[]>([]);
  const [reservationMemberInputFocused, setReservationMemberInputFocused] = useState(false);
  const [reservationSelectedMember, setReservationSelectedMember] = useState<Member | null>(null);
  const [sales, setSales] = useState<Sale[]>([]);
  const [salesKeyword, setSalesKeyword] = useState("");
  const [hideRefundSales, setHideRefundSales] = useState(true);
  const [salesSummary, setSalesSummary] = useState<SalesSummary | null>(null);
  const [salesSummaryRange, setSalesSummaryRange] = useState<SalesSummaryRange>("하루");
  const [salesSummaryTo, setSalesSummaryTo] = useState(today());
  const [salesSummaryFrom, setSalesSummaryFrom] = useState(today());
  const [salesSummaryModal, setSalesSummaryModal] = useState<SalesSummaryModalKey | null>(null);
  const [salesSummaryDetailItems, setSalesSummaryDetailItems] = useState<Sale[]>([]);
  const [salesSummaryDetailKeyword, setSalesSummaryDetailKeyword] = useState("");
  const [memberKeyword, setMemberKeyword] = useState("");
  const [deletedMemberKeyword, setDeletedMemberKeyword] = useState("");
  const [memberSalesReferenceDate, setMemberSalesReferenceDate] = useState(today());
  const [memberForm, setMemberForm] = useState<MemberForm>(emptyMemberForm);
  const [memberEditForm, setMemberEditForm] = useState<MemberForm>(emptyMemberForm);
  const [productForm, setProductForm] = useState<ProductForm>({
    name: "",
    product_type: "기간제",
    duration_days: "",
    total_count: "",
    price: ""
  });
  const [saleForm, setSaleForm] = useState<SaleForm>(emptySaleForm);
  const [saleEntryOpen, setSaleEntryOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [selectedMemberSales, setSelectedMemberSales] = useState<Sale[]>([]);
  const [selectedMemberMemberships, setSelectedMemberMemberships] = useState<MemberMembership[]>([]);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [memberRegisterOpen, setMemberRegisterOpen] = useState(false);
  const [memberEditOpen, setMemberEditOpen] = useState(false);
  const [memberRestoreOpen, setMemberRestoreOpen] = useState(false);
  const [productModalOpen, setProductModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<MembershipProduct | null>(null);
  const [saleMemberMatches, setSaleMemberMatches] = useState<Member[]>([]);
  const [saleMemberInputFocused, setSaleMemberInputFocused] = useState(false);
  const [saleSelectedMember, setSaleSelectedMember] = useState<Member | null>(null);
  const [saleNoteModal, setSaleNoteModal] = useState<Sale | null>(null);
  const [memberHistoryTarget, setMemberHistoryTarget] = useState<Member | null>(null);
  const [memberHistorySales, setMemberHistorySales] = useState<Sale[]>([]);
  const [periodAdjustMembership, setPeriodAdjustMembership] = useState<MemberMembership | null>(null);
  const [periodAdjustForm, setPeriodAdjustForm] = useState<MembershipPeriodForm>(emptyMembershipPeriodForm);
  const [countAdjustMembership, setCountAdjustMembership] = useState<MemberMembership | null>(null);
  const [countAdjustForm, setCountAdjustForm] = useState<MembershipCountForm>(emptyMembershipCountForm);
  const [membershipHistoryTarget, setMembershipHistoryTarget] = useState<MemberMembership | null>(null);
  const [membershipHistoryLogs, setMembershipHistoryLogs] = useState<MembershipUsageLog[]>([]);
  const [smsGroups, setSmsGroups] = useState<SmsGroup[]>([]);
  const [smsTemplates, setSmsTemplates] = useState<SmsTemplate[]>([]);
  const [smsHistory, setSmsHistory] = useState<SmsMessage[]>([]);
  const [smsSchedules, setSmsSchedules] = useState<SmsMessage[]>([]);
  const [smsMemberOptions, setSmsMemberOptions] = useState<Member[]>([]);
  const [smsComposeForm, setSmsComposeForm] = useState<SmsComposeForm>(emptySmsComposeForm);
  const [smsSendStep, setSmsSendStep] = useState<SmsSendStep>("target");
  const [smsLastSentMessage, setSmsLastSentMessage] = useState<SmsMessage | null>(null);
  const [smsLastSentDetailItems, setSmsLastSentDetailItems] = useState<SmsMessageRecipient[]>([]);
  const [smsLastSentDetailLoading, setSmsLastSentDetailLoading] = useState(false);
  const [smsPreview, setSmsPreview] = useState<SmsPreviewResult | null>(null);
  const [smsPreviewMode, setSmsPreviewMode] = useState<SmsPreviewMode | null>(null);
  const [smsPreviewModalOpen, setSmsPreviewModalOpen] = useState(false);
  const [smsPreviewKeyword, setSmsPreviewKeyword] = useState("");
  const [smsExcludedRecipients, setSmsExcludedRecipients] = useState<string[]>([]);
  const [smsEditingSchedule, setSmsEditingSchedule] = useState<SmsMessage | null>(null);
  const [smsEditingScheduleRecipients, setSmsEditingScheduleRecipients] = useState<SmsMessageRecipient[]>([]);
  const [smsScheduleModalOpen, setSmsScheduleModalOpen] = useState(false);
  const [smsGroupModalOpen, setSmsGroupModalOpen] = useState(false);
  const [smsGroupForm, setSmsGroupForm] = useState<SmsGroupForm>(emptySmsGroupForm);
  const [smsEditingGroup, setSmsEditingGroup] = useState<SmsGroup | null>(null);
  const [smsDeleteGroupTarget, setSmsDeleteGroupTarget] = useState<SmsGroup | null>(null);
  const [smsGroupMemberKeyword, setSmsGroupMemberKeyword] = useState("");
  const [smsGroupAvailableSelection, setSmsGroupAvailableSelection] = useState<string[]>([]);
  const [smsGroupSelectedSelection, setSmsGroupSelectedSelection] = useState<string[]>([]);
  const [smsTemplateModalOpen, setSmsTemplateModalOpen] = useState(false);
  const [smsTemplateForm, setSmsTemplateForm] = useState<SmsTemplateForm>(emptySmsTemplateForm);
  const [smsEditingTemplate, setSmsEditingTemplate] = useState<SmsTemplate | null>(null);
  const [smsHistoryModalOpen, setSmsHistoryModalOpen] = useState(false);
  const [smsHistoryMessageTarget, setSmsHistoryMessageTarget] = useState<SmsMessage | null>(null);
  const [smsHistoryDetailTarget, setSmsHistoryDetailTarget] = useState<SmsMessage | null>(null);
  const [smsHistoryDetailItems, setSmsHistoryDetailItems] = useState<SmsMessageRecipient[]>([]);
  const [smsHistoryDetailKeyword, setSmsHistoryDetailKeyword] = useState("");
  const [smsMonthlyBillingModalOpen, setSmsMonthlyBillingModalOpen] = useState(false);
  const [smsMonthlyBillingStatus, setSmsMonthlyBillingStatus] = useState<SmsMonthlyBillingStatus>("idle");
  const [smsMonthlyBilling, setSmsMonthlyBilling] = useState<SmsMonthlyBillingSummary | null>(null);
  const [smsMonthlyBillingError, setSmsMonthlyBillingError] = useState("");
  const [smsMonthlyBillingMonth, setSmsMonthlyBillingMonth] = useState(currentMonthValue());
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const [isFullscreen, setIsFullscreen] = useState(() =>
    typeof document !== "undefined" ? Boolean(document.fullscreenElement) : false
  );
  const currentTimeZone = useMemo(() => Intl.DateTimeFormat().resolvedOptions().timeZone || "로컬 시간", []);

  const activeSaleProducts = useMemo(() => products.filter((product) => product.is_active), [products]);
  const selectedSaleProduct = useMemo(
    () => activeSaleProducts.find((product) => String(product.id) === saleForm.product_id) || null,
    [activeSaleProducts, saleForm.product_id]
  );
  const filteredSales = useMemo(() => {
    const baseItems = hideRefundSales ? sales.filter((sale) => !isRefundSale(sale)) : sales;
    const keyword = salesKeyword.trim().toLowerCase();
    const normalized = digitsOnly(salesKeyword);
    if (!keyword && !normalized) return baseItems;
    return baseItems.filter((sale) => {
      const fields = [
        sale.member_name_snapshot || "비회원",
        displayPhone(sale.member_phone_snapshot),
        sale.sale_type,
        sale.payment_method,
        sale.note || "",
        sale.sale_date,
        sale.status,
        formatDateTime(sale.created_at)
      ]
        .join(" ")
        .toLowerCase();
      const phoneMatch = normalized ? (sale.member_phone_snapshot || "").includes(normalized) : false;
      return fields.includes(keyword) || phoneMatch;
    });
  }, [sales, salesKeyword, hideRefundSales]);
  const filteredSalesSummaryDetailItems = useMemo(() => {
    const baseItems = hideRefundSales ? salesSummaryDetailItems.filter((sale) => !isRefundSale(sale)) : salesSummaryDetailItems;
    const keyword = salesSummaryDetailKeyword.trim().toLowerCase();
    const normalized = digitsOnly(salesSummaryDetailKeyword);
    if (!keyword && !normalized) return baseItems;
    return baseItems.filter((sale) => {
      const text = [
        sale.member_name_snapshot || "비회원",
        displayPhone(sale.member_phone_snapshot),
        sale.sale_type,
        sale.payment_method,
        sale.sale_date,
        sale.status,
        sale.note || "",
        formatDateTime(sale.created_at),
        money(sale.amount),
      ]
        .join(" ")
        .toLowerCase();
      const phoneMatch = normalized ? (sale.member_phone_snapshot || "").includes(normalized) : false;
      return text.includes(keyword) || phoneMatch;
    });
  }, [salesSummaryDetailItems, salesSummaryDetailKeyword, salesSummaryModal, hideRefundSales]);
  const dashboardNewMemberDaysValue = Math.max(1, Number(dashboardNewMemberDays || 1));
  const dashboardSalesDaysValue = Math.max(1, Number(dashboardSalesDays || 1));
  const showMembershipFields = selectedSaleProduct?.product_type === "기간제" || selectedSaleProduct?.product_type === "횟수";
  const requiresMemberDetails = showMembershipFields;
  const activeMemberships = useMemo(() => memberships.filter((membership) => membership.status === "사용중"), [memberships]);
  const membershipTotalPages = Math.max(1, Math.ceil(membershipTotal / MEMBERSHIP_PAGE_SIZE));
  const filteredDeletedMembers = useMemo(() => {
    const keyword = deletedMemberKeyword.trim();
    if (!keyword) return deletedMembers;
    const normalized = digitsOnly(keyword);
    return deletedMembers.filter((member) => {
      const textMatches =
        member.name.includes(keyword) ||
        (member.memo || "").includes(keyword) ||
        displayPhone(member.phone).includes(keyword);
      const phoneMatches = normalized ? member.phone.includes(normalized) : false;
      return textMatches || phoneMatches;
    });
  }, [deletedMembers, deletedMemberKeyword]);
  const membershipsByMember = useMemo(() => {
    const byMember = new Map<number, MemberMembership[]>();
    activeMemberships.forEach((membership) => {
      const items = byMember.get(membership.member_id) || [];
      items.push(membership);
      byMember.set(membership.member_id, items);
    });
    return byMember;
  }, [activeMemberships]);
  const showSaleMemberMatches =
    saleMemberInputFocused &&
    saleForm.member_name.trim().length > 0 &&
    (!saleSelectedMember || saleForm.member_name !== saleSelectedMember.name) &&
    saleMemberMatches.length > 0;
  const reservationTimeSlots = useMemo(() => buildReservationTimeSlots(), []);
  const activeReservationItems = useMemo(() => reservations.filter((reservation) => reservation.status !== "취소"), [reservations]);
  const canceledReservationItems = useMemo(() => reservations.filter((reservation) => reservation.status === "취소"), [reservations]);
  const reservationStats = useMemo(
    () => ({
      reserved: reservations.filter((reservation) => reservation.status === "예약").length,
      canceled: canceledReservationItems.length
    }),
    [reservations, canceledReservationItems]
  );
  const showReservationMemberMatches =
    reservationMemberInputFocused &&
    reservationForm.customer_name.trim().length > 0 &&
    (!reservationSelectedMember || reservationForm.customer_name !== reservationSelectedMember.name) &&
    reservationMemberMatches.length > 0;
  const filteredSmsGroupMemberOptions = useMemo(() => {
    const keyword = smsGroupMemberKeyword.trim().toLowerCase();
    const normalized = digitsOnly(smsGroupMemberKeyword);
    if (!keyword && !normalized) return smsMemberOptions;
    return smsMemberOptions.filter((member) => {
      const text = [member.name, member.memo || "", displayPhone(member.phone), member.gender || "", member.birth_date || ""]
        .join(" ")
        .toLowerCase();
      const phoneMatch = normalized ? member.phone.includes(normalized) : false;
      return text.includes(keyword) || phoneMatch;
    });
  }, [smsGroupMemberKeyword, smsMemberOptions]);
  const smsGroupAvailableMembers = useMemo(() => {
    const selectedIds = new Set(smsGroupForm.member_ids);
    return filteredSmsGroupMemberOptions.filter((member) => !selectedIds.has(String(member.id)));
  }, [filteredSmsGroupMemberOptions, smsGroupForm.member_ids]);
  const smsGroupSelectedMembers = useMemo(() => {
    const membersById = new Map(smsMemberOptions.map((member) => [String(member.id), member]));
    return smsGroupForm.member_ids
      .map((memberId) => membersById.get(memberId))
      .filter((member): member is Member => Boolean(member));
  }, [smsGroupForm.member_ids, smsMemberOptions]);
  const filteredSmsPreviewEligible = useMemo(() => {
    const items = smsPreview?.eligible_recipients || [];
    const keyword = smsPreviewKeyword.trim().toLowerCase();
    const normalized = digitsOnly(smsPreviewKeyword);
    if (!keyword && !normalized) return items;
    return items.filter((item) => {
      const text = [item.recipient_name, displayPhone(item.phone), item.source_labels.join(" ")].join(" ").toLowerCase();
      const phoneMatch = normalized ? item.phone.includes(normalized) : false;
      return text.includes(keyword) || phoneMatch;
    });
  }, [smsPreview, smsPreviewKeyword]);
  const filteredSmsPreviewBlocked = useMemo(() => {
    const items = smsPreview?.blocked_recipients || [];
    const keyword = smsPreviewKeyword.trim().toLowerCase();
    const normalized = digitsOnly(smsPreviewKeyword);
    if (!keyword && !normalized) return items;
    return items.filter((item) => {
      const text = [item.recipient_name, displayPhone(item.phone), item.source_labels.join(" "), item.blocked_reason || ""]
        .join(" ")
        .toLowerCase();
      const phoneMatch = normalized ? item.phone.includes(normalized) : false;
      return text.includes(keyword) || phoneMatch;
    });
  }, [smsPreview, smsPreviewKeyword]);
  const filteredSmsHistoryDetailItems = useMemo(() => {
    const keyword = smsHistoryDetailKeyword.trim().toLowerCase();
    const normalized = digitsOnly(smsHistoryDetailKeyword);
    if (!keyword && !normalized) return smsHistoryDetailItems;
    return smsHistoryDetailItems.filter((item) => {
      const text = [
        item.member_name || item.recipient_name || "",
        displayPhone(item.phone),
        item.status,
        item.fail_code || "",
        item.fail_reason || "",
        formatDateTime(item.sent_at),
      ]
        .join(" ")
        .toLowerCase();
      const phoneMatch = normalized ? item.phone.includes(normalized) : false;
      return text.includes(keyword) || phoneMatch;
    });
  }, [smsHistoryDetailItems, smsHistoryDetailKeyword]);
  const smsEditingScheduleSignature = useMemo(() => smsTargetSummarySignature(smsEditingSchedule), [smsEditingSchedule]);
  const smsCurrentTargetSignature = useMemo(
    () => smsTargetConfigSignature(smsComposeForm, smsExcludedRecipients),
    [smsComposeForm, smsExcludedRecipients]
  );
  const smsCanUseScheduleSnapshot = useMemo(
    () =>
      Boolean(
        smsEditingSchedule &&
          smsEditingScheduleRecipients.length > 0 &&
          smsEditingScheduleSignature === smsCurrentTargetSignature
      ),
    [smsCurrentTargetSignature, smsEditingSchedule, smsEditingScheduleRecipients, smsEditingScheduleSignature]
  );

  async function refreshDashboard() {
    const params = new URLSearchParams({
      new_member_days: String(dashboardNewMemberDaysValue),
      sales_days: String(dashboardSalesDaysValue),
      expiring_days: String(Math.max(1, Number(dashboardExpiringDays || 7))),
      low_remaining_count: String(Math.max(0, Number(dashboardLowCount || 3)))
    });
    setDashboard(await api<DashboardSummary>(`/dashboard?${params.toString()}`));
  }

  async function openDashboardMembershipModal(type: DashboardMembershipModalKey) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ size: "500" });
      params.append("status", "사용중");
      if (type === "expiring") {
        params.set("expiring_days", String(Math.max(1, Number(dashboardExpiringDays || 7))));
      } else {
        params.set("remaining_count_lte", String(Math.max(0, Number(dashboardLowCount || 3))));
      }
      const result = await api<ListResult<MemberMembership>>(`/member-memberships?${params.toString()}`);
      setDashboardMembershipModal(type);
      setDashboardMembershipItems(result.items);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "보유 상품 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function openDashboardNewMembersModal() {
    setLoading(true);
    try {
      const toDate = today();
      const fromDate = shiftDate(toDate, -(dashboardNewMemberDaysValue - 1));
      const params = new URLSearchParams({
        size: "500",
        created_from: fromDate,
        created_to: toDate,
      });
      const result = await api<ListResult<Member>>(`/members?${params.toString()}`);
      setDashboardNewMemberItems(result.items);
      setDashboardNewMembersOpen(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "신규 회원 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function openDashboardSalesModal() {
    setLoading(true);
    try {
      const toDate = today();
      const fromDate = shiftDate(toDate, -(dashboardSalesDaysValue - 1));
      const params = new URLSearchParams({
        size: "500",
        from_date: fromDate,
        to_date: toDate,
      });
      const result = await api<ListResult<Sale>>(`/sales?${params.toString()}`);
      setDashboardSalesItems(result.items);
      setDashboardSalesOpen(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "매출 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchMembers(keyword = "", saleDate = memberSalesReferenceDate) {
    const params = new URLSearchParams({
      keyword,
      size: "50"
    });
    if (saleDate) {
      params.set("sale_date", saleDate);
    }
    const result = await api<ListResult<Member>>(`/members?${params.toString()}`);
    return result.items;
  }

  async function refreshMembers(keyword = "", saleDate = memberSalesReferenceDate) {
    const items = await fetchMembers(keyword, saleDate);
    setMembers(items);
    return items;
  }

  async function refreshMemberResults(keyword = memberKeyword, saleDate = memberSalesReferenceDate) {
    const items = await fetchMembers(keyword, saleDate);
    setMemberResults(items);
    return items;
  }

  async function refreshDeletedMembers() {
    const result = await api<ListResult<Member>>("/members?inactive_only=true&size=100");
    setDeletedMembers(result.items);
    return result.items;
  }

  async function refreshProducts() {
    const result = await api<ListResult<MembershipProduct>>("/membership-products?include_inactive=true");
    setProducts(result.items);
  }

  async function refreshMemberships() {
    const params = new URLSearchParams({ size: String(MEMBERSHIP_PAGE_SIZE) });
    params.append("status", "사용중");
    const result = await api<ListResult<MemberMembership>>(`/member-memberships?${params.toString()}`);
    setMemberships(result.items);
  }

  async function refreshMembershipResults() {
    if (membershipStatusFilters.length === 0) {
      setMembershipResults([]);
      setMembershipTotal(0);
      return;
    }
    const params = new URLSearchParams({
      page: String(membershipPage),
      size: String(MEMBERSHIP_PAGE_SIZE)
    });
    membershipStatusFilters.forEach((status) => params.append("status", status));
    if (membershipKeyword.trim()) {
      params.set("keyword", membershipKeyword.trim());
    }
    const result = await api<ListResult<MemberMembership>>(`/member-memberships?${params.toString()}`);
    setMembershipResults(result.items);
    setMembershipTotal(result.total ?? result.items.length);
  }

  async function refreshSales() {
    const result = await api<ListResult<Sale>>("/sales?size=50");
    setSales(result.items);
  }

  async function refreshReservations(targetDate = reservationDate) {
    const params = new URLSearchParams({ target_date: targetDate });
    const result = await api<ListResult<Reservation>>(`/reservations?${params.toString()}`);
    setReservations(result.items);
    return result.items;
  }

  async function refreshSalesSummary(fromDate = salesSummaryFrom, toDate = salesSummaryTo) {
    if (!fromDate || !toDate) return;
    const params = new URLSearchParams({
      from_date: fromDate,
      to_date: toDate
    });
    setSalesSummary(await api<SalesSummary>(`/sales/summary?${params.toString()}`));
  }

  async function refreshSmsGroups() {
    const result = await api<ListResult<SmsGroup>>("/sms/groups");
    setSmsGroups(result.items);
    const availableGroupIds = new Set(result.items.map((group) => String(group.id)));
    setSmsComposeForm((current) => {
      const nextGroupIds = current.group_ids.filter((groupId) => availableGroupIds.has(groupId));
      return nextGroupIds.length === current.group_ids.length ? current : { ...current, group_ids: nextGroupIds };
    });
    setSmsEditingGroup((current) => {
      if (!current) return current;
      return result.items.find((group) => group.id === current.id) || null;
    });
    setSmsDeleteGroupTarget((current) => {
      if (!current) return current;
      return result.items.find((group) => group.id === current.id) || null;
    });
  }

  async function refreshSmsTemplates() {
    const result = await api<ListResult<SmsTemplate>>("/sms/templates");
    setSmsTemplates(result.items);
    setSmsComposeForm((current) => {
      if (!current.template_id) return current;
      const selectedTemplate = result.items.find((template) => String(template.id) === current.template_id);
      if (selectedTemplate?.is_active) return current;
      return { ...current, template_id: "", title: "", content: "" };
    });
  }

  async function refreshSmsHistory() {
    const result = await api<ListResult<SmsMessage>>("/sms/history?size=50");
    setSmsHistory(result.items);
  }

  async function refreshSmsSchedules() {
    const result = await api<ListResult<SmsMessage>>("/sms/schedules?size=50");
    setSmsSchedules(result.items);
    setSmsEditingSchedule((current) => {
      if (!current) return current;
      return result.items.find((item) => item.id === current.id) || current;
    });
  }

  async function fetchSmsMessageRecipients(messageId: number) {
    return api<{ message: SmsMessage; items: SmsMessageRecipient[]; total: number }>(`/sms/${messageId}/recipients?size=500`);
  }

  function applySmsMessageDetailResult(result: { message: SmsMessage; items: SmsMessageRecipient[] }) {
    setSmsHistory((current) => current.map((item) => (item.id === result.message.id ? result.message : item)));
    setSmsSchedules((current) => current.map((item) => (item.id === result.message.id ? result.message : item)));
  }

  async function openSmsHistoryModal() {
    setSmsHistoryModalOpen(true);
    try {
      await refreshSmsHistory();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 발송 이력을 불러오지 못했습니다.");
    }
  }

  async function handleSmsHistoryRefresh() {
    try {
      await refreshSmsHistory();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 발송 이력을 불러오지 못했습니다.");
    }
  }

  async function refreshSmsLastSentResult(messageId?: number, showNotice = true) {
    const targetMessageId = messageId ?? smsLastSentMessage?.id;
    if (!targetMessageId) return;
    setSmsLastSentDetailLoading(true);
    try {
      const result = await fetchSmsMessageRecipients(targetMessageId);
      applySmsMessageDetailResult(result);
      setSmsLastSentMessage(result.message);
      setSmsLastSentDetailItems(result.items);
    } catch (error) {
      if (showNotice) {
        setNotice(error instanceof Error ? error.message : "문자 발송 결과를 불러오지 못했습니다.");
      }
    } finally {
      setSmsLastSentDetailLoading(false);
    }
  }

  async function refreshSmsMemberOptions() {
    const result = await api<ListResult<Member>>("/members?size=500");
    setSmsMemberOptions(result.items);
  }

  async function refreshSmsData() {
    await Promise.all([refreshSmsGroups(), refreshSmsTemplates(), refreshSmsHistory(), refreshSmsSchedules(), refreshSmsMemberOptions()]);
  }

  async function loadSmsMonthlyBilling(month = smsMonthlyBillingMonth) {
    setSmsMonthlyBillingStatus("loading");
    setSmsMonthlyBillingError("");
    try {
      const params = new URLSearchParams({ month: billingMonthQueryValue(month) });
      const result = await api<SmsMonthlyBillingSummary>(`/sms/monthly-billing?${params.toString()}`);
      setSmsMonthlyBilling(result);
      setSmsMonthlyBillingStatus("ready");
    } catch (error) {
      setSmsMonthlyBilling(null);
      setSmsMonthlyBillingStatus("error");
      setSmsMonthlyBillingError(error instanceof Error ? error.message : "월별 청구금액을 불러오지 못했습니다.");
    }
  }

  function openSmsMonthlyBillingModal() {
    const initialMonth = currentMonthValue();
    setSmsMonthlyBillingModalOpen(true);
    setSmsMonthlyBilling(null);
    setSmsMonthlyBillingMonth(initialMonth);
    void loadSmsMonthlyBilling(initialMonth);
  }

  function closeSmsMonthlyBillingModal() {
    setSmsMonthlyBillingModalOpen(false);
    setSmsMonthlyBilling(null);
    setSmsMonthlyBillingStatus("idle");
    setSmsMonthlyBillingError("");
  }

  async function refreshSmsDataAndClearTarget() {
    setSmsComposeForm((current) => ({
      ...current,
      include_all_members: false,
      include_expiring_memberships: false,
      include_low_remaining_memberships: false,
      include_birthdays: false,
      group_ids: []
    }));
    setSmsPreview(null);
    setSmsPreviewMode(null);
    setSmsPreviewModalOpen(false);
    setSmsPreviewKeyword("");
    setSmsExcludedRecipients([]);
    setSmsEditingSchedule(null);
    setSmsEditingScheduleRecipients([]);
    setSmsLastSentMessage(null);
    setSmsLastSentDetailItems([]);
    await refreshSmsData();
  }

  async function openSmsScheduleModal() {
    setSmsScheduleModalOpen(true);
    try {
      await refreshSmsSchedules();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 예약 목록을 불러오지 못했습니다.");
    }
  }

  function closeSmsScheduleEditor() {
    setSmsEditingSchedule(null);
    setSmsEditingScheduleRecipients([]);
  }

  async function openSmsScheduleEdit(message: SmsMessage) {
    setLoading(true);
    try {
      const result = await fetchSmsMessageRecipients(message.id);
      setSmsEditingSchedule(result.message);
      setSmsEditingScheduleRecipients(result.items);
      setSmsComposeForm(smsScheduleToComposeForm(result.message));
      setSmsExcludedRecipients(smsExcludedKeysFromSummary(result.message.target_summary));
      setSmsPreview(null);
      setSmsPreviewMode(null);
      setSmsPreviewKeyword("");
      setSmsPreviewModalOpen(false);
      setSmsLastSentMessage(null);
      setSmsLastSentDetailItems([]);
      setSmsSendStep("target");
      setSmsScheduleModalOpen(false);
      setActiveTab("sms");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 예약 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function openSmsGroupCreateModal() {
    setSmsEditingGroup(null);
    setSmsGroupForm(emptySmsGroupForm);
    setSmsGroupMemberKeyword("");
    setSmsGroupAvailableSelection([]);
    setSmsGroupSelectedSelection([]);
    setSmsGroupModalOpen(true);
  }

  function openSmsGroupEditModal(group: SmsGroup) {
    setSmsEditingGroup(group);
    setSmsGroupForm({
      name: group.name,
      description: group.description || "",
      member_ids: group.member_ids.map(String)
    });
    setSmsGroupMemberKeyword("");
    setSmsGroupAvailableSelection([]);
    setSmsGroupSelectedSelection([]);
    setSmsGroupModalOpen(true);
  }

  function openSmsGroupDeleteModal(group: SmsGroup) {
    setSmsDeleteGroupTarget(group);
  }

  function closeSmsGroupModal() {
    setSmsGroupModalOpen(false);
    setSmsGroupAvailableSelection([]);
    setSmsGroupSelectedSelection([]);
  }

  function closeSmsGroupDeleteModal() {
    setSmsDeleteGroupTarget(null);
  }

  function addSmsGroupMembers() {
    if (smsGroupAvailableSelection.length === 0) return;
    setSmsGroupForm((current) => {
      const nextMemberIds = [...current.member_ids];
      smsGroupAvailableSelection.forEach((memberId) => {
        if (!nextMemberIds.includes(memberId)) {
          nextMemberIds.push(memberId);
        }
      });
      return { ...current, member_ids: nextMemberIds };
    });
    setSmsGroupAvailableSelection([]);
  }

  function removeSmsGroupMembers() {
    if (smsGroupSelectedSelection.length === 0) return;
    const removeIds = new Set(smsGroupSelectedSelection);
    setSmsGroupForm((current) => ({
      ...current,
      member_ids: current.member_ids.filter((memberId) => !removeIds.has(memberId))
    }));
    setSmsGroupSelectedSelection([]);
  }

  function openSmsTemplateCreateModal() {
    setSmsEditingTemplate(null);
    setSmsTemplateForm(emptySmsTemplateForm);
    setSmsTemplateModalOpen(true);
  }

  function openSmsTemplateEditModal(template: SmsTemplate) {
    setSmsEditingTemplate(template);
    setSmsTemplateForm({
      title: template.title,
      content: template.content,
      is_active: template.is_active
    });
    setSmsTemplateModalOpen(true);
  }

  function smsRecipientKey(item: Pick<SmsPreviewRecipient, "member_id" | "phone">) {
    return item.member_id ? `member:${item.member_id}` : `phone:${item.phone}`;
  }

  function renderAiAssistButton() {
    return (
      <a
        className="ai-assist-button"
        href="https://chatgpt.com/"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="ChatGPT에서 AI에게 물어보기 새 창 열기"
      >
        <svg className="openai-logo-icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path
            d="M12 6.4 16.9 9.2v5.6L12 17.6 7.1 14.8V9.2L12 6.4Zm0 3.4 2 1.1v2.2l-2 1.1-2-1.1v-2.2l2-1.1Z"
            fill="currentColor"
          />
        </svg>
        AI에게 물어보기
      </a>
    );
  }

  function buildSmsTargetPayload(form: SmsComposeForm) {
    return {
      include_all_members: form.include_all_members,
      include_expiring_memberships: form.include_expiring_memberships,
      expiring_days: Math.max(1, Number(form.expiring_days || 7)),
      include_low_remaining_memberships: form.include_low_remaining_memberships,
      low_remaining_count: Math.max(0, Number(form.low_remaining_count || 3)),
      include_birthdays: form.include_birthdays,
      birthday_days: Math.max(0, Number(form.birthday_days || 0)),
      group_ids: form.group_ids.map(Number)
    };
  }

  function buildSmsRequestPayload(form: SmsComposeForm, excludedKeys: string[]) {
    const payload = {
      ...buildSmsTargetPayload(form),
      content_type: form.content_type,
      template_id: form.template_id ? Number(form.template_id) : null,
      title: form.title || null,
      content: form.content,
      ...smsExcludedKeysToPayload(excludedKeys)
    };
    if (form.send_mode === "scheduled") {
      return {
        ...payload,
        scheduled_at: localDateTimeInputToIso(form.scheduled_at)
      };
    }
    return payload;
  }

  function hasSmsTargetSelection(form: SmsComposeForm) {
    return (
      form.include_all_members ||
      form.include_expiring_memberships ||
      form.include_low_remaining_memberships ||
      form.include_birthdays ||
      form.group_ids.length > 0
    );
  }

  function moveToSmsContentStep() {
    if (!hasSmsTargetSelection(smsComposeForm)) {
      setNotice("발송 대상을 하나 이상 선택해 주세요.");
      setSmsSendStep("target");
      return;
    }
    setSmsSendStep("content");
  }

  function moveToSmsReviewStep() {
    if (smsPreview) {
      setSmsSendStep("review");
      return;
    }
    void handleSmsPreview();
  }

  function resetSmsSendFlow() {
    setSmsComposeForm(emptySmsComposeForm);
    setSmsPreview(null);
    setSmsPreviewMode(null);
    setSmsPreviewModalOpen(false);
    setSmsPreviewKeyword("");
    setSmsExcludedRecipients([]);
    setSmsEditingSchedule(null);
    setSmsEditingScheduleRecipients([]);
    setSmsLastSentMessage(null);
    setSmsLastSentDetailItems([]);
    setSmsLastSentDetailLoading(false);
    setSmsSendStep("target");
  }

  async function handleSmsTargetPreview() {
    if (!hasSmsTargetSelection(smsComposeForm)) {
      setNotice("발송 대상을 하나 이상 선택해 주세요.");
      setSmsSendStep("target");
      return;
    }
    setLoading(true);
    try {
      const result = smsCanUseScheduleSnapshot && smsEditingSchedule
        ? smsPreviewFromSchedule(smsEditingSchedule, smsEditingScheduleRecipients)
        : await api<SmsPreviewResult>("/sms/recipients/preview", {
            method: "POST",
            body: JSON.stringify({
              ...buildSmsTargetPayload(smsComposeForm),
              content_type: smsComposeForm.content_type
            })
          });
      setSmsPreview(result);
      setSmsPreviewMode(smsCanUseScheduleSnapshot ? "scheduleSnapshot" : "live");
      setSmsPreviewKeyword("");
      setSmsPreviewModalOpen(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "포함 회원을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSmsPreview() {
    if (!hasSmsTargetSelection(smsComposeForm)) {
      setNotice("발송 대상을 하나 이상 선택해 주세요.");
      setSmsSendStep("target");
      return;
    }
    if (!smsComposeForm.content.trim()) {
      setNotice("문자 내용을 입력해 주세요.");
      setSmsSendStep("content");
      return;
    }
    if (smsComposeForm.send_mode === "scheduled" && !smsComposeForm.scheduled_at) {
      setNotice("예약 발송 시각을 입력해 주세요.");
      setSmsSendStep("content");
      return;
    }
    setLoading(true);
    try {
      const result = smsCanUseScheduleSnapshot && smsEditingSchedule
        ? smsPreviewFromSchedule(smsEditingSchedule, smsEditingScheduleRecipients)
        : await api<SmsPreviewResult>("/sms/recipients/preview", {
            method: "POST",
            body: JSON.stringify({
              ...buildSmsTargetPayload(smsComposeForm),
              content_type: smsComposeForm.content_type
            })
          });
      setSmsPreview(result);
      setSmsPreviewMode(smsCanUseScheduleSnapshot ? "scheduleSnapshot" : "live");
      setSmsPreviewKeyword("");
      setSmsPreviewModalOpen(false);
      setSmsLastSentMessage(null);
      setSmsLastSentDetailItems([]);
      setSmsSendStep("review");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "발송 대상을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function toggleSmsRecipientExclusion(item: SmsPreviewRecipient) {
    const key = smsRecipientKey(item);
    setSmsExcludedRecipients((current) => (current.includes(key) ? current.filter((value) => value !== key) : [...current, key]));
  }

  async function handleSmsSend() {
    if (!hasSmsTargetSelection(smsComposeForm)) {
      setNotice("발송 대상을 하나 이상 선택해 주세요.");
      setSmsSendStep("target");
      return;
    }
    if (!smsComposeForm.content.trim()) {
      setNotice("문자 내용을 입력해 주세요.");
      setSmsSendStep("content");
      return;
    }
    if (smsComposeForm.send_mode === "scheduled" && !smsComposeForm.scheduled_at) {
      setNotice("예약 발송 시각을 입력해 주세요.");
      setSmsSendStep("content");
      return;
    }
    if (smsPreview) {
      const activeEligibleCount =
        smsPreview.eligible_recipients.length -
        smsPreview.eligible_recipients.filter((item) => smsExcludedRecipients.includes(smsRecipientKey(item))).length;
      if (activeEligibleCount <= 0) {
        setNotice("최종 발송 대상이 없습니다.");
        setSmsSendStep("review");
        return;
      }
    }
    const confirmMessage =
      smsComposeForm.send_mode === "scheduled"
        ? smsEditingSchedule
          ? "현재 대상 기준으로 예약을 수정할까요?"
          : "현재 대상 기준으로 예약을 등록할까요?"
        : "현재 대상 기준으로 문자를 발송할까요?";
    if (!window.confirm(confirmMessage)) return;
    setLoading(true);
    try {
      const preview =
        smsPreview ||
        (smsCanUseScheduleSnapshot && smsEditingSchedule
          ? smsPreviewFromSchedule(smsEditingSchedule, smsEditingScheduleRecipients)
          : await api<SmsPreviewResult>("/sms/recipients/preview", {
              method: "POST",
              body: JSON.stringify({
                ...buildSmsTargetPayload(smsComposeForm),
                content_type: smsComposeForm.content_type
              })
            }));
      const activeEligibleCount =
        preview.eligible_recipients.length -
        preview.eligible_recipients.filter((item) => smsExcludedRecipients.includes(smsRecipientKey(item))).length;
      if (activeEligibleCount <= 0) {
        setNotice("최종 발송 대상이 없습니다.");
        setSmsSendStep("review");
        return;
      }

      const isScheduled = smsComposeForm.send_mode === "scheduled";
      const path = isScheduled
        ? smsEditingSchedule
          ? `/sms/schedules/${smsEditingSchedule.id}`
          : "/sms/schedules"
        : "/sms/send";
      const method = isScheduled ? (smsEditingSchedule ? "PUT" : "POST") : "POST";
      const message = await api<SmsMessage>(path, {
        method,
        body: JSON.stringify(buildSmsRequestPayload(smsComposeForm, smsExcludedRecipients))
      });
      if (isScheduled) {
        setNotice(
          message.status === "실패"
            ? "문자 예약 요청이 실패 이력으로 저장되었습니다."
            : smsEditingSchedule
              ? "문자 예약을 수정했습니다."
              : "문자 예약을 등록했습니다."
        );
      } else {
        setNotice(message.status === "실패" ? "문자 발송 요청이 실패 이력으로 저장되었습니다." : "문자 발송 요청을 등록했습니다.");
      }
      setSmsLastSentMessage(message);
      setSmsLastSentDetailItems([]);
      setSmsPreview(null);
      setSmsPreviewMode(null);
      setSmsPreviewModalOpen(false);
      setSmsPreviewKeyword("");
      setSmsExcludedRecipients([]);
      setSmsEditingSchedule(null);
      setSmsEditingScheduleRecipients([]);
      setSmsSendStep("done");
      await Promise.all([refreshSmsHistory(), refreshSmsSchedules()]);
      void refreshSmsLastSentResult(message.id, false);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : smsComposeForm.send_mode === "scheduled" ? "문자 예약에 실패했습니다." : "문자 발송에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSmsGroupSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const path = smsEditingGroup ? `/sms/groups/${smsEditingGroup.id}` : "/sms/groups";
      const method = smsEditingGroup ? "PUT" : "POST";
      await api<SmsGroup>(path, {
        method,
        body: JSON.stringify({
          name: smsGroupForm.name,
          description: smsGroupForm.description || null,
          member_ids: smsGroupForm.member_ids.map(Number),
          is_active: smsEditingGroup ? true : undefined
        })
      });
      setNotice(smsEditingGroup ? "문자 그룹을 수정했습니다." : "문자 그룹을 저장했습니다.");
      setSmsGroupModalOpen(false);
      setSmsEditingGroup(null);
      setSmsGroupForm(emptySmsGroupForm);
      setSmsGroupAvailableSelection([]);
      setSmsGroupSelectedSelection([]);
      setSmsPreview(null);
      setSmsPreviewModalOpen(false);
      setSmsPreviewKeyword("");
      setSmsExcludedRecipients([]);
      setSmsLastSentMessage(null);
      setSmsLastSentDetailItems([]);
      await refreshSmsGroups();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 그룹 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSmsGroupDelete() {
    const targetGroup = smsDeleteGroupTarget;
    if (!targetGroup) return;
    setLoading(true);
    try {
      await api<void>(`/sms/groups/${targetGroup.id}`, { method: "DELETE" });
      setNotice("문자 그룹을 삭제했습니다.");
      setSmsDeleteGroupTarget(null);
      setSmsPreview(null);
      setSmsPreviewModalOpen(false);
      setSmsPreviewKeyword("");
      setSmsExcludedRecipients([]);
      setSmsLastSentMessage(null);
      setSmsLastSentDetailItems([]);
      await refreshSmsGroups();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 그룹 삭제에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSmsScheduleDelete(message: SmsMessage) {
    if (!window.confirm("선택한 문자 예약을 삭제할까요?")) return;
    setLoading(true);
    try {
      await api<SmsMessage>(`/sms/schedules/${message.id}`, { method: "DELETE" });
      setNotice("문자 예약을 삭제했습니다.");
      if (smsEditingSchedule?.id === message.id) {
        closeSmsScheduleEditor();
      }
      await Promise.all([refreshSmsSchedules(), refreshSmsHistory()]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 예약 삭제에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSmsTemplateSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const editingTemplate = smsEditingTemplate;
      const path = editingTemplate ? `/sms/templates/${editingTemplate.id}` : "/sms/templates";
      const method = editingTemplate ? "PUT" : "POST";
      const savedTemplate = await api<SmsTemplate>(path, {
        method,
        body: JSON.stringify({
          title: smsTemplateForm.title,
          content: smsTemplateForm.content,
          is_active: smsTemplateForm.is_active
        })
      });
      setNotice(editingTemplate ? "문자 템플릿을 수정했습니다." : "문자 템플릿을 저장했습니다.");
      setSmsEditingTemplate(savedTemplate);
      setSmsTemplateForm({
        title: savedTemplate.title,
        content: savedTemplate.content,
        is_active: savedTemplate.is_active
      });
      await refreshSmsTemplates();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 템플릿 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSmsTemplateDelete(template: SmsTemplate) {
    if (!window.confirm(`${template.title} 템플릿을 삭제할까요?`)) return;
    setLoading(true);
    try {
      await api<void>(`/sms/templates/${template.id}`, { method: "DELETE" });
      setNotice("문자 템플릿을 삭제했습니다.");
      if (smsEditingTemplate?.id === template.id) {
        setSmsEditingTemplate(null);
        setSmsTemplateForm(emptySmsTemplateForm);
      }
      setSmsComposeForm((current) =>
        current.template_id === String(template.id) ? { ...current, template_id: "", title: "", content: "" } : current
      );
      await refreshSmsTemplates();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 템플릿 삭제에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function applySmsTemplate(templateId: string) {
    const template = smsTemplates.find((item) => String(item.id) === templateId) || null;
    setSmsComposeForm((current) => ({
      ...current,
      template_id: templateId,
      title: template ? template.title : "",
      content: template ? template.content : ""
    }));
  }

  async function openSmsHistoryDetail(message: SmsMessage) {
    setLoading(true);
    try {
      const result = await fetchSmsMessageRecipients(message.id);
      applySmsMessageDetailResult(result);
      if (smsLastSentMessage?.id === result.message.id) {
        setSmsLastSentMessage(result.message);
        setSmsLastSentDetailItems(result.items);
      }
      setSmsHistoryDetailTarget(result.message);
      setSmsHistoryDetailItems(result.items);
      setSmsHistoryDetailKeyword("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "문자 발송 상세를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function closeSalesSummaryModal() {
    setSalesSummaryModal(null);
    setSalesSummaryDetailItems([]);
    setSalesSummaryDetailKeyword("");
  }

  async function openSalesSummaryModal(type: SalesSummaryModalKey) {
    if (type === "totalAmount" || type === "totalCount") {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          from_date: salesSummaryFrom,
          to_date: salesSummaryTo,
          size: "500",
        });
        const result = await api<ListResult<Sale>>(`/sales?${params.toString()}`);
        setSalesSummaryDetailItems(result.items);
        setSalesSummaryDetailKeyword("");
        setSalesSummaryModal(type);
      } catch (error) {
        setNotice(error instanceof Error ? error.message : "매출 상세 정보를 불러오지 못했습니다.");
      } finally {
        setLoading(false);
      }
      return;
    }
    setSalesSummaryDetailItems([]);
    setSalesSummaryDetailKeyword("");
    setSalesSummaryModal(type);
  }

  async function refreshAll() {
    setLoading(true);
    try {
      await Promise.all([
        refreshDashboard(),
        refreshMembers(),
        refreshMemberResults(),
        refreshDeletedMembers(),
        refreshProducts(),
        refreshMemberships(),
        refreshMembershipResults(),
        refreshReservations(),
        refreshSales(),
        refreshSalesSummary(),
      ]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "자료를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function openMember(member: Member) {
    setSelectedMember(member);
    setMemberEditForm(memberToForm(member));
    const [saleResult, membershipResult] = await Promise.all([
      api<ListResult<Sale>>(`/members/${member.id}/sales`),
      api<ListResult<MemberMembership>>(`/members/${member.id}/memberships`)
    ]);
    setSelectedMemberSales(saleResult.items);
    setSelectedMemberMemberships(membershipResult.items);
  }

  async function handleMemberSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const member = await api<Member>("/members", {
        method: "POST",
        body: JSON.stringify(compactPayload(memberForm))
      });
      setMemberForm(emptyMemberForm);
      setNotice("회원이 저장되었습니다.");
      await Promise.all([refreshMembers(), refreshMemberResults()]);
      await refreshDashboard();
      await openMember(member);
      setMemberRegisterOpen(false);
      setActiveTab("memberInfo");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "회원 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleMemberUpdate(event: FormEvent) {
    event.preventDefault();
    if (!selectedMember) return;
    setLoading(true);
    try {
      const member = await api<Member>(`/members/${selectedMember.id}`, {
        method: "PUT",
        body: JSON.stringify(memberUpdatePayload(memberEditForm))
      });
      setNotice("회원 정보가 수정되었습니다.");
      await Promise.all([refreshMembers(), refreshMemberResults()]);
      setSelectedMember(member);
      setMemberEditForm(memberToForm(member));
      setMemberEditOpen(false);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "회원 정보 수정에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleMemberDelete(member?: Member) {
    const targetMember = member || selectedMember;
    if (!targetMember) return;
    if (!window.confirm(`${targetMember.name} 회원 정보를 삭제 처리할까요?`)) return;
    setLoading(true);
    try {
      await api<Member>(`/members/${targetMember.id}/deactivate`, {
        method: "PATCH",
        body: JSON.stringify({ note: "화면에서 삭제 처리" })
      });
      setNotice("회원 정보가 삭제 처리되었습니다.");
      if (selectedMember?.id === targetMember.id) {
        setSelectedMember(null);
        setSelectedMemberSales([]);
        setSelectedMemberMemberships([]);
        setMemberEditForm(emptyMemberForm);
        setMemberEditOpen(false);
      }
      await Promise.all([refreshMembers(), refreshMemberResults(), refreshDeletedMembers(), refreshDashboard()]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "회원 삭제 처리에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleMemberRestore(member: Member) {
    setLoading(true);
    try {
      await api<Member>(`/members/${member.id}/restore`, {
        method: "PATCH",
        body: JSON.stringify({ note: "화면에서 회원 복원" })
      });
      setNotice(`${member.name} 회원 정보가 복원되었습니다.`);
      await Promise.all([refreshMembers(), refreshMemberResults(), refreshDeletedMembers(), refreshDashboard()]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "회원 복원에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleMemberPermanentDelete(member: Member) {
    if (!window.confirm(`${member.name} 회원 정보를 영구삭제할까요? 이 작업은 되돌릴 수 없습니다.`)) return;
    setLoading(true);
    try {
      await api<void>(`/members/${member.id}`, {
        method: "DELETE",
        body: JSON.stringify({ note: "삭제 회원정보 복구 팝업에서 영구삭제" })
      });
      setNotice(`${member.name} 회원 정보를 영구삭제했습니다.`);
      await Promise.all([refreshDeletedMembers(), refreshMembers(), refreshMemberResults()]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "영구삭제에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function openMemberSalesHistory(member: Member) {
    setLoading(true);
    try {
      const result = await api<ListResult<Sale>>(`/members/${member.id}/sales?size=100`);
      setMemberHistoryTarget(member);
      setMemberHistorySales(result.items);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "매출 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function handleProductTypeChange(productType: ProductForm["product_type"]) {
    setProductForm((current) => ({
      ...current,
      product_type: productType,
      duration_days: productType === "판매" ? "" : current.duration_days,
      total_count: productType === "횟수" ? current.total_count : ""
    }));
  }

  function openProductCreateModal() {
    setEditingProduct(null);
    setProductForm({
      name: "",
      product_type: "기간제",
      duration_days: "",
      total_count: "",
      price: ""
    });
    setProductModalOpen(true);
  }

  function openProductEditModal(product: MembershipProduct) {
    setEditingProduct(product);
    setProductForm(productToForm(product));
    setProductModalOpen(true);
  }

  function resetSaleEntryForm() {
    setSaleForm(emptySaleForm);
    setSaleMemberMatches([]);
    setSaleMemberInputFocused(false);
    setSaleSelectedMember(null);
  }

  function openSaleEntryModal() {
    resetSaleEntryForm();
    setSaleEntryOpen(true);
  }

  function closeSaleEntryModal() {
    setSaleEntryOpen(false);
    setSaleMemberMatches([]);
    setSaleMemberInputFocused(false);
  }

  function resetReservationForm(targetDate = reservationDate) {
    setReservationForm({
      ...emptyReservationForm,
      reservation_date: targetDate
    });
    setReservationMemberMatches([]);
    setReservationMemberInputFocused(false);
    setReservationSelectedMember(null);
  }

  function openReservationCreateModal(bayNumber = 1, startTime = RESERVATION_OPEN_TIME) {
    const endTime = addMinutesToTime(startTime, RESERVATION_SLOT_MINUTES);
    setEditingReservation(null);
    setReservationForm({
      ...emptyReservationForm,
      bay_number: String(bayNumber),
      reservation_date: reservationDate,
      start_time: startTime,
      end_time: endTime
    });
    setReservationMemberMatches([]);
    setReservationMemberInputFocused(false);
    setReservationSelectedMember(null);
    setReservationModalOpen(true);
  }

  function openReservationEditModal(reservation: Reservation) {
    setEditingReservation(reservation);
    setReservationForm({
      bay_number: String(reservation.bay_number),
      member_id: reservation.member_id ? String(reservation.member_id) : "",
      customer_name: reservation.customer_name,
      customer_phone: displayPhone(reservation.customer_phone),
      reservation_date: reservation.reservation_date,
      start_time: normalizeTimeValue(reservation.start_time),
      end_time: normalizeTimeValue(reservation.end_time),
      note: reservation.note || ""
    });
    setReservationMemberMatches([]);
    setReservationMemberInputFocused(false);
    setReservationSelectedMember(null);
    setReservationModalOpen(true);
  }

  function closeReservationModal() {
    setReservationModalOpen(false);
    setEditingReservation(null);
    resetReservationForm();
  }

  function reservationPayload() {
    return {
      bay_number: Number(reservationForm.bay_number),
      member_id: reservationForm.member_id ? Number(reservationForm.member_id) : null,
      customer_name: reservationForm.customer_name,
      customer_phone: digitsOnly(reservationForm.customer_phone),
      reservation_date: reservationForm.reservation_date,
      start_time: reservationForm.start_time,
      end_time: reservationForm.end_time,
      note: reservationForm.note || null
    };
  }

  async function handleReservationSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const path = editingReservation ? `/reservations/${editingReservation.id}` : "/reservations";
      const method = editingReservation ? "PUT" : "POST";
      await api<Reservation>(path, {
        method,
        body: JSON.stringify(reservationPayload())
      });
      setNotice(editingReservation ? "예약을 수정했습니다." : "예약을 등록했습니다.");
      setReservationModalOpen(false);
      setEditingReservation(null);
      resetReservationForm();
      await refreshReservations(reservationForm.reservation_date || reservationDate);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "예약 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function cancelReservation(reservation: Reservation) {
    if (!window.confirm(`${reservation.customer_name} 예약을 취소할까요?`)) return;
    setLoading(true);
    try {
      await api<Reservation>(`/reservations/${reservation.id}/cancel`, {
        method: "PATCH",
        body: JSON.stringify({ note: "화면에서 예약 취소" })
      });
      setNotice("예약을 취소했습니다.");
      setReservationModalOpen(false);
      await refreshReservations(reservationDate);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "예약 상태 변경에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function selectReservationMember(member: Member) {
    setReservationSelectedMember(member);
    setReservationMemberMatches([]);
    setReservationMemberInputFocused(false);
    setReservationForm((current) => ({
      ...current,
      member_id: String(member.id),
      customer_name: member.name,
      customer_phone: displayPhone(member.phone)
    }));
  }

  function handleReservationNameChange(value: string) {
    const shouldClearSelection = reservationSelectedMember && value !== reservationSelectedMember.name;
    if (shouldClearSelection) {
      setReservationSelectedMember(null);
    }
    setReservationForm((current) => ({
      ...current,
      member_id: shouldClearSelection ? "" : current.member_id,
      customer_name: value,
      customer_phone:
        shouldClearSelection && digitsOnly(current.customer_phone) === reservationSelectedMember?.phone ? "" : current.customer_phone
    }));
  }

  function handleReservationPhoneChange(value: string) {
    const shouldClearSelection = reservationSelectedMember && digitsOnly(value) !== reservationSelectedMember.phone;
    if (shouldClearSelection) {
      setReservationSelectedMember(null);
    }
    setReservationForm((current) => ({
      ...current,
      member_id: shouldClearSelection ? "" : current.member_id,
      customer_phone: value
    }));
  }

  function handleSaleProductChange(productId: string) {
    const product = activeSaleProducts.find((item) => String(item.id) === productId) || null;
    setSaleForm((current) => {
      if (!product) {
        return {
          ...current,
          product_id: "",
          start_date: "",
          end_date: "",
          total_count: ""
        };
      }

      const nextStartDate =
        product.product_type === "판매" ? "" : product.product_type === "횟수" ? today() : current.start_date || today();
      return {
        ...current,
        product_id: productId,
        amount: String(Number(product.price || 0)),
        start_date: nextStartDate,
        end_date: product.product_type === "판매" ? "" : addDays(nextStartDate, product.duration_days),
        total_count: product.product_type === "횟수" ? String(product.total_count || "") : ""
      };
    });
  }

  function handleSaleStartDateChange(value: string) {
    setSaleForm((current) => ({
      ...current,
      start_date: value,
      end_date: selectedSaleProduct ? addDays(value, selectedSaleProduct.duration_days) : current.end_date
    }));
  }

  async function handleProductSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const path = editingProduct ? `/membership-products/${editingProduct.id}` : "/membership-products";
      const method = editingProduct ? "PUT" : "POST";
      await api<MembershipProduct>(path, {
        method,
        body: JSON.stringify(
          compactPayload({
            ...productForm,
            duration_days: productForm.duration_days ? Number(productForm.duration_days) : "",
            total_count: productForm.total_count ? Number(productForm.total_count) : "",
            price: productForm.price ? Number(productForm.price) : 0
          })
        )
      });
      setProductForm({ name: "", product_type: "기간제", duration_days: "", total_count: "", price: "" });
      setEditingProduct(null);
      setProductModalOpen(false);
      setNotice(editingProduct ? "상품 정보가 수정되었습니다." : "상품이 저장되었습니다.");
      await refreshProducts();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : editingProduct ? "상품 수정에 실패했습니다." : "상품 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleProductStatusToggle(product: MembershipProduct) {
    setLoading(true);
    try {
      await api<MembershipProduct>(`/membership-products/${product.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !product.is_active })
      });
      setNotice(product.is_active ? "상품을 비활성 처리했습니다." : "상품을 활성화했습니다.");
      await refreshProducts();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "상품 상태 변경에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleProductDelete(product: MembershipProduct) {
    if (!window.confirm(`${product.name} 상품을 삭제할까요? 사용 이력이 있으면 삭제되지 않습니다.`)) return;
    setLoading(true);
    try {
      await api<void>(`/membership-products/${product.id}`, { method: "DELETE" });
      setNotice("상품을 삭제했습니다.");
      await refreshProducts();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "상품 삭제에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await api<Sale>("/sales", {
        method: "POST",
        body: JSON.stringify(
          compactPayload({
            ...saleForm,
            member_id: saleForm.member_id ? Number(saleForm.member_id) : "",
            product_id: saleForm.product_id ? Number(saleForm.product_id) : "",
            total_count: saleForm.total_count ? Number(saleForm.total_count) : "",
            amount: Number(saleForm.amount)
          })
        )
      });
      resetSaleEntryForm();
      setSaleEntryOpen(false);
      setNotice("매출이 저장되었습니다.");
      await Promise.all([
        refreshDashboard(),
        refreshSales(),
        refreshSalesSummary(),
        refreshMemberships(),
        refreshMembershipResults(),
        refreshMembers(),
        refreshMemberResults()
      ]);
      if (selectedMember) await openMember(selectedMember);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "매출 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function runMembershipAction(path: string, body: Record<string, unknown>, message: string) {
    setLoading(true);
    try {
      await api<MemberMembership>(path, { method: "POST", body: JSON.stringify(body) });
      setNotice(message);
      await Promise.all([refreshMemberships(), refreshMembershipResults()]);
      if (selectedMember) await openMember(selectedMember);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "처리에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function changeMembershipStatus(id: number, action: "pause" | "resume") {
    setLoading(true);
    try {
      await api<MemberMembership>(`/member-memberships/${id}/${action}`, {
        method: "PATCH",
        body: JSON.stringify({})
      });
      setNotice(action === "pause" ? "정지 처리되었습니다." : "재개 처리되었습니다.");
      await Promise.all([refreshMemberships(), refreshMembershipResults()]);
      if (selectedMember) await openMember(selectedMember);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "처리에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function toggleMembershipStatusFilter(status: MembershipStatusFilter) {
    setMembershipPage(1);
    setMembershipStatusFilters((current) =>
      current.includes(status) ? current.filter((item) => item !== status) : [...current, status]
    );
  }

  function handleMembershipKeywordChange(value: string) {
    setMembershipKeyword(value);
    setMembershipPage(1);
  }

  function openMembershipPeriodModal(item: MemberMembership) {
    setPeriodAdjustMembership(item);
    setPeriodAdjustForm({
      start_date: item.start_date,
      end_date: item.end_date || "",
      note: ""
    });
  }

  async function handleMembershipPeriodSubmit(event: FormEvent) {
    event.preventDefault();
    if (!periodAdjustMembership) return;
    setLoading(true);
    try {
      await api<MemberMembership>(`/member-memberships/${periodAdjustMembership.id}/period`, {
        method: "PATCH",
        body: JSON.stringify(
          compactPayload({
            start_date: periodAdjustForm.start_date,
            end_date: periodAdjustForm.end_date || null,
            note: periodAdjustForm.note || null
          })
        )
      });
      setNotice("유효기간을 보정했습니다.");
      setPeriodAdjustMembership(null);
      setPeriodAdjustForm(emptyMembershipPeriodForm);
      await Promise.all([refreshMemberships(), refreshMembershipResults()]);
      if (selectedMember) await openMember(selectedMember);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "유효기간 보정에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function updateMembershipPeriodInline(item: MemberMembership, startDate: string, endDate: string) {
    setLoading(true);
    try {
      await api<MemberMembership>(`/member-memberships/${item.id}/period`, {
        method: "PATCH",
        body: JSON.stringify({
          start_date: startDate,
          end_date: endDate || null,
          note: "화면에서 날짜 선택으로 기간 보정"
        })
      });
      setNotice("유효기간을 보정했습니다.");
      await Promise.all([refreshMemberships(), refreshMembershipResults()]);
      if (selectedMember) await openMember(selectedMember);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "유효기간 보정에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function openMembershipCountModal(item: MemberMembership) {
    setCountAdjustMembership(item);
    setCountAdjustForm({
      remaining_count: item.remaining_count === null || item.remaining_count === undefined ? "" : String(item.remaining_count),
      note: ""
    });
  }

  async function handleMembershipCountSubmit(event: FormEvent) {
    event.preventDefault();
    if (!countAdjustMembership) return;
    setLoading(true);
    try {
      await api<MemberMembership>(`/member-memberships/${countAdjustMembership.id}/adjust`, {
        method: "POST",
        body: JSON.stringify({
          remaining_count: Number(countAdjustForm.remaining_count),
          note: countAdjustForm.note || "화면에서 남은 횟수 변경"
        })
      });
      setNotice("남은 횟수를 변경했습니다.");
      setCountAdjustMembership(null);
      setCountAdjustForm(emptyMembershipCountForm);
      await Promise.all([refreshMemberships(), refreshMembershipResults()]);
      if (selectedMember) await openMember(selectedMember);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "남은 횟수 변경에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function deductCountFromModal() {
    if (!countAdjustMembership) return;
    await runMembershipAction(
      `/member-memberships/${countAdjustMembership.id}/deduct`,
      { count: 1, note: countAdjustForm.note || "화면에서 남은 횟수 팝업 차감" },
      "1회 차감했습니다."
    );
    setCountAdjustMembership(null);
    setCountAdjustForm(emptyMembershipCountForm);
  }

  async function openMembershipHistory(item: MemberMembership) {
    setLoading(true);
    try {
      const result = await api<ListResult<MembershipUsageLog>>(`/member-memberships/${item.id}/usage-logs`);
      setMembershipHistoryTarget(item);
      setMembershipHistoryLogs(result.items);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function applySalesSummaryRange(range: SalesSummaryRange) {
    setSalesSummaryRange(range);
    setSalesSummaryFrom(salesSummaryStartDate(salesSummaryTo, range));
  }

  function handleSalesSummaryToChange(value: string) {
    setSalesSummaryTo(value);
    setSalesSummaryFrom(salesSummaryStartDate(value, salesSummaryRange));
  }

  async function refundSale(sale: Sale) {
    if (!window.confirm(`${sale.sale_date} ${money(sale.amount)} 매출을 환불 처리할까요?`)) return;
    setLoading(true);
    try {
      await api<Sale>(`/sales/${sale.id}/refund`, {
        method: "POST",
        body: JSON.stringify({ note: "화면에서 환불 처리" })
      });
      setNotice("환불 처리되었습니다.");
      await Promise.all([refreshDashboard(), refreshSales(), refreshSalesSummary(), refreshMemberships(), refreshMembershipResults()]);
      if (selectedMember) await openMember(selectedMember);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "환불 처리에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTime(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    handleFullscreenChange();
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  useEffect(() => {
    if (!SMS_FEATURE_VISIBLE && activeTab === "sms") {
      setActiveTab("dashboard");
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== "dashboard") return;
    const timer = window.setTimeout(() => {
      void refreshDashboard();
    }, 200);
    return () => window.clearTimeout(timer);
  }, [activeTab, dashboardNewMemberDays, dashboardSalesDays, dashboardExpiringDays, dashboardLowCount]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshMemberResults(memberKeyword, memberSalesReferenceDate);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [memberKeyword, memberSalesReferenceDate]);

  useEffect(() => {
    if (activeTab !== "memberships") return;
    const timer = window.setTimeout(() => {
      void refreshMembershipResults();
    }, 220);
    return () => window.clearTimeout(timer);
  }, [activeTab, membershipKeyword, membershipPage, membershipStatusFilters]);

  useEffect(() => {
    if (activeTab !== "salesSummary") return;
    const timer = window.setTimeout(() => {
      void refreshSalesSummary();
    }, 180);
    return () => window.clearTimeout(timer);
  }, [activeTab, salesSummaryFrom, salesSummaryTo]);

  useEffect(() => {
    if (activeTab !== "sales") return;
    const timer = window.setTimeout(() => {
      void refreshSales();
    }, 180);
    return () => window.clearTimeout(timer);
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== "reservations") return;
    const timer = window.setTimeout(() => {
      void refreshReservations(reservationDate);
    }, 180);
    return () => window.clearTimeout(timer);
  }, [activeTab, reservationDate]);

  useEffect(() => {
    if (activeTab !== "sms") return;
    const timer = window.setTimeout(() => {
      void refreshSmsData();
    }, 180);
    return () => window.clearTimeout(timer);
  }, [activeTab]);

  useEffect(() => {
    if (!smsHistoryModalOpen || !smsHistory.some((message) => message.status === "발송중")) return;
    const timer = window.setInterval(() => {
      void refreshSmsHistory().catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [smsHistory, smsHistoryModalOpen]);

  useEffect(() => {
    if (!smsScheduleModalOpen || !smsSchedules.some((message) => message.status === "예약")) return;
    const timer = window.setInterval(() => {
      void refreshSmsSchedules().catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [smsScheduleModalOpen, smsSchedules]);

  useEffect(() => {
    if (smsSendStep !== "done" || !smsLastSentMessage || smsLastSentMessage.status !== "발송중") return;
    const timer = window.setInterval(() => {
      void refreshSmsLastSentResult(smsLastSentMessage.id, false);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [smsLastSentMessage, smsSendStep]);

  useEffect(() => {
    setSmsPreview(null);
    setSmsPreviewMode(null);
    setSmsPreviewModalOpen(false);
    setSmsPreviewKeyword("");
    setSmsLastSentMessage(null);
    setSmsLastSentDetailItems([]);
    setSmsLastSentDetailLoading(false);
    setSmsSendStep((current) => (current === "review" || current === "done" ? "target" : current));
  }, [
    smsComposeForm.include_all_members,
    smsComposeForm.include_expiring_memberships,
    smsComposeForm.expiring_days,
    smsComposeForm.include_low_remaining_memberships,
    smsComposeForm.low_remaining_count,
    smsComposeForm.include_birthdays,
    smsComposeForm.birthday_days,
    smsComposeForm.group_ids,
    smsComposeForm.content_type,
    smsComposeForm.send_mode
  ]);

  useEffect(() => {
    const query = saleForm.member_name.trim();
    if (!query || (saleSelectedMember && query === saleSelectedMember.name)) {
      setSaleMemberMatches([]);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          keyword: query,
          size: "8"
        });
        const result = await api<ListResult<Member>>(`/members?${params.toString()}`);
        if (cancelled) return;
        setSaleMemberMatches(result.items.filter((member) => member.name.includes(query)));
      } catch {
        if (!cancelled) {
          setSaleMemberMatches([]);
        }
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [saleForm.member_name, saleSelectedMember]);

  useEffect(() => {
    const query = reservationForm.customer_name.trim();
    if (!query || (reservationSelectedMember && query === reservationSelectedMember.name)) {
      setReservationMemberMatches([]);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          keyword: query,
          size: "8"
        });
        const result = await api<ListResult<Member>>(`/members?${params.toString()}`);
        if (cancelled) return;
        setReservationMemberMatches(result.items.filter((member) => member.name.includes(query)));
      } catch {
        if (!cancelled) {
          setReservationMemberMatches([]);
        }
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [reservationForm.customer_name, reservationSelectedMember]);

  function selectSaleMember(member: Member) {
    setSaleSelectedMember(member);
    setSaleMemberMatches([]);
    setSaleMemberInputFocused(false);
    setSaleForm((current) => ({
      ...current,
      member_id: String(member.id),
      member_name: member.name,
      member_phone: displayPhone(member.phone)
    }));
  }

  function handleSaleMemberNameChange(value: string) {
    const shouldClearSelection = saleSelectedMember && value !== saleSelectedMember.name;
    if (shouldClearSelection) {
      setSaleSelectedMember(null);
    }
    setSaleForm((current) => ({
      ...current,
      member_id: shouldClearSelection ? "" : current.member_id,
      member_name: value,
      member_phone:
        shouldClearSelection && digitsOnly(current.member_phone) === saleSelectedMember?.phone ? "" : current.member_phone
    }));
  }

  function handleSaleMemberPhoneChange(value: string) {
    const shouldClearSelection = saleSelectedMember && digitsOnly(value) !== saleSelectedMember.phone;
    if (shouldClearSelection) {
      setSaleSelectedMember(null);
    }
    setSaleForm((current) => ({
      ...current,
      member_id: shouldClearSelection ? "" : current.member_id,
      member_phone: value
    }));
  }

  async function toggleFullscreen() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
        return;
      }
      await document.exitFullscreen();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "전체화면 전환에 실패했습니다.");
    }
  }

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="brand">
          <img src="/golf-operator.svg" alt="스크린골프 운영" />
          <div>
            <strong>스크린골프 운영</strong>
            <span>회원, 보유 상품, 매출을 한곳에서 관리합니다.</span>
            <time className="brand-clock" dateTime={currentTime.toISOString()}>
              현재 {formatCurrentDateTime(currentTime)} · {currentTimeZone} 기준
            </time>
          </div>
        </div>
        <div className="top-bar-actions">
          <div className="top-bar-utility">
            <button
              type="button"
              className={`screen-toggle-button${isFullscreen ? " active" : ""}`}
              aria-pressed={isFullscreen}
              onClick={() => void toggleFullscreen()}
            >
              {isFullscreen ? "전체화면 종료" : "전체화면"}
            </button>
          </div>
          <nav className="main-nav" aria-label="주요 메뉴">
            {[
              ["dashboard", "홈"],
              ["memberInfo", "회원 정보"],
              ["reservations", "예약"],
              ["sales", "매출관리"],
              ["salesSummary", "매출현황"],
              ["memberships", "보유 상품"],
              ["products", "상품/요금"],
              ...(SMS_FEATURE_VISIBLE ? ([["sms", "문자발송"]] as Array<[string, string]>) : [])
            ].map(([key, label]) => (
              <button key={key} className={activeTab === key ? "active" : ""} onClick={() => setActiveTab(key as TabKey)}>
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main>
        {notice && (
          <div className="notice" role="status">
            {notice}
            <button onClick={() => setNotice("")}>닫기</button>
          </div>
        )}
        {loading && <div className="loading">처리 중입니다.</div>}
        {activeTab === "dashboard" && renderDashboard()}
        {activeTab === "memberInfo" && renderMemberInfo()}
        {activeTab === "reservations" && renderReservations()}
        {activeTab === "sales" && renderSales()}
        {activeTab === "salesSummary" && renderSalesSummary()}
        {activeTab === "memberships" && renderMemberships()}
        {activeTab === "products" && renderProducts()}
        {SMS_FEATURE_VISIBLE && activeTab === "sms" && renderSms()}
        {memberRegisterOpen && renderMemberRegisterModal()}
        {memberEditOpen && renderMemberEditModal()}
        {memberRestoreOpen && renderDeletedMembersModal()}
        {memberHistoryTarget && renderMemberSalesHistoryModal()}
        {productModalOpen && renderProductModal()}
        {saleEntryOpen && renderSaleEntryModal()}
        {reservationModalOpen && renderReservationModal()}
        {reservationCanceledModalOpen && renderCanceledReservationsModal()}
        {dashboardNewMembersOpen && renderDashboardNewMembersModal()}
        {dashboardSalesOpen && renderDashboardSalesModal()}
        {saleNoteModal && renderSaleNoteModal()}
        {periodAdjustMembership && renderMembershipPeriodModal()}
        {countAdjustMembership && renderMembershipCountModal()}
        {membershipHistoryTarget && renderMembershipHistoryModal()}
        {dashboardMembershipModal && renderDashboardMembershipModal()}
        {salesSummaryModal && renderSalesSummaryModal()}
        {SMS_FEATURE_VISIBLE && smsPreviewModalOpen && renderSmsPreviewModal()}
        {SMS_FEATURE_VISIBLE && smsGroupModalOpen && renderSmsGroupModal()}
        {SMS_FEATURE_VISIBLE && smsDeleteGroupTarget && renderSmsGroupDeleteModal()}
        {SMS_FEATURE_VISIBLE && smsTemplateModalOpen && renderSmsTemplateModal()}
        {SMS_FEATURE_VISIBLE && smsMonthlyBillingModalOpen && renderSmsMonthlyBillingModal()}
        {SMS_FEATURE_VISIBLE && smsScheduleModalOpen && renderSmsScheduleModal()}
        {SMS_FEATURE_VISIBLE && smsHistoryModalOpen && renderSmsHistoryModal()}
        {SMS_FEATURE_VISIBLE && smsHistoryDetailTarget && renderSmsHistoryDetailModal()}
        {SMS_FEATURE_VISIBLE && smsHistoryMessageTarget && renderSmsHistoryMessageModal()}
      </main>
    </div>
  );

  function renderDashboard() {
    return (
      <section className="page-section">
        <div className="metric-grid dashboard-metric-grid">
          <article className="metric metric-button-card">
            <span>현재 회원 수</span>
            <button type="button" onClick={() => setActiveTab("memberInfo")}>
              {dashboard?.current_member_count ?? 0}명
            </button>
          </article>
          <article className="metric metric-button-card">
            <span>신규 회원</span>
            <label className="metric-filter-control">
              <input
                inputMode="numeric"
                aria-label="신규 회원 집계 일수"
                value={dashboardNewMemberDays}
                onChange={(event) => setDashboardNewMemberDays(digitsOnly(event.target.value))}
              />
              <small>일</small>
            </label>
            <button type="button" onClick={() => void openDashboardNewMembersModal()}>
              {dashboard?.today_new_members ?? 0}명
            </button>
          </article>
          <article className="metric metric-button-card">
            <span>매출</span>
            <label className="metric-filter-control">
              <input
                inputMode="numeric"
                aria-label="매출 집계 일수"
                value={dashboardSalesDays}
                onChange={(event) => setDashboardSalesDays(digitsOnly(event.target.value))}
              />
              <small>일</small>
            </label>
            <button type="button" onClick={() => void openDashboardSalesModal()}>
              {money(dashboard?.today_sales)}
            </button>
          </article>
          <article className="metric warning metric-button-card">
            <span>만료 예정 상품</span>
            <label className="metric-filter-control">
              <input
                inputMode="numeric"
                aria-label="만료 예정 일수"
                value={dashboardExpiringDays}
                onChange={(event) => setDashboardExpiringDays(digitsOnly(event.target.value))}
              />
              <small>일 안에 만료</small>
            </label>
            <button type="button" onClick={() => void openDashboardMembershipModal("expiring")}>
              {dashboard?.expiring_memberships ?? 0}건
            </button>
          </article>
          <article className="metric warning metric-button-card">
            <span>잔여 횟수 부족</span>
            <label className="metric-filter-control">
              <input
                inputMode="numeric"
                aria-label="남은 횟수 기준"
                value={dashboardLowCount}
                onChange={(event) => setDashboardLowCount(digitsOnly(event.target.value))}
              />
              <small>회 이하 남음</small>
            </label>
            <button type="button" onClick={() => void openDashboardMembershipModal("lowCount")}>
              {dashboard?.low_remaining_memberships ?? 0}건
            </button>
          </article>
        </div>
        <div className="quick-actions">
          <button onClick={() => setActiveTab("memberInfo")}>회원 찾기</button>
          <button onClick={() => setActiveTab("sales")}>매출 등록</button>
          <button onClick={() => setActiveTab("memberships")}>보유 상품 확인</button>
        </div>
        <DataTable
          title="최근 매출"
          headers={["등록시각", "회원", "상품명", "결제", "금액", "상태"]}
          rows={(dashboard?.recent_sales || []).map((sale) => [
            formatDateTime(sale.created_at),
            sale.member_name_snapshot || "비회원",
            sale.sale_type,
            sale.payment_method,
            money(sale.amount),
            sale.status
          ])}
        />
      </section>
    );
  }

  function renderMemberInfo() {
    return (
      <section className="page-section">
        <div className="member-toolbar">
          <button
            type="button"
            onClick={() => {
              setMemberForm(emptyMemberForm);
              setMemberRegisterOpen(true);
            }}
          >
            신규 회원등록
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setDeletedMemberKeyword("");
              void refreshDeletedMembers();
              setMemberRestoreOpen(true);
            }}
          >
            삭제 회원정보 복구
          </button>
          <div className="member-count-pill" aria-label="현재 활성 회원 수">
            <span>현재 회원</span>
            <strong>{dashboard?.current_member_count ?? 0}명</strong>
          </div>
          <div className="search-row search-row-single">
            <input
              className="large-input"
              placeholder="이름, 전화번호, 메모를 입력하면 자동 검색됩니다"
              value={memberKeyword}
              onChange={(event) => setMemberKeyword(event.target.value)}
            />
          </div>
          <label className="reference-date-field">
            매출 기준일
            <input
              type="date"
              value={memberSalesReferenceDate}
              onChange={(event) => setMemberSalesReferenceDate(event.target.value)}
            />
          </label>
        </div>
        <section className="table-section member-table-section">
          {memberResults.length === 0 ? (
            <p className="empty">검색된 회원이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="member-table">
                <thead>
                  <tr>
                    <th>이름</th>
                    <th>연락처</th>
                    <th>생년월일</th>
                    <th>성별</th>
                    <th>메모</th>
                    <th>보유 상품</th>
                    <th>총매출</th>
                    <th>최근 30일 매출</th>
                    <th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {memberResults.map((member) => (
                    <tr key={member.id}>
                      <td>
                        <strong>{member.name}</strong>
                      </td>
                      <td>{displayPhone(member.phone)}</td>
                      <td>{member.birth_date || "-"}</td>
                      <td>{member.gender || "-"}</td>
                      <td className="memo-cell">{member.memo || "-"}</td>
                      <td>{renderMembershipBadges(member.id)}</td>
                      <td className="amount-cell">{money(member.total_sales_amount)}</td>
                      <td className="amount-cell">{money(member.recent_30_days_sales_amount)}</td>
                      <td>
                        <div className="table-actions">
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => {
                              setSelectedMember(member);
                              setMemberEditForm(memberToForm(member));
                              setMemberEditOpen(true);
                            }}
                          >
                            수정
                          </button>
                          <button type="button" className="secondary" onClick={() => void openMemberSalesHistory(member)}>
                            이력
                          </button>
                          <button type="button" className="danger" onClick={() => void handleMemberDelete(member)}>
                            삭제
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>
    );
  }

  function renderMembershipBadges(memberId: number) {
    const items = membershipsByMember.get(memberId) || [];
    if (items.length === 0) return <span className="muted">없음</span>;
    return (
      <div className="membership-tags">
        {items.map((item) => (
          <span key={item.id}>
            {item.product_name || item.product_type || "보유 상품"}
            {item.remaining_count === null || item.remaining_count === undefined ? "" : ` ${item.remaining_count}회`}
          </span>
        ))}
      </div>
    );
  }

  function renderMemberRegisterModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="member-register-title">
        <form className="form-panel modal-panel" onSubmit={handleMemberSubmit}>
          <div className="modal-title-row">
            <h2 id="member-register-title">신규 회원 등록</h2>
            <button type="button" className="secondary" onClick={() => setMemberRegisterOpen(false)}>
              닫기
            </button>
          </div>
          <label>
            이름 (필수)
            <input required value={memberForm.name} onChange={(event) => setMemberForm({ ...memberForm, name: event.target.value })} />
          </label>
          <label>
            휴대전화 (필수)
            <input
              required
              inputMode="numeric"
              placeholder="예: 010-1234-5678"
              value={memberForm.phone}
              onChange={(event) => setMemberForm({ ...memberForm, phone: event.target.value })}
            />
          </label>
          <div className="form-grid">
            <label>
              생년월일
              <input
                type="date"
                value={memberForm.birth_date}
                onChange={(event) => setMemberForm({ ...memberForm, birth_date: event.target.value })}
              />
            </label>
            <label>
              성별
              <select value={memberForm.gender} onChange={(event) => setMemberForm({ ...memberForm, gender: event.target.value })}>
                <option value="">선택 안함</option>
                <option value="남성">남성</option>
                <option value="여성">여성</option>
              </select>
            </label>
          </div>
          <label>
            이메일
            <input
              type="email"
              placeholder="예: screen-golf@example.com"
              value={memberForm.email}
              onChange={(event) => setMemberForm({ ...memberForm, email: event.target.value })}
            />
          </label>
          <label>
            주소
            <input value={memberForm.address} onChange={(event) => setMemberForm({ ...memberForm, address: event.target.value })} />
          </label>
          <label>
            메모
            <textarea value={memberForm.memo} onChange={(event) => setMemberForm({ ...memberForm, memo: event.target.value })} />
          </label>
          <label className="check-line">
            <input
              type="checkbox"
              checked={memberForm.sms_agree}
              onChange={(event) => setMemberForm({ ...memberForm, sms_agree: event.target.checked })}
            />
            문자 수신 동의
          </label>
          <button type="submit">회원 저장</button>
        </form>
      </div>
    );
  }

  function renderDeletedMembersModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="member-restore-title">
        <section className="form-panel modal-panel restore-panel">
          <div className="modal-title-row">
            <h2 id="member-restore-title">삭제 회원정보 복구</h2>
            <button type="button" className="secondary" onClick={() => setMemberRestoreOpen(false)}>
              닫기
            </button>
          </div>
          <input
            className="large-input"
            placeholder="삭제 회원 이름, 연락처, 메모를 입력하면 자동 검색됩니다"
            value={deletedMemberKeyword}
            onChange={(event) => setDeletedMemberKeyword(event.target.value)}
          />
          {filteredDeletedMembers.length === 0 ? (
            <p className="empty">삭제된 회원 정보가 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="member-table restore-table">
                <thead>
                  <tr>
                    <th>이름</th>
                    <th>연락처</th>
                    <th>생년월일</th>
                    <th>성별</th>
                    <th>메모</th>
                    <th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDeletedMembers.map((member) => (
                    <tr key={member.id}>
                      <td><strong>{member.name}</strong></td>
                      <td>{displayPhone(member.phone)}</td>
                      <td>{member.birth_date || "-"}</td>
                      <td>{member.gender || "-"}</td>
                      <td className="memo-cell">{member.memo || "-"}</td>
                      <td>
                        <div className="table-actions">
                          <button type="button" onClick={() => void handleMemberRestore(member)}>
                            복원
                          </button>
                          <button type="button" className="danger" onClick={() => void handleMemberPermanentDelete(member)}>
                            영구삭제
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderMemberSalesHistoryModal() {
    if (!memberHistoryTarget) return null;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="member-sales-history-title">
        <section className="form-panel modal-panel history-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="member-sales-history-title">매출 이력</h2>
              <p className="note-meta">
                {memberHistoryTarget.name} · {displayPhone(memberHistoryTarget.phone)}
              </p>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setMemberHistoryTarget(null);
                setMemberHistorySales([]);
              }}
            >
              닫기
            </button>
          </div>
          {memberHistorySales.length === 0 ? (
            <p className="empty">등록된 매출 이력이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>매출일</th>
                    <th>등록시각</th>
                    <th>상품명</th>
                    <th>결제수단</th>
                    <th>금액</th>
                    <th>상태</th>
                    <th>메모</th>
                  </tr>
                </thead>
                <tbody>
                  {memberHistorySales.map((sale) => (
                    <tr key={sale.id}>
                      <td>{sale.sale_date}</td>
                      <td>{formatDateTime(sale.created_at)}</td>
                      <td>{sale.sale_type}</td>
                      <td>{sale.payment_method}</td>
                      <td className="amount-cell">{money(sale.amount)}</td>
                      <td>{sale.status}</td>
                      <td className="memo-cell">{sale.note || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderMemberEditModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="member-edit-title">
        <form className="form-panel modal-panel" onSubmit={handleMemberUpdate}>
          <div className="modal-title-row">
            <h2 id="member-edit-title">회원 정보 수정</h2>
            <button type="button" className="secondary" onClick={() => setMemberEditOpen(false)}>
              닫기
            </button>
          </div>
          <label>
            이름 (필수)
            <input required value={memberEditForm.name} onChange={(event) => setMemberEditForm({ ...memberEditForm, name: event.target.value })} />
          </label>
          <label>
            휴대전화 (필수)
            <input
              required
              inputMode="numeric"
              placeholder="예: 010-1234-5678"
              value={memberEditForm.phone}
              onChange={(event) => setMemberEditForm({ ...memberEditForm, phone: event.target.value })}
            />
          </label>
          <div className="form-grid">
            <label>
              생년월일
              <input
                type="date"
                value={memberEditForm.birth_date}
                onChange={(event) => setMemberEditForm({ ...memberEditForm, birth_date: event.target.value })}
              />
            </label>
            <label>
              성별
              <select value={memberEditForm.gender} onChange={(event) => setMemberEditForm({ ...memberEditForm, gender: event.target.value })}>
                <option value="">선택 안함</option>
                <option value="남성">남성</option>
                <option value="여성">여성</option>
              </select>
            </label>
          </div>
          <label>
            이메일
            <input
              type="email"
              placeholder="예: screen-golf@example.com"
              value={memberEditForm.email}
              onChange={(event) => setMemberEditForm({ ...memberEditForm, email: event.target.value })}
            />
          </label>
          <label>
            주소
            <input value={memberEditForm.address} onChange={(event) => setMemberEditForm({ ...memberEditForm, address: event.target.value })} />
          </label>
          <label>
            메모
            <textarea value={memberEditForm.memo} onChange={(event) => setMemberEditForm({ ...memberEditForm, memo: event.target.value })} />
          </label>
          <label className="check-line">
            <input
              type="checkbox"
              checked={memberEditForm.sms_agree}
              onChange={(event) => setMemberEditForm({ ...memberEditForm, sms_agree: event.target.checked })}
            />
            문자 수신 동의
          </label>
          <button type="submit">수정 저장</button>
        </form>
      </div>
    );
  }

  function renderSaleNoteModal() {
    if (!saleNoteModal) return null;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sale-note-title">
        <section className="form-panel modal-panel note-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sale-note-title">매출 메모</h2>
              <p className="note-meta">
                {(saleNoteModal.member_name_snapshot || "비회원") + " · " + saleNoteModal.sale_type}
              </p>
            </div>
            <button type="button" className="secondary" onClick={() => setSaleNoteModal(null)}>
              닫기
            </button>
          </div>
          <div className="note-body">{saleNoteModal.note?.trim() || "입력된 메모가 없습니다."}</div>
        </section>
      </div>
    );
  }

  function renderMembershipPeriodModal() {
    if (!periodAdjustMembership) return null;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="membership-period-title">
        <form className="form-panel modal-panel" onSubmit={handleMembershipPeriodSubmit}>
          <div className="modal-title-row">
            <div>
              <h2 id="membership-period-title">유효기간 보정</h2>
              <p className="note-meta">
                {(periodAdjustMembership.member_name || `회원 ${periodAdjustMembership.member_id}`) +
                  " · " +
                  (periodAdjustMembership.product_name || periodAdjustMembership.product_type || "보유 상품")}
              </p>
            </div>
            <button type="button" className="secondary" onClick={() => setPeriodAdjustMembership(null)}>
              닫기
            </button>
          </div>
          <div className="form-grid">
            <label>
              시작일
              <input
                required
                type="date"
                value={periodAdjustForm.start_date}
                onChange={(event) => setPeriodAdjustForm({ ...periodAdjustForm, start_date: event.target.value })}
              />
            </label>
            <label>
              종료일
              <input
                type="date"
                value={periodAdjustForm.end_date}
                onChange={(event) => setPeriodAdjustForm({ ...periodAdjustForm, end_date: event.target.value })}
              />
            </label>
          </div>
          <label>
            메모
            <textarea value={periodAdjustForm.note} onChange={(event) => setPeriodAdjustForm({ ...periodAdjustForm, note: event.target.value })} />
          </label>
          <button type="submit">기간 보정 저장</button>
        </form>
      </div>
    );
  }

  function renderMembershipCountModal() {
    if (!countAdjustMembership) return null;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="membership-count-title">
        <form className="form-panel modal-panel count-panel" onSubmit={handleMembershipCountSubmit}>
          <div className="modal-title-row">
            <div>
              <h2 id="membership-count-title">남은 횟수 변경</h2>
              <p className="note-meta">
                {(countAdjustMembership.member_name || `회원 ${countAdjustMembership.member_id}`) +
                  " · " +
                  (countAdjustMembership.product_name || countAdjustMembership.product_type || "보유 상품")}
              </p>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setCountAdjustMembership(null);
                setCountAdjustForm(emptyMembershipCountForm);
              }}
            >
              닫기
            </button>
          </div>
          <label>
            남은 횟수
            <input
              required
              inputMode="numeric"
              value={countAdjustForm.remaining_count}
              onChange={(event) => setCountAdjustForm({ ...countAdjustForm, remaining_count: digitsOnly(event.target.value) })}
            />
          </label>
          <label>
            메모
            <textarea value={countAdjustForm.note} onChange={(event) => setCountAdjustForm({ ...countAdjustForm, note: event.target.value })} />
          </label>
          <div className="form-actions">
            {countAdjustMembership.status === "사용중" && (
              <button type="button" className="secondary" onClick={() => void deductCountFromModal()}>
                1회 차감
              </button>
            )}
            <button type="submit">남은 횟수 저장</button>
          </div>
        </form>
      </div>
    );
  }

  function renderMembershipHistoryModal() {
    if (!membershipHistoryTarget) return null;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="membership-history-title">
        <section className="form-panel modal-panel history-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="membership-history-title">이력</h2>
              <p className="note-meta">
                {(membershipHistoryTarget.member_name || `회원 ${membershipHistoryTarget.member_id}`) +
                  " · " +
                  (membershipHistoryTarget.product_name || membershipHistoryTarget.product_type || "보유 상품")}
              </p>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setMembershipHistoryTarget(null);
                setMembershipHistoryLogs([]);
              }}
            >
              닫기
            </button>
          </div>
          {membershipHistoryLogs.length === 0 ? (
            <p className="empty">등록된 이력이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>처리일시</th>
                    <th>구분</th>
                    <th>변경 횟수</th>
                    <th>보정 전</th>
                    <th>보정 후</th>
                    <th>메모</th>
                  </tr>
                </thead>
                <tbody>
                  {membershipHistoryLogs.map((log) => (
                    <tr key={log.id}>
                      <td>{formatDateTime(log.created_at)}</td>
                      <td>{log.action_type}</td>
                      <td>{log.change_count === null || log.change_count === undefined ? "-" : `${log.change_count}회`}</td>
                      <td>{log.before_remaining_count === null || log.before_remaining_count === undefined ? "-" : `${log.before_remaining_count}회`}</td>
                      <td>{log.after_remaining_count === null || log.after_remaining_count === undefined ? "-" : `${log.after_remaining_count}회`}</td>
                      <td className="memo-cell">{log.note || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderDashboardMembershipModal() {
    if (!dashboardMembershipModal) return null;
    const title =
      dashboardMembershipModal === "expiring"
        ? `${Number(dashboardExpiringDays || 7)}일 안에 만료`
        : `${Number(dashboardLowCount || 3)}회 이하 남음`;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="dashboard-membership-title">
        <section className="form-panel modal-panel history-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="dashboard-membership-title">{title}</h2>
              <p className="note-meta">{dashboardMembershipItems.length}건</p>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setDashboardMembershipModal(null);
                setDashboardMembershipItems([]);
              }}
            >
              닫기
            </button>
          </div>
          {dashboardMembershipItems.length === 0 ? (
            <p className="empty">해당하는 보유 상품이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>이름</th>
                    <th>연락처</th>
                    <th>상품명</th>
                    <th>시작일</th>
                    <th>종료일</th>
                    <th>남은 일수</th>
                    <th>남은 횟수</th>
                    <th>상태</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboardMembershipItems.map((item) => (
                    <tr key={item.id}>
                      <td>{item.member_name || `회원 ${item.member_id}`}</td>
                      <td>{displayPhone(item.member_phone)}</td>
                      <td>{item.product_name || item.product_type || "직접 등록"}</td>
                      <td>{item.start_date}</td>
                      <td>{item.end_date || "만료일 없음"}</td>
                      <td>{remainingDays(item.end_date) ?? "-"}</td>
                      <td>{item.remaining_count ?? "-"}</td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderDashboardNewMembersModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="dashboard-new-members-title">
        <section className="form-panel modal-panel history-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="dashboard-new-members-title">최근 {dashboardNewMemberDaysValue}일 신규 회원</h2>
              <p className="note-meta">{dashboardNewMemberItems.length}명</p>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setDashboardNewMembersOpen(false);
                setDashboardNewMemberItems([]);
              }}
            >
              닫기
            </button>
          </div>
          {dashboardNewMemberItems.length === 0 ? (
            <p className="empty">해당 기간에 등록된 신규 회원이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>이름</th>
                    <th>연락처</th>
                    <th>등록일시</th>
                    <th>메모</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboardNewMemberItems.map((member) => (
                    <tr key={member.id}>
                      <td>{member.name}</td>
                      <td>{displayPhone(member.phone)}</td>
                      <td>{formatDateTime(member.created_at)}</td>
                      <td className="memo-cell">{member.memo || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderDashboardSalesModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="dashboard-sales-title">
        <section className="form-panel modal-panel history-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="dashboard-sales-title">최근 {dashboardSalesDaysValue}일 매출</h2>
              <p className="note-meta">{money(dashboard?.today_sales)}</p>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setDashboardSalesOpen(false);
                setDashboardSalesItems([]);
              }}
            >
              닫기
            </button>
          </div>
          {dashboardSalesItems.length === 0 ? (
            <p className="empty">해당 기간에 등록된 매출이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>매출일</th>
                    <th>등록시각</th>
                    <th>회원</th>
                    <th>상품명</th>
                    <th>결제수단</th>
                    <th>금액</th>
                    <th>상태</th>
                    <th>메모</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboardSalesItems.map((sale) => (
                    <tr key={sale.id}>
                      <td>{sale.sale_date}</td>
                      <td>{formatDateTime(sale.created_at)}</td>
                      <td>{sale.member_name_snapshot || "비회원"}</td>
                      <td>{sale.sale_type}</td>
                      <td>{sale.payment_method}</td>
                      <td className="amount-cell">{money(sale.amount)}</td>
                      <td>{sale.status}</td>
                      <td className="memo-cell">{sale.note || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderProductModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="product-modal-title">
        <form className="form-panel modal-panel" onSubmit={handleProductSubmit}>
          <div className="modal-title-row">
            <h2 id="product-modal-title">{editingProduct ? "상품/요금 수정" : "상품/요금 등록"}</h2>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setProductModalOpen(false);
                setEditingProduct(null);
              }}
            >
              닫기
            </button>
          </div>
          <label>
            상품명 (필수)
            <input required value={productForm.name} onChange={(event) => setProductForm({ ...productForm, name: event.target.value })} />
          </label>
          <label>
            상품 종류 (필수)
            <select value={productForm.product_type} onChange={(event) => handleProductTypeChange(event.target.value as ProductForm["product_type"])}>
              <option value="기간제">기간제</option>
              <option value="횟수">횟수</option>
              <option value="판매">판매</option>
            </select>
          </label>
          {productForm.product_type !== "판매" && (
            <div className="form-grid">
              <label>
                유효 일수 (필수)
                <input
                  required
                  inputMode="numeric"
                  value={productForm.duration_days}
                  onChange={(event) => setProductForm({ ...productForm, duration_days: digitsOnly(event.target.value) })}
                />
              </label>
              {productForm.product_type === "횟수" && (
                <label>
                  횟수 입력 (필수)
                  <input
                    required
                    inputMode="numeric"
                    value={productForm.total_count}
                    onChange={(event) => setProductForm({ ...productForm, total_count: digitsOnly(event.target.value) })}
                  />
                </label>
              )}
            </div>
          )}
          <label>
            기본 판매가
            <input inputMode="numeric" value={productForm.price} onChange={(event) => setProductForm({ ...productForm, price: digitsOnly(event.target.value) })} />
          </label>
          <button type="submit">{editingProduct ? "수정 저장" : "상품 저장"}</button>
        </form>
      </div>
    );
  }

  function renderSaleEntryModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sale-entry-title">
        <form className="form-panel modal-panel" onSubmit={handleSaleSubmit}>
          <div className="modal-title-row">
            <h2 id="sale-entry-title">매출 등록</h2>
            <button type="button" className="secondary" onClick={closeSaleEntryModal}>
              닫기
            </button>
          </div>
          <div className="form-grid">
            <label>
              회원명
              <div className="member-autocomplete">
                <input
                  required={showMembershipFields}
                  autoComplete="off"
                  placeholder="이름을 입력하면 등록 회원이 바로 보입니다"
                  value={saleForm.member_name}
                  onChange={(event) => handleSaleMemberNameChange(event.target.value)}
                  onFocus={() => setSaleMemberInputFocused(true)}
                  onBlur={() => window.setTimeout(() => setSaleMemberInputFocused(false), 120)}
                />
                {showSaleMemberMatches && (
                  <div className="autocomplete-list" role="listbox" aria-label="회원 검색 결과">
                    {saleMemberMatches.map((member) => (
                      <button
                        key={member.id}
                        type="button"
                        className="autocomplete-item"
                        onMouseDown={(event) => {
                          event.preventDefault();
                          selectSaleMember(member);
                        }}
                      >
                        <strong>{member.name}</strong>
                        <span>{displayPhone(member.phone)}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </label>
            <label>
              휴대전화
              <input
                required={showMembershipFields}
                inputMode="numeric"
                placeholder="예: 010-1234-5678"
                value={saleForm.member_phone}
                onChange={(event) => handleSaleMemberPhoneChange(event.target.value)}
              />
            </label>
          </div>
          <p className="field-help">
            {saleForm.member_id
              ? `${saleForm.member_name} 회원을 선택했고 연락처를 자동 입력했습니다.`
              : requiresMemberDetails
                ? "기간제와 횟수 상품은 회원명과 휴대전화를 입력하면 회원을 자동 등록하고 보유 상품을 연결합니다."
                : "등록된 회원이 없으면 이름과 연락처를 그대로 입력하면 됩니다."}
          </p>
          <div className="form-grid">
            <label>
              상품명 (필수)
              <select required value={saleForm.product_id} onChange={(event) => handleSaleProductChange(event.target.value)}>
                <option value="">상품을 선택해 주세요</option>
                {activeSaleProducts.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} / {product.product_type} / {money(product.price)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              결제수단 (필수)
              <select value={saleForm.payment_method} onChange={(event) => setSaleForm({ ...saleForm, payment_method: event.target.value })}>
                <option>카드</option>
                <option>현금</option>
                <option>계좌이체</option>
                <option>기타</option>
              </select>
            </label>
          </div>
          <label>
            금액 (필수)
            <input
              required
              inputMode="numeric"
              value={saleForm.amount}
              onChange={(event) => setSaleForm({ ...saleForm, amount: digitsOnly(event.target.value) })}
            />
          </label>
          {showMembershipFields && (
            <div className="linked-fields">
              <p className="field-help linked-help">
                {selectedSaleProduct?.product_type} 상품입니다. 유효 일수 {selectedSaleProduct?.duration_days || 0}일 기준으로 종료일을 먼저 채우고,
                필요하면 종료일을 직접 바꿀 수 있습니다.
              </p>
              {selectedSaleProduct?.product_type === "기간제" && (
                <div className="form-grid">
                  <label>
                    시작일 (필수)
                    <input required type="date" value={saleForm.start_date} onChange={(event) => handleSaleStartDateChange(event.target.value)} />
                  </label>
                  <label>
                    종료일 (필수)
                    <input required type="date" value={saleForm.end_date} onChange={(event) => setSaleForm({ ...saleForm, end_date: event.target.value })} />
                  </label>
                </div>
              )}
              {selectedSaleProduct?.product_type === "횟수" && (
                <div className="form-grid">
                  <label>
                    시작일
                    <input type="date" value={saleForm.start_date} disabled />
                  </label>
                  <label>
                    종료일 (필수)
                    <input required type="date" value={saleForm.end_date} onChange={(event) => setSaleForm({ ...saleForm, end_date: event.target.value })} />
                  </label>
                  <label>
                    횟수 입력 (필수)
                    <input
                      required
                      inputMode="numeric"
                      value={saleForm.total_count}
                      onChange={(event) => setSaleForm({ ...saleForm, total_count: digitsOnly(event.target.value) })}
                    />
                  </label>
                </div>
              )}
            </div>
          )}
          <label>
            메모
            <textarea value={saleForm.note} onChange={(event) => setSaleForm({ ...saleForm, note: event.target.value })} />
          </label>
          <button type="submit">매출 저장</button>
        </form>
      </div>
    );
  }

  function renderReservations() {
    const reservationForSlot = (bayNumber: number, slot: string) =>
      activeReservationItems.find((reservation) => reservation.bay_number === bayNumber && reservationCoversSlot(reservation, slot));

    return (
      <section className="page-section reservations-page">
        <div className="page-title-row reservation-title-row">
          <button type="button" onClick={() => openReservationCreateModal(1, RESERVATION_OPEN_TIME)}>
            예약 등록
          </button>
          <button type="button" className="secondary" onClick={() => setReservationCanceledModalOpen(true)}>
            취소 이력 {reservationStats.canceled}건
          </button>
        </div>

        <section className="table-section reservation-control-panel">
          <div className="reservation-date-controls">
            <span className="reservation-count-pill">예약 {reservationStats.reserved}건</span>
            <input
              aria-label="예약 날짜"
              type="date"
              value={reservationDate}
              onChange={(event) => setReservationDate(event.target.value)}
            />
            <span className="reservation-date-display">{formatDateWithWeekday(reservationDate)}</span>
          </div>
        </section>

        <section className="table-section reservation-schedule-section">
          <div className="reservation-schedule-wrap">
            <div className="reservation-schedule-grid" style={{ gridTemplateColumns: `86px repeat(${RESERVATION_BAYS.length}, minmax(150px, 1fr))` }}>
              <div className="reservation-schedule-heading">시간</div>
              {RESERVATION_BAYS.map((bayNumber) => (
                <div key={bayNumber} className="reservation-schedule-heading">
                  {bayNumber}번 타석
                </div>
              ))}
              {reservationTimeSlots.map((slot) => (
                <Fragment key={slot}>
                  <div key={`${slot}-time`} className="reservation-time-cell">
                    {slot}
                  </div>
                  {RESERVATION_BAYS.map((bayNumber) => {
                    const reservation = reservationForSlot(bayNumber, slot);
                    const isStart = reservation ? reservationStartsAt(reservation, slot) : false;
                    return (
                      <button
                        key={`${slot}-${bayNumber}`}
                        type="button"
                        className={`reservation-slot ${reservation ? "occupied" : ""} ${
                          reservation ? `status-${reservation.status}` : ""
                        }`}
                        onClick={() => (reservation ? openReservationEditModal(reservation) : openReservationCreateModal(bayNumber, slot))}
                      >
                        {reservation ? (
                          isStart ? (
                            <span className="reservation-card-mini">
                              <strong>{reservation.customer_name}</strong>
                              <small>
                                {normalizeTimeValue(reservation.start_time)}-{normalizeTimeValue(reservation.end_time)} · {reservation.status}
                              </small>
                              {reservation.note?.trim() && <em>{reservation.note}</em>}
                            </span>
                          ) : (
                            <span className="reservation-continuation">예약중</span>
                          )
                        ) : (
                          <span className="reservation-empty">예약 가능</span>
                        )}
                      </button>
                    );
                  })}
                </Fragment>
              ))}
            </div>
          </div>
        </section>

      </section>
    );
  }

  function renderCanceledReservationsModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="canceled-reservations-title">
        <section className="form-panel modal-panel canceled-reservation-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="canceled-reservations-title">취소 이력</h2>
              <p className="note-meta">
                {reservationDate} 취소된 예약 {canceledReservationItems.length}건
              </p>
            </div>
            <button type="button" className="secondary" onClick={() => setReservationCanceledModalOpen(false)}>
              닫기
            </button>
          </div>
          {canceledReservationItems.length === 0 ? (
            <p className="empty">취소된 예약이 없습니다.</p>
          ) : (
            <div className="compact-list">
              {canceledReservationItems.map((reservation) => (
                <button
                  key={reservation.id}
                  type="button"
                  className="reservation-canceled-row"
                  onClick={() => {
                    setReservationCanceledModalOpen(false);
                    openReservationEditModal(reservation);
                  }}
                >
                  <strong>
                    {reservation.bay_number}번 타석 · {normalizeTimeValue(reservation.start_time)}-{normalizeTimeValue(reservation.end_time)}
                  </strong>
                  <span>
                    {reservation.customer_name} · {displayPhone(reservation.customer_phone)} · {reservation.note || "메모 없음"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderReservationModal() {
    const isCanceled = editingReservation?.status === "취소";
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="reservation-modal-title">
        <form className="form-panel modal-panel reservation-modal-panel" onSubmit={handleReservationSubmit}>
          <div className="modal-title-row">
            <div>
              <h2 id="reservation-modal-title">{editingReservation ? "예약 수정" : "예약 등록"}</h2>
              {editingReservation && <p className="note-meta">현재 상태: {editingReservation.status}</p>}
            </div>
            <button type="button" className="secondary" onClick={closeReservationModal}>
              닫기
            </button>
          </div>

          <div className="form-grid">
            <label>
              예약일
              <input
                required
                type="date"
                value={reservationForm.reservation_date}
                disabled={isCanceled}
                onChange={(event) => setReservationForm({ ...reservationForm, reservation_date: event.target.value })}
              />
            </label>
            <label>
              타석
              <select
                value={reservationForm.bay_number}
                disabled={isCanceled}
                onChange={(event) => setReservationForm({ ...reservationForm, bay_number: event.target.value })}
              >
                {RESERVATION_BAYS.map((bayNumber) => (
                  <option key={bayNumber} value={bayNumber}>
                    {bayNumber}번 타석
                  </option>
                ))}
              </select>
            </label>
            <label>
              시작 시간
              <input
                required
                type="time"
                step={RESERVATION_SLOT_MINUTES * 60}
                min={RESERVATION_OPEN_TIME}
                max={RESERVATION_CLOSE_TIME}
                value={reservationForm.start_time}
                disabled={isCanceled}
                onChange={(event) =>
                  setReservationForm({
                    ...reservationForm,
                    start_time: event.target.value,
                    end_time: addMinutesToTime(event.target.value, RESERVATION_SLOT_MINUTES)
                  })
                }
              />
            </label>
            <label>
              종료 시간
              <input
                required
                type="time"
                step={RESERVATION_SLOT_MINUTES * 60}
                min={RESERVATION_OPEN_TIME}
                max={RESERVATION_CLOSE_TIME}
                value={reservationForm.end_time}
                disabled={isCanceled}
                onChange={(event) => setReservationForm({ ...reservationForm, end_time: event.target.value })}
              />
            </label>
          </div>

          <label>
            예약자명
            <div className="member-autocomplete">
              <input
                required
                placeholder="회원명을 입력하면 등록 회원이 바로 보입니다"
                value={reservationForm.customer_name}
                disabled={isCanceled}
                onFocus={() => setReservationMemberInputFocused(true)}
                onBlur={() => window.setTimeout(() => setReservationMemberInputFocused(false), 120)}
                onChange={(event) => handleReservationNameChange(event.target.value)}
              />
              {showReservationMemberMatches && (
                <div className="autocomplete-list" role="listbox" aria-label="예약 회원 검색 결과">
                  {reservationMemberMatches.map((member) => (
                    <button
                      type="button"
                      className="autocomplete-item"
                      key={member.id}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        selectReservationMember(member);
                      }}
                    >
                      <strong>{member.name}</strong>
                      <span>{displayPhone(member.phone)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </label>
          <label>
            연락처
            <input
              required
              inputMode="tel"
              value={reservationForm.customer_phone}
              disabled={isCanceled}
              onChange={(event) => handleReservationPhoneChange(event.target.value)}
            />
          </label>
          <label>
            메모
            <textarea
              value={reservationForm.note}
              disabled={isCanceled}
              onChange={(event) => setReservationForm({ ...reservationForm, note: event.target.value })}
            />
          </label>

          <div className="form-actions reservation-modal-actions">
            {!isCanceled && <button type="submit">{editingReservation ? "예약 저장" : "예약 등록"}</button>}
            {editingReservation && !isCanceled && (
              <button type="button" className="danger" onClick={() => void cancelReservation(editingReservation)}>
                예약 취소
              </button>
            )}
          </div>
        </form>
      </div>
    );
  }

  function renderSales() {
    return (
      <section className="page-section">
        <div className="page-title-row">
          <button type="button" onClick={openSaleEntryModal}>
            매출 등록
          </button>
          <div className="sales-header-copy">
            <div className="section-title">
              <p>매출관리</p>
              <h1>최근 매출</h1>
            </div>
            <p className="sales-grid-help">
              최근 매출은 매출일이 아니라 화면에 저장된 시각 기준 최신 50건입니다. 아래 검색창은 입력 즉시 바로 반영됩니다.
            </p>
          </div>
        </div>
        <section className="table-section sales-grid-section">
          <div className="sales-grid-toolbar">
            <div className="search-row">
              <input
                className="large-input"
                placeholder="회원명, 연락처, 상품명, 메모, 결제수단을 입력하면 바로 찾습니다"
                value={salesKeyword}
                onChange={(event) => setSalesKeyword(event.target.value)}
              />
              <button type="button" className="secondary" onClick={() => setSalesKeyword("")}>
                지우기
              </button>
            </div>
            <label className="check-line filter-check-line">
              <input
                type="checkbox"
                checked={hideRefundSales}
                onChange={(event) => setHideRefundSales(event.target.checked)}
              />
              환불정보 미표기
            </label>
            <p className="sales-search-meta">최신 {sales.length}건 중 {filteredSales.length}건 표시</p>
          </div>
          <RecentSalesGrid items={filteredSales} onRefund={refundSale} onShowNote={setSaleNoteModal} />
        </section>
      </section>
    );
  }

  function renderSalesSummary() {
    return (
      <section className="page-section">
        <div className="summary-toolbar">
          <div className="range-buttons" aria-label="매출현황 기간 선택">
            {SALES_SUMMARY_RANGES.map((range) => (
              <button
                key={range}
                type="button"
                className={salesSummaryRange === range ? "active" : "secondary"}
                onClick={() => applySalesSummaryRange(range)}
              >
                {range}
              </button>
            ))}
          </div>
          <div className="summary-date-grid">
            <label>
              시작일
              <input type="date" value={salesSummaryFrom} onChange={(event) => setSalesSummaryFrom(event.target.value)} />
            </label>
            <label>
              종료일
              <input type="date" value={salesSummaryTo} onChange={(event) => handleSalesSummaryToChange(event.target.value)} />
            </label>
          </div>
        </div>

        <div className="metric-grid summary-metrics">
          <article className="metric summary-metric-card">
            <span>총 매출액</span>
            <strong>{money(salesSummary?.total_amount)}</strong>
            <button type="button" className="secondary metric-detail-button" onClick={() => void openSalesSummaryModal("totalAmount")}>
              상세 보기
            </button>
          </article>
          <article className="metric summary-metric-card">
            <span>매출 건수</span>
            <strong>{salesSummary?.total_count ?? 0}건</strong>
            <button type="button" className="secondary metric-detail-button" onClick={() => void openSalesSummaryModal("totalCount")}>
              상세 보기
            </button>
          </article>
        </div>

        <div className="summary-action-grid">
          <button type="button" className="summary-action-button" onClick={() => void openSalesSummaryModal("payment")}>
            <span className="summary-action-icon">결</span>
            <strong>결제 수단별 매출액</strong>
          </button>
          <button type="button" className="summary-action-button" onClick={() => void openSalesSummaryModal("product")}>
            <span className="summary-action-icon">상</span>
            <strong>상품별 매출액</strong>
          </button>
          <button type="button" className="summary-action-button" onClick={() => void openSalesSummaryModal("member")}>
            <span className="summary-action-icon">회</span>
            <strong>회원별 매출액</strong>
          </button>
          <button type="button" className="summary-action-button" onClick={() => void openSalesSummaryModal("day")}>
            <span className="summary-action-icon">일</span>
            <strong>기간 매출액</strong>
          </button>
        </div>
      </section>
    );
  }

  function renderSalesSummaryModal() {
    if (!salesSummaryModal) return null;
    const paymentItems = breakdownFromRecord(salesSummary?.by_payment_method || {});
    const productItems = breakdownFromRecord(salesSummary?.by_sale_type || {});
    const titles: Record<SalesSummaryModalKey, string> = {
      payment: "결제 수단별 매출액",
      product: "상품별 매출액",
      member: "회원별 매출액",
      day: "기간 매출액",
      totalAmount: "총 매출액 상세",
      totalCount: "매출 건수 상세",
    };
    const detailAmount = filteredSalesSummaryDetailItems.reduce((sum, sale) => sum + Number(sale.amount || 0), 0);
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sales-summary-modal-title">
        <section className="form-panel modal-panel summary-modal-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sales-summary-modal-title">{titles[salesSummaryModal]}</h2>
              <p className="note-meta">
                {salesSummaryFrom}부터 {salesSummaryTo}까지
              </p>
            </div>
            <button type="button" className="secondary" onClick={closeSalesSummaryModal}>
              닫기
            </button>
          </div>
          {(salesSummaryModal === "totalAmount" || salesSummaryModal === "totalCount") && (
            <div className="summary-detail-stack">
              <div className="search-row">
                <input
                  className="large-input"
                  placeholder="회원명, 연락처, 상품명, 메모, 결제수단을 입력하면 바로 찾습니다"
                  value={salesSummaryDetailKeyword}
                  onChange={(event) => setSalesSummaryDetailKeyword(event.target.value)}
                />
                <button type="button" className="secondary" onClick={() => setSalesSummaryDetailKeyword("")}>
                  지우기
                </button>
              </div>
              <label className="check-line filter-check-line">
                <input
                  type="checkbox"
                  checked={hideRefundSales}
                  onChange={(event) => setHideRefundSales(event.target.checked)}
                />
                환불정보 미표기
              </label>
              <p className="sales-search-meta">
                {salesSummaryModal === "totalAmount" && `검색 결과 ${filteredSalesSummaryDetailItems.length}건 · 합계 ${money(detailAmount)}`}
                {salesSummaryModal === "totalCount" && `검색 결과 ${filteredSalesSummaryDetailItems.length}건`}
              </p>
              {filteredSalesSummaryDetailItems.length === 0 ? (
                <p className="empty">조건에 맞는 매출이 없습니다.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>매출일</th>
                        <th>등록시각</th>
                        <th>회원</th>
                        <th>연락처</th>
                        <th>상품명</th>
                        <th>결제수단</th>
                        <th>금액</th>
                        <th>상태</th>
                        <th>메모</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSalesSummaryDetailItems.map((sale) => (
                        <tr key={sale.id}>
                          <td>{sale.sale_date}</td>
                          <td>{formatDateTime(sale.created_at)}</td>
                          <td>{sale.member_name_snapshot || "비회원"}</td>
                          <td>{displayPhone(sale.member_phone_snapshot)}</td>
                          <td>{sale.sale_type}</td>
                          <td>{sale.payment_method}</td>
                          <td className="amount-cell">{money(sale.amount)}</td>
                          <td>{sale.status}</td>
                          <td className="memo-cell">{sale.note || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
          {salesSummaryModal === "payment" && <PieChart items={paymentItems} />}
          {salesSummaryModal === "product" && <PieChart items={productItems} />}
          {salesSummaryModal === "member" && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>회원명</th>
                    <th>매출액</th>
                    <th>건수</th>
                  </tr>
                </thead>
                <tbody>
                  {(salesSummary?.by_member || []).map((item) => (
                    <tr key={item.label}>
                      <td>{item.label || "비회원"}</td>
                      <td className="amount-cell">{money(item.amount)}</td>
                      <td>{item.count}건</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {salesSummaryModal === "day" && <XYSalesChart items={salesSummary?.by_day || []} />}
        </section>
      </div>
    );
  }

  function renderMemberships() {
    return (
      <section className="page-section">
        <section className="membership-filter-panel" aria-label="보유 상품 상태 필터">
          <input
            className="large-input"
            placeholder="회원명, 연락처, 메모, 상품명을 입력하면 자동 검색됩니다"
            value={membershipKeyword}
            onChange={(event) => handleMembershipKeywordChange(event.target.value)}
          />
          <div className="status-filter-list">
            {MEMBERSHIP_STATUS_FILTERS.map((status) => (
              <label key={status} className="status-filter-chip">
                <input
                  type="checkbox"
                  checked={membershipStatusFilters.includes(status)}
                  onChange={() => toggleMembershipStatusFilter(status)}
                />
                {status} 목록
              </label>
            ))}
          </div>
        </section>
        {membershipResults.length === 0 ? (
          <p className="empty">선택한 상태의 보유 상품이 없습니다.</p>
        ) : (
          <section className="table-section membership-table-section">
            <div className="table-wrap">
              <table className="membership-table">
                <thead>
                  <tr>
                    <th>이름</th>
                    <th>메모</th>
                    <th>연락처</th>
                    <th>상품명</th>
                    <th>시작일</th>
                    <th>종료일</th>
                    <th>남은 일수</th>
                    <th>남은 횟수</th>
                    <th>상태</th>
                    <th>이력</th>
                  </tr>
                </thead>
                <tbody>
                  {membershipResults.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.member_name || `회원 ${item.member_id}`}</strong>
                      </td>
                      <td className="memo-cell">{item.member_memo || "-"}</td>
                      <td>{displayPhone(item.member_phone)}</td>
                      <td className="membership-product-cell">
                        <strong>{item.product_name || "직접 등록"}</strong>
                      </td>
                      <td className="membership-date-cell">
                        <input
                          className="table-date-input"
                          type="date"
                          value={item.start_date}
                          disabled={item.status === "환불"}
                          onChange={(event) => void updateMembershipPeriodInline(item, event.target.value, item.end_date || "")}
                        />
                      </td>
                      <td className="membership-date-cell">
                        <input
                          className="table-date-input"
                          type="date"
                          value={item.end_date || ""}
                          disabled={item.status === "환불"}
                          onChange={(event) => void updateMembershipPeriodInline(item, item.start_date, event.target.value)}
                        />
                      </td>
                      <td>{remainingDays(item.end_date) ?? "-"}</td>
                      <td className="membership-count-cell">
                        {item.remaining_count === null || item.remaining_count === undefined ? (
                          "-"
                        ) : item.status === "환불" ? (
                          <strong>{item.remaining_count}</strong>
                        ) : (
                          <button
                            type="button"
                            className="count-value-button"
                            onClick={() => openMembershipCountModal(item)}
                            aria-label={`${item.member_name || "회원"} 남은 횟수 변경`}
                          >
                            {item.remaining_count}
                          </button>
                        )}
                      </td>
                      <td className="membership-status-cell">
                        {item.status === "환불" ? (
                          <span className="status-chip inactive">환불</span>
                        ) : (
                          <div className="status-toggle">
                            <button
                              type="button"
                              className={item.status === "사용중" ? "active" : ""}
                              onClick={() => {
                                if (item.status !== "사용중") void changeMembershipStatus(item.id, "resume");
                              }}
                            >
                              사용중
                            </button>
                            <button
                              type="button"
                              className={item.status === "정지" ? "active" : ""}
                              onClick={() => {
                                if (item.status !== "정지") void changeMembershipStatus(item.id, "pause");
                              }}
                            >
                              일시정지
                            </button>
                          </div>
                        )}
                      </td>
                      <td>
                        <div className="table-actions membership-table-actions">
                          <button className="secondary" onClick={() => void openMembershipHistory(item)}>
                            보기
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
        {membershipTotalPages > 1 && (
          <div className="pagination" aria-label="보유 상품 페이지">
            {Array.from({ length: membershipTotalPages }, (_, index) => index + 1).map((page) => (
              <button
                key={page}
                type="button"
                className={membershipPage === page ? "active" : "secondary"}
                onClick={() => setMembershipPage(page)}
              >
                {page}
              </button>
            ))}
          </div>
        )}
      </section>
    );
  }

  function renderSmsPreviewModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-preview-title">
        <section className="form-panel modal-panel sms-preview-modal-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sms-preview-title">{smsSendStep === "target" ? "포함 회원 확인" : "발송 대상 미리보기"}</h2>
              <p className="note-meta">
                전체 {smsPreview?.summary.total_candidates || 0}명 · 발송 가능 {smsPreview?.summary.eligible_count || 0}명 ·
                차단 {smsPreview?.summary.blocked_count || 0}명
              </p>
            </div>
            <div className="modal-title-actions">
              {smsPreview && <strong>{smsPreview.summary.eligible_count}명 발송 가능</strong>}
              <button type="button" className="secondary" onClick={() => setSmsPreviewModalOpen(false)}>
                닫기
              </button>
            </div>
          </div>
          {smsPreview ? (
            <div className="summary-detail-stack">
              <div className="search-row">
                <input
                  className="large-input"
                  placeholder="이름, 연락처, 그룹명을 입력하면 바로 찾습니다"
                  value={smsPreviewKeyword}
                  onChange={(event) => setSmsPreviewKeyword(event.target.value)}
                />
                <button type="button" className="secondary" onClick={() => setSmsPreviewKeyword("")}>
                  지우기
                </button>
              </div>
              <div className="sms-preview-grid">
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>이름</th>
                        <th>연락처</th>
                        <th>포함 기준</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSmsPreviewEligible.map((item) => (
                        <tr key={smsRecipientKey(item)}>
                          <td>{item.recipient_name}</td>
                          <td>{displayPhone(item.phone)}</td>
                          <td className="memo-cell">{item.source_labels.join(", ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredSmsPreviewEligible.length === 0 && <p className="empty">발송 가능한 대상이 없습니다.</p>}
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>이름</th>
                        <th>연락처</th>
                        <th>차단 사유</th>
                        <th>포함 기준</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSmsPreviewBlocked.map((item) => (
                        <tr key={smsRecipientKey(item)}>
                          <td>{item.recipient_name}</td>
                          <td>{displayPhone(item.phone)}</td>
                          <td>{item.blocked_reason || "-"}</td>
                          <td className="memo-cell">{item.source_labels.join(", ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredSmsPreviewBlocked.length === 0 && <p className="empty">차단된 대상이 없습니다.</p>}
                </div>
              </div>
            </div>
          ) : (
            <p className="empty">대상 미리보기를 누르면 발송 가능/차단 대상을 바로 확인할 수 있습니다.</p>
          )}
        </section>
      </div>
    );
  }

  function renderSmsHistoryModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-history-title">
        <section className="form-panel modal-panel summary-modal-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sms-history-title">발송 이력</h2>
              <p className="note-meta">최근 50건 기준입니다. 총 {smsHistory.length}건</p>
            </div>
            <div className="table-actions">
              <button type="button" className="secondary" onClick={() => void handleSmsHistoryRefresh()}>
                새로고침
              </button>
              <button type="button" className="secondary" onClick={() => setSmsHistoryModalOpen(false)}>
                닫기
              </button>
            </div>
          </div>
          {smsHistory.length === 0 ? (
            <p className="empty">등록된 문자 발송 이력이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>등록시각</th>
                    <th>유형</th>
                    <th>대상</th>
                    <th>발송수</th>
                    <th>성공</th>
                    <th>실패</th>
                    <th>상태</th>
                    <th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {smsHistory.map((message) => (
                    <tr key={message.id}>
                      <td>{formatDateTime(message.created_at)}</td>
                      <td>
                        {message.content_type} / {message.message_type}
                      </td>
                      <td className="memo-cell">{smsTargetSummaryText(message.target_summary)}</td>
                      <td>{message.target_count}명</td>
                      <td>{message.success_count}명</td>
                      <td>{message.fail_count}명</td>
                      <td>{message.status}</td>
                      <td>
                        <div className="table-actions">
                          <button type="button" className="secondary" onClick={() => setSmsHistoryMessageTarget(message)}>
                            메시지
                          </button>
                          <button type="button" className="secondary" onClick={() => void openSmsHistoryDetail(message)}>
                            상세
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderSmsScheduleModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-schedule-title">
        <section className="form-panel modal-panel summary-modal-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sms-schedule-title">예약 발송 관리</h2>
              <p className="note-meta">예약중 또는 취소된 예약을 확인합니다. 발송 완료된 예약은 발송 이력으로 이동합니다.</p>
            </div>
            <div className="table-actions">
              <button type="button" className="secondary" onClick={() => void refreshSmsSchedules()}>
                새로고침
              </button>
              <button type="button" className="secondary" onClick={() => setSmsScheduleModalOpen(false)}>
                닫기
              </button>
            </div>
          </div>
          {smsSchedules.length === 0 ? (
            <p className="empty">등록된 문자 예약이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>예약시각</th>
                    <th>등록시각</th>
                    <th>유형</th>
                    <th>대상</th>
                    <th>예약수</th>
                    <th>상태</th>
                    <th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {smsSchedules.map((message) => (
                    <tr key={message.id}>
                      <td>{formatDateTime(message.scheduled_at)}</td>
                      <td>{formatDateTime(message.created_at)}</td>
                      <td>
                        {message.content_type} / {message.message_type}
                      </td>
                      <td className="memo-cell">{smsTargetSummaryText(message.target_summary)}</td>
                      <td>{message.target_count}명</td>
                      <td>
                        <span className={`status-chip ${message.status === "예약취소" ? "inactive" : "active"}`}>{message.status}</span>
                      </td>
                      <td>
                        <div className="table-actions">
                          <button type="button" className="secondary" onClick={() => setSmsHistoryMessageTarget(message)}>
                            메시지
                          </button>
                          <button type="button" className="secondary" onClick={() => void openSmsHistoryDetail(message)}>
                            대상
                          </button>
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => void openSmsScheduleEdit(message)}
                            disabled={message.status !== "예약"}
                          >
                            수정
                          </button>
                          <button
                            type="button"
                            className="danger"
                            onClick={() => void handleSmsScheduleDelete(message)}
                            disabled={message.status !== "예약"}
                          >
                            삭제
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderSms() {
    const smsTargetReady = hasSmsTargetSelection(smsComposeForm);
    const smsContentReady =
      smsComposeForm.content.trim().length > 0 &&
      (smsComposeForm.send_mode === "immediate" || Boolean(smsComposeForm.scheduled_at));
    const currentStepIndex = SMS_SEND_STEPS.findIndex((step) => step.key === smsSendStep);
    const excludedCount =
      smsPreview?.eligible_recipients.filter((item) => smsExcludedRecipients.includes(smsRecipientKey(item))).length || 0;
    const activeEligibleCount = (smsPreview?.eligible_recipients.length || 0) - excludedCount;
    const selectedGroupNames = smsGroups
      .filter((group) => smsComposeForm.group_ids.includes(String(group.id)))
      .map((group) => group.name);
    const isEditingSchedule = Boolean(smsEditingSchedule);
    const isScheduledMode = smsComposeForm.send_mode === "scheduled";
    const smsReviewActionLabel = isScheduledMode ? (isEditingSchedule ? "예약 수정" : "예약 등록") : "문자 발송";
    const smsDoneActionLabel =
      smsLastSentMessage?.status === "예약" || smsLastSentMessage?.status === "예약취소" ? "예약 목록 보기" : "발송 이력 보기";

    function smsStepDisabled(step: SmsSendStep) {
      if (step === "content") return !smsTargetReady;
      if (step === "review") return !smsTargetReady || !smsContentReady;
      if (step === "done") return !smsLastSentMessage;
      return false;
    }

    function handleSmsStepClick(step: SmsSendStep) {
      if (step === "target") {
        setSmsSendStep("target");
      } else if (step === "content") {
        moveToSmsContentStep();
      } else if (step === "review") {
        moveToSmsReviewStep();
      } else if (smsLastSentMessage) {
        setSmsSendStep("done");
      }
    }

    return (
      <section className="page-section sms-page">
        <div className="page-title-row sms-toolbar">
          <button type="button" onClick={openSmsGroupCreateModal}>
            그룹 생성
          </button>
          <button type="button" className="secondary" onClick={openSmsTemplateCreateModal}>
            템플릿 등록
          </button>
          <button type="button" className="secondary" onClick={() => void openSmsScheduleModal()}>
            예약 발송 관리 {smsSchedules.length}건
          </button>
          <button type="button" className="secondary" onClick={openSmsMonthlyBillingModal}>
            월별 청구금액
          </button>
          <button type="button" className="secondary" onClick={() => void openSmsHistoryModal()}>
            발송 이력 {smsHistory.length}건
          </button>
        </div>

        <nav className="sms-step-nav" aria-label="문자 발송 단계">
          {SMS_SEND_STEPS.map((step, index) => {
            const isActive = smsSendStep === step.key;
            const isComplete = index < currentStepIndex;
            return (
              <button
                key={step.key}
                type="button"
                className={["sms-step-button", isActive ? "active" : "", isComplete ? "complete" : ""].filter(Boolean).join(" ")}
                disabled={smsStepDisabled(step.key)}
                aria-current={isActive ? "step" : undefined}
                onClick={() => handleSmsStepClick(step.key)}
              >
                <span>{index + 1}</span>
                {step.label}
              </button>
            );
          })}
          <button type="button" className="sms-step-button sms-step-reset-button" onClick={resetSmsSendFlow}>
            처음부터
          </button>
        </nav>

        {smsSendStep === "target" && (
          <div className="sms-step-layout">
            <article className="form-panel sms-flow-panel sms-target-panel">
              <div className="modal-title-row">
                <div>
                  <h2>받는 사람</h2>
                  <p className="note-meta">
                    {isEditingSchedule
                      ? "예약 수정 중입니다. 대상 조건을 바꾸지 않으면 예약 당시 확정된 대상이 유지됩니다."
                      : "전체 회원, 만료 예정, 그룹을 합쳐서 중복 없이 발송합니다."}
                  </p>
                </div>
                <button type="button" className="secondary" onClick={() => void refreshSmsDataAndClearTarget()}>
                  새로고침
                </button>
              </div>
              <div className="sms-target-grid">
                <label className="sms-check-card">
                  <span>
                    <input
                      type="checkbox"
                      checked={smsComposeForm.include_all_members}
                      onChange={(event) => setSmsComposeForm({ ...smsComposeForm, include_all_members: event.target.checked })}
                    />
                    전체 회원
                  </span>
                  <small>활성 회원 전체</small>
                </label>
                <label className="sms-check-card">
                  <span>
                    <input
                      type="checkbox"
                      checked={smsComposeForm.include_expiring_memberships}
                      onChange={(event) =>
                        setSmsComposeForm({ ...smsComposeForm, include_expiring_memberships: event.target.checked })
                      }
                    />
                    기간제 만료 예정
                  </span>
                  <div className="inline-number-field">
                    <input
                      inputMode="numeric"
                      value={smsComposeForm.expiring_days}
                      onChange={(event) => setSmsComposeForm({ ...smsComposeForm, expiring_days: digitsOnly(event.target.value) })}
                    />
                    <small>일 안에 만료</small>
                  </div>
                </label>
                <label className="sms-check-card">
                  <span>
                    <input
                      type="checkbox"
                      checked={smsComposeForm.include_low_remaining_memberships}
                      onChange={(event) =>
                        setSmsComposeForm({ ...smsComposeForm, include_low_remaining_memberships: event.target.checked })
                      }
                    />
                    횟수 만료 예정
                  </span>
                  <div className="inline-number-field">
                    <input
                      inputMode="numeric"
                      value={smsComposeForm.low_remaining_count}
                      onChange={(event) =>
                        setSmsComposeForm({ ...smsComposeForm, low_remaining_count: digitsOnly(event.target.value) })
                      }
                    />
                    <small>회 이하 남음</small>
                  </div>
                </label>
                <label className="sms-check-card">
                  <span>
                    <input
                      type="checkbox"
                      checked={smsComposeForm.include_birthdays}
                      onChange={(event) => setSmsComposeForm({ ...smsComposeForm, include_birthdays: event.target.checked })}
                    />
                    생일자
                  </span>
                  <div className="inline-number-field">
                    <input
                      inputMode="numeric"
                      value={smsComposeForm.birthday_days}
                      onChange={(event) => setSmsComposeForm({ ...smsComposeForm, birthday_days: digitsOnly(event.target.value) })}
                    />
                    <small>일 안에 생일</small>
                  </div>
                </label>
              </div>
              <div className="sms-group-select-panel">
                <div className="sms-member-transfer-heading">
                  <span>그룹 선택</span>
                  <small>{smsComposeForm.group_ids.length}개 선택</small>
                </div>
                {smsGroups.length === 0 ? (
                  <p className="empty">등록된 문자 그룹이 없습니다.</p>
                ) : (
                  <div className="sms-group-choice-list">
                    {smsGroups.map((group) => {
                      const groupId = String(group.id);
                      const selected = smsComposeForm.group_ids.includes(groupId);
                      return (
                        <div key={group.id} className={`sms-group-choice ${selected ? "selected" : ""}`}>
                          <label className="sms-group-choice-main">
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() =>
                                setSmsComposeForm((current) => ({
                                  ...current,
                                  group_ids: selected
                                    ? current.group_ids.filter((item) => item !== groupId)
                                    : [...current.group_ids, groupId]
                                }))
                              }
                            />
                            <span>
                              <strong>{group.name}</strong>
                              <small>
                                {group.member_count}명 · {selected ? "선택됨" : "선택 안됨"}
                              </small>
                              <small className="sms-group-choice-description">{group.description || "설명 없음"}</small>
                            </span>
                          </label>
                          <div className="sms-group-choice-actions">
                            <button type="button" className="secondary" onClick={() => openSmsGroupEditModal(group)}>
                              수정
                            </button>
                            <button type="button" className="danger" onClick={() => openSmsGroupDeleteModal(group)}>
                              삭제
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="sms-flow-summary">
                <span>{smsTargetReady ? "대상 조건 선택됨" : "대상 조건을 선택해 주세요"}</span>
                <span>선택 그룹: {selectedGroupNames.length ? selectedGroupNames.join(", ") : "없음"}</span>
              </div>
            </article>
            <aside className="sms-side-actions" aria-label="받는 사람 단계 이동">
              <button type="button" className="secondary" onClick={() => void handleSmsTargetPreview()} disabled={!smsTargetReady}>
                포함 회원 확인
              </button>
              <button type="button" onClick={moveToSmsContentStep} disabled={!smsTargetReady}>
                다음: 내용 입력
              </button>
            </aside>
          </div>
        )}

        {smsSendStep === "content" && (
          <div className="sms-step-layout">
            <article className="form-panel sms-flow-panel sms-compose-panel">
              <div className="modal-title-row">
                <div>
                  <h2>내용 입력</h2>
                  <p className="note-meta">
                    광고용은 문자 수신 동의 회원만 발송 대상에 포함됩니다.
                    {isEditingSchedule && " 예약 시각과 내용은 여기서 함께 수정합니다."}
                  </p>
                </div>
              </div>
              <div className="form-grid">
                <label>
                  문자 유형
                  <select
                    value={smsComposeForm.content_type}
                    onChange={(event) =>
                      setSmsComposeForm({ ...smsComposeForm, content_type: event.target.value as SmsContentType })
                    }
                  >
                    <option value="COMM">일반용</option>
                    <option value="AD">광고용</option>
                  </select>
                </label>
                <label>
                  발송 방식
                  <select
                    value={smsComposeForm.send_mode}
                    onChange={(event) =>
                      setSmsComposeForm({ ...smsComposeForm, send_mode: event.target.value as SmsDispatchMode })
                    }
                  >
                    <option value="immediate">즉시 발송</option>
                    <option value="scheduled">예약 발송</option>
                  </select>
                </label>
                <label>
                  템플릿
                  <select value={smsComposeForm.template_id} onChange={(event) => applySmsTemplate(event.target.value)}>
                    <option value="">템플릿 선택 안함</option>
                    {smsTemplates
                      .filter((template) => template.is_active)
                      .map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.title}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              {smsComposeForm.send_mode === "scheduled" && (
                <label>
                  예약 발송 시각
                  <input
                    type="datetime-local"
                    value={smsComposeForm.scheduled_at}
                    onChange={(event) => setSmsComposeForm({ ...smsComposeForm, scheduled_at: event.target.value })}
                  />
                </label>
              )}
              <label>
                제목
                <input
                  value={smsComposeForm.title}
                  onChange={(event) => setSmsComposeForm({ ...smsComposeForm, title: event.target.value })}
                  placeholder="LMS로 보낼 때 제목을 입력합니다"
                />
              </label>
              <label className="sms-compose-content-field">
                <span className="sms-compose-content-header">
                  <span>본문</span>
                  {renderAiAssistButton()}
                </span>
                <textarea
                  className="sms-compose-content-input"
                  value={smsComposeForm.content}
                  onChange={(event) => setSmsComposeForm({ ...smsComposeForm, content: event.target.value })}
                  placeholder="발송할 문자 내용을 입력해 주세요"
                />
              </label>
            </article>
            <aside className="sms-side-actions" aria-label="내용 입력 단계 이동">
              <button type="button" className="secondary" onClick={() => setSmsSendStep("target")}>
                이전: 받는 사람
              </button>
              <button type="button" onClick={() => void handleSmsPreview()} disabled={!smsContentReady}>
                다음: 확인
              </button>
            </aside>
          </div>
        )}

        {smsSendStep === "review" && (
          <div className="sms-step-layout">
            <article className="form-panel sms-flow-panel sms-review-panel">
              <div className="modal-title-row">
                <div>
                  <h2>확인</h2>
                  <p className="note-meta">
                    전체 {smsPreview?.summary.total_candidates || 0}명 · 발송 가능 {smsPreview?.summary.eligible_count || 0}명 ·
                    차단 {smsPreview?.summary.blocked_count || 0}명 · 제외 {excludedCount}명
                  </p>
                </div>
                {smsPreview && <strong>{activeEligibleCount}명 최종 {isScheduledMode ? "예약" : "발송"}</strong>}
              </div>
              {smsPreview ? (
                <div className="summary-detail-stack">
                  {smsPreviewMode === "scheduleSnapshot" && (
                    <p className="note-meta">대상 조건이 바뀌지 않아 예약 당시 확정된 수신자 snapshot을 그대로 보여주고 있습니다.</p>
                  )}
                  <div className="search-row">
                    <input
                      className="large-input"
                      placeholder="이름, 연락처, 그룹명을 입력하면 바로 찾습니다"
                      value={smsPreviewKeyword}
                      onChange={(event) => setSmsPreviewKeyword(event.target.value)}
                    />
                    <button type="button" className="secondary" onClick={() => setSmsPreviewKeyword("")}>
                      지우기
                    </button>
                  </div>
                  <div className="sms-preview-grid">
                    <div className="sms-preview-column">
                      <div className="sms-preview-heading">
                        <strong>발송 가능</strong>
                        <span>{filteredSmsPreviewEligible.length}명</span>
                      </div>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>제외</th>
                              <th>이름</th>
                              <th>연락처</th>
                              <th>포함 기준</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredSmsPreviewEligible.map((item) => (
                              <tr key={smsRecipientKey(item)}>
                                <td>
                                  <input
                                    type="checkbox"
                                    checked={smsExcludedRecipients.includes(smsRecipientKey(item))}
                                    onChange={() => toggleSmsRecipientExclusion(item)}
                                  />
                                </td>
                                <td>{item.recipient_name}</td>
                                <td>{displayPhone(item.phone)}</td>
                                <td className="memo-cell">{item.source_labels.join(", ")}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {filteredSmsPreviewEligible.length === 0 && <p className="empty">발송 가능한 대상이 없습니다.</p>}
                      </div>
                    </div>
                    <div className="sms-preview-column">
                      <div className="sms-preview-heading">
                        <strong>차단</strong>
                        <span>{filteredSmsPreviewBlocked.length}명</span>
                      </div>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>이름</th>
                              <th>연락처</th>
                              <th>차단 사유</th>
                              <th>포함 기준</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredSmsPreviewBlocked.map((item) => (
                              <tr key={smsRecipientKey(item)}>
                                <td>{item.recipient_name}</td>
                                <td>{displayPhone(item.phone)}</td>
                                <td>{item.blocked_reason || "-"}</td>
                                <td className="memo-cell">{item.source_labels.join(", ")}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {filteredSmsPreviewBlocked.length === 0 && <p className="empty">차단된 대상이 없습니다.</p>}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="empty">대상 확인을 다시 실행해 주세요.</p>
              )}
            </article>
            <aside className="sms-side-actions" aria-label="확인 단계 이동">
              <button type="button" className="secondary" onClick={() => setSmsSendStep("content")}>
                이전: 내용 입력
              </button>
              <button type="button" className="secondary" onClick={() => void handleSmsPreview()}>
                대상 다시 확인
              </button>
              <button type="button" onClick={() => void handleSmsSend()} disabled={!smsPreview || activeEligibleCount <= 0}>
                {smsReviewActionLabel}
              </button>
            </aside>
          </div>
        )}

        {smsSendStep === "done" && (
          <div className="sms-step-layout">
            <article className="form-panel sms-flow-panel sms-result-panel">
              <div className="modal-title-row">
                <div>
                  <h2>결과</h2>
                  <p className="note-meta">
                    {smsLastSentMessage?.status === "예약"
                      ? "예약이 저장되었습니다. 발송 전까지 예약 발송 관리에서 확인, 수정, 삭제할 수 있습니다."
                      : "상태는 자동으로 다시 확인하며, 아래에서 보낸 메시지와 수신자별 결과를 바로 볼 수 있습니다."}
                  </p>
                </div>
                {smsLastSentMessage && (
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => void refreshSmsLastSentResult(undefined, true)}
                    disabled={smsLastSentDetailLoading}
                  >
                    {smsLastSentDetailLoading ? "불러오는 중..." : "결과 새로고침"}
                  </button>
                )}
              </div>
              {smsLastSentMessage ? (
                <>
                  <div className="sms-result-grid">
                    <div>
                      <span>상태</span>
                      <strong className={`status-chip ${smsLastSentMessage.status === "실패" ? "inactive" : "active"}`}>
                        {smsLastSentMessage.status}
                      </strong>
                    </div>
                    <div>
                      <span>발송 대상</span>
                      <strong>{smsLastSentMessage.target_count}명</strong>
                    </div>
                    <div>
                      <span>성공</span>
                      <strong>{smsLastSentMessage.success_count}명</strong>
                    </div>
                    <div>
                      <span>실패</span>
                      <strong>{smsLastSentMessage.fail_count}명</strong>
                    </div>
                  </div>

                  <div className="sms-history-message-meta">
                    <span>
                      {formatDateTime(smsLastSentMessage.created_at)} · {smsLastSentMessage.content_type} / {smsLastSentMessage.message_type} ·{" "}
                      {smsLastSentMessage.target_count}명
                    </span>
                    {smsLastSentMessage.scheduled_at && <span>예약 시각: {formatDateTime(smsLastSentMessage.scheduled_at)}</span>}
                    <span>발송 대상: {smsTargetSummaryText(smsLastSentMessage.target_summary)}</span>
                    {smsLastSentMessage.sync_completed_at && <span>최종 확인: {formatDateTime(smsLastSentMessage.sync_completed_at)}</span>}
                  </div>

                  <div className="sms-result-section">
                    <div className="sms-preview-heading">
                      <strong>보낸 메시지</strong>
                    </div>
                    <div className="sms-result-message-card">
                      <div className="sms-flow-summary">
                        <span>제목: {smsLastSentMessage.title || "제목 없음"}</span>
                      </div>
                      <pre className="sms-history-message-content">{smsLastSentMessage.content}</pre>
                    </div>
                  </div>

                  <div className="sms-result-section">
                    <div className="sms-preview-heading">
                      <strong>상세 결과</strong>
                      <span>{smsLastSentDetailItems.length}건</span>
                    </div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>이름</th>
                            <th>연락처</th>
                            <th>상태</th>
                            <th>실패 코드</th>
                            <th>실패 사유</th>
                          </tr>
                        </thead>
                        <tbody>
                          {smsLastSentDetailItems.map((item) => (
                            <tr key={item.id}>
                              <td>{item.recipient_name || item.member_name || "-"}</td>
                              <td>{displayPhone(item.phone)}</td>
                              <td>{item.status}</td>
                              <td>{item.fail_code || "-"}</td>
                              <td className="memo-cell">{item.fail_reason || "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {smsLastSentDetailItems.length === 0 && (
                        <p className="empty">
                          {smsLastSentDetailLoading ? "상세 결과를 불러오는 중입니다." : "상세 결과가 아직 없습니다. 잠시 후 다시 확인해 주세요."}
                        </p>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <p className="empty">아직 발송 결과가 없습니다.</p>
              )}
            </article>
            <aside className="sms-side-actions" aria-label="결과 단계 이동">
              <button type="button" onClick={resetSmsSendFlow}>
                {smsLastSentMessage?.status === "예약" ? "새 예약 등록" : "새 문자 발송"}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => void (smsLastSentMessage?.status === "예약" ? openSmsScheduleModal() : openSmsHistoryModal())}
              >
                {smsDoneActionLabel}
              </button>
            </aside>
          </div>
        )}
      </section>
    );
  }

  function renderSmsGroupModal() {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-group-title">
        <form className="form-panel modal-panel sms-member-select-panel" onSubmit={handleSmsGroupSubmit}>
          <div className="modal-title-row">
            <div>
              <h2 id="sms-group-title">{smsEditingGroup ? "문자 그룹 수정" : "문자 그룹 생성"}</h2>
              <p className="note-meta">활성 회원만 그룹에 넣을 수 있습니다.</p>
            </div>
            <button type="button" className="secondary" onClick={closeSmsGroupModal}>
              닫기
            </button>
          </div>
          <label>
            그룹명
            <input value={smsGroupForm.name} onChange={(event) => setSmsGroupForm({ ...smsGroupForm, name: event.target.value })} />
          </label>
          <label>
            설명
            <input
              value={smsGroupForm.description}
              onChange={(event) => setSmsGroupForm({ ...smsGroupForm, description: event.target.value })}
            />
          </label>
          <label>
            회원 검색
            <input
              className="large-input"
              placeholder="이름, 연락처, 메모로 찾습니다"
              value={smsGroupMemberKeyword}
              onChange={(event) => {
                setSmsGroupMemberKeyword(event.target.value);
                setSmsGroupAvailableSelection([]);
              }}
            />
          </label>
          <div className="sms-member-transfer-grid">
            <label className="sms-member-transfer-column">
              <span className="sms-member-transfer-heading">
                <span>회원 목록</span>
                <small>{smsGroupAvailableMembers.length}명</small>
              </span>
              <select
                multiple
                size={14}
                value={smsGroupAvailableSelection}
                onChange={(event) => setSmsGroupAvailableSelection(selectedValues(event))}
              >
                {smsGroupAvailableMembers.map((member) => (
                  <option key={member.id} value={String(member.id)}>
                    {smsMemberOptionLabel(member)}
                  </option>
                ))}
              </select>
            </label>
            <div className="sms-member-transfer-actions" aria-label="그룹 회원 이동">
              <button
                type="button"
                className="secondary"
                onClick={addSmsGroupMembers}
                disabled={smsGroupAvailableSelection.length === 0}
                aria-label="선택 회원 추가"
              >
                →
              </button>
              <button
                type="button"
                className="secondary"
                onClick={removeSmsGroupMembers}
                disabled={smsGroupSelectedSelection.length === 0}
                aria-label="선택 회원 제거"
              >
                ←
              </button>
            </div>
            <label className="sms-member-transfer-column">
              <span className="sms-member-transfer-heading">
                <span>그룹 회원</span>
                <small>{smsGroupForm.member_ids.length}명</small>
              </span>
              <select
                multiple
                size={14}
                value={smsGroupSelectedSelection}
                onChange={(event) => setSmsGroupSelectedSelection(selectedValues(event))}
              >
                {smsGroupSelectedMembers.map((member) => (
                  <option key={member.id} value={String(member.id)}>
                    {smsMemberOptionLabel(member)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="sales-search-meta">선택 {smsGroupForm.member_ids.length}명</p>
          <button type="submit">{smsEditingGroup ? "그룹 수정" : "그룹 저장"}</button>
        </form>
      </div>
    );
  }

  function renderSmsGroupDeleteModal() {
    if (!smsDeleteGroupTarget) return null;
    const memberLookup = new Map(smsMemberOptions.map((member) => [member.id, member]));
    const deleteTargetMembers = smsDeleteGroupTarget.member_ids
      .map((memberId) => memberLookup.get(memberId) || null)
      .filter((member): member is Member => member !== null);

    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-group-delete-title">
        <section className="form-panel modal-panel sms-group-delete-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sms-group-delete-title">문자 그룹 삭제</h2>
              <p className="note-meta">아래 정보를 확인한 뒤 삭제합니다. 삭제 후에는 복구할 수 없습니다.</p>
            </div>
            <button type="button" className="secondary" onClick={closeSmsGroupDeleteModal}>
              닫기
            </button>
          </div>
          <div className="sms-group-delete-summary">
            <div>
              <span>그룹명</span>
              <strong>{smsDeleteGroupTarget.name}</strong>
            </div>
            <div>
              <span>설명</span>
              <strong>{smsDeleteGroupTarget.description || "-"}</strong>
            </div>
            <div>
              <span>회원 수</span>
              <strong>{smsDeleteGroupTarget.member_count}명</strong>
            </div>
          </div>
          <section className="sms-group-delete-members" aria-label="삭제 대상 그룹 회원">
            <div className="sms-member-transfer-heading">
              <span>포함 회원</span>
              <small>{smsDeleteGroupTarget.member_count}명</small>
            </div>
            {deleteTargetMembers.length > 0 ? (
              <div className="sms-group-delete-member-list">
                {deleteTargetMembers.map((member) => (
                  <span key={member.id} className="sms-group-delete-member">
                    {smsMemberOptionLabel(member)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="empty">현재 불러온 활성 회원 목록에서 확인 가능한 회원이 없습니다.</p>
            )}
          </section>
          <div className="form-actions sms-group-delete-actions">
            <button type="button" className="secondary" onClick={closeSmsGroupDeleteModal}>
              취소
            </button>
            <button type="button" className="danger" onClick={() => void handleSmsGroupDelete()}>
              그룹 삭제
            </button>
          </div>
        </section>
      </div>
    );
  }

  function renderSmsTemplateModal() {
    const activeTemplateCount = smsTemplates.filter((template) => template.is_active).length;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-template-title">
        <form className="form-panel modal-panel sms-template-modal-panel" onSubmit={handleSmsTemplateSubmit}>
          <div className="modal-title-row">
            <div>
              <h2 id="sms-template-title">{smsEditingTemplate ? "문자 템플릿 수정" : "문자 템플릿 등록"}</h2>
              <p className="note-meta">저장 후 작성 화면에서 바로 불러올 수 있습니다.</p>
            </div>
            <div className="modal-title-actions">
              {smsEditingTemplate && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setSmsEditingTemplate(null);
                    setSmsTemplateForm(emptySmsTemplateForm);
                  }}
                >
                  새 템플릿
                </button>
              )}
              <button type="button" className="secondary" onClick={() => setSmsTemplateModalOpen(false)}>
                닫기
              </button>
            </div>
          </div>
          <label>
            제목
            <input
              value={smsTemplateForm.title}
              onChange={(event) => setSmsTemplateForm({ ...smsTemplateForm, title: event.target.value })}
            />
          </label>
          <label className="sms-compose-content-field">
            <span className="sms-compose-content-header">
              <span>내용</span>
              {renderAiAssistButton()}
            </span>
            <textarea
              className="sms-template-content-input"
              value={smsTemplateForm.content}
              onChange={(event) => setSmsTemplateForm({ ...smsTemplateForm, content: event.target.value })}
            />
          </label>
          <label className="check-line">
            <input
              type="checkbox"
              checked={smsTemplateForm.is_active}
              onChange={(event) => setSmsTemplateForm({ ...smsTemplateForm, is_active: event.target.checked })}
            />
            템플릿 사용
          </label>
          <button type="submit">{smsEditingTemplate ? "템플릿 수정" : "템플릿 저장"}</button>
          <section className="sms-template-manage-section" aria-label="기존 문자 템플릿">
            <div className="sms-member-transfer-heading">
              <span>기존 템플릿</span>
              <small>
                전체 {smsTemplates.length}개 · 사용 {activeTemplateCount}개
              </small>
            </div>
            {smsTemplates.length === 0 ? (
              <p className="empty">등록된 문자 템플릿이 없습니다.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>상태</th>
                      <th>제목</th>
                      <th>내용</th>
                      <th>관리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {smsTemplates.map((template) => (
                      <tr key={template.id}>
                        <td>
                          <span className={`status-chip ${template.is_active ? "active" : "inactive"}`}>
                            {template.is_active ? "사용" : "제외"}
                          </span>
                        </td>
                        <td>{template.title}</td>
                        <td className="memo-cell">{template.content}</td>
                        <td>
                          <div className="table-actions">
                            <button type="button" className="secondary" onClick={() => openSmsTemplateEditModal(template)}>
                              수정
                            </button>
                            <button type="button" className="danger" onClick={() => void handleSmsTemplateDelete(template)}>
                              삭제
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </form>
      </div>
    );
  }

  function renderSmsMonthlyBillingModal() {
    const billing = smsMonthlyBilling;
    const currencyCode = billing?.currency_code || "KRW";
    const hasMatchedItems = (billing?.matched_items.length || 0) > 0;
    const billingMonthLabel = formatBillingMonth(billing?.month || billingMonthQueryValue(smsMonthlyBillingMonth));

    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-monthly-billing-title">
        <section className="form-panel modal-panel sms-billing-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sms-monthly-billing-title">월별 청구금액</h2>
              <p className="note-meta">NAVER Cloud Billing API 기준 문자 서비스 월 청구 항목입니다.</p>
            </div>
            <div className="modal-title-actions">
              <button type="button" className="secondary" onClick={() => void loadSmsMonthlyBilling()}>
                조회
              </button>
              <button type="button" className="secondary" onClick={closeSmsMonthlyBillingModal}>
                닫기
              </button>
            </div>
          </div>

          <div className="sms-billing-toolbar">
            <label className="sms-billing-month-field">
              <span>조회 월</span>
              <input
                type="month"
                value={normalizeMonthValue(smsMonthlyBillingMonth)}
                onChange={(event) => setSmsMonthlyBillingMonth(event.target.value)}
              />
            </label>
          </div>

          {smsMonthlyBillingStatus === "loading" && <p className="empty">{billingMonthLabel} 청구금액을 조회하고 있습니다.</p>}

          {smsMonthlyBillingStatus === "error" && (
            <div className="summary-detail-stack">
              <p className="empty">{smsMonthlyBillingError}</p>
              <p className="note-meta">네이버 클라우드 Billing 권한, 인증키, 조회 월을 확인해 주세요.</p>
            </div>
          )}

          {smsMonthlyBillingStatus === "ready" && billing && (
            <div className="summary-detail-stack">
              <div className="sms-billing-summary">
                <div>
                  <span>조회 월</span>
                  <strong>{formatBillingMonth(billing.month)}</strong>
                </div>
                <div>
                  <span>총 청구금액</span>
                  <strong>{formatCurrencyAmount(billing.total_demand_amount, currencyCode)}</strong>
                </div>
                <div>
                  <span>마지막 집계</span>
                  <strong>{formatDateTime(billing.last_write_date)}</strong>
                </div>
              </div>
              <div className="sms-history-message-meta">
                <span>통화</span>
                <strong>{billing.currency_name ? `${billing.currency_name} (${currencyCode})` : currencyCode}</strong>
              </div>
              {hasMatchedItems ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>청구 항목</th>
                        <th>코드</th>
                        <th>사용금액</th>
                        <th>청구금액</th>
                        <th>집계시각</th>
                      </tr>
                    </thead>
                    <tbody>
                      {billing.matched_items.map((item, index) => (
                        <tr key={`${item.product_demand_type_code || "billing"}-${index}`}>
                          <td className="sms-billing-item-name">{item.product_demand_type_name || "-"}</td>
                          <td>{item.product_demand_type_code || "-"}</td>
                          <td>{formatCurrencyAmount(item.use_amount, currencyCode)}</td>
                          <td>{formatCurrencyAmount(item.demand_amount, currencyCode)}</td>
                          <td>{formatDateTime(item.write_date)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="summary-detail-stack">
                  <p className="empty">{billingMonthLabel}에 매칭된 문자 청구 항목이 없습니다.</p>
                  <p className="note-meta">청구 집계 시점에 따라 선택한 월 항목이 아직 보이지 않을 수 있습니다.</p>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderSmsHistoryMessageModal() {
    if (!smsHistoryMessageTarget) return null;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-history-message-title">
        <section className="form-panel modal-panel sms-history-message-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sms-history-message-title">발송 메시지</h2>
              <p className="note-meta">
                {formatDateTime(smsHistoryMessageTarget.created_at)} · {smsHistoryMessageTarget.content_type} /{" "}
                {smsHistoryMessageTarget.message_type} · {smsHistoryMessageTarget.target_count}명
              </p>
            </div>
            <button type="button" className="secondary" onClick={() => setSmsHistoryMessageTarget(null)}>
              닫기
            </button>
          </div>
          <div className="summary-detail-stack">
            <div className="sms-history-message-meta">
              <span>제목</span>
              <strong>{smsHistoryMessageTarget.title || "제목 없음"}</strong>
            </div>
            <div className="sms-history-message-meta">
              <span>대상</span>
              <strong>{smsTargetSummaryText(smsHistoryMessageTarget.target_summary)}</strong>
            </div>
            <pre className="sms-history-message-content">{smsHistoryMessageTarget.content}</pre>
          </div>
        </section>
      </div>
    );
  }

  function renderSmsHistoryDetailModal() {
    if (!smsHistoryDetailTarget) return null;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sms-history-detail-title">
        <section className="form-panel modal-panel summary-modal-panel">
          <div className="modal-title-row">
            <div>
              <h2 id="sms-history-detail-title">문자 발송 상세</h2>
              <p className="note-meta">
                {formatDateTime(smsHistoryDetailTarget.created_at)} · {smsTargetSummaryText(smsHistoryDetailTarget.target_summary)}
              </p>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setSmsHistoryDetailTarget(null);
                setSmsHistoryDetailItems([]);
                setSmsHistoryDetailKeyword("");
              }}
            >
              닫기
            </button>
          </div>
          <div className="summary-detail-stack">
            <div className="search-row">
              <input
                className="large-input"
                placeholder="이름, 연락처, 상태, 실패 사유를 입력하면 바로 찾습니다"
                value={smsHistoryDetailKeyword}
                onChange={(event) => setSmsHistoryDetailKeyword(event.target.value)}
              />
              <button type="button" className="secondary" onClick={() => setSmsHistoryDetailKeyword("")}>
                지우기
              </button>
            </div>
            <p className="sales-search-meta">
              총 {smsHistoryDetailItems.length}건 중 {filteredSmsHistoryDetailItems.length}건 표시
            </p>
            {filteredSmsHistoryDetailItems.length === 0 ? (
              <p className="empty">조건에 맞는 수신 대상이 없습니다.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>이름</th>
                      <th>연락처</th>
                      <th>상태</th>
                      <th>발송시각</th>
                      <th>실패코드</th>
                      <th>실패사유</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSmsHistoryDetailItems.map((item) => (
                      <tr key={item.id}>
                        <td>{item.member_name || item.recipient_name || "-"}</td>
                        <td>{displayPhone(item.phone)}</td>
                        <td>{item.status}</td>
                        <td>{formatDateTime(item.sent_at)}</td>
                        <td>{item.fail_code || "-"}</td>
                        <td className="memo-cell">{item.fail_reason || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </div>
    );
  }

  function renderProducts() {
    return (
      <section className="page-section">
        <div className="page-title-row">
          <button type="button" onClick={openProductCreateModal}>
            상품/요금 등록
          </button>
          <div className="section-title">
            <p>상품/요금</p>
            <h1>등록 상품</h1>
          </div>
        </div>
        <section className="table-section">
          {products.length === 0 ? (
            <p className="empty">등록된 상품이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="product-table">
                <thead>
                  <tr>
                    <th>상품명</th>
                    <th>상품 종류</th>
                    <th>유효 일수</th>
                    <th>횟수</th>
                    <th>기본 판매가</th>
                    <th>판매활성화</th>
                    <th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id}>
                      <td>
                        <strong>{product.name}</strong>
                      </td>
                      <td>{product.product_type}</td>
                      <td>{product.duration_days || "-"}</td>
                      <td>{product.total_count || "-"}</td>
                      <td className="amount-cell">{money(product.price)}</td>
                      <td>
                        <span className={`status-chip ${product.is_active ? "active" : "inactive"}`}>
                          {product.is_active ? "활성화" : "비활성"}
                        </span>
                      </td>
                      <td>
                        <div className="table-actions">
                          <button type="button" className="secondary" onClick={() => openProductEditModal(product)}>
                            수정
                          </button>
                          <button type="button" className="secondary" onClick={() => void handleProductStatusToggle(product)}>
                            {product.is_active ? "비활성" : "활성화"}
                          </button>
                          <button type="button" className="danger" onClick={() => void handleProductDelete(product)}>
                            삭제
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>
    );
  }
}

function amountNumber(value: string | number | null | undefined) {
  return Number(value || 0);
}

function breakdownFromRecord(record: Record<string, string>): SalesBreakdownItem[] {
  return Object.entries(record)
    .map(([label, amount]) => ({ label, amount, count: 0 }))
    .sort((left, right) => amountNumber(right.amount) - amountNumber(left.amount));
}

function PieChart({ items }: { items: SalesBreakdownItem[] }) {
  const positiveItems = items.filter((item) => amountNumber(item.amount) > 0);
  const total = positiveItems.reduce((sum, item) => sum + amountNumber(item.amount), 0);
  if (total <= 0) return <p className="empty">표시할 매출이 없습니다.</p>;
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  let cumulative = 0;
  return (
    <div className="chart-layout">
      <svg className="pie-chart" viewBox="0 0 160 160" role="img" aria-label="매출 비율 원형 그래프">
        <circle cx="80" cy="80" r={radius} fill="none" stroke="#edf3f0" strokeWidth="28" />
        {positiveItems.map((item, index) => {
          const length = (amountNumber(item.amount) / total) * circumference;
          const offset = cumulative;
          cumulative += length;
          return (
            <circle
              key={item.label}
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              strokeWidth="28"
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 80 80)"
            />
          );
        })}
      </svg>
      <div className="chart-legend">
        {positiveItems.map((item, index) => {
          const percent = ((amountNumber(item.amount) / total) * 100).toFixed(1);
          return (
            <div key={item.label} className="legend-row">
              <span style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }} />
              <strong>{item.label}</strong>
              <em>{money(item.amount)} · {percent}%</em>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function compactMoney(value: number) {
  const absValue = Math.abs(value);
  if (absValue >= 100000000) return `${Math.round(value / 100000000)}억`;
  if (absValue >= 10000) return `${Math.round(value / 10000)}만`;
  return value.toLocaleString("ko-KR");
}

function XYSalesChart({ items }: { items: SalesDailyItem[] }) {
  const amounts = items.map((item) => amountNumber(item.amount));
  const maxAmount = Math.max(0, ...amounts);
  const minAmount = Math.min(0, ...amounts);
  if (items.length === 0 || (maxAmount === 0 && minAmount === 0)) return <p className="empty">표시할 매출이 없습니다.</p>;

  const width = Math.max(760, items.length * 64);
  const height = 360;
  const margin = { top: 28, right: 28, bottom: 70, left: 88 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const range = maxAmount - minAmount || 1;
  const xFor = (index: number) => margin.left + (items.length === 1 ? chartWidth / 2 : (index / (items.length - 1)) * chartWidth);
  const yFor = (amount: number) => margin.top + ((maxAmount - amount) / range) * chartHeight;
  const zeroY = yFor(0);
  const linePath = items
    .map((item, index) => `${index === 0 ? "M" : "L"} ${xFor(index)} ${yFor(amountNumber(item.amount))}`)
    .join(" ");
  const yTicks = Array.from({ length: 5 }, (_, index) => minAmount + (range / 4) * index).reverse();

  return (
    <div className="xy-chart-wrap">
      <svg className="xy-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="x축 날짜, y축 매출액 그래프">
        <line x1={margin.left} y1={margin.top} x2={margin.left} y2={margin.top + chartHeight} className="axis-line" />
        <line x1={margin.left} y1={zeroY} x2={margin.left + chartWidth} y2={zeroY} className="axis-line" />
        {yTicks.map((tick) => {
          const y = yFor(tick);
          return (
            <g key={tick}>
              <line x1={margin.left} y1={y} x2={margin.left + chartWidth} y2={y} className="grid-line" />
              <text x={margin.left - 12} y={y + 5} textAnchor="end" className="axis-text">
                {compactMoney(Math.round(tick))}
              </text>
            </g>
          );
        })}
        {items.map((item, index) => {
          const amount = amountNumber(item.amount);
          const x = xFor(index);
          const y = yFor(amount);
          const barTop = Math.min(y, zeroY);
          const barHeight = Math.max(2, Math.abs(zeroY - y));
          return (
            <g key={item.sale_date}>
              <rect x={x - 14} y={barTop} width="28" height={barHeight} className="xy-bar" />
              <text x={x} y={margin.top + chartHeight + 24} textAnchor="middle" className="axis-text">
                {item.sale_date.slice(5)}
              </text>
              <text x={x} y={y - 10} textAnchor="middle" className="point-label">
                {compactMoney(amount)}
              </text>
            </g>
          );
        })}
        <path d={linePath} className="trend-line" />
        {items.map((item, index) => (
          <circle key={`${item.sale_date}-point`} cx={xFor(index)} cy={yFor(amountNumber(item.amount))} r="5" className="trend-point" />
        ))}
        <text x={margin.left + chartWidth / 2} y={height - 18} textAnchor="middle" className="axis-title">
          날짜
        </text>
        <text x="20" y={margin.top + chartHeight / 2} textAnchor="middle" className="axis-title vertical-axis-title" transform={`rotate(-90 20 ${margin.top + chartHeight / 2})`}>
          매출액
        </text>
      </svg>
    </div>
  );
}

function RecentSalesGrid({
  items,
  onRefund,
  onShowNote
}: {
  items: Sale[];
  onRefund: (sale: Sale) => Promise<void>;
  onShowNote: (sale: Sale) => void;
}) {
  if (items.length === 0) return <p className="empty">조건에 맞는 최근 매출이 없습니다.</p>;
  return (
    <div className="sale-card-grid">
      {items.map((sale) => (
        <article className="sale-card" key={sale.id}>
          <div className="sale-card-top">
            <div className="sale-card-title">
              <strong>{sale.member_name_snapshot || "비회원"}</strong>
              <small>{displayPhone(sale.member_phone_snapshot)}</small>
            </div>
            <div className="sale-card-amount">
              <strong>{money(sale.amount)}</strong>
              <em>{sale.status}</em>
            </div>
          </div>
          <div className="sale-card-meta">
            <div className="sale-card-meta-item">
              <span>매출일</span>
              <strong>{sale.sale_date}</strong>
            </div>
            <div className="sale-card-meta-item">
              <span>등록시각</span>
              <strong>{formatTime(sale.created_at)}</strong>
            </div>
            <div className="sale-card-meta-item">
              <span>상품명</span>
              <strong>{sale.sale_type}</strong>
            </div>
            <div className="sale-card-meta-item">
              <span>결제수단</span>
              <strong>{sale.payment_method}</strong>
            </div>
          </div>
          <p className="sale-card-caption">등록시각 {formatDateTime(sale.created_at)}</p>
          {sale.note?.trim() && <p className="sale-card-note">{sale.note}</p>}
          <div className="sale-card-actions">
            <button type="button" className="secondary" onClick={() => onShowNote(sale)}>
              메모
            </button>
            {sale.status === "정상" && Number(sale.amount) > 0 && (
              <button type="button" className="danger" onClick={() => void onRefund(sale)}>
                환불
              </button>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}

function SimpleMembershipList({ items }: { items: MemberMembership[] }) {
  if (items.length === 0) return <p className="empty">보유 상품이 없습니다.</p>;
  return (
    <div className="compact-list">
      {items.map((item) => (
        <p key={item.id}>
          <strong>{item.product_name || item.product_type || "직접 등록"}</strong>
          <span>
            {item.status} / {item.remaining_count === null || item.remaining_count === undefined ? "기간권" : `${item.remaining_count}회 남음`}
          </span>
        </p>
      ))}
    </div>
  );
}

function DataTable({ title, headers, rows }: { title: string; headers: string[]; rows: Array<Array<string | number>> }) {
  return (
    <section className="table-section">
      <h2>{title}</h2>
      {rows.length === 0 ? (
        <p className="empty">표시할 자료가 없습니다.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {headers.map((header) => (
                  <th key={header}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default App;
