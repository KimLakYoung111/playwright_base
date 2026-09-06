"""여러 화면에서 반복되는 UI 조각(Component) 패키지.

헤더, 좌측 메뉴, 페이징, 모달, 그리드처럼 화면마다 다시 쓰이는 영역은
Page Object 가 아니라 Component 로 만들어 재사용합니다.
"""

from components.base_component import BaseComponent

__all__ = ["BaseComponent"]
