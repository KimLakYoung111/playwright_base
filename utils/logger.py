"""공통 로깅.

- Console 과 파일(artifacts/<run_id>/logs/run.log) 양쪽에 기록합니다.
- 비밀번호/토큰 같은 민감정보는 자동으로 ``***`` 로 가립니다.
  메시지뿐 아니라 **예외 traceback 까지** 가립니다.
- 테스트 하나하나의 로그도 따로 모아 두었다가 실패 시 Evidence 로 저장합니다.

리포트(result.json / report.html)에 들어가는 문자열도 같은 규칙으로 가려야 하므로
``mask_secrets()`` 를 공개 함수로 제공합니다. reporting 쪽에서 이 함수를 씁니다.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOGGER_NAME = "automation"

#: 값 자체를 몰라도 잡아내는 패턴 (key=value / "key": "value" 형태)
_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key|authorization)"
               r"(\"?\s*[:=]\s*\"?)([^\s\",;}]+)"),
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._\-]{8,})"),
]

MASK = "***"

#: exc_text 를 만들 때 쓰는 포맷터 (핸들러와 무관하게 동작해야 해서 따로 둡니다)
_EXC_FORMATTER = logging.Formatter()


class SensitiveDataFilter(logging.Filter):
    """로그 레코드에서 민감정보를 가립니다.

    핸들러에 붙여서 씁니다. 레코드 자체를 고치기 때문에 같은 레코드를 받는
    모든 핸들러가 가려진 값을 보게 됩니다.
    """

    def __init__(self) -> None:
        super().__init__()
        self._literals: set[str] = set()

    def register(self, *values: str) -> None:
        """설정에서 읽은 실제 비밀번호/토큰 값을 등록합니다."""
        for value in values:
            if value and len(value) >= 4:
                self._literals.add(value)

    def mask(self, text: str) -> str:
        """등록된 값과 패턴을 모두 가린 문자열을 돌려줍니다."""
        if not text:
            return text
        for literal in self._literals:
            if literal in text:
                text = text.replace(literal, MASK)
        text = _SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)
        text = _SECRET_PATTERNS[1].sub(lambda m: f"{m.group(1)} {MASK}", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = self.mask(str(record.getMessage()))
            record.args = ()          # 이미 포맷했으므로 args 는 비웁니다.

            # traceback 도 가립니다.
            # exc_text 를 미리 채워두면 이후 어떤 Formatter 도 이 값을 그대로 씁니다.
            if record.exc_info and not record.exc_text:
                record.exc_text = _EXC_FORMATTER.formatException(record.exc_info)
            if record.exc_text:
                record.exc_text = self.mask(record.exc_text)
            if record.stack_info:
                record.stack_info = self.mask(record.stack_info)
        except Exception:             # 로깅 때문에 테스트가 죽으면 안 됩니다.
            pass
        return True


class TestLogCapture(logging.Handler):
    """테스트 하나 동안의 로그를 메모리에 모아 두는 핸들러."""

    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        self._lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._lines.append(self.format(record))
        except Exception:
            pass

    def start(self) -> None:
        self._lines.clear()

    @property
    def text(self) -> str:
        return "\n".join(self._lines)

    def dump(self, path: Path) -> Path | None:
        if not self._lines:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.text + "\n", encoding="utf-8")
        return path


#: 전역 인스턴스 (conftest 가 사용)
sensitive_filter = SensitiveDataFilter()
test_log_capture = TestLogCapture()


def mask_secrets(text: str) -> str:
    """로그가 아닌 곳(리포트 등)에서도 같은 규칙으로 민감정보를 가릴 때 씁니다."""
    return sensitive_filter.mask(text) if isinstance(text, str) else text


def setup_logging(log_file: Path, level: int = logging.INFO,
                  prefix: str = "") -> logging.Logger:
    """세션 로거를 구성합니다. 실행마다 새 로그 파일이 만들어집니다.

    ``prefix`` 는 xdist 워커 구분용입니다. 예) "[gw0] "
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):     # 재실행/재구성 대비
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(f"[%(asctime)s] [%(levelname)s] {prefix}%(message)s",
                                  DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(level)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    # 워커가 여러 개여도 같은 파일에 안전하게 덧붙이도록 append 모드
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    test_log_capture.setFormatter(formatter)
    test_log_capture.setLevel(logging.DEBUG)

    # 필터는 핸들러에 붙입니다. 로거에 붙이면 하위 로거(automation.pages.*)의
    # 레코드에는 적용되지 않아 민감정보가 새어나갈 수 있습니다.
    for handler in (console, file_handler, test_log_capture):
        handler.addFilter(sensitive_filter)
        logger.addHandler(handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """페이지 객체/테스트에서 쓰는 로거."""
    return logging.getLogger(LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}")
