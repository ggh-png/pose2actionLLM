# FastAPI

```bash
uvicorn pose_llm_classifier.api:app --host 127.0.0.1 --port 8080
```

`GET /health`, `POST /predict`, `/docs`를 제공합니다. 요청 형태는 `{"sample": { ...pose... }, "min_confidence": 0.2}`입니다. 기본은 mock입니다. 원격 연결은 `.env.example`의 환경변수를 직접 export하여 설정합니다 (`.env` 자동 로드 없음). `POSE_VISUALIZATION_REVIEWED=1`이 필요합니다.
