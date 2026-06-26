# API 배포 운영 Runbook

## 1. 문서 개요

이 문서는 API 배포 실패 또는 API 장애 발생 시 원인을 판단하기 위한 장애 판단용 Runbook이다.

- 대상 Jenkins Job: `api-service-cicd`
- 대상 ECS Service: `securevoice-dev-api-service`
- 대상 Health Check URL: `http://api-origin.mzmt.shop/api/health`
- 주요 점검 대상: Jenkins, ECR Image/Digest, ECS API Service, ECS Task Definition Revision, ALB Target Group, `/api/health`, CloudWatch Logs, Deployment Summary Artifact, Slack 알림

다루는 범위:

- Jenkins 실패 stage 확인
- Python Build/Test 실패 확인
- Docker Build/Smoke Test 실패 확인
- Trivy Warning Mode 확인
- ECR Push 실패 확인
- ECS Service Update 실패 확인
- ECS Stable Wait 실패 확인
- ALB Target Health 확인
- `/api/health` 확인
- CloudWatch Logs 확인
- Rollback 필요 여부 판단

다루지 않는 범위:

- Worker SQS polling 장애
- DLQ 유입 장애
- 모델 inference 장애
- RDS schema 변경
- Terraform apply 장애
- CloudFront/S3 frontend 장애

API는 SQS 메시지를 발행할 수 있지만, Queue 적체/DLQ/Worker inference 처리는 Worker Runbook에서 다룬다.

## 2. API 배포 아키텍처 및 배포 흐름

```text
GitHub
→ Jenkins API Pipeline
→ ECR
→ ECS API Service
→ ALB Target Group
→ /api/health
→ CloudWatch Logs
→ Slack Notification
```

API Service의 역할:

- 사용자 요청 수신
- wav 파일 `multipart/form-data` 수신
- S3 Audio Bucket 업로드
- RDS metadata 저장
- Free/Paid SQS 메시지 발행
- `request_id` 기반 결과 조회

Worker inference 자체는 API Runbook 범위가 아니다.

## 3. 정상 배포 기준

- Jenkins build result가 `SUCCESS`
- Python build/test 통과
- Docker image smoke test 통과
- Trivy scan이 `WARNING` mode로 실행됨
- ECR push 성공
- Image digest 확인
- ECS Task Definition Revision 생성
- ECS Service Update 요청 성공
- ECS service stable
- Running Task가 새 revision 사용
- ALB Target Group healthy target 존재
- `/api/health` HTTP 200 응답
- Deployment Summary Artifact 생성
- Slack 성공 알림 수신

## 4. API 장애 대응 우선순위

### 4.1 Jenkins 실행 자체가 안 됨

#### 증상

- Jenkins UI 접속 불가
- `api-service-cicd` Job이 시작되지 않음
- 수동 `Build Now`가 queue에만 머무름

#### 주요 원인

- Jenkins 서비스 또는 executor 장애
- Jenkins EC2/컨테이너 문제
- Jenkins UI 접근 경로 문제

#### 확인 방법

- Jenkins UI 접속 가능 여부 확인
- Jenkins queue 및 executor 상태 확인
- Jenkins node 상태 확인

#### 조치 방법

- executor 부족이면 대기 후 재시도
- Jenkins 자체 장애면 Jenkins 운영 담당자에게 에스컬레이션
- 애플리케이션 코드나 Terraform을 임의 변경하지 않음

#### 재시도 기준

- Jenkins UI 및 executor 정상
- `api-service-cicd` 수동 실행 가능

### 4.2 GitHub Webhook이 Jenkins를 트리거하지 못함

#### 증상

- GitHub push 후 Jenkins build가 자동 시작되지 않음
- Jenkins build 원인에 `Started by GitHub push`가 없음

#### 주요 원인

- GitHub Webhook 비활성화
- Payload URL 오류
- Webhook shared secret mismatch
- Jenkins `/github-webhook/` endpoint 접근 실패

#### 확인 방법

- GitHub Recent Deliveries에서 `ping`/`push` 이벤트 200 확인
- Jenkins build cause 확인
- Jenkins Job trigger 설정 확인

#### 조치 방법

- Webhook URL, Content type, push event, Active 상태 확인
- 기존 Jenkins/GitHub shared secret으로 재설정
- 긴급 시 `Build Now`로 수동 배포

#### 재시도 기준

- Recent Deliveries 200
- 작은 commit push 후 자동 build 시작

### 4.3 Source Checkout 실패

#### 증상

- Git clone/fetch/checkout 실패
- Jenkinsfile을 가져오지 못함

#### 주요 원인

- GitHub credential 문제
- Repository URL, Branch Specifier, Script Path 오류
- GitHub token 권한 부족

