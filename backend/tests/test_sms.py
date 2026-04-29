from datetime import date, timedelta

from app import models, services


class FakeSmsProvider:
    def send_messages(self, *, recipients, content, title, content_type, message_type, reserve_time=None, reserve_time_zone=None):
        return {
            "requestId": "REQ-001",
            "requestTime": "2026-04-12 10:00:00",
            "statusCode": "202",
            "statusName": "success",
        }

    def list_messages(self, *, request_id, page_size=100, page_index=0, next_token=None):
        assert request_id == "REQ-001"
        assert page_index == 0
        return {
            "statusCode": "202",
            "statusName": "success",
            "messages": [
                {
                    "requestId": "REQ-001",
                    "messageId": "MSG-001",
                    "requestTime": "2026-04-12 10:00:00",
                    "to": "01011112222",
                    "status": "COMPLETED",
                    "statusCode": "0",
                    "statusName": "success",
                    "statusMessage": "",
                },
                {
                    "requestId": "REQ-001",
                    "messageId": "MSG-002",
                    "requestTime": "2026-04-12 10:00:00",
                    "to": "01033334444",
                    "status": "COMPLETED",
                    "statusCode": "0",
                    "statusName": "success",
                    "statusMessage": "",
                },
            ],
            "hasMore": False,
        }

    def get_message(self, *, message_id):
        return {
            "statusCode": "200",
            "statusName": "success",
            "messages": [
                {
                    "requestId": "REQ-001",
                    "messageId": message_id,
                    "requestTime": "2026-04-12 10:00:00",
                    "completeTime": "2026-04-12 10:00:01",
                    "status": "COMPLETED",
                    "statusCode": "0",
                    "statusName": "success",
                    "statusMessage": "",
                    "to": "01011112222" if message_id == "MSG-001" else "01033334444",
                }
            ],
        }

    def get_reservation_status(self, *, reserve_id):
        return {
            "reserveId": reserve_id,
            "reserveTimeZone": "Asia/Seoul",
            "reserveTime": "2026-05-01T13:00:00+09:00",
            "reserveStatus": "READY",
        }

    def cancel_reservation(self, *, reserve_id):
        return {}


class DeferredSmsProvider(FakeSmsProvider):
    def __init__(self):
        self.list_call_count = 0

    def list_messages(self, *, request_id, page_size=100, page_index=0, next_token=None):
        self.list_call_count += 1
        status = "PROCESSING" if self.list_call_count == 1 else "COMPLETED"
        status_code = "" if status == "PROCESSING" else "0"
        status_name = "" if status == "PROCESSING" else "success"
        return {
            "statusCode": "202",
            "statusName": "success",
            "messages": [
                {
                    "requestId": request_id,
                    "messageId": "MSG-001",
                    "requestTime": "2026-04-12 10:00:00",
                    "completeTime": None if status == "PROCESSING" else "2026-04-12 10:00:01",
                    "to": "01011112222",
                    "status": status,
                    "statusCode": status_code,
                    "statusName": status_name,
                    "statusMessage": "",
                }
            ],
            "hasMore": False,
        }

    def get_message(self, *, message_id):
        status = "PROCESSING" if self.list_call_count == 1 else "COMPLETED"
        status_code = "" if status == "PROCESSING" else "0"
        status_name = "" if status == "PROCESSING" else "success"
        return {
            "statusCode": "200",
            "statusName": "success",
            "messages": [
                {
                    "requestId": "REQ-001",
                    "messageId": message_id,
                    "requestTime": "2026-04-12 10:00:00",
                    "completeTime": None if status == "PROCESSING" else "2026-04-12 10:00:01",
                    "status": status,
                    "statusCode": status_code,
                    "statusName": status_name,
                    "statusMessage": "",
                    "to": "01011112222",
                }
            ],
        }


