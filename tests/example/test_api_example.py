"""API 예제.

UI 테스트의 사전조건/사후처리를 API 로 처리하는 방법을 보여줍니다.
Browser 를 띄우지 않으므로 훨씬 빠릅니다.

    pytest -m api

여기서는 공개 테스트 API(jsonplaceholder)를 씁니다.
실제 프로젝트에서는 ``ApiClient`` 를 상속해 업무 API 를 메서드로 정리하세요.

    class OrderApi(ApiClient):
        def create_order(self, product_id):
            return self.json(self.expect_ok(
                self.post("/orders", json={"productId": product_id}), 201))
"""

from __future__ import annotations

import os

import pytest

from api.api_client import ApiClient
from utils.steps import test_step


@pytest.fixture
def api(run_config) -> ApiClient:
    """설정의 api_base_url 로 만들어진 클라이언트."""
    with ApiClient(base_url=run_config.api_base_url) as client:
        if os.getenv("API_TOKEN"):
            client.set_token(os.environ["API_TOKEN"])   # 토큰이 있으면 붙입니다
        yield client


@pytest.mark.api
@pytest.mark.tc_id("API001")
@pytest.mark.category("Api")
def test_api_get_works(api: ApiClient) -> None:
    """API 로 데이터를 조회한다"""
    with test_step("todos/1 조회"):
        response = api.expect_ok(api.get("/todos/1"), 200)

    with test_step("응답 본문 확인"):
        body = api.json(response)
        assert body["id"] == 1
        assert "title" in body


@pytest.mark.api
@pytest.mark.tc_id("API002")
@pytest.mark.category("Api")
def test_api_crud_flow(api: ApiClient) -> None:
    """생성 → 전체수정 → 부분수정 → 삭제 (사전조건 생성 / Cleanup 패턴)

    jsonplaceholder 는 흉내만 내는 공개 API 라 POST 로 만든 자원이 실제로
    저장되지는 않습니다. 그래서 수정/삭제는 미리 있는 자원(1번)에 합니다.
    실제 프로젝트에서는 POST 가 돌려준 id 를 그대로 이어서 쓰면 됩니다.
    """
    payload = {"title": "자동화 사전조건", "body": "테스트용", "userId": 1}
    target_id = 1

    with test_step("POST 로 생성"):
        created = api.json(api.expect_ok(api.post("/posts", json=payload), 201))
        assert created["title"] == payload["title"]
        assert created["id"]

    try:
        with test_step("PUT 으로 전체 수정"):
            updated = api.json(api.expect_ok(
                api.put(f"/posts/{target_id}", json={**payload, "title": "수정됨"}), 200))
            assert updated["title"] == "수정됨"

        with test_step("PATCH 로 일부만 수정"):
            patched = api.json(api.expect_ok(
                api.patch(f"/posts/{target_id}", json={"body": "부분 수정"}), 200))
            assert patched["body"] == "부분 수정"
    finally:
        # Cleanup 은 앞 단계가 실패해도 반드시 돌아야 다음 테스트가 깨끗합니다.
        with test_step("DELETE 로 정리"):
            api.expect_ok(api.delete(f"/posts/{target_id}"), (200, 204))


@pytest.mark.api
@pytest.mark.tc_id("API003")
@pytest.mark.category("Api")
def test_api_error_message_is_useful(api: ApiClient) -> None:
    """상태코드가 다르면 원인 파악에 필요한 정보가 에러에 담긴다"""
    with test_step("없는 경로를 일부러 200 으로 기대"):
        with pytest.raises(AssertionError) as error:
            api.expect_ok(api.get("/이런경로는없음"), 200)

    with test_step("에러 메시지에 요청/기대/실제/본문이 들어있는지 확인"):
        message = str(error.value)
        for keyword in ("요청", "기대", "실제", "본문"):
            assert keyword in message
