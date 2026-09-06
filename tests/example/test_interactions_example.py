"""까다로운 상호작용 예제 - Popup / 새 탭 / iframe / Dialog / Upload / Download / API 대기.

``utils/interactions.py`` 와 ``utils/assertions.py`` 를 실제로 어떻게 쓰는지 보여줍니다.
화면은 ``set_content`` 로 직접 만들기 때문에 특정 사이트 구조에 의존하지 않고,
새 프로젝트에서 그대로 복사해 쓸 수 있습니다.

    pytest tests/example/test_interactions_example.py -v
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from utils.assertions import (
    should_be_visible,
    should_contain_text,
    should_have_count,
    should_have_status,
    should_have_text,
)
from utils.data_loader import data_path
from utils.interactions import (
    download_file,
    frame,
    handle_dialog,
    open_new_tab,
    open_popup,
    wait_for_response,
)
from utils.steps import test_step


@pytest.fixture
def blank_page(page: Page, run_config) -> Page:
    """set_content 로 화면을 그리기 전에 실제 origin 을 잡아둡니다.

    about:blank 상태에서는 iframe/다운로드 같은 기능이 브라우저 정책에 막힐 수 있습니다.
    """
    page.goto(run_config.base_url or "https://example.com/")
    return page


# ----------------------------------------------------------------------
# Dialog (alert / confirm / prompt)
# ----------------------------------------------------------------------
@pytest.mark.tc_id("INT001")
@pytest.mark.category("Interaction")
def test_confirm_dialog(blank_page: Page) -> None:
    """확인 창(confirm)을 수락하고 메시지를 검증한다"""
    blank_page.set_content("""
        <button id="del">삭제</button>
        <p id="result">대기</p>
        <script>
          document.getElementById('del').onclick = () => {
            document.getElementById('result').textContent =
              confirm('정말 삭제할까요?') ? '삭제됨' : '취소됨';
          };
        </script>
    """)

    with test_step("삭제 버튼 클릭 후 확인 창 수락"):
        with handle_dialog(blank_page, accept=True) as messages:
            blank_page.get_by_role("button", name="삭제").click()

    with test_step("확인 창 문구와 처리 결과 검증"):
        assert messages == ["정말 삭제할까요?"]
        should_have_text(blank_page.locator("#result"), "삭제됨", "처리 결과")


# ----------------------------------------------------------------------
# 새 탭 / Popup
# ----------------------------------------------------------------------
@pytest.mark.tc_id("INT002")
@pytest.mark.category("Interaction")
def test_new_tab_and_popup(blank_page: Page, run_config) -> None:
    """target=_blank 새 탭과 window.open Popup 을 각각 받아온다"""
    url = run_config.base_url
    blank_page.set_content(f"""
        <a id="tab" href="{url}" target="_blank">새 탭으로 열기</a>
        <button id="pop">팝업 열기</button>
        <script>
          document.getElementById('pop').onclick = () => {{
            const w = window.open('', '_blank', 'width=400,height=300');
            w.document.write('<h1>약관 안내</h1>');
            w.document.close();
          }};
        </script>
    """)

    with test_step("target=_blank 링크로 새 탭 열기"):
        new_tab = open_new_tab(
            blank_page, lambda: blank_page.get_by_role("link", name="새 탭으로 열기").click()
        )
        # 사이트가 #/ 같은 경로로 리다이렉트할 수 있어 앞부분만 확인합니다.
        expect(new_tab).to_have_url(re.compile("^" + re.escape(url)))
        new_tab.close()

    with test_step("window.open 으로 Popup 열기"):
        popup = open_popup(blank_page, lambda: blank_page.get_by_role("button", name="팝업 열기").click())
        should_be_visible(popup.get_by_role("heading", name="약관 안내"), "팝업 제목")
        popup.close()


# ----------------------------------------------------------------------
# iframe
# ----------------------------------------------------------------------
@pytest.mark.tc_id("INT003")
@pytest.mark.category("Interaction")
def test_iframe_input(blank_page: Page) -> None:
    """iframe 안의 입력 요소를 다룬다"""
    inner = "<label for='card'>카드번호</label><input id='card'>"
    blank_page.set_content(f"""
        <iframe id="payment" srcdoc="{inner}" width="400" height="200"></iframe>
    """)

    with test_step("iframe 안 카드번호 입력"):
        payment = frame(blank_page, "#payment")
        payment.get_by_label("카드번호").fill("4111111111111111")

    with test_step("입력값 검증"):
        expect(payment.get_by_label("카드번호")).to_have_value("4111111111111111")


# ----------------------------------------------------------------------
# 파일 업로드
# ----------------------------------------------------------------------
@pytest.mark.tc_id("INT004")
@pytest.mark.category("Interaction")
def test_file_upload(blank_page: Page) -> None:
    """file input 에 파일을 올린다"""
    blank_page.set_content("""
        <label for="attach">첨부파일</label>
        <input id="attach" type="file">
        <ul id="names"></ul>
        <script>
          document.getElementById('attach').onchange = (e) => {
            document.getElementById('names').innerHTML =
              [...e.target.files].map(f => `<li>${f.name}</li>`).join('');
          };
        </script>
    """)

    with test_step("파일 선택"):
        blank_page.get_by_label("첨부파일").set_input_files(str(data_path("products.json")))

    with test_step("업로드된 파일명 확인"):
        should_have_count(blank_page.locator("#names li"), 1, "첨부 목록")
        should_contain_text(blank_page.locator("#names"), "products.json", "첨부 파일명")


# ----------------------------------------------------------------------
# 다운로드
# ----------------------------------------------------------------------
@pytest.mark.tc_id("INT005")
@pytest.mark.category("Interaction")
def test_download(blank_page: Page, tmp_path) -> None:
    """다운로드를 받아 파일로 저장한다"""
    blank_page.set_content("""
        <a id="dl" download="report.csv"
           href="data:text/csv;charset=utf-8,id%2Cname%0A1%2C%ED%85%8C%EC%8A%A4%ED%8A%B8">
          엑셀 다운로드
        </a>
    """)

    with test_step("다운로드 버튼 클릭 후 저장"):
        saved = download_file(
            blank_page,
            lambda: blank_page.get_by_role("link", name="엑셀 다운로드").click(),
            save_dir=tmp_path,
        )

    with test_step("저장된 파일 내용 확인"):
        assert saved.name == "report.csv"
        assert "테스트" in saved.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# API 응답 대기
# ----------------------------------------------------------------------
@pytest.mark.tc_id("INT006")
@pytest.mark.category("Interaction")
def test_wait_for_api_response(blank_page: Page) -> None:
    """버튼을 눌렀을 때 오는 API 응답을 기다린다

    route 로 응답을 가짜로 만들어서 서버 상태와 무관하게 항상 같은 결과를 얻습니다.
    실제 프로젝트에서는 route 없이 진짜 API 를 기다리면 됩니다.
    """
    blank_page.route("**/api/orders",
                     lambda route: route.fulfill(status=201, json={"id": 1001}))
    blank_page.set_content("""
        <button id="order">주문</button>
        <p id="msg">대기</p>
        <script>
          document.getElementById('order').onclick = async () => {
            const res = await fetch('/api/orders', {method: 'POST'});
            const body = await res.json();
            document.getElementById('msg').textContent = '주문번호 ' + body.id;
          };
        </script>
    """)

    with test_step("주문 버튼 클릭 후 응답 대기"):
        response = wait_for_response(
            blank_page, "**/api/orders",
            lambda: blank_page.get_by_role("button", name="주문").click(),
        )

    with test_step("응답 상태와 화면 반영 확인"):
        should_have_status(response, 201)
        should_have_text(blank_page.locator("#msg"), "주문번호 1001", "주문 결과")