class ScheduledSmsProvider(FakeSmsProvider):
    def __init__(self):
        self.request_index = 0
        self.canceled_reservations = []
        self.reserve_statuses = {}

    def send_messages(self, *, recipients, content, title, content_type, message_type, reserve_time=None, reserve_time_zone=None):
        if reserve_time:
            self.request_index += 1
            request_id = f"RSSA-00{self.request_index}"
            self.reserve_statuses[request_id] = {
                "reserveId": request_id,
                "reserveTimeZone": reserve_time_zone or "Asia/Seoul",
                "reserveTime": f"{reserve_time.replace(' ', 'T')}:00+09:00",
                "reserveStatus": "READY",
            }
            return {
                "requestId": request_id,
                "requestTime": "2026-04-12 10:00:00",
                "statusCode": "202",
                "statusName": "success",
            }
        return super().send_messages(
            recipients=recipients,
            content=content,
            title=title,
            content_type=content_type,
            message_type=message_type,
        )

    def get_reservation_status(self, *, reserve_id):
        return self.reserve_statuses[reserve_id]

    def cancel_reservation(self, *, reserve_id):
        self.canceled_reservations.append(reserve_id)
        if reserve_id in self.reserve_statuses:
            self.reserve_statuses[reserve_id]["reserveStatus"] = "CANCELED"
        return {}

    def list_messages(self, *, request_id, page_size=100, page_index=0, next_token=None):
        if request_id.startswith("RSSA-"):
            return {
                "statusCode": "202",
                "statusName": "success",
                "messages": [
                    {
                        "requestId": request_id,
                        "messageId": "MSG-SCHEDULE-001",
                        "requestTime": "2026-05-01 13:00:00",
                        "completeTime": "2026-05-01 13:00:01",
                        "to": "01011112222",
                        "status": "COMPLETED",
                        "statusCode": "0",
                        "statusName": "success",
                        "statusMessage": "",
                    }
                ],
                "hasMore": False,
            }
        return super().list_messages(request_id=request_id, page_size=page_size, page_index=page_index, next_token=next_token)

    def get_message(self, *, message_id):
        if message_id == "MSG-SCHEDULE-001":
            return {
                "statusCode": "200",
                "statusName": "success",
                "messages": [
                    {
                        "requestId": "RSSA-001",
                        "messageId": message_id,
                        "requestTime": "2026-05-01 13:00:00",
                        "completeTime": "2026-05-01 13:00:01",
                        "status": "COMPLETED",
                        "statusCode": "0",
                        "statusName": "success",
                        "statusMessage": "",
                        "to": "01011112222",
                    }
                ],
            }
        return super().get_message(message_id=message_id)


class PaginatedSmsProvider(FakeSmsProvider):
    def __init__(self):
        self.sent_recipients = []

    def send_messages(self, *, recipients, content, title, content_type, message_type, reserve_time=None, reserve_time_zone=None):
        self.sent_recipients = recipients
        return {
            "requestId": "REQ-PAGED",
            "requestTime": "2026-04-12 10:00:00",
            "statusCode": "202",
            "statusName": "success",
        }

    def list_messages(self, *, request_id, page_size=100, page_index=0, next_token=None):
        assert request_id == "REQ-PAGED"
        start = int(next_token) if next_token else page_index * page_size
        end = min(start + page_size, len(self.sent_recipients))
        messages = []
        for idx, phone in enumerate(self.sent_recipients[start:end], start=start):
            is_failure = idx >= len(self.sent_recipients) - 2
            messages.append(
                {
                    "requestId": request_id,
                    "messageId": f"MSG-PAGED-{idx + 1:03d}",
                    "requestTime": "2026-04-12 10:00:00",
                    "completeTime": "2026-04-12 10:00:01",
                    "to": phone,
                    "status": "COMPLETED",
                    "statusCode": "3001" if is_failure else "0",
                    "statusName": "fail" if is_failure else "success",
                    "statusMessage": "carrier rejected" if is_failure else "",
                }
            )
        has_more = end < len(self.sent_recipients)
        return {
            "statusCode": "202",
            "statusName": "success",
            "messages": messages,
            "hasMore": has_more,
            "nextToken": str(end) if has_more else None,
        }


