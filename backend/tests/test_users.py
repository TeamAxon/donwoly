def signup_user(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "profile@example.com",
            "name": "기존이름",
            "password": "Password1!",
            "age": 24,
            "region": "SYDNEY",
            "industry": "HOSPITALITY",
        },
    )
    assert response.status_code == 201
    return response.json()


def headers(tokens):
    return {"Authorization": f"Bearer {tokens['accessToken']}"}


def test_get_my_profile(client):
    tokens = signup_user(client)
    response = client.get("/api/users/me", headers=headers(tokens))

    assert response.status_code == 200
    assert response.json() == {
        "id": tokens["userId"],
        "email": "profile@example.com",
        "name": "기존이름",
        "age": 24,
        "region": "SYDNEY",
        "industry": "HOSPITALITY",
    }


def test_update_my_profile_partially(client):
    tokens = signup_user(client)
    response = client.patch(
        "/api/users/me",
        headers=headers(tokens),
        json={"name": "새이름", "age": 28, "region": "PERTH", "industry": "FARM"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "profile@example.com"
    assert body["name"] == "새이름"
    assert body["age"] == 28
    assert body["region"] == "PERTH"
    assert body["industry"] == "FARM"


def test_profile_update_rejects_invalid_or_empty_payload(client):
    tokens = signup_user(client)
    invalid = client.patch(
        "/api/users/me",
        headers=headers(tokens),
        json={"age": 17, "region": "CANBERRA"},
    )
    empty = client.patch("/api/users/me", headers=headers(tokens), json={})

    assert invalid.status_code == 422
    assert invalid.json()["error"] == "VALIDATION_ERROR"
    assert empty.status_code == 422
    assert empty.json()["error"] == "VALIDATION_ERROR"


def test_profile_endpoints_require_authentication(client):
    assert client.get("/api/users/me").status_code == 401
    assert client.patch("/api/users/me", json={"name": "새이름"}).status_code == 401
