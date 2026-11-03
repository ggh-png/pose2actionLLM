# 시각화

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

## 클래스별 합성 데이터 100개

```bash
python scripts/generate_synthetic_dataset.py --per-class 25 --seed 42
```

`data/sample/synthetic_100.jsonl`에 4개 클래스 각각 25개를 저장하고,
`data/sample/synthetic_100/`에 개별 JSON 100개·PNG 100장과 클래스별 5×5 모음 PNG 4장을 생성합니다. 이 파일들은 저장소에도 포함합니다.
`manifest.json`에는 클래스별 수량과 seed가 기록됩니다. 같은 seed로 재생성할 수 있습니다.

몸의 비율·위치·크기와 팔·다리 위치를 변화시킵니다. HAND_UP에는 왼팔/오른팔/양팔을 든 경우가
포함됩니다. 정면·비반전 카메라를 가정합니다. 앉은 자세의 무릎은 각 골반 아래에서 조금 벌어지고,
골반–무릎의 화면상 길이는 선 자세보다 짧게 설정했습니다. 양쪽 무릎을 한 방향으로 이동시키던 기존 측면 생성 방식은 제거했습니다. 어깨·팔꿈치·골반·무릎을 좌우 각각 생성하여 총 8개 관절만 포함합니다.
실제 사람의 측정값이나 카메라 투영 시뮬레이션이 아니므로 실제 모델 성능 평가에는 사용하지 마세요.

사진은 **정면 비반전 · 8개 관절 · 생성기 v2** 기준입니다. 각 모음에는 해당 클래스의 새 샘플 25개가 표시됩니다.

## 0: SITTING_HAND_DOWN

![SITTING_HAND_DOWN 합성 샘플 25개](assets/front-v2-overview_0_SITTING_HAND_DOWN.png)

## 1: SITTING_HAND_UP

![SITTING_HAND_UP 합성 샘플 25개](assets/front-v2-overview_1_SITTING_HAND_UP.png)

## 2: STANDING_HAND_DOWN

![STANDING_HAND_DOWN 합성 샘플 25개](assets/front-v2-overview_2_STANDING_HAND_DOWN.png)

## 3: STANDING_HAND_UP

![STANDING_HAND_UP 합성 샘플 25개](assets/front-v2-overview_3_STANDING_HAND_UP.png)

정면 비반전 예시에서는 해부학적 왼쪽(파랑)이 화면 오른쪽에 표시됩니다. 실제 입력의 좌우를 자동으로 교환하는 기능은 아닙니다. 8개 관절 정면 2D 좌표만으로 앉기/서기를 구분하기 어려운 경우가 있으므로 이 합성 패턴을 실제 성능의 근거로 사용하지 마세요.


## JSON과 개별 이미지 내려받기

[GitHub의 전체 JSON/PNG 폴더](https://github.com/ggh-png/pose2actionLLM/tree/main/data/sample/synthetic_100)에서
샘플별 좌표와 이미지를 함께 볼 수 있습니다. 동일한 ID의 `.json`과 `.png`가 한 쌍입니다.
[통합 JSONL](https://github.com/ggh-png/pose2actionLLM/blob/main/data/sample/synthetic_100.jsonl)과
[매니페스트](https://github.com/ggh-png/pose2actionLLM/blob/main/data/sample/synthetic_100/manifest.json)도 제공합니다.
