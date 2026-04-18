from datetime import date


def test_create_and_list_reservations_for_target_date(client):
    member = client.post("/api/members", json={"name": "예약회원", "phone": "010-1111-2222"}).json()

    response = client.post(
        "/api/reservations",
        json={
            "bay_number": 1,
            "member_id": member["id"],
            "reservation_date": date.today().isoformat(),
            "start_time": "10:00",
            "end_time": "10:30",
            "note": "오전 예약",
        },
    )

    assert response.status_code == 201
    reservation = response.json()
    assert reservation["customer_name"] == "예약회원"
    assert reservation["customer_phone"] == "01011112222"
    assert reservation["member_id"] == member["id"]
    assert reservation["status"] == "예약"

    reservations = client.get(f"/api/reservations?target_date={date.today().isoformat()}").json()
    assert reservations["total"] == 1
    assert reservations["items"][0]["id"] == reservation["id"]


def test_create_non_member_reservation_normalizes_phone(client):
    response = client.post(
        "/api/reservations",
        json={
            "bay_number": 2,
            "customer_name": "전화예약",
            "customer_phone": "010-3333-4444",
            "reservation_date": date.today().isoformat(),
            "start_time": "11:00",
            "end_time": "12:00",
        },
    )

    assert response.status_code == 201
    reservation = response.json()
    assert reservation["member_id"] is None
    assert reservation["customer_name"] == "전화예약"
    assert reservation["customer_phone"] == "01033334444"


def test_reservation_blocks_overlapping_same_bay(client):
    payload = {
        "bay_number": 3,
        "customer_name": "겹침예약",
        "customer_phone": "01055556666",
        "reservation_date": date.today().isoformat(),
        "start_time": "13:00",
        "end_time": "14:00",
    }
    assert client.post("/api/reservations", json=payload).status_code == 201

    conflict = client.post(
        "/api/reservations",
        json={**payload, "customer_name": "겹침예약2", "customer_phone": "01077778888", "start_time": "13:30", "end_time": "14:30"},
    )
    other_bay = client.post("/api/reservations", json={**payload, "bay_number": 4, "customer_phone": "01099990000"})

    assert conflict.status_code == 409
    assert conflict.json()["code"] == "reservation_conflict"
    assert other_bay.status_code == 201


def test_reservation_rejects_invalid_time_slot_and_hours(client):
    base = {
        "bay_number": 1,
        "customer_name": "시간검증",
        "customer_phone": "01012121212",
        "reservation_date": date.today().isoformat(),
    }

    invalid_slot = client.post("/api/reservations", json={**base, "start_time": "10:15", "end_time": "10:45"})
    invalid_hours = client.post("/api/reservations", json={**base, "start_time": "08:30", "end_time": "09:30"})
    invalid_order = client.post("/api/reservations", json={**base, "start_time": "12:00", "end_time": "12:00"})

    assert invalid_slot.status_code == 400
    assert invalid_slot.json()["code"] == "invalid_reservation_slot"
    assert invalid_hours.status_code == 400
    assert invalid_hours.json()["code"] == "invalid_reservation_hours"
    assert invalid_order.status_code == 400
    assert invalid_order.json()["code"] == "invalid_reservation_time"


def test_reservation_cancel_status_and_reuses_canceled_slot(client):
    cancel_target = client.post(
        "/api/reservations",
        json={
            "bay_number": 5,
            "customer_name": "취소예약",
            "customer_phone": "01056565656",
            "reservation_date": date.today().isoformat(),
            "start_time": "16:00",
            "end_time": "16:30",
        },
    ).json()

    cancel = client.patch(f"/api/reservations/{cancel_target['id']}/cancel", json={"note": "고객 요청 취소"})

    assert cancel.status_code == 200
    assert cancel.json()["status"] == "취소"
    assert cancel.json()["canceled_at"] is not None
    assert cancel.json()["note"] == "고객 요청 취소"

    reuse_canceled_slot = client.post(
        "/api/reservations",
        json={
            "bay_number": 5,
            "customer_name": "재예약",
            "customer_phone": "01078787878",
            "reservation_date": date.today().isoformat(),
            "start_time": "16:00",
            "end_time": "16:30",
        },
    )
    assert reuse_canceled_slot.status_code == 201
