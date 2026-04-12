from datetime import date, datetime, time, timedelta

from app import models


def test_create_member_normalizes_phone_and_blocks_duplicate(client):
    response = client.post(
        "/api/members",
        json={
            "name": "김철수",
            "phone": "010-1234-5678",
            "sms_agree": True,
            "memo": "오전 방문 선호",
        },
    )

    assert response.status_code == 201
    member = response.json()
    assert member["phone"] == "01012345678"

    duplicate = client.post(
        "/api/members",
        json={
            "name": "김철수2",
            "phone": "01012345678",
        },
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "duplicate_phone"

    search = client.get("/api/members?keyword=1234")
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["name"] == "김철수"


def test_deactivated_member_can_be_listed_and_restored(client):
    create = client.post(
        "/api/members",
        json={
            "name": "복구회원",
            "phone": "010-5555-7777",
        },
    )
    assert create.status_code == 201
    member = create.json()

    deactivate = client.patch(f"/api/members/{member['id']}/deactivate", json={})
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    active_list = client.get("/api/members?keyword=5555").json()
    deleted_list = client.get("/api/members?inactive_only=true&keyword=5555").json()

    assert active_list["total"] == 0
    assert deleted_list["total"] == 1
    assert deleted_list["items"][0]["name"] == "복구회원"

    restore = client.patch(f"/api/members/{member['id']}/restore", json={})
    assert restore.status_code == 200
    assert restore.json()["is_active"] is True

    restored_list = client.get("/api/members?keyword=5555").json()
    assert restored_list["total"] == 1


def test_inactive_member_without_history_can_be_permanently_deleted(client):
    create = client.post(
        "/api/members",
        json={
            "name": "영구삭제회원",
            "phone": "010-5656-7878",
        },
    )
    assert create.status_code == 201
    member = create.json()

    deactivate = client.patch(f"/api/members/{member['id']}/deactivate", json={})
    assert deactivate.status_code == 200

    delete = client.request("DELETE", f"/api/members/{member['id']}", json={})
    assert delete.status_code == 204

    deleted_list = client.get("/api/members?inactive_only=true&keyword=5656").json()
    assert deleted_list["total"] == 0


def test_permanent_delete_blocks_member_with_sales_history(client):
    member = client.post(
        "/api/members",
        json={
            "name": "이력회원",
            "phone": "010-6767-8989",
        },
    ).json()
    product = next(product for product in client.get("/api/membership-products").json()["items"] if product["product_type"] == "판매")
    sale = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": product["id"],
            "payment_method": "카드",
            "amount": 10000,
        },
    )
    assert sale.status_code == 201
    deactivate = client.patch(f"/api/members/{member['id']}/deactivate", json={})
    assert deactivate.status_code == 200

    delete = client.request("DELETE", f"/api/members/{member['id']}", json={})

    assert delete.status_code == 400
    assert delete.json()["code"] == "member_has_history"


def test_member_list_filters_by_created_date_range(client, db_session):
    recent_member = client.post(
        "/api/members",
        json={
            "name": "최근회원",
            "phone": "010-9191-9292",
        },
    ).json()
    old_member = client.post(
        "/api/members",
        json={
            "name": "예전회원",
            "phone": "010-9393-9494",
        },
    ).json()

    member = db_session.get(models.Member, old_member["id"])
    member.created_at = datetime.combine(date.today() - timedelta(days=2), time(hour=9))
    db_session.commit()

    filtered = client.get(f"/api/members?created_from={date.today().isoformat()}&created_to={date.today().isoformat()}").json()

    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == recent_member["id"]
