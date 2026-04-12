def test_member_validation_error_returns_readable_message(client):
    response = client.post(
        "/api/members",
        json={
            "name": "오류회원",
            "phone": "dddddddd",
            "email": "bad-email",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert "휴대전화" in body["message"]
    assert "이메일" in body["message"]
    assert body["details"] == [
        {"field": "phone", "label": "휴대전화", "message": "휴대전화 번호를 확인해 주세요."},
        {"field": "email", "label": "이메일", "message": "이메일 형식을 확인해 주세요."},
    ]
