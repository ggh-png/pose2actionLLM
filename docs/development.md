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
정적 사이트 호스팅 배포는 설정하지 않았습니다.

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
cp results/synthetic_100/overview_*.png docs/assets/
cp results/visualize_pose/preprocessed_pose.png docs/assets/eight-joint-pose.png
mkdocs build --strict
```

[개발 진행 현황](STATUS.md)과 [최초 첨부 요구사항](visualization-requirements.md)은 별도로 보존합니다.
현재 입력 계약은 [8개 관절 데이터 형식](data-format.md)을 기준으로 합니다.
