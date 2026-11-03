# 개발 상태

로컬 검증: Python 3.12에서 pytest 31개 통과, Ruff 통과. 합성 pixel sample의 원본/정규화 PNG를 열어 확인했고 전처리, CSV feature 추출, mock benchmark CLI를 실행했습니다. FastAPI 테스트에서 외부 라이브러리의 httpx 사용 중단 예정 경고 1건이 있으나 테스트는 통과합니다. 실제 원격 모델 연결은 검증하지 않았습니다.

## 구현한 범위

- 명시적 좌표 검증, JSON/JSONL/CSV/dict 입력
- 관절 연결, 라벨·예측·누락 목록, confidence 표시, 원본/전처리 PNG 비교
- seed 기반 샘플 및 클래스별/오분류 시각화
- pixel → normalized 전처리, confidence 필터, 파생 feature
- zero-shot/few-shot 프롬프트, strict class parser, 원격 HTTP 어댑터
- mock 평가, 혼동행렬 및 실패 집계, 모델 비교 결과, 오분류 자동 저장
- FastAPI 및 모델 없는 통합 테스트, CI, 저장소 관리 파일

## 의도적으로 아직 실행하지 않은 단계

- 실제 pose 데이터 검토: 사용자가 제공한 것은 요구사항뿐이며 sample은 합성 데이터입니다.
- Qwen3-4B 모델 다운로드/단일 추론
- 실제 zero-shot/few-shot 데이터셋 평가와 Qwen/Llama 비교
- 최적 모델 선정: 실제 성능 근거가 없으므로 선정하지 않았습니다.
- GPU 서버 구축, 학습, 배포

## 서버에서 이어갈 순서

1. estimator의 keypoint 이름/좌표계/이미지 크기와 클래스 ID를 입력 계약에 맞춥니다.
2. 실제 클래스별 여러 sample을 시각화하고 좌우·누락·범위를 확인합니다.
3. 전처리 비교 PNG 및 dry-run 프롬프트를 검토합니다.
4. chat completions 서버에서 Qwen3-4B를 준비하고 단일 sample 파일로 평가합니다.
5. train/test 중복 없이 zero-shot/few-shot 평가, Qwen/Llama 비교를 실행합니다.
6. 오분류를 확인하고 정확도와 지연시간으로 모델을 선정합니다.
7. FastAPI의 remote 설정과 실제 모델 연동을 검증합니다.

첨부 문서는 추가 시각화 요구사항입니다. 별도의 기존 전체 계획은 제공되지 않아 데이터 스키마, 클래스 순서, HAND_UP 기준, HTTP 어댑터는 README에 명시한 개발 가정을 사용했습니다.

## 8개 관절 입력으로 변경

좌우 어깨·팔꿈치·골반·무릎만 입력받습니다. 모든 샘플과 합성 100개, 시각화, feature, 프롬프트를 이 계약으로 수정했습니다. HAND_UP은 팔꿈치 높이를 사용하는 대리 기준이며 실제 손 높이를 판별하지 않습니다. `visualization-requirements.md`는 최초 첨부 원문을 보존한 문서로, 손목/발목 관련 내용은 현재 입력 계약보다 이전 요구사항입니다.

## 서버 자동 실행 스크립트

`run_server.sh`가 환경을 준비하고 `run_pipeline.py`가 점검·시각화·프롬프트·단일 추론·zero-shot/few-shot 평가·피드백을 연결합니다. 모델별 vLLM 시작/종료 옵션과 기존 endpoint 사용을 지원합니다. 로컬 mock 100개 실행, 셸 래퍼 실행, 가짜 HTTP endpoint 및 실패 응답 보존을 검증했습니다. 실제 vLLM 설치·GPU 기동은 서버에서 추가 검증해야 합니다.

## 서버 최초 설치 스크립트

`setup_server.sh`는 단독으로 다운로드해 실행하거나 기존 checkout에서 사용할 수 있습니다. 저장소 clone/재사용, 격리된 venv와 패키지 설치, mock 연결 시험, 설치 보고서 저장을 수행합니다. apt 시스템 패키지와 vLLM은 각각 옵션으로 설치합니다. 로컬에서는 기존 환경 재사용을 확인했고 CI에서 새 venv 설치를 검증합니다. 시스템 패키지 설치와 실제 GPU 기동은 로컬에서 실행하지 않았습니다.
