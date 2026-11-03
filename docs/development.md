# 코드 구조와 문서 관리

```text
mkdocs.yml                  문서 사이트 설정과 목차
src/pose_llm_classifier/     입력·전처리·시각화·분류·평가·API
scripts/                    6개 처리 CLI + 합성 데이터 생성기
data/sample/                JSON/JSONL/CSV 합성 데이터
tests/                      모델 없이 실행하는 테스트
docs/                       MkDocs Markdown과 예시 이미지
site/                       빌드 산출물 (Git 제외)
results/                    실행 결과 (Git 제외)
```

## 문서 로컬 실행

저장소 루트에서 실행합니다. 기존 가상환경이 있다면 그대로 사용합니다.

```bash
source .venv/bin/activate
python -m pip install -e '.[docs]'
mkdocs serve --dev-addr 127.0.0.1:8001
```

브라우저에서 <http://127.0.0.1:8001>에 접속합니다. 서버는 Ctrl+C로 종료합니다.
API의 예제 포트 8080, 모델 서버의 예제 포트 8000과 충돌하지 않도록 8001을 사용합니다.

## 빌드와 검증

```bash
mkdocs build --strict
```

`site/`에 정적 HTML이 생성됩니다. 문서 CI에서도 strict 빌드를 실행하여 깨진 문서 링크와 설정 경고를 확인합니다.
GitHub Actions에서 빌드 결과물을 저장하며, Pages 배포는 아래 조건을 충족한 뒤 활성화합니다.

## Mermaid

`mermaid` 코드 블록으로 다이어그램을 작성합니다. Material 테마의 Mermaid 렌더링을 사용하며,
브라우저가 Mermaid 리소스를 로드하려면 인터넷 연결이 필요할 수 있습니다.

설정은 [Material 공식 다이어그램 문서](https://squidfunk.github.io/mkdocs-material/reference/diagrams/)와
[MkDocs 설정 문서](https://www.mkdocs.org/user-guide/configuration/)를 참고했습니다.

## 문서 이미지 갱신

`docs/assets/`의 이미지는 8개 관절 합성 예시를 저장한 스냅샷입니다. 데이터 생성 로직을 바꾸면 다음 명령으로 갱신합니다.

```bash
python scripts/generate_synthetic_dataset.py --per-class 25 --seed 42
python scripts/visualize_pose.py --input data/sample/pixel.json --show-preprocessed --show-features
cp data/sample/synthetic_100/overview_*.png docs/assets/
cp results/visualize_pose/preprocessed_pose.png docs/assets/eight-joint-pose.png
mkdocs build --strict
```

[개발 진행 현황](STATUS.md)과 [최초 첨부 요구사항](visualization-requirements.md)은 별도로 보존합니다.
현재 입력 계약은 [8개 관절 데이터 형식](data-format.md)을 기준으로 합니다.

## GitHub Actions와 Pages

[Documentation 워크플로](https://github.com/ggh-png/pose2actionLLM/actions/workflows/docs.yml)는
main의 문서·설정 변경 시 자동 실행되고 수동 실행도 가능합니다.
성공한 실행의 **Artifacts → documentation-html**에서 정적 HTML 사이트를 다운로드합니다.
압축을 풀고 해당 폴더에서 `python3 -m http.server 8001`을 실행하면 로컬에서 볼 수 있습니다.
아티팩트 보관 기간은 30일입니다.

저장소는 공개로 전환되었으며 GitHub Pages의 Actions 배포를 활성화했습니다.
main의 문서 변경 시 자동 배포됩니다. 다음은 설정을 재구성할 때 사용하는 절차입니다.

1. 저장소 **Settings → Pages → Source**를 **GitHub Actions**로 설정합니다.
2. **Settings → Secrets and variables → Actions → Variables**에 `PAGES_ENABLED=true`를 추가합니다.
3. **Actions → Documentation → Run workflow**를 실행합니다.

문서 주소는 <https://ggh-png.github.io/pose2actionLLM/>입니다.
자세한 지원 조건은
[GitHub Pages 공식 안내](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)를 참고하세요.
