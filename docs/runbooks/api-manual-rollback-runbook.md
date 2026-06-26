# API 수동 Rollback Runbook

## 1. 문서 목적

이 문서는 API Service를 이전 정상 Task Definition Revision으로 수동 롤백하고, 정상 확인 후 최신 정상 Revision으로 복구하는 CLI 기반 절차형 Runbook이다.

본문 실행 명령어는 특정 revision 번호를 고정하지 않는다. 실제 장애 대응 시에는 반드시 현재 상태를 다시 조회한 뒤 아래 placeholder 값을 채워서 실행한다.

| 항목 | 값 |
|---|---|
| ECS Cluster | `securevoice-dev-cluster` |
| API Service | `securevoice-dev-api-service` |
| ECR Repository | `voice-api-service` |
| 현재 정상 Revision | `<API-현재-Revision>` |
| 이전 정상 Revision | `<API-이전-정상-Revision>` |
| 현재 이미지 태그 | `<API-현재-이미지-태그>` |
| 이전 정상 이미지 태그 | `<API-이전-정상-이미지-태그>` |
| API Health URL | `http://api-origin.mzmt.shop/api/health` |

## 2. 테스트 전 주의사항

- 현재 Revision과 이전 정상 Revision을 확인하기 전에는 update-service를 실행하지 않는다.
- 이전 정상 Revision이 참조하는 이미지가 ECR에 존재하는지 확인한다.
- Jenkins Pipeline이 동시에 실행 중이면 수동 롤백과 충돌할 수 있으므로 중단 또는 대기한다.
- Terraform apply로 API 롤백을 수행하지 않는다.
- DB schema나 secret 값을 임의 변경하지 않는다.

## 3. 현재 API Service 상태 확인

```powershell
aws ecs describe-services `
  --region ap-northeast-2 `
  --cluster securevoice-dev-cluster `
  --services securevoice-dev-api-service `
  --query "services[0].{TaskDefinition:taskDefinition,Desired:desiredCount,Running:runningCount}" `
  --output table
```

## 4. 현재 정상 Revision 기록

위 명령의 `TaskDefinition` 값을 `<API-현재-Revision>`에 기록한다. 이 값은 검증 후 원래 상태로 복구할 때 사용한다.

## 5. 이전 정상 Revision 후보 조회

```powershell
aws ecs list-task-definitions `
  --region ap-northeast-2 `
  --family-prefix securevoice-dev-api `
  --status ACTIVE `
  --sort DESC `
  --query "taskDefinitionArns[0:5]" `
  --output table
```

가장 최근 revision이 항상 rollback 대상이라고 가정하지 않는다. Jenkins 성공 이력, Slack 알림, Deployment Summary artifact, CloudWatch Logs를 함께 확인해 이전 정상 revision을 선정한다.

## 6. 이전 정상 Revision의 이미지 태그 확인

```powershell
aws ecs describe-task-definition `
  --region ap-northeast-2 `
  --task-definition <API-이전-정상-Revision> `
  --query "taskDefinition.containerDefinitions[].{Name:name,Image:image}" `
  --output table
```

출력된 image URI에서 `<API-이전-정상-이미지-태그>`를 기록한다.

## 7. ECR에 이전 이미지가 존재하는지 확인

```powershell
aws ecr describe-images `
  --region ap-northeast-2 `
  --repository-name voice-api-service `
  --image-ids imageTag=<API-이전-정상-이미지-태그> `
  --query "imageDetails[0].{Tag:imageTags[0],Digest:imageDigest}" `
  --output table
```

이미지가 없으면 다음 단계로 진행하지 않는다.

## 8. API Service를 이전 정상 Revision으로 수동 롤백

```powershell
aws ecs update-service `
  --region ap-northeast-2 `
  --cluster securevoice-dev-cluster `
  --service securevoice-dev-api-service `
  --task-definition <API-이전-정상-Revision> `
  --no-cli-pager
```

## 9. services-stable 대기

```powershell
aws ecs wait services-stable `
  --region ap-northeast-2 `
  --cluster securevoice-dev-cluster `
  --services securevoice-dev-api-service
```

## 10. 롤백 후 describe-services 확인

```powershell
aws ecs describe-services `
  --region ap-northeast-2 `
  --cluster securevoice-dev-cluster `
  --services securevoice-dev-api-service `
  --query "services[0].{TaskDefinition:taskDefinition,Desired:desiredCount,Running:runningCount}" `
  --output table
```

`TaskDefinition`이 `<API-이전-정상-Revision>`이고 Running Count가 Desired Count와 일치해야 한다.

## 11. 롤백 후 /api/health 확인

```powershell
Invoke-RestMethod http://api-origin.mzmt.shop/api/health
```

HTTP 200과 정상 payload를 확인한다.

## 12. 최신 정상 Revision으로 복구

롤백 검증 캡처를 완료한 뒤 최신 정상 revision으로 다시 복구한다.

```powershell
aws ecs update-service `
  --region ap-northeast-2 `
  --cluster securevoice-dev-cluster `
  --service securevoice-dev-api-service `
  --task-definition <API-현재-Revision> `
  --no-cli-pager
```

## 13. services-stable 대기

```powershell
aws ecs wait services-stable `
  --region ap-northeast-2 `
  --cluster securevoice-dev-cluster `
  --services securevoice-dev-api-service
```

## 14. 복구 후 describe-services 확인

```powershell
aws ecs describe-services `
  --region ap-northeast-2 `
  --cluster securevoice-dev-cluster `
  --services securevoice-dev-api-service `
  --query "services[0].{TaskDefinition:taskDefinition,Desired:desiredCount,Running:runningCount}" `
  --output table
```

`TaskDefinition`이 `<API-현재-Revision>`으로 돌아왔는지 확인한다.

## 15. 복구 후 /api/health 확인

```powershell
Invoke-RestMethod http://api-origin.mzmt.shop/api/health
```

## 16. 실패 시 중단 기준

아래 상황에서는 다음 단계로 진행하지 않고 중단한다.

- 현재 Revision을 확인하지 못한 경우
- 이전 정상 Revision을 확정하지 못한 경우
- 이전 정상 Revision이 참조하는 이미지가 ECR에 없는 경우
- update-service 실행 후 services-stable이 실패한 경우
- rollback 후 Running Count가 Desired Count와 일치하지 않는 경우
- API의 경우 `/api/health`가 실패하는 경우
- CloudWatch Logs 또는 ECS Events에서 반복적인 crash, image pull error, permission error가 확인되는 경우

중단 후에는 다음을 확인한다.

- ECS Service Events
- Stopped Task Reason
- CloudWatch Logs
- ECR 이미지 존재 여부
- Jenkins Pipeline과의 충돌 여부
- 담당자 승인 필요 여부


## 17. 검증 체크리스트

- [ ] 현재 정상 Revision 기록
- [ ] 이전 정상 Revision 확정
- [ ] 이전 정상 이미지 ECR 존재 확인
- [ ] 이전 정상 Revision으로 update-service 실행
- [ ] services-stable 성공
- [ ] rollback 후 Running Count와 Desired Count 일치
- [ ] rollback 후 `/api/health` 정상
- [ ] 최신 정상 Revision으로 복구
- [ ] 복구 후 services-stable 성공
- [ ] 복구 후 `/api/health` 정상


| 구분 | Task Definition Revision | 이미지 태그 |
|---|---|---|
| 현재 정상 Revision | `securevoice-dev-api:15` | `build-10-7e90b95` |
| 롤백 대상 Revision | `securevoice-dev-api:14` | `build-9-3331f49` |

