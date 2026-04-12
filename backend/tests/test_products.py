def test_product_can_be_deactivated_and_listed_with_include_inactive(client):
    create_response = client.post(
        "/api/membership-products",
        json={
            "name": "비활성 테스트 상품",
            "product_type": "판매",
            "price": 50000,
        },
    )
    assert create_response.status_code == 201
    product = create_response.json()

    update_response = client.put(
        f"/api/membership-products/{product['id']}",
        json={"is_active": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False

    active_products = client.get("/api/membership-products").json()["items"]
    all_products = client.get("/api/membership-products?include_inactive=true").json()["items"]

    assert all(item["id"] != product["id"] for item in active_products)
    assert any(item["id"] == product["id"] and item["is_active"] is False for item in all_products)


def test_product_delete_blocks_used_product_and_deletes_unused_product(client):
    unused_product = client.post(
        "/api/membership-products",
        json={
            "name": "삭제 테스트 상품",
            "product_type": "판매",
            "price": 70000,
        },
    ).json()

    delete_response = client.delete(f"/api/membership-products/{unused_product['id']}")
    assert delete_response.status_code == 204

    all_products = client.get("/api/membership-products?include_inactive=true").json()["items"]
    assert all(item["id"] != unused_product["id"] for item in all_products)

    period_product = next(
        product for product in client.get("/api/membership-products").json()["items"] if product["product_type"] == "기간제"
    )
    member = client.post(
        "/api/members",
        json={"name": "상품사용회원", "phone": "010-3131-4141"},
    ).json()
    sale_response = client.post(
        "/api/sales",
        json={
            "member_id": member["id"],
            "product_id": period_product["id"],
            "payment_method": "카드",
            "amount": 120000,
        },
    )
    assert sale_response.status_code == 201

    blocked_delete = client.delete(f"/api/membership-products/{period_product['id']}")
    assert blocked_delete.status_code == 400
    assert blocked_delete.json()["code"] == "product_in_use"