#### 확인 방법

- Jenkins Job SCM 설정 확인
- GitHub token credential 연결 확인
- Console Log의 Git 오류 확인

#### 조치 방법

- 기존 정상 Job 설정과 비교
- token 권한 또는 branch 이름 수정

#### 재시도 기준

- Jenkins가 대상 branch의 Jenkinsfile을 정상 checkout

### 4.4 Python Build & Test 실패

#### 증상

- dependency 설치 실패
- import error
- pytest 실패

#### 주요 원인

- `requirements.txt` 변경 문제
- Python 버전/패키지 호환성 문제
- 테스트 코드 실패
- 환경 변수 의존성 누락

#### 확인 방법

- Jenkins Console Log에서 pip/pytest 실패 위치 확인
- 최근 commit의 dependency 변경 확인
- 테스트 실패가 배포 차단 조건인지 확인

#### 조치 방법

- dependency version 또는 import 경로 수정
- 실패 테스트 원인 수정
- 민감 환경 변수를 로그에 노출하지 않음

#### 재시도 기준

- requirements 설치 성공
- import와 pytest 모두 통과

### 4.5 Docker Image Build 실패

#### 증상

- BuildKit image build 실패
- base image pull 실패
- requirements install 실패

#### 주요 원인

- Dockerfile 경로/문법 문제
- Docker daemon/socket 문제
- registry 접근 실패
- Jenkins workspace 권한 문제

#### 확인 방법

- Dockerfile 경로 확인
- BuildKit 사용 로그 확인
- base image pull 오류 확인
- Docker socket 접근 가능 여부 확인

#### 조치 방법

- Dockerfile 또는 dependency 오류 수정
- Docker daemon 상태 확인
- Jenkins 권한 문제는 인프라 담당자와 분리 검토

#### 재시도 기준

- BuildKit build 성공 및 image tag 생성

### 4.6 Docker Image Smoke Test 실패

#### 증상

- 컨테이너 실행 실패
- 로컬 `/api/health` smoke test 실패
- 포트 8000 응답 실패

#### 주요 원인

- 컨테이너 entrypoint 오류
- FastAPI app import 실패
- 포트 설정 오류
- 필수 환경 변수 의존성 문제

#### 확인 방법

- smoke test container 로그 확인
- 컨테이너가 포트 8000에서 기동되는지 확인
- `/api/health` 로컬 응답 확인
- smoke test container cleanup 여부 확인

#### 조치 방법

- app startup 오류 수정
- Dockerfile/entrypoint/환경 변수 의존성 수정

#### 재시도 기준

- smoke container 정상 기동 및 `/api/health` 응답

### 4.7 Trivy Scan 실패 또는 finding 존재

#### 증상

- Trivy 실행 실패
- HIGH/CRITICAL finding 존재

#### 주요 원인

- Trivy DB 다운로드 실패
- 이미지 취약점 발견
- 네트워크 일시 장애

#### 확인 방법

- Trivy summary/artifact 확인
- `Trivy Mode=WARNING`
- `Trivy Gate=NOT_APPLIED`

#### 조치 방법

- Trivy 실행 실패면 네트워크/도구 상태 확인 후 재시도
- finding은 별도 보안 조치 항목으로 등록
- 현재 finding 자체는 배포 차단 또는 rollback 원인이 아님

#### 재시도 기준

- Trivy scan 완료 및 summary/artifact 생성

### 4.8 ECR Login/Push 실패

#### 증상

- ECR login 실패
- image push 실패
- digest 조회 실패

#### 주요 원인

- Jenkins Role 권한 부족
- ECR repository 이름 오류
- AWS CLI 인증 문제
- ECR 일시 장애

#### 확인 방법

- ECR login 로그 확인
- repository name, image tag 확인
- image digest 조회 결과 확인
- Jenkins EC2 IAM Role 권한 확인

#### 조치 방법

- ECR repository와 region 확인
- 권한 문제는 Jenkins Role policy 확인
- tag 충돌 또는 네트워크 장애 여부 확인

#### 재시도 기준

- ECR push 완료
- image digest 확인 가능

### 4.9 ECS Task Definition Revision Register 실패

#### 증상

- 새 task definition revision 등록 실패
- task-definition JSON 생성 또는 AWS CLI 오류 발생

#### 주요 원인

- 기존 task definition 조회 실패
- 새 image URI 반영 실패
- task role/execution role/log 설정 누락
- IAM 권한 부족

#### 확인 방법

- 기존 task definition 조회 로그 확인
- 생성된 task definition JSON artifact 확인
- image URI와 digest 확인
- 기존 환경 변수/role/log 설정 유지 여부 확인

#### 조치 방법

