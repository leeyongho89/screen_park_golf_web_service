from datetime import date, datetime, time, timedelta

from app import models


def get_product(client, product_type: str) -> dict:
    products = client.get("/api/membership-products").json()["items"]
    return next(product for product in products if product["product_type"] == product_type)


def test_count_sale_creates_member_membership_and_usage_log(client):
    count_product = get_product(client, "횟수")
    member = client.post(
        "/api/members",
        json={"name": "박영희", "phone": "010-2222-3333"},
    ).json()

    sale_response = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": count_product["id"],
            "payment_method": "카드",
            "amount": 150000,
        },
    )

    assert sale_response.status_code == 201
    sale = sale_response.json()
    assert sale["member_id"] == member["id"]
    assert sale["sale_type"] == count_product["name"]
    assert sale["related_membership_id"] is not None

    memberships = client.get(f"/api/members/{member['id']}/memberships").json()["items"]
    assert len(memberships) == 1
    assert memberships[0]["remaining_count"] == 10
    assert memberships[0]["end_date"] == (date.today() + timedelta(days=29)).isoformat()

    deduct = client.post(
        f"/api/member-memberships/{memberships[0]['id']}/deduct",
        json={"count": 1, "note": "입장 사용"},
    )
    assert deduct.status_code == 200
    assert deduct.json()["remaining_count"] == 9

    logs = client.get(f"/api/member-memberships/{memberships[0]['id']}/usage-logs")
    assert logs.status_code == 200
    assert logs.json()["items"][0]["action_type"] == "사용"


def test_period_sale_uses_custom_start_and_end_dates(client):
    period_product = get_product(client, "기간제")
    member = client.post(
        "/api/members",
        json={"name": "기간회원", "phone": "010-3333-4444"},
    ).json()

    sale_response = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": period_product["id"],
            "payment_method": "현금",
            "amount": 220000,
            "start_date": "2026-04-15",
            "end_date": "2026-05-20",
        },
    )

    assert sale_response.status_code == 201
    memberships = client.get(f"/api/members/{member['id']}/memberships").json()["items"]
    assert memberships[0]["start_date"] == "2026-04-15"
    assert memberships[0]["end_date"] == "2026-05-20"
    assert memberships[0]["remaining_count"] is None


def test_count_product_auto_creates_member_when_name_and_phone_are_entered(client):
    count_product = get_product(client, "횟수")

    response = client.post(
        "/api/sales",
        json={
            "member_name": "미등록 고객",
            "member_phone": "010-1234-5678",
            "product_id": count_product["id"],
            "payment_method": "카드",
            "amount": 99000,
        },
    )

    assert response.status_code == 201
    sale = response.json()
    assert sale["member_id"] is not None
    assert sale["member_name_snapshot"] == "미등록 고객"
    assert sale["member_phone_snapshot"] == "01012345678"

    members = client.get("/api/members?keyword=1234").json()["items"]
    assert len(members) == 1
    assert members[0]["name"] == "미등록 고객"
    assert members[0]["phone"] == "01012345678"

    memberships = client.get(f"/api/members/{members[0]['id']}/memberships").json()["items"]
    assert len(memberships) == 1
    assert memberships[0]["remaining_count"] == 10


def test_count_product_requires_name_and_phone_without_selected_member(client):
    count_product = get_product(client, "횟수")

    response = client.post(
        "/api/sales",
        json={
            "member_name": "연락처 없음",
            "product_id": count_product["id"],
            "payment_method": "카드",
            "amount": 99000,
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "member_details_required"


def test_refund_sale_creates_negative_sale_and_marks_membership(client):
    period_product = get_product(client, "기간제")
    member = client.post(
        "/api/members",
        json={"name": "이민수", "phone": "010-4444-5555"},
    ).json()
    sale_response = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": period_product["id"],
            "payment_method": "현금",
            "amount": 220000,
        },
    )
    sale = sale_response.json()

    refund_response = client.post(f"/api/sales/{sale['id']}/refund", json={"note": "테스트 환불"})

    assert refund_response.status_code == 201
    refund = refund_response.json()
    assert refund["amount"] == "-220000"
    assert refund["original_sale_id"] == sale["id"]
    assert refund["sale_date"] == sale["sale_date"]

    sales = client.get("/api/sales?size=10").json()["items"]
    original = next(item for item in sales if item["id"] == sale["id"])
    assert original["status"] == "환불"

    memberships = client.get(f"/api/members/{member['id']}/memberships").json()["items"]
    assert memberships[0]["status"] == "환불"


