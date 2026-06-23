# API 배포 운영 Runbook

## 1. 목적

이 문서는 API 배포 실패, API rollback 결과, API AI Failure Summary Slack 알림 이후 운영자가 실제로 어떤 순서로 확인해야 하는지 정리한 운영 Runbook입니다.

API Service는 ALB를 통해 외부 요청을 받는 FastAPI 기반 서비스입니다. 따라서 API 장애 대응의 핵심 점검 대상은 Jenkins, ECS Service, ALB Target Group, `/api/health`, CloudWatch Logs입니다.

Worker처럼 SQS 메시지를 직접 소비하는 구조가 아니므로, API Runbook에서는 SQS/DLQ를 핵심 점검 항목으로 두지 않습니다. 필요 시 API가 SQS 메시지 발행 단계까지 도달했는지 정도만 후속 연계 확인으로 다룹니다. SQS/DLQ 상세 점검은 Worker Runbook에서 수행합니다.

## 2. 연결되는 Slack 알림

| 우선순위 | Runbook 필요한 부분 | Slack 알림 | 왜 필요한지 |
| --- | --- | --- | --- |
| 1 | API 배포 실패 | `API deployment failed` | ECS 배포 전/후 어디서 실패했는지 확인하고 Jenkins, ECS, ALB, Logs를 점검해야 합니다. |
| 2 | API 롤백 결과 | `API rollback result` | `RECOVERY_VERIFIED` 이후 실제 ECS revision, ALB target health, 서비스 정상성을 후속 확인해야 합니다. |
| 3 | API AI Failure Summary | `API AI Failure Summary` | AI가 제시한 `Next Action`을 실제 운영 점검 절차로 연결해야 합니다. |

## 3. 빠른 점검 순서

1. Slack 알림의 Jenkins Build URL을 확인합니다.
2. Jenkins Build 결과를 확인합니다.
3. `Deploy Phase`를 확인합니다.
4. `Service Update State`를 확인합니다.
5. `Rollback Needed` 값을 확인합니다.
6. Rollback 결과 Slack 알림을 확인합니다.
7. `Rollback Result`를 확인합니다.
8. `Baseline Revision`과 `Final Revision`을 비교합니다.
9. `Baseline Restored`가 `true`인지 확인합니다.
10. ECS Service의 현재 Task Definition을 확인합니다.
11. Desired count와 Running count가 일치하는지 확인합니다.
12. ALB Target Group에 healthy target이 있는지 확인합니다.
13. `/api/health`가 HTTP 200으로 응답하는지 확인합니다.
14. CloudWatch Logs에서 API 애플리케이션 오류를 확인합니다.
15. 필요 시 ECS Service Events에서 배포 이벤트를 확인합니다.

## 4. Jenkins 확인 항목

| 확인 항목 | 기대 값 / 확인 의미 |
| --- | --- |
| Build 결과 | 정상 배포는 `SUCCESS`, 실패 테스트는 `FAILED` 가능 |
| Deploy Phase | 예: `POST_DEPLOY_VERIFICATION_FAILED` |
| Service Update State | `AFTER_ECS_SERVICE_UPDATE`이면 rollback 대상일 수 있음 |
| Rollback Needed | rollback 필요 여부 |
| Rollback Attempted | rollback 시도 여부 |
| Rollback Result | `RECOVERY_VERIFIED` 여부 |
| Baseline Revision | rollback 기준 revision |
| Final Revision | rollback 후 최종 revision |
| Baseline Restored | `true` 여부 |
| Deployment Summary Artifact | image, digest, revision, rollback 결과 확인 |
| Trivy Artifact | 상세 보안 스캔 JSON |
| Trivy Mode | `WARNING` |
| Trivy Gate | `NOT_APPLIED` |

## 5. ECS 확인 항목

| 확인 항목 | 확인 위치 | 기대 값 / 확인 의미 |
| --- | --- | --- |
| Service task definition | ECS Service Overview | Slack의 `Final Revision`과 일치 |
| Deployment status | ECS Service Deployment 탭 | 성공 또는 완료 상태 |
| Desired / Running count | ECS Service Overview | Desired count와 Running count 일치 |
| Running Task revision | ECS Service Tasks 탭 | Running Task가 `Final Revision` 사용 |
| ECS Service Events | ECS Service Events 탭 | `deployment completed`, `steady state` 이벤트 확인 |
| Deployment circuit breaker | ECS Service Configuration | `enable=true`, `rollback=true` |