- task definition JSON 오류 수정
- image URI 반영 로직 확인
- role/log/secret 설정을 임의 변경하지 않음

#### 재시도 기준

- 새 revision 등록 성공

### 4.10 ECS Service Update 실패

#### 증상

- `aws ecs update-service` 실패
- service update 요청 직후 오류

#### 주요 원인

- Service/Cluster 이름 오류
- task definition ARN 오류
- IAM 권한 부족
- ECS service 상태 문제

#### 확인 방법

- cluster/service 이름 확인
- requested task definition 확인
- circuit breaker enable/rollback 상태 확인
- ECS Service Events 확인

#### 조치 방법

- ARN/name 오류 수정
- 권한 문제 확인
- Service Update 전 실패라면 rollback 불필요

#### 재시도 기준

- `update-service` 요청 성공

### 4.11 ECS Stable Wait 실패

#### 증상

- `aws ecs wait services-stable` timeout 또는 실패
- task 반복 stop/restart

#### 주요 원인

- 새 container 기동 실패
- ALB health check 실패
- desired/running count 불일치
- ECS Circuit Breaker rollback 발생

#### 확인 방법

- ECS deployments 상태 확인
- ECS Service Events 확인
- Running/Stopped task 상태 확인
- CloudWatch Logs 확인
- final revision과 requested revision 비교

#### 조치 방법

- ECS가 baseline으로 rollback했는지 확인
- Jenkins rollback result 확인
- stopped reason과 로그 기반 원인 분석

#### 재시도 기준

- ECS service stable
- final revision이 expected revision 또는 baseline으로 명확히 정리됨

### 4.12 ALB Target Health 실패

#### 증상

- ALB Target Group healthy target 부족
- target 상태가 unhealthy/draining

#### 주요 원인

- `/api/health` 실패
- 컨테이너 포트/보안그룹 문제
- task 기동 지연
- 애플리케이션 startup 오류

#### 확인 방법

- Target Group health details 확인
- health check path `/api/health` 확인
- ECS task 상태와 CloudWatch Logs 확인

#### 조치 방법

- unhealthy reason 기준으로 포트, path, app log 확인
- rollback 이후 healthy target 복구 여부 확인

#### 재시도 기준

- healthy target 존재
- desired/running count 정상

### 4.13 `/api/health` 실패

#### 증상

- `/api/health` HTTP 200 실패
- payload가 기대값과 다름

#### 주요 원인

- API app startup 오류
- routing 오류
- DB/외부 의존성 오류
- 잘못된 image/revision 배포

#### 확인 방법

```bash
curl -i http://api-origin.mzmt.shop/api/health
```

- Jenkins Console Log의 Post-Deploy Verification 확인
- CloudWatch Logs의 health endpoint 처리 오류 확인

#### 조치 방법

- CloudWatch Logs에서 예외 확인
- final revision 확인
- 필요 시 rollback result 확인

#### 재시도 기준

- `/api/health` HTTP 200 및 정상 payload 확인

### 4.14 Rollback 실패

#### 증상

- rollback result가 `RECOVERY_VERIFIED`가 아님
- final revision이 baseline과 다름
- rollback 후 health check 실패

#### 주요 원인

- ECS Service Update 실패
- baseline revision 정보 누락
- 외부 배포 개입
- rollback 후 task 기동 실패

#### 확인 방법

- Baseline Revision, Failed Revision, Final Revision 확인
- ECS Service Events 확인
- `/api/health`와 ALB Target Health 확인

#### 조치 방법

- 마지막 정상 revision으로 수동 복구가 필요하면 `API 수동 Rollback Runbook`으로 이동
- 외부 변경 여부 확인
- 실패 revision 원인 분석 기록

#### 재시도 기준

- final revision이 baseline 또는 의도한 정상 revision으로 복구
- ALB Target Health와 `/api/health` 정상

### 4.15 Slack Notification 실패

#### 증상

- 배포 결과는 나왔지만 Slack 알림이 오지 않음
- Console Log에 Slack 전송 실패 메시지 표시

#### 주요 원인

- Jenkins credential `slack-webhook-url` 문제
- Slack webhook 만료
- Slack API/네트워크 장애

#### 확인 방법

- Jenkins Console Log 확인
- credential ID 존재 여부 확인
- Slack Webhook URL 값은 출력하지 않음

#### 조치 방법

- Slack credential 상태 확인
- Slack 실패는 배포 실패와 동일한 의미가 아님

#### 재시도 기준

- Slack 알림 정상 수신

### 4.16 Deployment Summary Artifact 누락

#### 증상

- Jenkins Artifacts에 deployment summary가 없음
- image/digest/revision/rollback 결과 확인이 어려움

#### 주요 원인

- summary 생성 전 stage 실패
- archiveArtifacts 실패
- workspace 권한 문제