def test_refund_keeps_dashboard_today_sales_at_zero(client):
    sell_product = get_product(client, "판매")
    member = client.post(
        "/api/members",
        json={"name": "환불보정회원", "phone": "010-4545-5656"},
    ).json()
    sale_response = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": sell_product["id"],
            "payment_method": "카드",
            "amount": 50000,
        },
    )
    assert sale_response.status_code == 201

    refund_response = client.post(f"/api/sales/{sale_response.json()['id']}/refund", json={"note": "전일 매출 환불"})
    assert refund_response.status_code == 201
    assert refund_response.json()["sale_date"] == date.today().isoformat()

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["today_sales"] == "0"


def test_member_list_includes_sales_amounts(client):
    sell_product = get_product(client, "판매")
    member = client.post(
        "/api/members",
        json={"name": "매출회원", "phone": "010-7777-8888"},
    ).json()
    sale_response = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": sell_product["id"],
            "payment_method": "카드",
            "amount": 33000,
        },
    )
    assert sale_response.status_code == 201

    members = client.get("/api/members?keyword=7777").json()["items"]

    assert len(members) == 1
    assert members[0]["total_sales_amount"] == "33000"
    assert members[0]["recent_30_days_sales_amount"] == "33000"


def test_member_list_recent_sales_uses_selected_reference_date(client):
    sell_product = get_product(client, "판매")
    member = client.post(
        "/api/members",
        json={"name": "기준일회원", "phone": "010-8888-9999"},
    ).json()
    old_sale = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": sell_product["id"],
            "payment_method": "카드",
            "amount": 11000,
        },
    )
    assert old_sale.status_code == 201

    recent_sale = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": sell_product["id"],
            "payment_method": "카드",
            "amount": 22000,
        },
    )
    assert recent_sale.status_code == 201

    today_members = client.get(f"/api/members?keyword=8888&sale_date={date.today().isoformat()}").json()["items"]
    old_reference_members = client.get(
        f"/api/members?keyword=8888&sale_date={(date.today() - timedelta(days=60)).isoformat()}"
    ).json()["items"]

    assert today_members[0]["total_sales_amount"] == "33000"
    assert today_members[0]["recent_30_days_sales_amount"] == "33000"
    assert old_reference_members[0]["total_sales_amount"] == "33000"
    assert old_reference_members[0]["recent_30_days_sales_amount"] == "0"


def test_sales_list_orders_by_created_at_desc(client):
    sell_product = get_product(client, "판매")
    member = client.post(
        "/api/members",
        json={"name": "정렬회원", "phone": "010-1212-3434"},
    ).json()

    earlier_created = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": sell_product["id"],
            "payment_method": "카드",
            "amount": 15000,
        },
    )
    assert earlier_created.status_code == 201

    later_created = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": sell_product["id"],
            "payment_method": "현금",
            "amount": 17000,
        },
    )
    assert later_created.status_code == 201

    sales = client.get("/api/sales?size=10").json()["items"]

    assert sales[0]["id"] == later_created.json()["id"]
    assert sales[1]["id"] == earlier_created.json()["id"]


