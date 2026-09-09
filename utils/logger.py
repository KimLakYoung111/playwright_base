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

MASK = "***"


def _mask_url_credentials(match: re.Match) -> str:
    """URL userinfo 를 가립니다. 콜론 유무로 판단이 갈립니다.

    ``https://admin:pw@host`` 처럼 콜론이 있으면 앞은 정의상 사용자명이므로
    남기고 뒤만 가립니다. 사용자명은 비밀이 아니고, 남겨야 어느 계정으로
    돌렸는지 알 수 있습니다.

    콜론이 없으면 그 한 덩어리가 사용자명인지 토큰인지 **구분할 수 없습니다**.
    ``https://ghp_xxx@github.com/...`` 이 GitHub PAT 의 표준 형태입니다.
    구분이 안 되면 가리는 쪽으로 실패해야 합니다 — 안 가려서 토큰이 고객사
    리포트로 나가는 손해가, 사용자명을 못 보는 손해보다 큽니다.
    """
    scheme, user, password = match.group(1), match.group(2), match.group(3)
    if password is None:
        return f"{scheme}{MASK}@"
    return f"{scheme}{user}:{MASK}@"


#: 비밀을 가리키는 키 이름. key=value 형태와 ``--key value`` 형태가 함께 씁니다.
#:
#: **흔한 낱말을 넣지 마세요.** ``auth`` 하나를 넣었더니 ``GET /auth: 200 OK`` 가
#: ``GET /auth: *** OK`` 가 되고 ``--auth-file conf.yaml`` 의 파일명까지 사라졌습니다.
#: 가려서 얻는 것보다 로그를 읽을 수 없게 되는 손해가 큽니다.
_SECRET_KEYS = (r"password|passwd|pwd|token|secret|api[_-]?key|"
                r"authorization|auth[_-]?token")

#: HTTP 인증 스킴. 스킴 이름은 비밀이 아니므로 남기고 뒤의 자격증명만 가립니다.
_AUTH_SCHEMES = r"bearer|basic|digest"

#: 값 자체를 몰라도 잡아내는 패턴. (정규식, 치환식) 쌍입니다.
#: 치환식은 문자열도 함수도 됩니다 (``re.sub`` 규칙 그대로).
#:
#: **스킴은 key=value 패턴 *안에서* 처리합니다.** 예전에는 값이 스킴 이름이면
#: key=value 가 비켜서고 뒤의 스킴 패턴에 넘기게 했는데, 스킴 패턴은 "공백 +
#: 8자 이상 토큰" 을 요구하므로 ``password=basic`` 이나
#: ``Authorization: Bearer abc123`` 은 **아무도 안 잡아** 원문이 그대로 나갔습니다.
#: 한 패턴이 스킴까지 함께 보면 이 구멍이 생길 수 없습니다.
_SECRET_PATTERNS = [
    # key=value / "key": "value" / {'key': 'value'}
    #  값 앞에 인증 스킴이 붙어 있으면(``Authorization: Bearer <토큰>``) 스킴은
    #  남기고 뒤만 가립니다. 어느 인증 방식이었는지는 비밀이 아니고 디버깅에 씁니다.
    (re.compile(r"(?i)\b(" + _SECRET_KEYS + r")"
                r"(['\"]?\s*[:=]\s*['\"]?)"
                r"((?:" + _AUTH_SCHEMES + r")[ \t]+)?"
                r"([^\s'\",;}]+)"),
     r"\1\2\3" + MASK),
    # 키 없이 헤더 값만 있는 경우 (``Bearer <토큰>``).
    #  Base64 는 +, /, = 를 쓰므로 문자 집합에 넣습니다. 길이 하한은 "basic auth"
    #  같은 평범한 문장을 건드리지 않기 위한 것입니다 — 키가 붙은 형태는 위
    #  패턴이 길이와 무관하게 이미 잡습니다.
    (re.compile(r"(?i)\b(" + _AUTH_SCHEMES + r")[ \t]+([A-Za-z0-9._\-+/=]{8,})"),
     r"\1 " + MASK),
    # 공백으로 값을 넘기는 명령행 플래그 (--password hunter2).
    #  ``--password=hunter2`` 는 위 key=value 가 잡지만 공백 형태는 못 잡습니다.
    #  실행 명령은 result.json / report.html 로 고객사에 전달됩니다.
    #  경계 셋이 전부 필요합니다:
    #   (?<![\w-])  앞이 낱말이면 하이픈이 아니라 낱말의 일부다 (next-line-token)
    #   [ \t]+      줄바꿈을 넘으면 다음 *줄*의 첫 토큰을 지운다
    #   (?!-)       뒤따르는 것이 값이 아니라 다른 플래그면 가릴 이유가 없다
    #  "가리는 쪽으로 실패" 는 **값**에 대한 원칙입니다. 플래그를 가려도 보안
    #  이득은 0 이고 실행 명령만 읽을 수 없게 됩니다.
    (re.compile(r"(?i)(?<![\w-])(--?(?:" + _SECRET_KEYS + r"))\b([ \t]+)(?!-)(\S+)"),
     r"\1\2" + MASK),
    # URL 에 박은 자격증명. key=value 가 아니라서 위 패턴에 안 걸리는데,
    # --base-url 로 넘기면 실행 명령에 그대로 남아 고객사에 전달하는
    # result.json / report.html 까지 따라갑니다. 세 형태를 모두 잡습니다:
    #   https://user:pw@host   https://token@host   https://:pw@host
    (re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)([^/\s:@]*)(?::([^/\s@]*))?@"),
     _mask_url_credentials),
]

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
        for pattern, replacement in _SECRET_PATTERNS:
            text = pattern.sub(replacement, text)
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
