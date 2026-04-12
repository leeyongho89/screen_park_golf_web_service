from datetime import date, timedelta


def get_product(client, product_type: str) -> dict:
    products = client.get("/api/membership-products").json()["items"]
    return next(product for product in products if product["product_type"] == product_type)


def create_period_membership(client, name: str, phone: str) -> dict:
    product = get_product(client, "기간제")
    sale = client.post(
        "/api/sales",
        json={
            "member_name": name,
            "member_phone": phone,
            "product_id": product["id"],
            "payment_method": "카드",
            "amount": 120000,
        },
    )
    assert sale.status_code == 201
    return sale.json()


def test_member_memberships_search_status_pagination_and_member_phone(client):
    first_sale = create_period_membership(client, "검색회원", "010-1919-2020")
    create_period_membership(client, "다른회원", "010-2121-2222")

    first_membership_id = first_sale["related_membership_id"]
    pause = client.patch(f"/api/member-memberships/{first_membership_id}/pause", json={})
    assert pause.status_code == 200

    status_filtered = client.get("/api/member-memberships?status=정지&keyword=1919&size=500").json()
    assert status_filtered["total"] == 1
    assert status_filtered["items"][0]["member_name"] == "검색회원"
    assert status_filtered["items"][0]["member_phone"] == "01019192020"

    paged = client.get("/api/member-memberships?status=사용중&status=정지&page=1&size=1").json()
    assert paged["total"] == 2
    assert paged["page"] == 1
    assert paged["size"] == 1
    assert len(paged["items"]) == 1


def test_membership_period_adjust_changes_dates_and_logs_action(client):
    sale = create_period_membership(client, "기간보정회원", "010-2323-2424")
    membership_id = sale["related_membership_id"]

    adjusted = client.patch(
        f"/api/member-memberships/{membership_id}/period",
        json={
            "start_date": "2026-04-20",
            "end_date": "2026-05-25",
            "note": "기간 보정 테스트",
        },
    )

    assert adjusted.status_code == 200
    assert adjusted.json()["start_date"] == "2026-04-20"
    assert adjusted.json()["end_date"] == "2026-05-25"

    logs = client.get(f"/api/member-memberships/{membership_id}/usage-logs").json()["items"]
    assert logs[0]["action_type"] == "기간 보정"
    assert logs[0]["note"] == "기간 보정 테스트"

    invalid = client.patch(
        f"/api/member-memberships/{membership_id}/period",
        json={"start_date": "2026-05-01", "end_date": "2026-04-30"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "invalid_membership_period"


def test_member_memberships_filters_by_remaining_count(client):
    count_product = get_product(client, "횟수")
    member = client.post("/api/members", json={"name": "잔여횟수회원", "phone": "010-2828-2929"}).json()
    sale = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": count_product["id"],
            "payment_method": "카드",
            "amount": 99000,
        },
    )
    assert sale.status_code == 201
    membership = client.get(f"/api/members/{member['id']}/memberships").json()["items"][0]
    adjust = client.post(f"/api/member-memberships/{membership['id']}/adjust", json={"remaining_count": 3})
    assert adjust.status_code == 200

    filtered = client.get("/api/member-memberships?status=사용중&remaining_count_lte=3").json()

    assert filtered["total"] == 1
    assert filtered["items"][0]["member_name"] == "잔여횟수회원"
    assert filtered["items"][0]["remaining_count"] == 3


def test_member_memberships_searches_member_memo_and_returns_member_memo(client):
    period_product = get_product(client, "기간제")
    member = client.post(
        "/api/members",
        json={
            "name": "메모검색회원",
            "phone": "010-5151-5252",
            "memo": "VIP 라운지 선호",
        },
    ).json()

    sale = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": period_product["id"],
            "payment_method": "카드",
            "amount": 120000,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=29)).isoformat(),
        },
    )
    assert sale.status_code == 201

    filtered = client.get("/api/member-memberships?status=사용중&keyword=VIP&size=500").json()

    assert filtered["total"] == 1
    assert filtered["items"][0]["member_name"] == "메모검색회원"
    assert filtered["items"][0]["member_memo"] == "VIP 라운지 선호"