class DelayedResolutionSmsProvider(FakeSmsProvider):
    def __init__(self):
        self.sent_recipients = []
        self.sync_round = 0

    def send_messages(self, *, recipients, content, title, content_type, message_type, reserve_time=None, reserve_time_zone=None):
        self.sent_recipients = recipients
        return {
            "requestId": "REQ-DELAYED",
            "requestTime": "2026-04-12 10:00:00",
            "statusCode": "202",
            "statusName": "success",
        }

    def _current_round(self, *, page_index, next_token):
        if page_index == 0 and not next_token:
            self.sync_round += 1
        return self.sync_round

    def _message_payload(self, request_id: str, idx: int, *, round_number: int) -> dict:
        phone = self.sent_recipients[idx]
        if round_number == 1 and idx >= 99:
            return {
                "requestId": request_id,
                "messageId": f"MSG-DELAYED-{idx + 1:03d}",
                "requestTime": "2026-04-12 10:00:00",
                "completeTime": None,
                "to": phone,
                "status": "PROCESSING",
                "statusCode": "",
                "statusName": "",
                "statusMessage": "",
            }
        is_failure = idx >= len(self.sent_recipients) - 2
        return {
            "requestId": request_id,
            "messageId": f"MSG-DELAYED-{idx + 1:03d}",
            "requestTime": "2026-04-12 10:00:00",
            "completeTime": "2026-04-12 10:00:01",
            "to": phone,
            "status": "COMPLETED",
            "statusCode": "3001" if is_failure else "0",
            "statusName": "fail" if is_failure else "success",
            "statusMessage": "carrier rejected" if is_failure else "",
        }

    def list_messages(self, *, request_id, page_size=100, page_index=0, next_token=None):
        assert request_id == "REQ-DELAYED"
        round_number = self._current_round(page_index=page_index, next_token=next_token)
        start = int(next_token) if next_token else page_index * page_size
        end = min(start + page_size, len(self.sent_recipients))
        messages = [self._message_payload(request_id, idx, round_number=round_number) for idx in range(start, end)]
        has_more = end < len(self.sent_recipients)
        return {
            "statusCode": "202",
            "statusName": "success",
            "messages": messages,
            "hasMore": has_more,
            "nextToken": str(end) if has_more else None,
        }

    def get_message(self, *, message_id):
        idx = int(message_id.rsplit("-", 1)[-1]) - 1
        payload = self._message_payload("REQ-DELAYED", idx, round_number=self.sync_round)
        return {
            "statusCode": "200",
            "statusName": "success",
            "messages": [payload],
        }


class DuplicatePhoneSmsProvider(FakeSmsProvider):
    def list_messages(self, *, request_id, page_size=100, page_index=0, next_token=None):
        assert request_id == "REQ-DUPLICATE"
        return {
            "statusCode": "202",
            "statusName": "success",
            "messages": [
                {
                    "requestId": request_id,
                    "messageId": "MSG-DUP-001",
                    "requestTime": "2026-04-12 10:00:00",
                    "completeTime": "2026-04-12 10:00:01",
                    "to": "01077778888",
                    "status": "COMPLETED",
                    "statusCode": "0",
                    "statusName": "success",
                    "statusMessage": "",
                },
                {
                    "requestId": request_id,
                    "messageId": "MSG-DUP-002",
                    "requestTime": "2026-04-12 10:00:00",
                    "completeTime": "2026-04-12 10:00:01",
                    "to": "01077778888",
                    "status": "COMPLETED",
                    "statusCode": "3001",
                    "statusName": "fail",
                    "statusMessage": "carrier rejected",
                },
            ],
            "hasMore": False,
        }

    def get_message(self, *, message_id):
        detail = {
            "MSG-DUP-001": {
                "requestId": "REQ-DUPLICATE",
                "messageId": "MSG-DUP-001",
                "requestTime": "2026-04-12 10:00:00",
                "completeTime": "2026-04-12 10:00:01",
                "to": "01077778888",
                "status": "COMPLETED",
                "statusCode": "0",
                "statusName": "success",
                "statusMessage": "",
            },
            "MSG-DUP-002": {
                "requestId": "REQ-DUPLICATE",
                "messageId": "MSG-DUP-002",
                "requestTime": "2026-04-12 10:00:00",
                "completeTime": "2026-04-12 10:00:01",
                "to": "01077778888",
                "status": "COMPLETED",
                "statusCode": "3001",
                "statusName": "fail",
                "statusMessage": "carrier rejected",
            },
        }
        return {
            "statusCode": "200",
            "statusName": "success",
            "messages": [detail[message_id]],
        }


