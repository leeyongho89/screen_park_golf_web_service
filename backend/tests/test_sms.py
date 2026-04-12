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
        json={"title": "만료 안내", "content": "안녕하세요. 만료 예정 안내입니다."},
    )
    assert create_template.status_code == 201
    template = create_template.json()
    assert template["title"] == "만료 안내"

    update_template = client.put(
        f"/api/sms/templates/{template['id']}",
        json={"title": "만료 안내 수정", "content": "수정된 안내입니다.", "is_active": False},
    )
    assert update_template.status_code == 200
    assert update_template.json()["is_active"] is False


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