#### 확인 방법

- Jenkins artifact 목록 확인
- Console Log에서 summary 생성/archiving 로그 확인

#### 조치 방법

- 실패 stage 해결 후 재실행
- summary만 누락되면 Console Log와 Slack을 함께 확인

#### 재시도 기준

- Deployment Summary Artifact 생성 및 archive 완료

## 5. API Stage별 상세 장애 대응

### Python Build & Test

- requirements 설치 실패 여부
- import 실패 여부
- pytest 실패 여부
- 환경 변수 의존성 문제
- 테스트 실패가 배포 차단 사유인지 확인

테스트 실패는 배포 차단 사유로 본다.

### Docker Image Build

- Dockerfile 경로
- BuildKit 사용 여부
- base image pull 실패
- requirements install 실패
- Docker daemon/socket 문제
- Jenkins workspace 권한 문제

Docker socket 사용은 운영 리스크가 있으므로 후속 고도화 항목으로 관리한다.

### Docker Image Smoke Test

- 컨테이너 실행 여부
- `/api/health` 로컬 smoke test 응답
- 포트 8000
- 컨테이너 로그
- smoke test container cleanup 여부

### Trivy Image Scan

- 현재 Trivy는 `WARNING` 모드이다.
- `HIGH/CRITICAL` finding이 있어도 현재는 배포 차단 Gate가 아니다.
- `Trivy Gate=NOT_APPLIED`
- finding은 별도 보안 조치 항목으로 관리한다.
- 발표/보고서에서는 “취약점 스캔은 수행하지만 차단 정책은 후속 고도화”라고 설명한다.

### ECR Push

- ECR login 성공
- repository name
- image tag
- image digest
- ECR 권한
- Jenkins Role 권한
- push retry 여부

### ECS Deploy

- 기존 Task Definition 조회
- 새 image URI로 revision 생성
- 기존 환경 변수/role/log 설정 유지 여부
- ECS Service Update 요청 성공 여부
- circuit breaker enable/rollback 상태
- services-stable 성공 여부

### Post-Deploy Verification

- ECS Running Task revision
- ALB Target Health
- `/api/health`
- CloudWatch Logs
- ECS Service Events

### Rollback 필요 여부 판단

- Baseline Revision
- Failed Revision
- Final Revision
- Baseline Restored
- Rollback Result
- `/api/health` 복구 여부
- ALB Target Health 복구 여부

수동 복구가 필요한 경우 아래 절차형 Runbook을 따른다.

- API 수동 Rollback Runbook: `docs/runbooks/api-manual-rollback-runbook.md`

## 6. API 수동 복구 판단 절차

1. Slack 실패 알림에서 Jenkins Build URL 확인
2. Failed Stage 확인
3. Jenkins Console Log 확인
4. ECS Service Events 확인
5. Running Task revision 확인
6. ALB Target Health 확인
7. `/api/health` 확인
8. CloudWatch Logs 확인
9. Rollback Result 확인
10. Jenkins 자동 rollback으로 복구되지 않은 경우 `API 수동 Rollback Runbook`으로 이동

주의:

- 즉시 Terraform apply로 해결하지 않는다.
- DB schema를 임의 변경하지 않는다.
- Worker/SQS/DLQ 장애를 API 배포 실패로 오인하지 않는다.

## 7. API Rollback 판단 기준

자동 rollback이 시도될 수 있는 조건:

- ECS Service Update 이후 실패
- ECS Stable Wait 실패
- Post-Deploy Verification 실패
- final revision이 requested revision으로 남아 있고 baseline 복구가 필요한 경우

rollback이 필요 없는 조건:

- Service Update 전 실패
- ECS Circuit Breaker가 이미 baseline으로 복구한 경우
- 외부 업데이트가 감지되어 자동 rollback이 위험한 경우

검증 기준:

- Baseline Revision과 Final Revision 비교
- ALB Target Health 복구 확인
- `/api/health` 복구 확인
- Running Task revision 확인

## 8. API 보안 및 운영 주의사항

- AWS Access Key를 Jenkins Credential에 직접 저장하지 않는다.
- Jenkins는 EC2 IAM Role 기반으로 AWS 인증을 수행한다.
- Slack Webhook URL은 문서나 로그에 노출하지 않는다.
- GitHub token은 문서나 로그에 노출하지 않는다.
- Trivy Warning Mode와 Gate 미적용 상태를 구분한다.
- Docker socket mount 리스크는 후속 고도화 항목이다.
- API desired count가 1인 환경에서는 완전 무중단 배포라고 표현하지 않는다.
- 발표/보고서에서는 “중단 위험을 줄이는 rolling deployment와 rollback 구조”로 표현한다.