class FakeBillingClient:
    def __init__(self, response):
        self.response = response
        self.called_with = None

    def get_product_demand_cost_list(self, *, start_month, end_month):
        self.called_with = (start_month, end_month)
        return self.response


def create_members(client, count: int, *, name_prefix: str, phone_prefix: str = "01055"):
    members = []
    for idx in range(count):
        phone = f"{phone_prefix}{idx:06d}"[-11:]
        members.append(
            client.post(
                "/api/members",
                json={"name": f"{name_prefix}{idx + 1}", "phone": phone},
            ).json()
        )
    return members


def test_sms_group_and_template_crud(client):
    first_member = client.post("/api/members", json={"name": "문자회원1", "phone": "010-1111-2222"}).json()
    second_member = client.post("/api/members", json={"name": "문자회원2", "phone": "010-3333-4444"}).json()

    create_group = client.post(
        "/api/sms/groups",
        json={
            "name": "4월 만료 안내",
            "description": "테스트 그룹",
            "member_ids": [first_member["id"], second_member["id"]],
        },
    )
    assert create_group.status_code == 201
    group = create_group.json()
    assert group["member_count"] == 2
    assert sorted(group["member_ids"]) == sorted([first_member["id"], second_member["id"]])

    update_group = client.put(
        f"/api/sms/groups/{group['id']}",
        json={
            "name": "4월 만료 안내 수정",
            "description": "수정된 설명",
            "member_ids": [second_member["id"]],
            "is_active": True,
        },
    )
    assert update_group.status_code == 200
    assert update_group.json()["member_count"] == 1
    assert update_group.json()["member_ids"] == [second_member["id"]]

    create_template = client.post(
        "/api/sms/templates",
        json={"title": "만료 안내", "content": "안녕하세요. 만료 예정 안내입니다.", "is_active": False},
    )
    assert create_template.status_code == 201
    template = create_template.json()
    assert template["title"] == "만료 안내"
    assert template["is_active"] is False

    update_template = client.put(
        f"/api/sms/templates/{template['id']}",
        json={"title": "만료 안내 수정", "content": "수정된 안내입니다.", "is_active": True},
    )
    assert update_template.status_code == 200
    assert update_template.json()["is_active"] is True

    delete_template = client.delete(f"/api/sms/templates/{template['id']}")
    assert delete_template.status_code == 204
    templates = client.get("/api/sms/templates").json()["items"]
    assert all(item["id"] != template["id"] for item in templates)


def test_sms_preview_blocks_ad_members_without_sms_agree(client):
    agree_member = client.post(
        "/api/members",
        json={"name": "수신동의", "phone": "010-1111-2222", "sms_agree": True},
    ).json()
    disagree_member = client.post(
        "/api/members",
        json={"name": "수신거부", "phone": "010-3333-4444", "sms_agree": False},
    ).json()
    group = client.post(
        "/api/sms/groups",
        json={
            "name": "광고 발송 그룹",
            "member_ids": [agree_member["id"], disagree_member["id"]],
        },
    ).json()

    preview = client.post(
        "/api/sms/recipients/preview",
        json={
            "include_all_members": True,
            "group_ids": [group["id"]],
            "content_type": "AD",
        },
    )

    assert preview.status_code == 200
    data = preview.json()
    assert data["summary"]["total_candidates"] == 2
    assert data["summary"]["eligible_count"] == 1
    assert data["summary"]["blocked_count"] == 1
    assert data["blocked_recipients"][0]["blocked_reason"] == "문자 수신 미동의"


