# 서버 최초 설치

`setup_server.sh`는 처음 접속한 Linux 서버에 저장소와 Python 실행 환경을 준비하는 설치 스크립트입니다.
설치 후에는 [자동 실행 스크립트](server-automation.md)로 실제 데이터를 처리합니다.

| 스크립트 | 역할 |
|---|---|
| `setup_server.sh` | 최초 설치: 저장소 → 가상환경 → 패키지 → mock 연결 시험 |
| `run_server.sh` | 실행 환경을 확인하고 파이프라인 실행 |
| `run_pipeline.py` | 데이터 점검 → 시각화 → 평가 → 피드백 보고서 |

## Ubuntu / Debian 서버에서 시작

curl이 설치되어 있다면 아래 명령으로 시작합니다. curl이 없으면 서버의 패키지 관리자로 먼저 설치하세요.

```bash
curl -fsSL https://raw.githubusercontent.com/ggh-png/pose2actionLLM/main/scripts/setup_server.sh \
  -o /tmp/pose2action-setup.sh
bash /tmp/pose2action-setup.sh --install-system
```

기본 저장소 위치는 `~/pose2actionLLM`, 가상환경은 그 아래 `.venv-server`입니다.
`--install-system`은 apt로 git, Python 3, venv, pip, curl, CA 인증서를 설치합니다.
root가 아니면 sudo를 사용하며 비밀번호를 요청할 수 있습니다.
서버 Python은 3.10 이상이 필요합니다. 드라이버·CUDA 변경, 모델 다운로드·추론은 수행하지 않습니다.

이미 시스템 패키지가 준비된 서버는 `--install-system` 없이 실행합니다.
다른 Linux 배포판에서는 Python·git·venv/pip를 해당 배포판의 패키지 관리자로 먼저 준비하세요.

## 저장소가 이미 있을 때

```bash
cd ~/pose2actionLLM
bash scripts/setup_server.sh
```

스크립트는 자신의 저장소를 감지하여 재사용합니다. 기존 checkout에서 자동 pull·reset·브랜치 변경을 하지 않습니다.
업데이트가 필요하면 변경사항을 확인한 후 `git pull --ff-only`를 직접 실행하세요.
다른 프로젝트로 채워진 설치 경로에는 덮어쓰지 않고 오류를 냅니다.

## GPU 모델 서버 준비

NVIDIA 드라이버가 준비되고 `nvidia-smi`가 정상 작동하는 GPU 서버에서는 다음 옵션을 추가합니다.

```bash
bash /tmp/pose2action-setup.sh --install-system --with-vllm
```

vLLM과 GPU 의존성이 다운로드되므로 기본 설치보다 디스크·시간이 더 필요합니다.
선택한 vLLM 버전의 Python·GPU·드라이버 호환성은 서버에서 확인해야 합니다.
이 옵션도 모델 가중치를 다운로드하거나 실제 추론을 실행하지 않습니다.
모델 준비와 평가는 설치 후 `run_server.sh --mode remote --start-model-server`에서 수행합니다.

## 경로와 설치 옵션

```bash
bash /tmp/pose2action-setup.sh \
  --directory /srv/pose2actionLLM \
  --python python3.12 \
  --with-docs --with-dev
```

`--directory`의 경로는 현재 사용자에게 쓰기 권한이 있어야 합니다.
상대 경로는 설치 스크립트를 실행한 디렉토리 기준입니다.
`--venv /path/to/venv`로 별도 가상환경을 지정할 수도 있습니다.

| 옵션 | 의미 |
|---|---|
| `--install-system` | Ubuntu/Debian 시스템 패키지 설치 |
| `--with-vllm` | NVIDIA GPU 서버용 vLLM 설치 |
| `--with-docs` | MkDocs와 Material 테마 설치 |
| `--with-dev` | API·테스트·lint 도구 설치 |
| `--python COMMAND` | 사용할 Python 실행기 |
| `--ref REF` | 새 clone 시 사용할 브랜치/태그 (기본 main) |
| `--skip-smoke` | 마지막 mock 파이프라인 시험 생략 |
| `--check` | 경로·도구 존재 여부·설치 계획 출력, 변경 없음 |

`--check`는 존재 여부를 보여주는 계획 확인용이며 완전한 호환성 검증은 아닙니다.

## 설치 결과와 다음 실행

설치 마지막에 합성 샘플 4개로 mock 파이프라인을 실행합니다.
성공하면 설치 환경과 패키지 버전을 `results/setup/setup.json`에 기록하고,
mock 피드백은 `results/runs/` 아래에 저장합니다.
설치 또는 mock 시험이 실패하면 성공 보고서를 작성하기 전에 종료됩니다.
동일 환경에 재실행하면 패키지 설치를 다시 확인하고 mock 결과를 새 폴더에 저장합니다.
설치 보고서는 가장 최근 성공한 설치 기준으로 덮어씁니다.

```bash
cd ~/pose2actionLLM
bash scripts/run_server.sh --input data/test.jsonl
```

별도 venv 경로를 지정했다면 설치 끝에 출력되는 `export POSE_RUN_VENV=...` 명령을 먼저 실행하세요.
이후 좌표와 시각화를 확인한 다음 [서버 자동 실행 가이드](server-automation.md)에 따라 실제 모델을 평가합니다.

로컬에서는 기존 venv 재사용·mock 시험까지 검증했고, 새로운 서버의 apt 설치·드라이버 호환성과
실제 vLLM 설치는 해당 서버에서 확인해야 합니다.