def test_sales_summary_includes_payment_product_member_and_day_breakdowns(client):
    sell_product = get_product(client, "판매")
    member_a = client.post("/api/members", json={"name": "요약회원A", "phone": "010-1515-1616"}).json()
    member_b = client.post("/api/members", json={"name": "요약회원B", "phone": "010-1717-1818"}).json()

    first = client.post(
        "/api/sales",
        json={
            "member_id": member_a["id"],
            "product_id": sell_product["id"],
            "payment_method": "카드",
            "amount": 10000,
        },
    )
    second = client.post(
        "/api/sales",
        json={
            "member_id": member_b["id"],
            "product_id": sell_product["id"],
            "payment_method": "현금",
            "amount": 30000,
        },
    )
    assert first.status_code == 201
    assert second.status_code == 201

    today = date.today().isoformat()
    summary = client.get(f"/api/sales/summary?from_date={today}&to_date={today}").json()

    assert summary["total_amount"] == "40000"
    assert summary["by_payment_method"] == {"카드": "10000", "현금": "30000"}
    assert summary["by_sale_type"] == {sell_product["name"]: "40000"}
    assert summary["by_member"][0]["label"] == "요약회원B"
    assert summary["by_member"][0]["amount"] == "30000"
    assert summary["by_day"] == [
        {"sale_date": today, "amount": "40000", "count": 2},
    ]


def test_dashboard_uses_expiring_days_and_low_remaining_count_thresholds(client):
    count_product = get_product(client, "횟수")
    period_product = get_product(client, "기간제")
    count_member = client.post("/api/members", json={"name": "홈횟수회원", "phone": "010-3030-3131"}).json()
    period_member = client.post("/api/members", json={"name": "홈기간회원", "phone": "010-3232-3333"}).json()

    count_sale = client.post(
        "/api/sales",
        json={
            "member_id": count_member["id"],
            "product_id": count_product["id"],
            "payment_method": "카드",
            "amount": 90000,
        },
    )
    assert count_sale.status_code == 201
    count_membership = client.get(f"/api/members/{count_member['id']}/memberships").json()["items"][0]
    adjust_count = client.post(f"/api/member-memberships/{count_membership['id']}/adjust", json={"remaining_count": 3})
    assert adjust_count.status_code == 200

    period_sale = client.post(
        "/api/sales",
        json={
            "member_id": period_member["id"],
            "product_id": period_product["id"],
            "payment_method": "현금",
            "amount": 120000,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=6)).isoformat(),
        },
    )
    assert period_sale.status_code == 201

    dashboard = client.get("/api/dashboard?expiring_days=500&low_remaining_count=3").json()

    assert dashboard["expiring_memberships"] >= 1
    assert dashboard["low_remaining_memberships"] == 1


def test_dashboard_uses_new_member_days_and_sales_days(client, db_session):
    sale_product = get_product(client, "판매")
    recent_member = client.post("/api/members", json={"name": "최근등록회원", "phone": "010-4141-4242"}).json()
    old_member = client.post("/api/members", json={"name": "예전등록회원", "phone": "010-4343-4444"}).json()

    member = db_session.get(models.Member, old_member["id"])
    member.created_at = datetime.combine(date.today() - timedelta(days=2), time(hour=10))
    db_session.commit()

    old_sale = client.post(
        "/api/sales",
        json={
            "member_id": old_member["id"],
            "product_id": sale_product["id"],
            "payment_method": "현금",
            "amount": 30000,
        },
    )
    assert old_sale.status_code == 201
    old_sale_item = db_session.get(models.Sale, old_sale.json()["id"])
    old_sale_item.sale_date = date.today() - timedelta(days=2)
    db_session.commit()

    recent_sale = client.post(
        "/api/sales",
        json={
            "member_id": recent_member["id"],
            "product_id": sale_product["id"],
            "payment_method": "카드",
            "amount": 70000,
        },
    )
    assert recent_sale.status_code == 201

    one_day = client.get("/api/dashboard?new_member_days=1&sales_days=1").json()
    three_days = client.get("/api/dashboard?new_member_days=3&sales_days=3").json()

    assert one_day["today_new_members"] == 1
    assert one_day["today_sales"] == "70000"
    assert three_days["today_new_members"] == 2
    assert three_days["today_sales"] == "100000"
