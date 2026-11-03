## 추가 기능: Pose 데이터 시각화 도구 구현

입력된 2D keypoint coordinate가 올바른 형태인지 사람이 직접 확인할 수 있도록 **Pose Visualization Script**를 반드시 구현한다.

목적은 다음과 같다.

```text id="n834mx"
1. 좌표 입력 오류 확인
2. 좌/우 keypoint 뒤바뀜 확인
3. coordinate convention 확인
4. missing keypoint 확인
5. 전처리 전/후 좌표 비교
6. LLM에 실제로 어떤 pose가 전달되는지 검증
```

### 파일 추가

프로젝트 구조에 다음 파일을 추가한다.

```text id="b3l0xx"
pose_llm_classifier/
│
├── scripts/
│   ├── visualize_pose.py
│   ├── visualize_dataset.py
│   ├── preprocess.py
│   ├── extract_features.py
│   ├── evaluate_llm.py
│   └── benchmark_models.py
│
├── src/
│   ├── visualization.py
│   └── ...
```

---

## visualize_pose.py

하나의 pose sample을 입력받아 skeleton 형태로 시각화한다.

지원 입력:

```text id="010ajc"
JSON
JSONL의 특정 sample
CSV의 특정 row
Python dict
```

예:

```bash id="iubiu3"
python scripts/visualize_pose.py \
    --input data/sample/sample.json
```

또는:

```bash id="saw299"
python scripts/visualize_pose.py \
    --input data/test.jsonl \
    --index 12
```

출력:

```text id="vo5469"
2D skeleton plot
keypoint name
(x, y) coordinate
ground truth label
optional prediction
```

---

## Skeleton 연결 구조

사용 가능한 keypoint가 있을 경우 다음 연결을 사용한다.

```text id="tjp1t9"
left_shoulder  ─ right_shoulder

left_shoulder  ─ left_elbow
left_elbow     ─ left_wrist

right_shoulder ─ right_elbow
right_elbow    ─ right_wrist

left_shoulder  ─ left_hip
right_shoulder ─ right_hip

left_hip       ─ right_hip

left_hip       ─ left_knee
left_knee      ─ left_ankle

right_hip      ─ right_knee
right_knee     ─ right_ankle
```

keypoint가 없는 경우 해당 edge만 skip한다.

예를 들어 wrist가 없다면:

```text id="foruwz"
shoulder → elbow
```

까지만 그린다.

---

## Coordinate Convention

Pose Estimator의 image coordinate convention을 그대로 반영한다.

기본:

```text id="51j8wb"
origin = top-left

x 증가 → 오른쪽
y 증가 → 아래쪽
```

따라서 matplotlib에서는 y축을 invert한다.

예:

```python id="t922ke"
ax.invert_yaxis()
```

또는:

```python id="6prpd7"
ax.set_ylim(1.0, 0.0)
```

정규화 좌표를 사용하는 경우 기본 plot 범위는:

```text id="ve1qes"
x = [0, 1]
y = [0, 1]
```

로 한다.

---

## 시각화 정보

각 keypoint에는 다음을 표시할 수 있도록 한다.

```text id="8wzz7s"
keypoint name
coordinate
presence/confidence (있는 경우)
```

예:

```text id="z2aegc"
L shoulder
(0.578, 0.512)
```

---

## Label 표시

Ground truth가 존재하는 경우 figure 상단에 표시한다.

예:

```text id="oy3vzl"
Ground Truth:
STANDING_HAND_DOWN
```

모델 prediction까지 같이 넘기는 경우:

```text id="c7wzr0"
Ground Truth : STANDING_HAND_DOWN
Prediction   : STANDING_HAND_UP
```

형태로 표시한다.

---

## Correct / Incorrect Visualization

Evaluation 결과를 시각화할 때 prediction 결과에 따라 구분한다.

예:

```text id="3scz43"
GT   : STANDING_HAND_DOWN
Pred : STANDING_HAND_DOWN
Result : Correct
```

또는

```text id="9jk1t0"
GT   : STANDING_HAND_DOWN
Pred : SITTING_HAND_DOWN
Result : Incorrect
```

---

## Raw / Preprocessed 비교

디버깅을 위해 동일 pose의

```text id="ogshna"
Raw Coordinate
vs
Preprocessed Coordinate
```

