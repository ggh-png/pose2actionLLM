# LLM 평가와 모델 비교

## 기록된 실험

2026-11-04 세 VL 모델을 골격 모양 중심 프롬프트와 동일한 합성 100개로 비교했습니다. **Qwen3-VL-8B-Instruct: 확대 PNG+JSON 90% · InternVL3_5-8B-HF: 확대 PNG+JSON 51% · Idefics3-8B-Llama3: 확대 PNG+JSON 36%**. 기존 도식과 확대 골격, PNG만과 PNG+JSON을 구분해 평가했습니다.
[최신 평가 보고서](experiment-results.md)에서 혼동행렬·클래스별 지표·재현 명령·원본 응답을 확인하세요.
이전 정면 v2 결과 11%는 [이전 실험 기록](experiment-results-v2.md)에 보존했습니다.
Qwen 4B/8B와 Llama 8B의 동일 입력 비교를 완료했습니다. 실제 관측 데이터 평가는 아직 수행하지 않았습니다.

텍스트 전용 기본 system 프롬프트는 `inference.py`의 `SYSTEM_PROMPT`이고, PNG 비교는 `vision.py`의 `VISION_SYSTEM_PROMPT`를 두 조건에 동일하게 사용합니다. [수치 규칙 프롬프트 전문](assets/experiments/2026-11-04-numeric-rules/system-prompt.txt)을 그대로 사용하며 모델별 문구를 덧붙이지 않습니다. Qwen thinking 비활성화는 서버 chat-template 설정으로 적용합니다.

## 평가 실행

가벼운 개발용 연결 테스트:

```bash
python scripts/evaluate_llm.py --input data/sample/poses.jsonl
python scripts/benchmark_models.py --input data/sample/poses.jsonl --models Qwen/Qwen3-4B llama-server-model
python scripts/visualize_dataset.py --input results/evaluate_llm/predictions.jsonl --errors-only
```

`metrics.json`에는 accuracy, confusion matrix, 클래스별 precision/recall/F1, 실패 수, 평균 지연시간이 들어갑니다. `predictions.jsonl`은 원본 pose, 실제 프롬프트, 응답, 예측을 보존합니다. `errors/`에는 오분류 PNG가 저장됩니다. 응답 파싱/추론 실패는 전체 accuracy에서 오답으로 계산하고 confusion matrix에서는 제외합니다. `--no-error-plots`로 이미지 저장을 생략합니다. 동일 출력 폴더를 재사용하면 결과 파일은 덮어쓰고 기존 PNG는 남으므로 실행별 별도 폴더를 권장합니다.

mock benchmark는 각 이름에 대해 같은 상수 백엔드를 실행하며, 결과 모델명은 `mock-constant-0`입니다. 이 수치로 최적 모델을 선정하면 안 됩니다.

실제 모델은 충분한 사양의 별도 서버에서 제공해야 합니다. [Hugging Face Messages API](https://huggingface.co/docs/text-generation-inference/en/messages_api)의 chat completions 형식에 맞춘 HTTP 어댑터를 제공합니다. 이 평가 명령은 이미 실행 중인 endpoint를 호출합니다. 서버 설치·기동 자동화는 [자동 실행 가이드](server-automation.md)를 참고하세요. 서버의 모델명과 chat template, thinking 비활성화 설정은 별도로 확인해야 하며 응답은 정확히 숫자 한 개여야 합니다.

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

## PNG와 JSON을 함께 평가하기

`scripts/benchmark_vision.py`는 이미지 입력 모델에서 동일한 프롬프트·JSON을 유지하고 PNG 유무만 비교합니다. 텍스트 전용 모델에는 이미지를 전달할 수 없습니다.
기존 검토용 PNG에는 정답이 표시되어 있으므로 사용하지 않고, `vision.py`의 `render_model_input`으로 정답·예측·샘플 ID를 제외한 PNG를 생성합니다.
`VisionClassifier`가 JSON text part와 실제 PNG data URL을 같은 user 메시지에 넣습니다.

```bash
.venv/bin/python scripts/benchmark_vision.py --input data/sample/synthetic_100.jsonl \
  --output-dir results/new-vision-run --prepare-only
# 생성한 입력 이미지를 검토하고 Qwen3-VL 서버를 준비한 뒤:
.venv/bin/python scripts/benchmark_vision.py --input data/sample/synthetic_100.jsonl \
  --output-dir results/new-vision-run --visualization-reviewed
```

[이미지+JSON 결과와 재현 조건](experiment-results.md) · [이전 텍스트 수치 규칙 결과](experiment-results-2026-11-04-numeric-rules.md)

## 골격 모양 중심 프롬프트와 확대 이미지

현재 `VISION_SYSTEM_PROMPT`는 이미지의 몸통·허벅지 연결 모양과 팔 방향을 먼저 판단합니다. 이전 수치 프롬프트는 실험 산출물의 텍스트로 보존했습니다. `--prompt-file`로 저장한 버전을 재실행할 수 있습니다.
`--image-style clean`은 축·격자·관절 글자 없이 같은 좌표의 골격을 균일 확대해 그립니다. 기존 도식은 `--image-style plot`입니다. 이미지 스타일은 같은 출력 폴더에서 섞어 쓸 수 없습니다.
`--modes json_only png_only png_json`은 세 입력 조건을 비교합니다. PNG만 조건은 JSON 좌표·Feature를 전송하지 않습니다.

```bash
.venv/bin/python scripts/benchmark_vision.py --input data/sample/synthetic_100.jsonl \
  --output-dir results/new-clean-run --image-style clean --prepare-only
# 입력 PNG를 검토하고 해당 모델 서버를 준비한 다음:
.venv/bin/python scripts/benchmark_vision.py --input data/sample/synthetic_100.jsonl \
  --output-dir results/new-clean-run --image-style clean --visualization-reviewed \
  --model Qwen/Qwen3-VL-8B-Instruct --base-url http://127.0.0.1:18083/v1 \
  --modes png_only png_json
```

[최신 세 모델 비교](experiment-results.md)에서 실제 서버 명령과 모델별 전처리 조건을 확인하세요.
