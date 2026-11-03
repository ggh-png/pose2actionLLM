# LLM 평가와 모델 비교

## 기록된 실험

2026-11-03의 [합성 100개 LLM 실험 결과](experiment-results.md)에 Qwen3-4B의
zero-shot 정확도 11%(11/100), 실패 0건, 혼동행렬, 클래스별 지표와 100개별 응답을 기록했습니다.
동일 입력의 mock 정확도는 25%입니다. Llama는 아직 실행하지 않았으며 실제 관측 데이터의 성능 비교는 아닙니다.

## 평가 실행

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
