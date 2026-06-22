from __future__ import annotations

from typing import Any

import httpx

from app.connectors.base import BaseConnector, ConnectorCapabilities
from app.connectors.sankhya.auth import build_auth_headers, build_auth_payload
from app.connectors.sankhya.exceptions import (
    SankhyaAuthenticationError,
    SankhyaError,
    SankhyaRateLimitError,
    SankhyaTimeoutError,
)
from app.connectors.sankhya.schemas import SankhyaAuthResult, SankhyaCredentials


class SankhyaClient(BaseConnector):
    def __init__(self, credentials: SankhyaCredentials, client: httpx.Client | None = None) -> None:
        self.credentials = credentials
        self._client = client or httpx.Client(
            base_url=str(credentials.base_url),
            timeout=credentials.timeout_seconds,
        )
        self._session_token: str | None = credentials.token

    @classmethod
    def default_capabilities(cls) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            supports_authentication=True,
            supports_test_connection=True,
            supports_query=True,
            supports_save_record=True,
            supports_load_records=True,
            supports_upsert_record=True,
            supports_delete_record=False,
            supports_raw_execution=True,
            supported_entities=[
                "parceiros",
                "produtos",
                "vendedores",
                "pedidos",
                "estoque",
                "financeiro",
                "notas",
                "consultas_customizadas",
            ],
        )

    def authenticate(self) -> SankhyaAuthResult:
        if self._session_token:
            return SankhyaAuthResult(
                token=self._session_token,
                headers=build_auth_headers(self.credentials, self._session_token),
                authenticated=True,
            )

        if self.credentials.token:
            self._session_token = self.credentials.token
            return SankhyaAuthResult(
                token=self._session_token,
                headers=build_auth_headers(self.credentials, self._session_token),
                authenticated=True,
            )

        payload = build_auth_payload(self.credentials)
        if not payload:
            raise SankhyaAuthenticationError("Missing Sankhya credentials for authentication")

        try:
            response = self._client.post(self.credentials.auth_path, json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaError(str(exc)) from exc

        data = response.json() if response.content else {}
        token = data.get("token") or data.get("access_token")
        if not token:
            raise SankhyaAuthenticationError("Sankhya did not return an access token")
        self._session_token = token
        return SankhyaAuthResult(
            token=token,
            headers=build_auth_headers(self.credentials, token),
            authenticated=True,
        )

    def test_connection(self) -> dict[str, Any]:
        auth = self.authenticate()
        headers = auth.headers
        try:
            response = self._client.get(self.credentials.health_path, headers=headers)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaError(str(exc)) from exc

        return {
            "success": True,
            "status_code": response.status_code,
            "message": "Connection successful",
            "details": response.json() if response.content else {},
        }

    def execute_query(self, query: str, params: dict[str, Any] | None = None) -> Any:
        auth = self.authenticate()
        payload = {"query": query, "params": params or {}}
        try:
            response = self._client.post(self.credentials.query_path, json=payload, headers=auth.headers)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaError(str(exc)) from exc

    def save_record(self, entity: str, payload: dict[str, Any]) -> Any:
        auth = self.authenticate()
        body = {"entity": entity, "payload": payload}
        try:
            response = self._client.post(self.credentials.record_path, json=body, headers=auth.headers)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaError(str(exc)) from exc

    def load_records(self, entity: str, filters: dict[str, Any] | None = None) -> Any:
        auth = self.authenticate()
        params = {"entity": entity, **(filters or {})}
        try:
            response = self._client.get(self.credentials.record_path, params=params, headers=auth.headers)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaError(str(exc)) from exc

    def get_records(self, entity: str, **kwargs: Any) -> Any:
        return self.load_records(entity, kwargs or None)

    def get_record(self, entity: str, record_id: str, **kwargs: Any) -> Any:
        records = self.load_records(entity, {"id": record_id, **kwargs})
        return records

    def create_record(self, entity: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        return self.save_record(entity, payload)

    def update_record(self, entity: str, record_id: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        body = {"id": record_id, "payload": payload, **kwargs}
        return self.save_record(entity, body)

    def upsert_record(self, entity: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        body = {"entity": entity, "payload": payload, **kwargs}
        return self.save_record(entity, body)

    def delete_record(self, entity: str, record_id: str, **kwargs: Any) -> Any:
        auth = self.authenticate()
        try:
            response = self._client.request(
                "DELETE",
                self.credentials.record_path,
                json={"entity": entity, "id": record_id, **kwargs},
                headers=auth.headers,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaError(str(exc)) from exc

    def execute_raw(self, statement: str, **kwargs: Any) -> Any:
        auth = self.authenticate()
        body = {"statement": statement, **kwargs}
        try:
            response = self._client.post(self.credentials.query_path, json=body, headers=auth.headers)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaError(str(exc)) from exc

    def get_capabilities(self) -> ConnectorCapabilities:
        return self.default_capabilities()

    def normalize_error(self, error: Exception) -> dict[str, Any]:
        if isinstance(error, SankhyaTimeoutError):
            category = "timeout_error"
        elif isinstance(error, SankhyaAuthenticationError):
            category = "authentication_error"
        elif isinstance(error, SankhyaRateLimitError):
            category = "rate_limit_error"
        elif isinstance(error, SankhyaError):
            category = "external_api_error"
        else:
            category = "unknown_error"
        return {"category": category, "message": str(error)}

    def _map_http_error(self, exc: httpx.HTTPStatusError) -> SankhyaError:
        status_code = exc.response.status_code
        if status_code in (401, 403):
            return SankhyaAuthenticationError(f"Sankhya authentication failed: {status_code}")
        if status_code == 429:
            return SankhyaRateLimitError("Sankhya rate limit reached")
        if status_code >= 500:
            return SankhyaError(f"Sankhya server error: {status_code}")
        return SankhyaError(f"Sankhya request failed: {status_code}")

    def close(self) -> None:
        self._client.close()
