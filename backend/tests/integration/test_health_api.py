from __future__ import annotations


class _FakeRedis:
    def ping(self) -> bool:
        return True


def test_healthcheck_reports_ok(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.routes_health.redis.Redis.from_url",
        lambda *args, **kwargs: _FakeRedis(),
    )

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
