import jwt


VALID_USER = {
    "email": "worker@example.com",
    "name": "김워홀",
    "password": "Password1!",
    "age": 24,
    "region": "SYDNEY",
    "industry": "HOSPITALITY",
}


def test_signup_returns_spec_response_and_tokens(client):
    response = client.post("/api/auth/signup", json=VALID_USER)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"userId", "accessToken", "refreshToken"}
    assert jwt.decode(body["accessToken"], options={"verify_signature": False})["type"] == "access"
    assert jwt.decode(body["refreshToken"], options={"verify_signature": False})["type"] == "refresh"


def test_duplicate_email_returns_email_taken(client):
    assert client.post("/api/auth/signup", json=VALID_USER).status_code == 201
    response = client.post(
        "/api/auth/signup", json={**VALID_USER, "email": "WORKER@example.com"}
    )

    assert response.status_code == 409
    assert response.json() == {"error": "EMAIL_TAKEN"}


def test_signup_validation_matches_spec(client):
    response = client.post(
        "/api/auth/signup",
        json={
            **VALID_USER,
            "password": "onlyletters",
            "age": 17,
            "region": "CANBERRA",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert {error["loc"][-1] for error in body["details"]} == {
        "password",
        "age",
        "region",
    }


def test_check_email_availability(client):
    before = client.get("/api/auth/check-email", params={"email": VALID_USER["email"]})
    client.post("/api/auth/signup", json=VALID_USER)
    after = client.get("/api/auth/check-email", params={"email": VALID_USER["email"]})

    assert before.status_code == 200
    assert before.json() == {"available": True}
    assert after.json() == {"available": False}


def test_check_email_rejects_invalid_format(client):
    response = client.get("/api/auth/check-email", params={"email": "not-an-email"})

    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_login_returns_tokens_and_user_profile(client):
    client.post("/api/auth/signup", json=VALID_USER)
    response = client.post(
        "/api/auth/login",
        json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"accessToken", "refreshToken", "user"}
    assert body["user"] == {
        "id": body["user"]["id"],
        "email": VALID_USER["email"],
        "name": VALID_USER["name"],
        "age": VALID_USER["age"],
        "region": VALID_USER["region"],
        "industry": VALID_USER["industry"],
    }


def test_login_rejects_invalid_credentials(client):
    response = client.post(
        "/api/auth/login",
        json={"email": VALID_USER["email"], "password": "WrongPassword1!"},
    )

    assert response.status_code == 401
    assert response.json() == {"error": "INVALID_CREDENTIALS"}


def test_password_longer_than_bcrypt_limit_is_supported(client):
    long_password = "A1!" + "가" * 30
    signup = client.post(
        "/api/auth/signup", json={**VALID_USER, "password": long_password}
    )
    login = client.post(
        "/api/auth/login",
        json={"email": VALID_USER["email"], "password": long_password},
    )

    assert signup.status_code == 201
    assert login.status_code == 200
