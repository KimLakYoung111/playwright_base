"""BasePage 공통 메서드 사용 예제.

`pages/base_page.py` 가 제공하는 동작을 한 파일에서 전부 보여주고 검증합니다.
화면은 ``set_content`` 로 직접 만들어서 특정 사이트에 의존하지 않습니다.

> 여기서는 기능 확인이 목적이라 ``BasePage`` 를 그대로 인스턴스화했습니다.
> **실제 프로젝트에서는 화면마다 ``BasePage`` 를 상속한 Page Object 를 만드세요.**
> (README 8장 참고)

    pytest tests/example/test_base_page_example.py -v
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from pages.base_page import BasePage
from utils.data_loader import data_path
from utils.steps import test_step

FORM_HTML = """
<style>
  #tip { display: none; color: green; }
  #hover-target:hover + #tip { display: block; }
  .spacer { height: 1200px; background: #fafafa; }
</style>

<label for="keyword">검색어</label>
<input id="keyword" placeholder="검색어 입력">

<label for="grade">등급</label>
<select id="grade">
  <option value="basic">일반</option>
  <option value="vip">우수</option>
  <option value="vvip">최우수</option>
</select>

<label for="agree">약관 동의</label>
<input id="agree" type="checkbox">

<label for="attach">첨부파일</label>
<input id="attach" type="file">
<span id="attached"></span>

<button id="hover-target">도움말</button>
<span id="tip">마우스를 올리면 보입니다</span>

<button id="load">불러오기</button>
<span id="spinner" hidden>불러오는 중...</span>
<ul id="rows"></ul>

<div class="spacer"></div>
<p id="footer-note">맨 아래 안내문</p>

<script>
  document.getElementById('attach').onchange = (e) => {
    document.getElementById('attached').textContent = e.target.files[0].name;
  };
  document.getElementById('load').onclick = () => {
    const spinner = document.getElementById('spinner');
    spinner.hidden = false;
    setTimeout(() => {
      spinner.hidden = true;
      document.getElementById('rows').innerHTML =
        ['첫째 줄', '둘째 줄', '셋째 줄'].map(t => `<li>${t}</li>`).join('');
    }, 400);
  };
</script>
"""


@pytest.fixture
def form(page: Page, run_config) -> BasePage:
    """샘플 폼 화면을 띄운 BasePage."""
    page.goto(run_config.base_url)      # set_content 전에 실제 origin 을 잡아둡니다
    page.set_content(FORM_HTML)
    return BasePage(page)


@pytest.mark.tc_id("BP001")
@pytest.mark.category("BasePage")
def test_input_and_select(form: BasePage) -> None:
    """입력 / 한 글자씩 입력 / 선택 / 체크박스"""
    with test_step("fill 로 입력하고 값 확인"):
        form.fill("#keyword", "자동화")
        assert form.get_value("#keyword") == "자동화"

    with test_step("type_text 로 한 글자씩 입력"):
        form.fill("#keyword", "")
        form.type_text("#keyword", "타자", delay=10)
        assert form.get_value("#keyword") == "타자"

    with test_step("select_option 으로 등급 선택"):
        assert form.select_option("#grade", "vip") == ["vip"]

    with test_step("체크박스 켜고 끄기"):
        form.check("#agree")
        assert form.is_visible("#agree")
        form.check("#agree", checked=False)


@pytest.mark.tc_id("BP002")
@pytest.mark.category("BasePage")
def test_hover_scroll_upload(form: BasePage) -> None:
    """hover / scroll / 파일 업로드"""
    with test_step("hover 하면 숨겨진 안내가 보인다"):
        form.wait_for_hidden("#tip")
        form.hover("#hover-target")
        form.wait_for_visible("#tip")

    with test_step("맨 아래 요소로 스크롤"):
        form.scroll_to("#footer-note")
        assert form.get_text("#footer-note") == "맨 아래 안내문"

    with test_step("파일 업로드"):
        form.upload_file("#attach", data_path("sample.pdf"))
        assert form.get_text("#attached") == "sample.pdf"


@pytest.mark.tc_id("BP003")
@pytest.mark.category("BasePage")
def test_wait_and_read(form: BasePage) -> None:
    """나타났다 사라지는 요소 기다리기 / 목록 읽기"""
    with test_step("불러오기 클릭"):
        form.click("#load")

    with test_step("스피너가 떴다가 사라질 때까지 대기"):
        form.wait_for_visible("#spinner")
        form.wait_for_hidden("#spinner")

    with test_step("목록 내용과 개수 확인"):
        assert form.count("#rows li") == 3
        assert form.get_texts("#rows li") == ["첫째 줄", "둘째 줄", "셋째 줄"]


@pytest.mark.tc_id("BP004")
@pytest.mark.category("BasePage")
def test_navigation_and_screenshot(page: Page, run_config, tmp_path) -> None:
    """goto / reload / 수동 스크린샷"""
    base = BasePage(page)

    with test_step("절대 URL 로 이동"):
        base.goto(run_config.base_url)
        expect(page.get_by_placeholder("What needs to be done?")).to_be_visible()

    with test_step("새로고침해도 화면이 유지된다"):
        base.reload()
        assert base.is_visible("input.new-todo") or base.count("input") > 0
        assert base.title

    with test_step("수동 스크린샷 저장"):
        saved = base.screenshot(tmp_path / "manual.png")
        assert saved.exists() and saved.stat().st_size > 0