def test_sms_preview_can_target_upcoming_birthdays(client):
    today_date = date.today()
    upcoming_birthday = today_date + timedelta(days=3)
    upcoming_birth_year = 1992 if (upcoming_birthday.month, upcoming_birthday.day) == (2, 29) else 1990
    client.post(
        "/api/members",
        json={
            "name": "생일대상",
            "phone": "010-1111-2222",
            "birth_date": upcoming_birthday.replace(year=upcoming_birth_year).isoformat(),
        },
    )
    excluded_birthday = today_date + timedelta(days=20)
    excluded_birth_year = 1992 if (excluded_birthday.month, excluded_birthday.day) == (2, 29) else 1990
    client.post(
        "/api/members",
        json={
            "name": "생일제외",
            "phone": "010-3333-4444",
            "birth_date": excluded_birthday.replace(year=excluded_birth_year).isoformat(),
        },
    )

    preview = client.post(
        "/api/sms/recipients/preview",
        json={
            "include_birthdays": True,
            "birthday_days": 7,
            "content_type": "COMM",
        },
    )

    assert preview.status_code == 200
    data = preview.json()
    assert data["summary"]["eligible_count"] == 1
    assert data["eligible_recipients"][0]["recipient_name"] == "생일대상"
    assert data["eligible_recipients"][0]["source_labels"] == ["7일 안 생일자"]


def test_sms_send_saves_history_and_recipient_details(client, monkeypatch):
    monkeypatch.setattr(services, "get_sms_provider", lambda: FakeSmsProvider())

    first_member = client.post("/api/members", json={"name": "발송회원1", "phone": "010-1111-2222"}).json()
    second_member = client.post("/api/members", json={"name": "발송회원2", "phone": "010-3333-4444"}).json()
    group = client.post(
        "/api/sms/groups",
        json={"name": "중복 제거 그룹", "member_ids": [first_member["id"]]},
    ).json()
    template = client.post(
        "/api/sms/templates",
        json={"title": "안내 템플릿", "content": "안녕하세요. 운영 안내입니다."},
    ).json()

    send = client.post(
        "/api/sms/send",
        json={
            "include_all_members": True,
            "group_ids": [group["id"]],
            "content_type": "COMM",
            "template_id": template["id"],
            "content": "안녕하세요. 운영 안내입니다.",
            "excluded_member_ids": [],
            "excluded_phones": [],
        },
    )

    assert send.status_code == 201
    message = send.json()
    assert message["target_count"] == 2
    assert message["success_count"] == 2
    assert message["fail_count"] == 0
    assert message["status"] == "완료"
    assert message["provider_request_id"] == "REQ-001"

    history = client.get("/api/sms/history?size=10")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["id"] == message["id"]

    recipients = client.get(f"/api/sms/{message['id']}/recipients?keyword=3333&size=10")
    assert recipients.status_code == 200
    assert recipients.json()["total"] == 1
    assert recipients.json()["items"][0]["phone"] == "01033334444"
    assert recipients.json()["items"][0]["status"] == "성공"


def test_sms_history_syncs_pending_messages(client, monkeypatch):
    provider = DeferredSmsProvider()
    monkeypatch.setattr(services, "get_sms_provider", lambda: provider)

    client.post("/api/members", json={"name": "대기회원", "phone": "010-1111-2222"})

    send = client.post(
        "/api/sms/send",
        json={
            "include_all_members": True,
            "content_type": "COMM",
            "content": "발송 상태 확인 문자입니다.",
            "excluded_member_ids": [],
            "excluded_phones": [],
        },
    )

    assert send.status_code == 201
    sent_message = send.json()
    assert sent_message["status"] == "발송중"
    assert sent_message["success_count"] == 0
    assert sent_message["fail_count"] == 0

    history = client.get("/api/sms/history?size=10")

    assert history.status_code == 200
    history_message = history.json()["items"][0]
    assert history_message["id"] == sent_message["id"]
    assert history_message["status"] == "완료"
    assert history_message["success_count"] == 1
    assert history_message["fail_count"] == 0


def test_sms_send_syncs_all_paginated_results(client, monkeypatch):
    provider = PaginatedSmsProvider()
    monkeypatch.setattr(services, "get_sms_provider", lambda: provider)

    create_members(client, 115, name_prefix="페이지회원")

    send = client.post(
        "/api/sms/send",
        json={
            "include_all_members": True,
            "content_type": "COMM",
            "content": "페이지 전체 동기화 확인 문자입니다.",
            "excluded_member_ids": [],
            "excluded_phones": [],
        },
    )

    assert send.status_code == 201
    message = send.json()
    assert message["target_count"] == 115
    assert message["success_count"] == 113
    assert message["fail_count"] == 2
    assert message["status"] == "완료"

    recipients = client.get(f"/api/sms/{message['id']}/recipients?size=200")
    assert recipients.status_code == 200
    assert recipients.json()["total"] == 115
    assert sum(1 for item in recipients.json()["items"] if item["status"] == "성공") == 113
    assert sum(1 for item in recipients.json()["items"] if item["status"] == "실패") == 2


