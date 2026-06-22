from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.connectors.sankhya.client import SankhyaClient
from app.connectors.sankhya.exceptions import (
    SankhyaAuthenticationError,
    SankhyaAuthorizationError,
    SankhyaTimeoutError,
)
from app.connectors.sankhya.schemas import SankhyaCredentials
from app.connectors.sankhya.services import mask_connection_credentials
from app.core.encryption import encrypt_secret
from app.core.security import mask_payload
from app.models.connection import Connection


def _build_client(handler, *, credentials: SankhyaCredentials) -> SankhyaClient:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url=str(credentials.base_url))
    return SankhyaClient(credentials=credentials, client=client)


def _build_oauth_credentials() -> SankhyaCredentials:
    return SankhyaCredentials(
        base_url="https://api.sandbox.sankhya.com.br",
        environment="sandbox",
        auth_mode="oauth_client_credentials",
        client_id="client-id",
        client_secret="client-secret",
        x_token="x-token-789",
        timeout_seconds=5,
    )


def test_authenticate_success_masks_sensitive_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/authenticate":
            form = parse_qs(request.content.decode("utf-8"))
            assert form["grant_type"] == ["client_credentials"]
            assert form["client_id"] == ["client-id"]
            assert form["client_secret"] == ["client-secret"]
            assert request.headers["x-token"] == "x-token-789"
            return httpx.Response(
                200,
                json={
                    "access_token": "access-123",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_token": "refresh-secret",
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    sankhya = _build_client(handler, credentials=_build_oauth_credentials())

    auth = sankhya.authenticate()

    assert auth.authenticated is True
    assert auth.access_token == "access-123"
    assert auth.headers["Authorization"] == "Bearer access-123"
    masked = json.dumps(auth.raw_response_masked, ensure_ascii=False)
    assert "access-123" not in masked
    assert "refresh-secret" not in masked
    assert auth.raw_response_masked["access_token"] == "***"
    sankhya.close()


def test_authenticate_invalid_credentials_raise_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/authenticate":
            return httpx.Response(401, json={"message": "invalid credentials"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    sankhya = _build_client(handler, credentials=_build_oauth_credentials())

    with pytest.raises(SankhyaAuthenticationError):
        sankhya.authenticate()
    sankhya.close()


def test_authenticate_timeout_raises_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    sankhya = _build_client(handler, credentials=_build_oauth_credentials())

    with pytest.raises(SankhyaTimeoutError):
        sankhya.authenticate()
    sankhya.close()


def test_authenticate_403_raises_authorization_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/authenticate":
            return httpx.Response(403, json={"message": "forbidden"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    sankhya = _build_client(handler, credentials=_build_oauth_credentials())

    with pytest.raises(SankhyaAuthorizationError):
        sankhya.authenticate()
    sankhya.close()


def test_mock_test_connection_preserved_without_network_calls():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    sankhya = _build_client(handler, credentials=_build_oauth_credentials())

    result = sankhya.test_connection(mode="mock")

    assert result.success is True
    assert result.mode == "mock"
    assert result.read_check is False
    assert result.details["mock"] is True
    sankhya.close()


def test_real_test_connection_authenticates_without_read_check():
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/authenticate":
            return httpx.Response(200, json={"access_token": "access-123", "expires_in": 60})
        if request.url.path == "/gateway/v1/mge/service.sbr":
            raise AssertionError("read check should not run")
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    sankhya = _build_client(handler, credentials=_build_oauth_credentials())

    result = sankhya.test_connection(mode="real", read_check=False)

    assert result.success is True
    assert result.mode == "real"
    assert result.read_check is False
    assert result.details["auth"]["authenticated"] is True
    assert seen_paths == ["/authenticate"]
    sankhya.close()


def test_real_test_connection_can_run_read_check():
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/authenticate":
            return httpx.Response(200, json={"access_token": "access-123", "expires_in": 60})
        if request.url.path == "/gateway/v1/mge/service.sbr":
            body = json.loads(request.content.decode("utf-8"))
            assert request.url.params["serviceName"] == "CRUDServiceProvider.loadRecords"
            assert body["requestBody"]["dataSet"]["rootEntity"] == "Produto"
            assert body["requestBody"]["dataSet"]["entity"][0]["fieldset"]["list"] == "CODPROD, DESCRPROD"
            return httpx.Response(
                201,
                json={
                    "serviceName": "CRUDServiceProvider.loadRecords",
                    "responseBody": {
                        "entities": {
                            "total": "1",
                            "hasMoreResult": "false",
                        }
                    },
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    sankhya = _build_client(handler, credentials=_build_oauth_credentials())
    sankhya._read_check_config = lambda: ("Produto", ["CODPROD", "DESCRPROD"], 1)  # type: ignore[method-assign]

    result = sankhya.test_connection(mode="real", read_check=True)

    assert result.success is True
    assert result.read_check is True
    assert result.details["read_check"]["record_count"] == 1
    assert seen_paths == ["/authenticate", "/gateway/v1/mge/service.sbr"]
    sankhya.close()


def test_normalize_error_maps_http_status_and_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/authenticate":
            return httpx.Response(403, json={"message": "forbidden"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    sankhya = _build_client(handler, credentials=_build_oauth_credentials())

    with pytest.raises(SankhyaAuthorizationError) as exc_info:
        sankhya.authenticate()

    normalized = sankhya.normalize_error(exc_info.value)
    assert normalized["error_type"] == "authorization_error"
    assert normalized["retryable"] is False

    timeout_normalized = sankhya.normalize_error(SankhyaTimeoutError("timeout"))
    assert timeout_normalized["error_type"] == "timeout_error"
    assert timeout_normalized["retryable"] is True
    sankhya.close()


def test_connection_credentials_masking_hides_secrets():
    connection = Connection(
        id="connection-1",
        tenant_id="tenant-1",
        name="Sankhya",
        platform="sankhya",
        environment="sandbox",
        base_url="https://api.sandbox.sankhya.com.br",
        credentials_encrypted=encrypt_secret(
            json.dumps(
                {
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "x_token": "x-token-789",
                    "access_token": "access-123",
                    "verify_ssl": True,
                }
            )
        ),
        status="inactive",
    )

    masked = mask_connection_credentials(connection) or {}
    masked_json = json.dumps(masked, ensure_ascii=False)

    assert masked["client_secret"] == "***"
    assert masked["x_token"] == "***"
    assert masked["access_token"] == "***"
    assert "client-secret" not in masked_json
    assert "x-token-789" not in masked_json
    assert "access-123" not in masked_json


def test_mask_payload_hides_sankhya_tokens():
    masked = mask_payload({"x_token": "secret", "client_secret": "secret", "nested": {"token": "secret"}})
    assert masked["x_token"] != "secret"
    assert masked["client_secret"] != "secret"
    assert masked["nested"]["token"] != "secret"
    assert "***" in masked["x_token"]