## 6. ALB 확인 항목

| 확인 항목 | 확인 위치 | 기대 값 / 확인 의미 |
| --- | --- | --- |
| Target Group Healthy | EC2 Target Groups | healthy target 존재 |
| Health check path | Target Group Health checks | `/api/health` |
| Success code | Target Group Health checks | `200` |
| Target unhealthy reason | Target health details | unhealthy 시 reason 확인 |
| 실제 API Health 응답 | 브라우저, curl, PowerShell | `/api/health` HTTP 200 및 정상 payload |

## 7. CloudWatch Logs 확인 항목

CloudWatch Logs에서는 API 컨테이너와 애플리케이션 레벨 오류를 확인합니다.

| 확인 항목 | 확인 의미 |
| --- | --- |
| API 컨테이너 기동 오류 | 컨테이너 시작 실패, import 실패, 설정 누락 여부 확인 |
| `/api/health` 요청 처리 오류 | health endpoint 라우팅 또는 애플리케이션 처리 오류 확인 |
| DB 연결 오류 | DB 접속 실패, 인증 실패, 네트워크 경로 문제 확인 |
| S3 연계 호출 오류 | 업로드/다운로드 연계 호출 실패 여부 확인 |
| SQS 메시지 발행 호출 오류 | API가 Worker 처리 요청을 큐에 발행하는 단계의 실패 여부 확인 |
| 애플리케이션 예외 로그 | FastAPI 예외, validation 오류, 내부 서버 오류 확인 |

API Runbook에서 SQS는 메시지 발행 호출 여부만 후속 연계 확인으로 다룹니다. SQS Queue 적체, DLQ 유입, 메시지 재처리 여부는 Worker Runbook의 중심 점검 항목입니다.

## 8. Rollback 검증 기준

아래 조건이 모두 충족되면 API rollback이 정상 복구된 것으로 판단합니다.

- `Rollback Result=RECOVERY_VERIFIED`
- `Baseline Revision`과 `Final Revision`이 같습니다.
- `Baseline Restored=true`
- ECS Service task definition이 `Final Revision`과 일치합니다.
- Desired count와 Running count가 정상입니다.
- ALB Target Group에 healthy target이 존재합니다.
- `/api/health`가 HTTP 200으로 응답합니다.

## 9. 다음 조치

| 상황 | 조치 |
| --- | --- |
| Rollback 복구 완료 | baseline revision을 유지하고 실패 revision의 Jenkins/ECS/CloudWatch 로그를 확인합니다. |
| Rollback 실패 | 마지막 정상 task definition으로 ECS Service를 수동 업데이트합니다. |
| ALB target unhealthy | Target health reason, ECS task logs, `/api/health` 응답을 확인합니다. |
| `/api/health` 실패 | API 컨테이너 로그, 라우팅, 포트, 애플리케이션 상태를 확인합니다. |
| ECS task가 RUNNING이 아님 | stopped reason, ECS events, CloudWatch Logs를 확인합니다. |
| CloudWatch Logs에서 애플리케이션 오류 발견 | 오류 원인별 조치를 기록하고 재배포 여부를 판단합니다. |
| Trivy finding 존재 | Trivy는 Warning Mode이므로 rollback 원인으로 판단하지 않고 별도 보안 조치 항목으로 관리합니다. |

## 10. 주의사항

- Trivy finding을 배포 실패 또는 rollback 원인으로 판단하지 않습니다.
- Trivy는 현재 `WARNING` 모드이고 `Gate=NOT_APPLIED`입니다.
- Trivy finding은 별도 보안 조치 항목으로 관리합니다.
- API 장애 대응은 ALB/ECS/CloudWatch 중심으로 수행합니다.
- Worker 장애 대응은 ECS/SQS/DLQ/CloudWatch 중심으로 수행합니다.
- API Runbook에서 SQS/DLQ를 핵심 점검 대상으로 두지 않습니다.
- 민감정보, Account ID, Secret ARN, DB 정보는 문서나 캡처에 직접 노출하지 않습니다.

