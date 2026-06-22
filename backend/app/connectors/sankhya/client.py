from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector, ConnectorCapabilities
from app.connectors.sankhya.auth import (
    build_auth_headers,
    build_auth_payload,
    build_auth_request_headers,
    build_auth_result,
)
from app.connectors.sankhya.exceptions import (
    SankhyaAuthenticationError,
    SankhyaAuthorizationError,
    SankhyaError,
    SankhyaExternalAPIError,
    SankhyaRateLimitError,
    SankhyaTimeoutError,
    SankhyaUnknownError,
    SankhyaValidationError,
)
from app.connectors.sankhya.mapper import (
    count_records,
    mask_payload_with_sensitive_fields,
    normalize_read_records_response,
)
from app.connectors.sankhya.schemas import (
    SankhyaAuthResult,
    SankhyaConnectionTestResult,
    SankhyaCredentials,
    SankhyaReadOperationConfig,
    SankhyaReadOperationResult,
)
from app.connectors.sankhya.schemas import (
    SankhyaError as SankhyaErrorSchema,
)
from app.core.config import get_settings
from app.core.security import mask_payload


class SankhyaClient(BaseConnector):
    def __init__(self, credentials: SankhyaCredentials, client: httpx.Client | None = None) -> None:
        self.credentials = credentials
        self._client = client or httpx.Client(
            base_url=str(credentials.base_url),
            timeout=credentials.timeout_seconds,
            verify=credentials.verify_ssl,
        )
        self._auth_result: SankhyaAuthResult | None = None

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

    def authenticate(self, force_refresh: bool = False) -> SankhyaAuthResult:
        if not force_refresh and self._auth_result is not None and not self._token_expired(self._auth_result):
            return self._auth_result
        if self.credentials.auth_mode == "legacy_appkey_token":
            auth_result = self._authenticate_legacy()
        else:
            auth_result = self._authenticate_oauth()
        self._auth_result = auth_result
        return auth_result

    def get_auth_headers(self) -> dict[str, str]:
        return self.authenticate().headers

    def test_connection(self, mode: str = "mock", read_check: bool = False) -> SankhyaConnectionTestResult:
        if mode not in {"mock", "real"}:
            raise SankhyaValidationError("Invalid connection test mode")
        if mode == "mock":
            return SankhyaConnectionTestResult(
                success=True,
                status_code=200,
                message="Mock connection successful",
                status="active",
                last_test_status="success",
                mode="mock",
                read_check=False,
                details={"mock": True},
            )

        auth = self.authenticate(force_refresh=False)
        details: dict[str, Any] = {
            "auth": {
                "authenticated": auth.authenticated,
                "token_type": auth.token_type,
                "expires_in": auth.expires_in,
            }
        }
        status_code = 200
        message = "Connection successful"

        if read_check:
            read_config = self._read_check_config()
            if read_config is not None:
                read_result = self.execute_read_operation(read_config.model_dump())
                details["read_check"] = mask_payload(read_result.model_dump())
                message = "Connection and read check successful"
            else:
                details["read_check"] = {"skipped": True, "reason": "missing_configuration"}

        return SankhyaConnectionTestResult(
            success=True,
            status_code=status_code,
            message=message,
            status="active",
            last_test_status="success",
            mode="real",
            read_check=read_check,
            details=details,
        )

    def load_records(
        self,
        entity_name: str,
        fields: list[str],
        criteria: dict[str, Any] | str | None = None,
        limit: int = 1,
    ) -> Any:
        raw_response = self._load_records_raw(entity_name, fields, criteria=criteria, limit=limit)
        return normalize_read_records_response(raw_response, fields=fields, limit=limit)

    def execute_read_operation(
        self,
        operation_config: dict[str, Any] | SankhyaReadOperationConfig,
        *,
        sensitive_fields: list[str] | tuple[str, ...] | None = None,
    ) -> SankhyaReadOperationResult:
        config = (
            operation_config
            if isinstance(operation_config, SankhyaReadOperationConfig)
            else SankhyaReadOperationConfig.model_validate(operation_config)
        )
        if config.mode == "mock":
            records = [
                {field: f"mock-{field.lower()}" for field in config.fields},
            ]
            return SankhyaReadOperationResult(
                success=True,
                operation=config.operation,
                mode="mock",
                entity_name=config.entity_name,
                fields=config.fields,
                criteria=config.criteria,
                limit=config.limit,
                records_count=len(records),
                records=records,
                raw_response_masked=mask_payload_with_sensitive_fields(
                    {"mock": True, "entity_name": config.entity_name},
                    sensitive_fields=sensitive_fields,
                ),
            )

        raw_response = self._load_records_raw(
            config.entity_name,
            config.fields,
            criteria=config.criteria,
            limit=config.limit,
        )
        records = normalize_read_records_response(
            raw_response,
            fields=config.fields,
            limit=config.limit,
            mask_sensitive_fields=False,
        )
        return SankhyaReadOperationResult(
            success=True,
            operation=config.operation,
            mode="real",
            entity_name=config.entity_name,
            fields=config.fields,
            criteria=config.criteria,
            limit=config.limit,
            records_count=count_records(raw_response),
            records=records,
            raw_response_masked=mask_payload_with_sensitive_fields(
                raw_response,
                sensitive_fields=sensitive_fields,
            ),
        )

    def _load_records_raw(
        self,
        entity_name: str,
        fields: list[str],
        criteria: dict[str, Any] | str | None = None,
        limit: int = 1,
    ) -> Any:
        auth = self.authenticate()
        payload: dict[str, Any] = {
            "serviceName": "CRUDServiceProvider.loadRecords",
            "requestBody": {
                "dataSet": {
                    "rootEntity": entity_name,
                    "ignoreCalculatedFields": "true",
                    "useFileBasedPagination": "true",
                    "includePresentationFields": "N",
                    "tryJoinedFields": "true",
                    "offsetPage": "0",
                    "entity": [
                        {
                            "path": "",
                            "fieldset": {"list": ", ".join(fields)},
                        }
                    ],
                }
            },
        }
        if criteria is not None:
            payload["requestBody"]["dataSet"]["criteria"] = self._build_criteria(criteria)
        try:
            response = self._client.post(
                self.credentials.gateway_path,
                params={"serviceName": "CRUDServiceProvider.loadRecords", "outputType": "json"},
                json=payload,
                headers=auth.headers,
            )
            response.raise_for_status()
            return self._parse_json_any(response)
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaUnknownError(str(exc)) from exc

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
            raise SankhyaUnknownError(str(exc)) from exc

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
            raise SankhyaUnknownError(str(exc)) from exc

    def get_records(self, entity: str, **kwargs: Any) -> Any:
        raw_fields = kwargs.pop("fields", [])
        if isinstance(raw_fields, str):
            fields = [raw_fields]
        else:
            fields = list(raw_fields or [])
        criteria = kwargs.pop("criteria", None)
        limit = int(kwargs.pop("limit", 1) or 1)
        if fields:
            return self.load_records(entity, fields, criteria=criteria, limit=limit)
        return self.load_records(entity, ["*"], criteria=criteria, limit=limit)

    def get_record(self, entity: str, record_id: str, **kwargs: Any) -> Any:
        return self.load_records(entity, kwargs.pop("fields", ["*"]), criteria={"id": record_id, **kwargs})

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
            raise SankhyaUnknownError(str(exc)) from exc

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
            raise SankhyaUnknownError(str(exc)) from exc

    def get_capabilities(self) -> ConnectorCapabilities:
        return self.default_capabilities()

    def normalize_error(self, error: Exception) -> dict[str, Any]:
        if isinstance(error, SankhyaError):
            schema = SankhyaErrorSchema(
                error_type=error.error_type,
                message=str(error),
                normalized_message=str(error),
                retryable=error.retryable,
                raw_error_masked=error.raw_error_masked,
                http_status_code=error.http_status_code,
            )
            return schema.model_dump()

        if isinstance(error, httpx.TimeoutException):
            schema = SankhyaErrorSchema(
                error_type="timeout_error",
                message=str(error),
                normalized_message="Sankhya request timed out",
                retryable=True,
                raw_error_masked={"error": "timeout"},
            )
            return schema.model_dump()

        if isinstance(error, httpx.HTTPStatusError):
            return self._normalize_http_status_error(error).model_dump()

        schema = SankhyaErrorSchema(
            error_type="unknown_error",
            message=str(error),
            normalized_message=str(error),
            retryable=False,
            raw_error_masked=mask_payload({"error": str(error)}),
        )
        return schema.model_dump()

    def _authenticate_oauth(self) -> SankhyaAuthResult:
        if not self.credentials.client_id or not self.credentials.client_secret or not self.credentials.x_token:
            raise SankhyaValidationError("Missing Sankhya OAuth credentials")

        try:
            response = self._client.post(
                self.credentials.auth_path,
                data=build_auth_payload(self.credentials),
                headers=build_auth_request_headers(self.credentials),
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SankhyaTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise SankhyaUnknownError(str(exc)) from exc

        data = self._parse_json_response(response)
        access_token = data.get("access_token") or data.get("token")
        if not access_token:
            raise SankhyaAuthenticationError("Sankhya did not return an access token")
        return build_auth_result(data, self.credentials)

    def _authenticate_legacy(self) -> SankhyaAuthResult:
        if not self.credentials.token:
            raise SankhyaValidationError("Missing legacy Sankhya token")
        return SankhyaAuthResult(
            access_token=self.credentials.token,
            authenticated=True,
            headers=build_auth_headers(self.credentials, self.credentials.token),
            raw_response_masked={"legacy": True, "mode": "appkey_token"},
        )

    def _parse_json_response(self, response: httpx.Response) -> dict[str, Any]:
        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError as exc:
            raise SankhyaExternalAPIError("Invalid JSON returned by Sankhya") from exc
        if isinstance(data, dict):
            return data
        raise SankhyaExternalAPIError("Unexpected response structure returned by Sankhya")

    def _parse_json_any(self, response: httpx.Response) -> Any:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise SankhyaExternalAPIError("Invalid JSON returned by Sankhya") from exc

    def _map_http_error(self, exc: httpx.HTTPStatusError) -> SankhyaError:
        response = exc.response
        status_code = response.status_code
        raw_error_masked = self._masked_response(response)
        message = self._message_from_response(response) or f"Sankhya request failed: {status_code}"
        if status_code == 401:
            return SankhyaAuthenticationError(message, http_status_code=status_code, raw_error_masked=raw_error_masked)
        if status_code == 403:
            return SankhyaAuthorizationError(message, http_status_code=status_code, raw_error_masked=raw_error_masked)
        if status_code == 429:
            return SankhyaRateLimitError(message, http_status_code=status_code, raw_error_masked=raw_error_masked)
        if status_code == 400:
            return SankhyaValidationError(message, http_status_code=status_code, raw_error_masked=raw_error_masked)
        if status_code >= 500:
            return SankhyaExternalAPIError(message, http_status_code=status_code, raw_error_masked=raw_error_masked)
        return SankhyaUnknownError(message, http_status_code=status_code, raw_error_masked=raw_error_masked)

    def _normalize_http_status_error(self, error: httpx.HTTPStatusError) -> SankhyaErrorSchema:
        mapped = self._map_http_error(error)
        return SankhyaErrorSchema(
            error_type=mapped.error_type,
            message=str(mapped),
            normalized_message=str(mapped),
            retryable=mapped.retryable,
            raw_error_masked=mapped.raw_error_masked,
            http_status_code=mapped.http_status_code,
        )

    def _token_expired(self, auth_result: SankhyaAuthResult) -> bool:
        if auth_result.expires_at is None:
            return False
        return auth_result.expires_at <= datetime.now(timezone.utc)

    def _masked_response(self, response: httpx.Response) -> dict[str, Any] | str:
        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError:
            return {"body": response.text[:500]}
        return mask_payload(data) if isinstance(data, dict) else {"body": mask_payload(data)}

    def _message_from_response(self, response: httpx.Response) -> str | None:
        if not response.content:
            return None
        try:
            data = response.json()
        except ValueError:
            return response.text[:500] or None
        if isinstance(data, dict):
            for key in ("message", "error", "error_description", "detail", "title"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return None

    def _build_criteria(self, criteria: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(criteria, dict):
            return criteria
        return {"expression": {"$": criteria}}

    def _read_check_config(self) -> SankhyaReadOperationConfig | None:
        settings = get_settings()
        entity = settings.sankhya_read_test_entity.strip()
        fields = settings.sankhya_read_test_fields_list
        if not entity or not fields:
            return None
        return SankhyaReadOperationConfig(
            entity_name=entity,
            fields=fields,
            limit=settings.sankhya_read_test_limit,
            mode="real",
        )

    def close(self) -> None:
        self._client.close()