를 비교할 수 있도록 한다.

예:

```bash id="j81qtu"
python scripts/visualize_pose.py \
    --input sample.json \
    --show-preprocessed
```

출력은 가능하면 두 개의 별도 figure로 저장한다.

```text id="37nu8w"
raw_pose.png
preprocessed_pose.png
```

---

## Derived Feature 표시

필요하면 시각화 이미지에 다음 feature를 함께 표시한다.

예:

```text id="mp1js3"
left_hand_above_shoulder = True
right_hand_above_shoulder = False

torso_length = 0.203
left_wrist_relative_y = -0.42
```

다만 기본 시각화에서는 과도한 정보를 표시하지 않고, `--show-features` 옵션으로 활성화한다.

---

## Dataset Visualization

전체 dataset에서 임의의 pose sample을 확인할 수 있도록 별도 script를 만든다.

```bash id="8ka5xk"
python scripts/visualize_dataset.py \
    --input data/test.jsonl \
    --num-samples 16
```

이 명령은 여러 sample을 이미지로 저장한다.

예:

```text id="mq2tr7"
results/visualization/
├── sample_0001.png
├── sample_0002.png
├── sample_0003.png
...
```

---

## Class별 Visualization

특정 class만 확인하는 기능도 지원한다.

예:

```bash id="lyp8mw"
python scripts/visualize_dataset.py \
    --input data/test.jsonl \
    --class-id 3 \
    --num-samples 20
```

이를 통해

```text id="t9x52i"
SITTING_HAND_DOWN
SITTING_HAND_UP
STANDING_HAND_DOWN
STANDING_HAND_UP
```

각 class 데이터가 실제 의도한 pose인지 검증한다.

---

## Misclassification Visualization

모델 evaluation 이후 잘못 분류된 sample만 자동으로 저장하는 기능을 구현한다.

예:

```text id="68lxl9"
results/
└── errors/
    ├── sample_0012_GT_2_PRED_0.png
    ├── sample_0047_GT_1_PRED_3.png
    └── ...
```

이 기능은 모델 분석에서 중요하다.

단순히 Accuracy만 확인하지 말고,

```text id="wdpsr6"
어떤 자세에서
어떤 class로
왜 오분류되는지
```

를 사람이 직접 확인할 수 있어야 한다.

---

## 최종 Visualization 흐름

전체 시스템에서 시각화는 다음 위치에 둔다.

```text id="we482q"
2D Pose Input
      │
      ├──────────────→ Visualization
      │                    ↓
      │              입력 데이터 검증
      │
      ↓
Preprocessing
      │
      ├──────────────→ Visualization
      │                    ↓
      │              전처리 결과 검증
      │
      ↓
LLM Classification
      │
      ↓
Prediction
      │
      └──────────────→ Error Visualization
                           ↓
                     오분류 분석
```

---

## 개발 순서에 추가

기존 개발 순서를 다음과 같이 수정한다.

```text id="k4031y"
Step 1
서버 환경 확인

Step 2
프로젝트 구조 생성

Step 3
Pose JSON loader 구현

Step 4
Pose Visualization 구현

Step 5
실제 좌표 sample을 시각화하여
coordinate convention과 skeleton 연결 검증

Step 6
Preprocessing 구현

Step 7
Preprocessing 전/후 visualization 검증

Step 8
Qwen3-4B 단일 sample inference

Step 9
Zero-shot dataset evaluation

Step 10
Few-shot 구현

Step 11
Qwen / Llama 모델 비교

Step 12
Misclassification visualization

Step 13
최적 모델 선정

Step 14
FastAPI 연결

Step 15
통합 테스트
```

---

## 최소 성공 조건에 Visualization 추가

초기 milestone은 다음과 같이 한다.

```text id="k0wdnd"
Pose JSON
   ↓
Loader
   ↓
Visualization
   ↓
사람 형태가 정상적으로 보이는지 확인
   ↓
Preprocessing
   ↓
Prompt
   ↓
Qwen3-4B
   ↓
0 / 1 / 2 / 3
```

LLM inference를 시작하기 전에 반드시 최소 몇 개 sample을 시각화하여 좌표가 올바르게 해석되고 있는지 검증한다.

좌표가 잘못된 상태로 LLM benchmark를 진행하지 않는다.