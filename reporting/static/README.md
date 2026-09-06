# reporting/static

Custom Report 에 넣을 정적 파일 자리입니다.

현재 `templates/report.html` 은 CSS/JS 를 모두 안에 담고 있어서
**리포트 파일 하나만 메일로 보내도 그대로 열립니다.** 그래서 이 폴더는 비어 있습니다.

여기에 파일을 두는 경우

- 고객사 로고 (`logo.png`)
- 공통 스타일을 여러 템플릿에서 나눠 쓸 때 (`report.css`)
- 사내 폰트

사용하려면 `reporting/report_generator.py` 의 `render_html()` 에서
이 폴더를 `artifacts/<run_id>/report/static/` 으로 복사한 뒤
템플릿에서 `static/logo.png` 로 참조하세요.

```python
import shutil
shutil.copytree(Path(__file__).parent / "static",
                path.parent / "static", dirs_exist_ok=True)
```
