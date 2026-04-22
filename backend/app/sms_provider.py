import base64
import hashlib
import hmac
import json
import time
from typing import Any

import httpx


class NcloudApiClient:
    def __init__(
        self,
        *,
        access_key: str,
        secret_key: str,
        base_url: str,
    ) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")

    def _signature(self, method: str, uri: str, timestamp: str) -> str:
        message = f"{method} {uri}\n{timestamp}\n{self.access_key}"
        digest = hmac.new(self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _headers(self, method: str, uri: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        return {
            "Content-Type": "application/json; charset=utf-8",
            "x-ncp-apigw-timestamp": timestamp,
            "x-ncp-iam-access-key": self.access_key,
            "x-ncp-apigw-signature-v2": self._signature(method, uri, timestamp),
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query_string = str(httpx.QueryParams(params or {}))
        uri = path if not query_string else f"{path}?{query_string}"
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            params=params,
            json=json_body,
            headers=self._headers(method, uri),
            timeout=20.0,
        )
        if response.status_code >= 400:
            message = response.text
            try:
                data = response.json()
                if isinstance(data, dict):
                    message = str(data.get("message") or data.get("errorMessage") or data.get("returnMessage") or data.get("error") or message)
            except json.JSONDecodeError:
                pass
            raise RuntimeError(message or "Ncloud API 요청이 실패했습니다.")
        return response.json()


class NaverSensSmsProvider(NcloudApiClient):
    def __init__(
        self,
        *,
        service_id: str,
        access_key: str,
        secret_key: str,
        from_number: str,
        base_url: str = "https://sens.apigw.ntruss.com",
    ) -> None:
        super().__init__(access_key=access_key, secret_key=secret_key, base_url=base_url)
        self.service_id = service_id
        self.from_number = from_number

    def send_messages(
        self,
        *,
        recipients: list[str],
        content: str,
        title: str | None,
        content_type: str,
        message_type: str,
    ) -> dict[str, Any]:
        path = f"/sms/v2/services/{self.service_id}/messages"
        body: dict[str, Any] = {
            "type": message_type,
            "contentType": content_type,
            "countryCode": "82",
            "from": self.from_number,
            "content": content,
            "messages": [{"to": phone} for phone in recipients],
        }
        if message_type == "LMS":
            body["subject"] = title or ""
        return self._request("POST", path, json_body=body)

    def list_messages(self, *, request_id: str, page_size: int = 100, page_index: int = 0, next_token: str | None = None) -> dict[str, Any]:
        path = f"/sms/v2/services/{self.service_id}/messages"
        params: dict[str, Any] = {
            "requestId": request_id,
            "pageSize": page_size,
            "pageIndex": page_index,
        }
        if next_token:
            params["nextToken"] = next_token
        return self._request("GET", path, params=params)

    def get_message(self, *, message_id: str) -> dict[str, Any]:
        path = f"/sms/v2/services/{self.service_id}/messages/{message_id}"
        return self._request("GET", path)


class NcloudBillingClient(NcloudApiClient):
    def __init__(
        self,
        *,
        access_key: str,
        secret_key: str,
        base_url: str = "https://billingapi.apigw.ntruss.com",
    ) -> None:
        super().__init__(access_key=access_key, secret_key=secret_key, base_url=base_url)

    def get_product_demand_cost_list(self, *, start_month: str, end_month: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/billing/v1/cost/getProductDemandCostList",
            params={"startMonth": start_month, "endMonth": end_month, "responseFormatType": "json"},
        )