def test_sms_history_refresh_resolves_processing_recipients(client, monkeypatch):
    provider = DelayedResolutionSmsProvider()
    monkeypatch.setattr(services, "get_sms_provider", lambda: provider)

    create_members(client, 115, name_prefix="지연회원", phone_prefix="01066")

    send = client.post(
        "/api/sms/send",
        json={
            "include_all_members": True,
            "content_type": "COMM",
            "content": "처리중 동기화 확인 문자입니다.",
            "excluded_member_ids": [],
            "excluded_phones": [],
        },
    )

    assert send.status_code == 201
    sent_message = send.json()
    assert sent_message["target_count"] == 115
    assert sent_message["status"] == "발송중"
    assert sent_message["success_count"] == 99
    assert sent_message["fail_count"] == 0

    history = client.get("/api/sms/history?size=10")
    assert history.status_code == 200
    history_message = history.json()["items"][0]
    assert history_message["id"] == sent_message["id"]
    assert history_message["status"] == "완료"
    assert history_message["success_count"] == 113
    assert history_message["fail_count"] == 2

    recipients = client.get(f"/api/sms/{sent_message['id']}/recipients?size=200")
    assert recipients.status_code == 200
    assert sum(1 for item in recipients.json()["items"] if item["status"] == "발송중") == 0
    assert sum(1 for item in recipients.json()["items"] if item["status"] == "성공") == 113
    assert sum(1 for item in recipients.json()["items"] if item["status"] == "실패") == 2


def test_sms_recipient_detail_resyncs_incomplete_completed_message(client, db_session, monkeypatch):
    provider = DelayedResolutionSmsProvider()
    monkeypatch.setattr(services, "get_sms_provider", lambda: provider)

    create_members(client, 115, name_prefix="복구회원", phone_prefix="01067")

    send = client.post(
        "/api/sms/send",
        json={
            "include_all_members": True,
            "content_type": "COMM",
            "content": "불완전 완료 복구 문자입니다.",
            "excluded_member_ids": [],
            "excluded_phones": [],
        },
    )

    assert send.status_code == 201
    message_id = send.json()["id"]

    message = db_session.get(models.SmsMessage, message_id)
    message.status = "완료"
    db_session.commit()

    recipients = client.get(f"/api/sms/{message_id}/recipients?size=200")
    assert recipients.status_code == 200
    payload = recipients.json()
    assert payload["message"]["status"] == "완료"
    assert payload["message"]["success_count"] == 113
    assert payload["message"]["fail_count"] == 2
    assert sum(1 for item in payload["items"] if item["status"] == "발송중") == 0


def test_sync_sms_delivery_matches_duplicate_phone_recipients(db_session):
    provider = DuplicatePhoneSmsProvider()
    message = models.SmsMessage(
        target_type="전체 회원",
        content="중복 번호 확인 문자입니다.",
        content_type="COMM",
        message_type="SMS",
        target_count=2,
        success_count=0,
        fail_count=0,
        status="발송중",
        provider_name="NAVER_SENS",
        provider_request_id="REQ-DUPLICATE",
    )
    db_session.add(message)
    db_session.flush()
    db_session.add_all(
        [
            models.SmsMessageRecipient(
                sms_message_id=message.id,
                recipient_name="중복1",
                phone="01077778888",
                sms_agree=True,
                status="발송중",
            ),
            models.SmsMessageRecipient(
                sms_message_id=message.id,
                recipient_name="중복2",
                phone="01077778888",
                sms_agree=True,
                status="발송중",
            ),
        ]
    )
    db_session.commit()

    synced = services.sync_sms_message_delivery(db_session, message.id, provider)

    assert synced.status == "완료"
    assert synced.success_count == 1
    assert synced.fail_count == 1
    assert sorted(item.provider_message_id for item in synced.recipients) == ["MSG-DUP-001", "MSG-DUP-002"]
    assert sorted(item.status for item in synced.recipients) == ["성공", "실패"]


