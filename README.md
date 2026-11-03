# pose2actionLLM

2D pose 좌표를 검증·시각화하고, 전처리 → 프롬프트 → LLM 분류 → 오분류 분석으로 연결하는 Python 프로젝트입니다.
현재 개발 모드에서는 모델을 다운로드하거나 GPU를 사용하지 않습니다. 기본 `mock`은 항상 **0**을 반환하며, 정확도 검증용 모델이 아닙니다.

## 설치

Python 3.10 이상이 필요합니다. 저장소 루트에서 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[api,dev]'
pytest -q
```

검증한 Python 3.12 개발 환경 버전을 재현하려면 `python -m pip install -c requirements-dev.lock.txt -e '.[api,dev]'`를 사용하세요. 다른 Python 버전에서는 일부 고정 패키지가 맞지 않을 수 있습니다.

Ubuntu에서 `ensurepip` 오류가 발생하면 `python3-venv` 패키지를 설치한 뒤 환경을 생성하세요.
시각화만 필요하면 `pip install -e .`로 설치합니다. PyTorch, Transformers, 모델 가중치는 의존성에 없습니다.

## 입력 형식과 클래스

`data/sample/`의 데이터는 코드 검증을 위한 **합성 예시**입니다. 실제 pose estimator 출력 검증을 대신하지 않습니다.

```json
{
  "id": "example",
  "coordinate_space": "normalized",
  "label": 2,
  "keypoints": {
    "left_shoulder": [0.4, 0.28],
    "right_shoulder": {"x": 0.6, "y": 0.28, "confidence": 0.95},
    "left_elbow": null
  }
}
```

- JSON: 단일 객체 또는 객체 배열. JSONL: 줄당 객체 하나. CSV: `keypoints` 열에 JSON 객체를 넣습니다 (`data/sample/poses.csv` 참고).
- Python dict는 `load_sample({...})`, `plot_pose({...}, 'pose.png')`로 전달합니다.
- 입력은 좌우 shoulder, elbow, hip, knee의 8개 관절이며 영문 snake_case 이름을 사용합니다. 머리·손목·발목은 입력에 포함하지 않습니다. 순서만 있는 배열이나 estimator별 인덱스는 자동 추측하지 않습니다.
- 기본 좌표는 `[0,1]`, 좌상단 원점, x 오른쪽/y 아래쪽입니다. pixel 입력은 `coordinate_space: "pixel"`, 양수 `image_width`, `image_height`가 필요합니다.
- 누락 좌표는 `null`; `(0,0)`은 유효한 좌표입니다. `presence=0`은 사용하지 않으며 `--min-confidence` 미만 관절도 전처리에서 제외합니다.
- NaN/Infinity, 범위 초과, 알 수 없는 관절명, 일부만 있는 x/y는 오류입니다. crop 밖 좌표를 자동으로 잘라내지 않습니다.
- label/prediction은 0~3 정수 또는 아래 이름입니다. 좌우는 사람의 **해부학적 좌우**이며 자동 교환하지 않습니다.

첨부 문서의 나열 순서로 아래 매핑을 정했습니다. 실제 데이터셋 매핑이 다르면 먼저 변환해야 합니다.

| ID | 클래스 |
|---|---|
| 0 | SITTING_HAND_DOWN |
| 1 | SITTING_HAND_UP |
| 2 | STANDING_HAND_DOWN |
| 3 | STANDING_HAND_UP |

기존 클래스명 HAND_UP은 유지하되, 어느 한쪽 팔꿈치라도 같은 쪽 어깨보다 위에 있는 것을 팔 올림의 대리 기준으로 사용합니다. 손목이 없으므로 실제 손 높이는 알 수 없으며, 팔꿈치를 내린 채 손만 올린 자세는 구분할 수 없습니다. 앉기/서기 판단은 LLM에 맡기며 검증된 규칙 기반 분류기는 포함하지 않습니다.

## 시각화부터 시작

```bash
python scripts/visualize_pose.py --input data/sample/sample.json
python scripts/visualize_pose.py --input data/sample/pixel.json --show-preprocessed --show-features
python scripts/visualize_pose.py --input data/sample/poses.jsonl --index 2 --prediction 3
python scripts/visualize_dataset.py --input data/sample/poses.jsonl --num-samples 16
python scripts/visualize_dataset.py --input data/sample/poses.jsonl --class-id 3 --num-samples 20
```

PNG는 `results/visualize_pose/`, `results/visualize_dataset/`에 저장됩니다. `--output-dir`로 변경합니다.
전처리 비교는 `raw_pose.png`, `preprocessed_pose.png` 두 장입니다. 관절명·좌표·confidence/presence·정답·예측·정오 여부를 표시합니다.
없는 관절의 edge만 생략하고 누락 목록을 출력합니다. 파랑은 해부학적 왼쪽, 주황은 오른쪽입니다. 정규화 plot은 x/y 범위 `[0,1]`이고 y축은 뒤집혀 있습니다.
데이터셋 추출은 seed 42의 reservoir sampling으로 메모리를 제한하며 `selection.json`에 원본 인덱스를 기록합니다. 인덱스는 0부터 시작합니다.

## 전처리와 프롬프트 검증

```bash
python scripts/preprocess.py --input data/sample/pixel.json --output results/preprocessed.jsonl
python scripts/extract_features.py --input data/sample/poses.jsonl --output results/features.jsonl
python scripts/evaluate_llm.py --input data/sample/poses.jsonl --dry-run
```

pixel 좌표를 이미지 너비/높이로 나눕니다. 중심 이동, 좌우 반전, 좌표 추측은 하지 않습니다. feature는 정규화된 이미지 공간에서 계산합니다. torso_length는 사용 가능한 좌우 어깨-엉덩이 거리의 평균이며, elbow_relative_y는 어깨 기준 y차이를 torso_length로 나눈 값입니다. 계산할 수 없는 값은 null입니다.

`prompts.jsonl`에서 실제 전달할 좌표·feature를 확인할 수 있습니다. label/prediction/id 등의 메타데이터는 질의 프롬프트에 들어가지 않습니다. `--few-shot train_examples.jsonl`로 별도 학습 예시를 넣을 수 있습니다. 같은 파일 사용은 거부하지만, 파일 간 중복 샘플 방지는 사용자가 데이터 분할 단계에서 확인해야 합니다.

## 평가와 모델 비교

가벼운 개발용 연결 테스트:

```bash
python scripts/evaluate_llm.py --input data/sample/poses.jsonl
python scripts/benchmark_models.py --input data/sample/poses.jsonl --models Qwen/Qwen3-4B llama-server-model
python scripts/visualize_dataset.py --input results/evaluate_llm/predictions.jsonl --errors-only
```

`metrics.json`에는 accuracy, confusion matrix, 클래스별 precision/recall/F1, 실패 수, 평균 지연시간이 들어갑니다. `predictions.jsonl`은 원본 pose, 실제 프롬프트, 응답, 예측을 보존합니다. `errors/`에는 오분류 PNG가 저장됩니다. 응답 파싱/추론 실패는 전체 accuracy에서 오답으로 계산하고 confusion matrix에서는 제외합니다. `--no-error-plots`로 이미지 저장을 생략합니다. 동일 출력 폴더를 재사용하면 결과 파일은 덮어쓰고 기존 PNG는 남으므로 실행별 별도 폴더를 권장합니다.

mock benchmark는 각 이름에 대해 같은 상수 백엔드를 실행하며, 결과 모델명은 `mock-constant-0`입니다. 이 수치로 최적 모델을 선정하면 안 됩니다.

실제 모델은 충분한 사양의 별도 서버에서 제공해야 합니다. [Hugging Face Messages API](https://huggingface.co/docs/text-generation-inference/en/messages_api)의 chat completions 형식에 맞춘 HTTP 어댑터를 제공합니다. 서버를 직접 설치하거나 구동하지 않습니다. 서버의 모델명과 chat template, thinking 비활성화 설정은 별도로 확인해야 하며 응답은 정확히 숫자 한 개여야 합니다.

**실제 데이터 여러 개의 원본/전처리 시각화를 사람이 확인한 후에만** 다음 명령을 사용하세요. 플래그는 사람의 검토 완료 선언이며 자동 검사 인증은 아닙니다.

```bash
export POSE_API_KEY='your-server-key'  # 인증이 필요한 서버만
python scripts/evaluate_llm.py --input data/test.jsonl \
  --backend remote --model Qwen/Qwen3-4B --base-url http://localhost:8000/v1 \
  --visualization-reviewed --output-dir results/qwen-zero-shot
