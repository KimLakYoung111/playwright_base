"""가벼운 REST 클라이언트.

용도
----
- UI 테스트 사전조건 만들기 (테스트 데이터 생성, 로그인 토큰 발급)
- 테스트 종료 후 Cleanup (만든 데이터 삭제)
- 간단한 API 검증

Base 에서는 최소한만 제공합니다. 프로젝트에서는 이 클래스를 상속해
업무 API 를 메서드로 추가하세요.

    class OrderApi(ApiClient):
        def create_order(self, product_id):
            return self.post("/orders", json={"productId": product_id}).json()
"""

from __future__ import annotations

from typing import Any

import requests

from utils.logger import get_logger

logger = get_logger("api")


class ApiClient:
    def __init__(self, base_url: str = "", token: str | None = None,
                 timeout: float = 30.0, verify: bool = True) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify
        self.session.headers.update({"Accept": "application/json"})
        if token:
            self.set_token(token)

    # ------------------------------------------------------------------
    def set_token(self, token: str) -> "ApiClient":
        self.session.headers["Authorization"] = f"Bearer {token}"
        return self

    def url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = self.url(path)
        kwargs.setdefault("timeout", self.timeout)
        logger.info("API %s %s", method.upper(), url)
        response = self.session.request(method, url, **kwargs)
        logger.info("API %s %s -> %s (%.0fms)", method.upper(), url,
                    response.status_code, response.elapsed.total_seconds() * 1000)
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    # ------------------------------------------------------------------
    def expect_ok(self, response: requests.Response,
                  expected: int | tuple[int, ...] = (200, 201, 204)) -> requests.Response:
        """상태코드를 확인하고, 다르면 원인 파악에 필요한 정보를 함께 보여줍니다."""
        allowed = (expected,) if isinstance(expected, int) else expected
        if response.status_code not in allowed:
            raise AssertionError(
                f"API 응답 상태가 예상과 다릅니다.\n"
                f"  요청 : {response.request.method} {response.url}\n"
                f"  기대 : {allowed}\n"
                f"  실제 : {response.status_code}\n"
                f"  본문 : {response.text[:500]}"
            )
        return response

    def json(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            raise AssertionError(
                f"JSON 응답이 아닙니다: {response.status_code} {response.text[:200]}"
            ) from None

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
