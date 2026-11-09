import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from app import app, ITEMS  # noqa: E402


@pytest.fixture
def client():
    ITEMS.clear()
    return app.test_client()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_home_page(client):
    assert b"CI/CD Pipeline Demo" in client.get("/").data


def test_add_and_list_item(client):
    r = client.post("/api/items", json={"name": "first"})
    assert r.status_code == 201
    assert client.get("/api/items").get_json() == [{"id": 1, "name": "first"}]


def test_add_item_requires_name(client):
    assert client.post("/api/items", json={}).status_code == 400
