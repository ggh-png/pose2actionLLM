# 설치와 빠른 시작

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

## 모델 없이 전체 연결 확인

```bash
python scripts/visualize_pose.py --input data/sample/pixel.json --show-preprocessed --show-features
python scripts/evaluate_llm.py --input data/sample/poses.jsonl --dry-run
python scripts/evaluate_llm.py --input data/sample/poses.jsonl --output-dir results/mock-check
```

입력 좌표와 프롬프트를 확인한 다음 mock으로 결과 저장 경로까지 검증합니다. 실제 LLM은 실행하지 않습니다.