def test_sms_schedule_crud(client, monkeypatch):
    provider = ScheduledSmsProvider()
    monkeypatch.setattr(services, "get_sms_provider", lambda: provider)

    client.post("/api/members", json={"name": "예약회원", "phone": "010-1111-2222"})

    create = client.post(
        "/api/sms/schedules",
        json={
            "include_all_members": True,
            "content_type": "COMM",
            "content": "예약 문자입니다.",
            "scheduled_at": "2026-05-01T13:00:00+09:00",
            "excluded_member_ids": [],
            "excluded_phones": [],
        },
    )

    assert create.status_code == 201
    schedule = create.json()
    assert schedule["status"] == "예약"
    assert schedule["provider_request_id"] == "RSSA-001"

    schedules = client.get("/api/sms/schedules?size=10")
    assert schedules.status_code == 200
    assert schedules.json()["total"] == 1
    assert schedules.json()["items"][0]["id"] == schedule["id"]

    update = client.put(
        f"/api/sms/schedules/{schedule['id']}",
        json={
            "include_all_members": True,
            "content_type": "COMM",
            "content": "예약 문자 수정입니다.",
            "scheduled_at": "2026-05-01T15:00:00+09:00",
            "excluded_member_ids": [],
            "excluded_phones": [],
        },
    )

    assert update.status_code == 200
    updated = update.json()
    assert updated["status"] == "예약"
    assert updated["provider_request_id"] == "RSSA-002"
    assert provider.canceled_reservations == ["RSSA-001"]

    delete = client.delete(f"/api/sms/schedules/{schedule['id']}")

    assert delete.status_code == 200
    canceled = delete.json()
    assert canceled["status"] == "예약취소"
    assert provider.canceled_reservations == ["RSSA-001", "RSSA-002"]

    schedules_after_delete = client.get("/api/sms/schedules?size=10")
    assert schedules_after_delete.status_code == 200
    assert schedules_after_delete.json()["total"] == 1
    assert schedules_after_delete.json()["items"][0]["status"] == "예약취소"

    history = client.get("/api/sms/history?size=10")
    assert history.status_code == 200
    assert history.json()["total"] == 0


def test_sms_schedule_moves_to_history_after_delivery(client, monkeypatch):
    provider = ScheduledSmsProvider()
    monkeypatch.setattr(services, "get_sms_provider", lambda: provider)

    client.post("/api/members", json={"name": "예약발송회원", "phone": "010-1111-2222"})

    create = client.post(
        "/api/sms/schedules",
        json={
            "include_all_members": True,
            "content_type": "COMM",
            "content": "예약 후 발송 문자입니다.",
            "scheduled_at": "2026-05-01T13:00:00+09:00",
            "excluded_member_ids": [],
            "excluded_phones": [],
        },
    )

    assert create.status_code == 201
    schedule = create.json()
    provider.reserve_statuses[schedule["provider_request_id"]]["reserveStatus"] = "DONE"

    history = client.get("/api/sms/history?size=10")

    assert history.status_code == 200
    assert history.json()["total"] == 1
    message = history.json()["items"][0]
    assert message["id"] == schedule["id"]
    assert message["status"] == "완료"
    assert message["success_count"] == 1
    assert message["scheduled_at"].startswith("2026-05-01T13:00:00")

    schedules = client.get("/api/sms/schedules?size=10")
    assert schedules.status_code == 200
    assert schedules.json()["total"] == 0


