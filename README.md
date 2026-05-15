# API Service

FastAPI 기반 AI 음성 진위 판별 API Service.

현재 단계에서는 프론트엔드 명세 확정 전이므로 router/main.py 구현 전 공통 기반 레이어만 구성한다.

## 구조

- core: 환경변수, AWS client, security
- db: RDS MySQL connection
- services: S3, SQS, inference request business logic
- schemas: request/response schema
- routers: 추후 frontend 명세 반영
- models: 추후 users/request model 확장

## 실행 준비

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt