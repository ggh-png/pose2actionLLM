# 현재 데이터셋 · v4 측면 100개

**앉기·서기 모두 측면에서 본 합성 관절 도식입니다.** 2026-11-03 Qwen3-4B 재평가에 사용했습니다.
[모델별 최신 평가](experiment-results.md) · [클래스별 이미지](visualization.md) · [이전 v2 입력](dataset-v2.md)

## 데이터 구성

| 항목 | 값 |
|---|---|
| 생성기 | v4 · seed 42 |
| 수량 | 100개 · 클래스별 25개 |
| 관절 | 좌우 어깨·팔꿈치·골반·무릎 · 총 8개 |
| 좌표 | 0~1 정규화 · x 오른쪽 · y 아래쪽 |
| 시점 | 정면 기준 85~88도 정사영 |
| 방향 | 화면 왼쪽 50개 · 화면 오른쪽 50개 |

| ID | 클래스 | 개수 |
|---|---|---:|
| 0 | 앉기 · 팔 내림 | 25 |
| 1 | 앉기 · 팔 올림 | 25 |
| 2 | 서기 · 팔 내림 | 25 |
| 3 | 서기 · 팔 올림 | 25 |

팔 올림은 같은 쪽 어깨보다 높은 팔꿈치를 기준으로 합니다. 실제 사람이 측정한 좌표가 아니며 실제 카메라의 가림을 모사하지 않습니다.

## 파일 위치와 다운로드

| 용도 | 위치 |
|---|---|
| 로컬 통합 입력 | `data/sample/synthetic_100.jsonl` |
| 로컬 개별 JSON·PNG | `data/sample/synthetic_100/<클래스 ID>_<클래스명>/` |
| 로컬 클래스별 이미지 | `data/sample/synthetic_100/overview_*.png` |
| 평가 입력 스냅샷 | [100개 JSONL](assets/experiments/2026-11-03-side-v4/synthetic_100.jsonl) |
| 샘플별 파일 목록 | [manifest.json](assets/experiments/2026-11-03-side-v4/manifest.json) |
| 검사 기록 | [dataset-inspection.json](assets/experiments/2026-11-03-side-v4/dataset-inspection.json) |

예를 들어 `0_SITTING_HAND_DOWN/synthetic-0-000.json`과 같은 이름의 `.png`가 한 쌍입니다.
manifest의 `json`·`image` 경로는 로컬 `data/sample/synthetic_100/`를 기준으로 합니다.

## 평가 전 검사

| 검사 | 결과 |
|---|---:|
| 정답 누락 | 0개 |
| 정규화 좌표 중복 | 0개 |
| 전처리 후 누락 관절 | 0개 |
| 팔꿈치 높이와 팔 올림 라벨 불일치 | 0개 |
| 개별 JSON / PNG 존재 | 각각 100개 |

입력 SHA256:

```text
c509713c7ded6b41146a4fb2166db6317b2e8b1179d26b4f91155be211e1a7cb
```

이 검사는 파일·좌표·라벨 대리 기준의 일관성 확인입니다. 실제 자세 라벨의 정확성을 인증하지 않습니다.

## 같은 데이터 재생성

```bash
python scripts/generate_synthetic_dataset.py --per-class 25 --seed 42
```

기본 출력 경로의 입력과 이미지를 다시 생성합니다. 평가 스냅샷은 별도로 보존합니다.
100개별 정답·예측은 [평가 보고서의 펼침 목록](experiment-results.md#artifacts)과 원본 예측 JSONL에서 확인하세요.