def test_sms_monthly_billing_returns_matching_items(client, monkeypatch):
    billing_client = FakeBillingClient(
        {
            "getProductDemandCostListResponse": {
                "totalRows": 3,
                "productDemandCostList": [
                    {
                        "productDemandType": {"code": "SENS_SMS", "codeName": "Simple & Easy Notification Service SMS"},
                        "useAmount": 1500,
                        "demandAmount": 1500,
                        "writeDate": "2026-04-18T09:00:00+0900",
                        "payCurrency": {"code": "KRW", "codeName": "South Korea Won"},
                    },
                    {
                        "productDemandType": {"code": "SENS_ALIM", "codeName": "SENS 알림톡"},
                        "useAmount": 500,
                        "demandAmount": 500,
                        "writeDate": "2026-04-19T09:00:00+0900",
                        "payCurrency": {"code": "KRW", "codeName": "South Korea Won"},
                    },
                    {
                        "productDemandType": {"code": "NET_SVR", "codeName": "Network - Server&LoadBalancer"},
                        "useAmount": 9999,
                        "demandAmount": 9999,
                        "writeDate": "2026-04-17T09:00:00+0900",
                        "payCurrency": {"code": "KRW", "codeName": "South Korea Won"},
                    },
                ],
                "returnCode": "0",
                "returnMessage": "success",
            }
        }
    )
    monkeypatch.setattr(services, "get_ncloud_billing_client", lambda: billing_client)
    monkeypatch.setattr(services, "current_billing_month", lambda now=None: "202604")

    response = client.get("/api/sms/monthly-billing")

    assert response.status_code == 200
    data = response.json()
    assert billing_client.called_with == ("202604", "202604")
    assert data["month"] == "202604"
    assert data["currency_code"] == "KRW"
    assert data["total_demand_amount"] == "1500"
    assert len(data["matched_items"]) == 1
    assert data["matched_items"][0]["product_demand_type_code"] == "SENS_SMS"
    assert data["last_write_date"].startswith("2026-04-18T09:00:00")


def test_sms_monthly_billing_accepts_selected_month_query(client, monkeypatch):
    billing_client = FakeBillingClient(
        {
            "getProductDemandCostListResponse": {
                "totalRows": 1,
                "productDemandCostList": [
                    {
                        "productDemandType": {"code": "SENS_SMS", "codeName": "Simple & Easy Notification Service SMS"},
                        "useAmount": 300,
                        "demandAmount": 300,
                        "writeDate": "2026-03-31T09:00:00+0900",
                        "payCurrency": {"code": "KRW", "codeName": "South Korea Won"},
                    }
                ],
                "returnCode": "0",
                "returnMessage": "success",
            }
        }
    )
    monkeypatch.setattr(services, "get_ncloud_billing_client", lambda: billing_client)

    response = client.get("/api/sms/monthly-billing?month=2026-03")

    assert response.status_code == 200
    data = response.json()
    assert billing_client.called_with == ("202603", "202603")
    assert data["month"] == "202603"
    assert data["total_demand_amount"] == "300"


def test_sms_monthly_billing_returns_zero_when_no_sms_items(client, monkeypatch):
    billing_client = FakeBillingClient(
        {
            "getProductDemandCostListResponse": {
                "totalRows": 1,
                "productDemandCostList": [
                    {
                        "productDemandType": {"code": "NET_SVR", "codeName": "Network - Server&LoadBalancer"},
                        "useAmount": 9999,
                        "demandAmount": 9999,
                        "writeDate": "2026-04-17T09:00:00+0900",
                        "payCurrency": {"code": "KRW", "codeName": "South Korea Won"},
                    }
                ],
                "returnCode": "0",
                "returnMessage": "success",
            }
        }
    )
    monkeypatch.setattr(services, "get_ncloud_billing_client", lambda: billing_client)
    monkeypatch.setattr(services, "current_billing_month", lambda now=None: "202604")

    response = client.get("/api/sms/monthly-billing")

    assert response.status_code == 200
    data = response.json()
    assert data["month"] == "202604"
    assert data["total_demand_amount"] == "0"
    assert data["matched_items"] == []
    assert data["currency_code"] == "KRW"
    assert data["last_write_date"] is None


def test_sms_monthly_billing_rejects_invalid_month(client):
    response = client.get("/api/sms/monthly-billing?month=2026/03")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_billing_month"


def test_sms_monthly_billing_requires_access_keys(client, monkeypatch):
    class MissingBillingSettings:
        ncp_access_key = None
        ncp_secret_key = None
        sms_billing_keyword_list = ["simple & easy notification service", "sens", "sms"]

    monkeypatch.setattr(services, "get_settings", lambda: MissingBillingSettings())

    response = client.get("/api/sms/monthly-billing")

    assert response.status_code == 400
    assert response.json()["code"] == "ncloud_billing_not_configured"
