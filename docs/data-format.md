# 8개 관절 데이터 형식

`data/sample/`의 데이터는 코드 검증용 **합성 예시**입니다. 실제 사람 pose estimator 결과를 그대로 의미하지 않으며, 실험에서 사용하는 입력 계약을 문서화하는 용도입니다.

## 한눈에 보는 입력 계약

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

- JSON: 단일 객체 또는 객체 배열
- JSONL: 줄당 객체 하나
- CSV: `keypoints` 열에 JSON 문자열을 넣음 (`data/sample/poses.csv` 참고)
- Python dict는 `load_sample(...)`, `plot_pose(...)`로 바로 전달 가능

## 핵심 규칙

- 입력 관절은 좌우 `shoulder`, `elbow`, `hip`, `knee` 총 8개입니다.
- 이름은 영문 snake_case로 고정합니다.
- 머리·손목·발목은 사용하지 않습니다.
- 기본 좌표계는 `[0, 1]` 범위, 좌상단 원점, x는 오른쪽, y는 아래쪽입니다.
- pixel 좌표를 쓰려면 `coordinate_space: "pixel"`과 `image_width`, `image_height`를 함께 넣어야 합니다.
- 누락 좌표는 `null`로 표기하고, `(0, 0)`은 유효한 좌표로 처리합니다.
- NaN, Infinity, 범위 초과, 알 수 없는 관절명, x 또는 y만 있는 값은 오류로 간주합니다.
- 좌우는 사람의 **해부학적 좌우**를 기준으로 하며 자동 교환하지 않습니다.
- `label`/`prediction`은 0~3 정수 또는 아래 이름을 사용합니다.

## 클래스 ID와 의미

첨부 문서의 나열 순서로 아래 매핑을 정했습니다. 실제 데이터셋이 다른 ID를 쓰면 먼저 변환해야 합니다.

| ID | 클래스 |
|---|---|
| 0 | SITTING_HAND_DOWN |
| 1 | SITTING_HAND_UP |
| 2 | STANDING_HAND_DOWN |
| 3 | STANDING_HAND_UP |

기존 클래스명 `HAND_UP`은 유지하되, 어느 한쪽 팔꿈치라도 같은 쪽 어깨보다 위에 있으면 팔 올림으로 간주합니다. 손목이 없으므로 실제 손 높이를 알 수 없고, 팔꿈치를 내린 채 손만 올린 자세는 구분할 수 없습니다.

앉기/서기 판정은 모델이 맡으며, 검증된 규칙 기반 분류기는 별도로 포함하지 않습니다.

## 관절 이름 목록

| 부위 | 왼쪽 | 오른쪽 |
|---|---|---|
| 어깨 | `left_shoulder` | `right_shoulder` |
| 팔꿈치 | `left_elbow` | `right_elbow` |
| 골반 | `left_hip` | `right_hip` |
| 무릎 | `left_knee` | `right_knee` |

허용되는 이름은 총 8개입니다. 일부 관절이 비어 있거나 `null`이어도 처리 가능하지만, 유효한 좌표가 적어도 하나는 있어야 합니다. 8개 외의 이름은 오류로 처리합니다.

## 시각화 예시

![8개 관절의 정규화 좌표와 파생 feature](assets/eight-joint-pose.png)

이 데이터는 합성 문장 생성, 좌표 가공, PNG 렌더링, 모델 입력 비교를 위해 고정된 형식으로 설계되었습니다. 실험의 핵심은 “같은 좌표를 어떻게 보여주느냐”가 모델 성능을 바꾼다는 점입니다.
