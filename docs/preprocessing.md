# 전처리와 Feature

```bash
python scripts/preprocess.py --input data/sample/pixel.json --output results/preprocessed.jsonl
python scripts/extract_features.py --input data/sample/poses.jsonl --output results/features.jsonl
python scripts/evaluate_llm.py --input data/sample/poses.jsonl --dry-run
```

pixel 좌표를 이미지 너비/높이로 나눕니다. 중심 이동, 좌우 반전, 좌표 추측은 하지 않습니다. feature는 정규화된 이미지 공간에서 계산합니다. torso_length는 사용 가능한 좌우 어깨-엉덩이 거리의 평균이며, elbow_relative_y는 어깨 기준 y차이를 torso_length로 나눈 값입니다. 계산할 수 없는 값은 null입니다.

`prompts.jsonl`에서 실제 전달할 좌표·feature를 확인할 수 있습니다. label/prediction/id 등의 메타데이터는 질의 프롬프트에 들어가지 않습니다. `--few-shot train_examples.jsonl`로 별도 학습 예시를 넣을 수 있습니다. 같은 파일 사용은 거부하지만, 파일 간 중복 샘플 방지는 사용자가 데이터 분할 단계에서 확인해야 합니다.
