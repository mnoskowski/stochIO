import uuid
import pytest
from httpx2 import AsyncClient
from fastapi import status


@pytest.fixture
def make_register_payload():
    def _make(**overrides) -> dict:
        suffix = uuid.uuid4().hex[:8]
        base = {
            "username": f"user_{suffix}",
            "email": f"user_{suffix}@example.com",
            "password": "StrongPass123!",
            "display_name": f"user",
            "first_name": "john",
            "last_name": "doe",
        }
        return {**base, **overrides}

    return _make

@pytest.fixture
async def registered_user(client: AsyncClient, make_register_payload) -> dict[str, str]:
    payload = make_register_payload()
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    return payload


@pytest.mark.parametrize(
    "overrides, expected_status",
    [
        ({}, status.HTTP_201_CREATED),
        ({"first_name": None, "last_name": None}, status.HTTP_201_CREATED),
        ({"email": "badexample.com"}, status.HTTP_422_UNPROCESSABLE_CONTENT),
        ({"email": "badexample@mail"}, status.HTTP_422_UNPROCESSABLE_CONTENT),
        ({"email": "bad example@mail.com"}, status.HTTP_422_UNPROCESSABLE_CONTENT),
    ],
)
async def test_register_valid_payload(
    client: AsyncClient, make_register_payload, overrides: dict, expected_status: int
):
    payload = make_register_payload(**overrides)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == expected_status, response.text


@pytest.mark.parametrize(
    "same_field, expected_second_status",
    [
        (None, status.HTTP_201_CREATED),
        (
            "email",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ),  # Same email, different username -> 201, 422
        (
            "username",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ),  # Same username, different email -> 201, 422
    ],
)
async def test_duplicate_register(
    client: AsyncClient,
    make_register_payload,
    same_field: str | None,
    expected_second_status: int,
) -> None:
    first_payload = make_register_payload()
    second_payload = make_register_payload()

    if same_field:
        second_payload[same_field] = first_payload[same_field]

    res1 = await client.post("/auth/register", json=first_payload)
    assert res1.status_code == status.HTTP_201_CREATED, res1.text

    res2 = await client.post("/auth/register", json=second_payload)
    assert res2.status_code == expected_second_status, res2.text


async def test_login_ep(
    registered_user: dict,
    client: AsyncClient,
):
    response = await client.post(
        "/auth/login",
        json={
            "username": registered_user["username"],
            "password": registered_user["password"],
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text


async def test_password_validation(
    registered_user: dict,
    client: AsyncClient,
):
    response = await client.post(
        "/auth/login",
        json={
            "username": registered_user["username"],
            "password": "definetelywrongpassword",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


async def test_login_sets_httponly_cookie_and_authenticates(
    registered_user: dict,
    client: AsyncClient,
):
    # Clear the cookie left by registered_user
    client.cookies.clear()
    response = await client.get("/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    response = await client.post("/auth/login", json={
        "username": registered_user["username"],
        "password": registered_user["password"]
    })
    assert response.status_code == status.HTTP_200_OK, response.text
    assert "access_token" in response.cookies, response.text
    assert "SameSite=lax" in response.headers["Set-Cookie"], response.text
    assert "HttpOnly" in response.headers["Set-Cookie"], response.text

    response = await client.get("/auth/me")
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["username"] == registered_user["username"]

    # Make sure there aren't any password leaks
    assert "hashed_password" not in response.json()

async def test_logout_ep(client: AsyncClient, registered_user: dict):
    response = await client.post(
        "/auth/logout",
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await client.get("/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
