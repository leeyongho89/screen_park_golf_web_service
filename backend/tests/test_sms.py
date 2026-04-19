from datetime import date, timedelta

from app import services


class FakeSmsProvider:
    def send_messages(self, *, recipients, content, title, content_type, message_type):
        return {
            "requestId": "REQ-001",
            "requestTime": "2026-04-12 10:00:00",
            "statusCode": "202",
            "statusName": "success",
        }

    def list_messages(self, *, request_id, page_size=100, page_index=1, next_token=None):
        assert request_id == "REQ-001"
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


class FakeBillingClient:
    def __init__(self, response):
        self.response = response
        self.called_with = None

    def get_product_demand_cost_list(self, *, start_month, end_month):
        self.called_with = (start_month, end_month)
        return self.response


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