python scripts/benchmark_models.py --input data/test.jsonl --backend remote \
  --models Qwen/Qwen3-4B llama-server-model --base-url http://localhost:8000/v1 \
  --visualization-reviewed --output-dir results/benchmark
```

한 benchmark 실행의 모델들은 같은 endpoint가 제공해야 합니다. 서로 다른 서버는 평가를 별도로 실행하세요. 모델 이름만 바꿔도 서버에 모델이 자동으로 설치되는 것은 아닙니다.

## FastAPI

```bash
uvicorn pose_llm_classifier.api:app --host 127.0.0.1 --port 8080
```

`GET /health`, `POST /predict`, `/docs`를 제공합니다. 요청 형태는 `{"sample": { ...pose... }, "min_confidence": 0.2}`입니다. 기본은 mock입니다. 원격 연결은 `.env.example`의 환경변수를 직접 export하여 설정합니다 (`.env` 자동 로드 없음). `POSE_VISUALIZATION_REVIEWED=1`이 필요합니다.

## 구조와 개발 상태

```text
src/pose_llm_classifier/  # loader, preprocessing, features, visualization, inference, evaluation, API
scripts/                 # 계획에 나온 6개 CLI
data/sample/             # 작은 합성 JSON/JSONL/CSV 예시
tests/                   # 모델 없이 실행되는 단위·통합 테스트
docs/                    # 원본 요구사항, 진행 현황
```

[개발 진행 현황](docs/STATUS.md)을 확인하세요. 실제 데이터, 모델, API 키, 생성 결과와 가상환경은 Git에서 제외됩니다. GitHub Actions도 모델 없이 테스트와 lint만 실행합니다.

## 클래스별 합성 데이터 100개 생성

```bash
python scripts/generate_synthetic_dataset.py --per-class 25 --seed 42
```

`data/sample/synthetic_100.jsonl`에 4개 클래스 각각 25개를 저장하고,
`results/synthetic_100/`에 개별 PNG 100장과 클래스별 5×5 모음 PNG 4장을 생성합니다.
`manifest.json`에는 클래스별 수량과 seed가 기록됩니다. 같은 seed로 재생성할 수 있습니다.

몸의 비율·위치·크기와 팔·다리 위치를 변화시킵니다. HAND_UP에는 왼손/오른손/양손을 든 경우가
포함됩니다. 앉은 자세는 허벅지가 대체로 수평인 비스듬한 측면 도식이며,
선 자세는 허벅지가 대체로 수직입니다. 어깨·팔꿈치·골반·무릎을 좌우 각각 생성하여 총 8개 관절만 포함합니다.
실제 사람의 측정값이나 카메라 투영 시뮬레이션이 아니므로 실제 모델 성능 평가에는 사용하지 마세요.

## MkDocs 문서 사이트

전체 흐름 Mermaid, 8개 관절 입력 형식, 시각화 갤러리, 전처리·LLM 평가·API 가이드를 제공합니다.

```bash
source .venv/bin/activate
python -m pip install -e '.[docs]'
mkdocs serve --dev-addr 127.0.0.1:8001
```

브라우저에서 <http://127.0.0.1:8001>로 접속하세요.
`mkdocs build --strict`로 정적 문서를 `site/`에 빌드합니다.
[문서 홈](docs/index.md) · [전체 흐름](docs/pipeline.md) · [문서 관리](docs/development.md)


문서 자동 빌드: [Documentation Actions](https://github.com/ggh-png/pose2actionLLM/actions/workflows/docs.yml).
성공한 실행의 `documentation-html` 아티팩트에서 HTML을 다운로드할 수 있습니다.
문서 사이트: <https://ggh-png.github.io/pose2actionLLM/>. main의 문서 변경 시 GitHub Pages로 자동 배포합니다.
활성화 절차는 [문서 관리 가이드](docs/development.md)에 정리했습니다.


## 서버 자동 실행과 피드백

```bash
# 환경 생성 → 데이터 검증·시각화·전처리·프롬프트 → feedback.md
bash scripts/run_server.sh --input data/test.jsonl

# 검토 후 GPU 서버에서 모델 준비와 평가까지 한 번에
bash scripts/run_server.sh --input data/test.jsonl --mode remote \
  --visualization-reviewed --install-vllm --start-model-server
```

실행별 `results/runs/` 폴더에 점검·평가·오분류·실패 원인을 저장합니다.
기존 모델 endpoint 사용, few-shot, 여러 모델 비교도 지원합니다.
[서버 자동화 가이드](docs/server-automation.md)를 참고하세요.


## 서버 최초 설치

Ubuntu/Debian 서버에서:

```bash
curl -fsSL https://raw.githubusercontent.com/ggh-png/pose2actionLLM/main/scripts/setup_server.sh \
  -o /tmp/pose2action-setup.sh
bash /tmp/pose2action-setup.sh --install-system
```

저장소 clone, 가상환경·기본 패키지 설치, mock 연결 시험을 진행합니다.
GPU 서버의 vLLM 설치는 `--with-vllm`을 추가합니다.
[서버 최초 설치 가이드](docs/server-setup.md)를 참고하세요.
