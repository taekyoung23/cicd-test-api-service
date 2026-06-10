pipeline {
    agent any

    options {
        // 장애 분석을 위해 로그에 시간을 기록하고, 동일 Job의 배포가 동시에 실행되지 않도록 합니다.
        timestamps()
        disableConcurrentBuilds()
        // Jenkins 저장공간이 계속 증가하지 않도록 최근 빌드 이력 20개만 보관합니다.
        buildDiscarder(logRotator(numToKeepStr: '20'))
        // 명령 또는 AWS 배포가 장시간 멈춰 있으면 전체 Pipeline을 종료합니다.
        timeout(time: 30, unit: 'MINUTES')
    }

    environment {
        DOCKER_BUILDKIT = '1'
        APP_ENV = 'ci'
        INPUT_BUCKET = 'ci-placeholder-input-bucket'
        RESULT_BUCKET = 'ci-placeholder-result-bucket'
        AWS_REGION = 'ap-northeast-2'
        AWS_ACCOUNT_ID = '455535733131'
        ECR_REPOSITORY = 'voice-api-service'
        ECS_CLUSTER_NAME = 'securevoice-dev-cluster'
        ECS_SERVICE_NAME = 'securevoice-dev-api-service'
        ECS_TASK_FAMILY = 'securevoice-dev-api'
        CONTAINER_NAME = 'api'
        // ECS와 ALB가 안정화된 후 실제 API 응답을 확인할 주소입니다.
        API_HEALTH_URL = 'http://api-origin.mzmt.shop/api/health'
    }

    stages {
        // Webhook을 발생시킨 커밋을 Checkout하고 빌드마다 고유한 이미지 태그를 생성합니다.
        stage('Source Checkout') {
            steps {
                checkout scm
                script {
                    // 전체 SHA는 배포 추적용으로, 짧은 SHA는 이미지 태그용으로 저장합니다.
                    env.GIT_COMMIT_SHA = sh(
                        script: 'git rev-parse HEAD',
                        returnStdout: true
                    ).trim()
                    env.GIT_SHORT_SHA = sh(
                        script: 'git rev-parse --short=7 HEAD',
                        returnStdout: true
                    ).trim()
                    env.GIT_REPOSITORY_URL = sh(
                        script: 'git config --get remote.origin.url',
                        returnStdout: true
                    ).trim()
                    env.IMAGE_TAG = "build-${env.BUILD_NUMBER}-${env.GIT_SHORT_SHA}"
                }
                echo "Image tag: ${env.IMAGE_TAG}"
            }
        }

        // Python 문법과 주요 모듈 Import를 검증하고, 테스트 파일이 있으면 pytest를 실행합니다.
        stage('Python Build & Test') {
            steps {
                sh '''
                    set -eu
                    python3 -m venv .venv
                    . .venv/bin/activate
                    python -m pip install --upgrade pip setuptools wheel
                    pip install -r requirements.txt
                    python -m compileall app
                    python -c "from app.main import app"
                    if find . -maxdepth 3 -type f \\( -name "test_*.py" -o -name "*_test.py" \\) | grep -q .; then
                      pip install pytest
                      pytest
                    else
                      echo "No pytest test files found. Skipping pytest."
                    fi
                '''
            }
        }

        // Jenkins 빌드 번호와 커밋 SHA를 사용하여 API 이미지를 한 번 빌드합니다.
        stage('BuildKit Image Build') {
            steps {
                script {
                    env.ECR_REGISTRY = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_REGION}.amazonaws.com"
                    env.IMAGE_URI = "${env.ECR_REGISTRY}/${env.ECR_REPOSITORY}:${env.IMAGE_TAG}"
                }
                sh '''
                    set -eu
                    docker build \
                      --progress=plain \
                      --label securevoice.service=api \
                      --label securevoice.git_sha="${GIT_SHORT_SHA}" \
                      --label securevoice.jenkins_build="${BUILD_NUMBER}" \
                      -t "${IMAGE_URI}" \
                      .
                '''
            }
        }

        // 빌드한 이미지를 로컬 컨테이너로 실행하고 API Health Endpoint를 확인합니다.
        stage('Docker Image Smoke Test') {
            steps {
                sh '''
                    set -eu
                    CONTAINER_NAME="api-smoke-${BUILD_NUMBER}"

                    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

                    cleanup() {
                      docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
                    }
                    trap cleanup EXIT

                    docker run -d \
                      --name "${CONTAINER_NAME}" \
                      -e APP_ENV="${APP_ENV}" \
                      -e INPUT_BUCKET="${INPUT_BUCKET}" \
                      -e RESULT_BUCKET="${RESULT_BUCKET}" \
                      "${IMAGE_URI}"

                    for i in $(seq 1 30); do
                      if docker exec -i "${CONTAINER_NAME}" python - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))

if payload.get("status") != "ok":
    raise SystemExit(f"unexpected health payload: {payload}")

print(payload)
PY
                      then
                        echo "API Docker image smoke test passed."
                        exit 0
                      fi

                      echo "Waiting for API container health check... attempt=${i}"
                      docker logs --tail=20 "${CONTAINER_NAME}" || true
                      sleep 2
                    done

                    echo "API Docker image smoke test failed."
                    docker logs "${CONTAINER_NAME}" || true
                    exit 1
                '''
            }
        }

        // 이미지를 Push하기 전에 Docker가 ECR에 인증하도록 로그인합니다.
        stage('ECR Login') {
            steps {
                // ECR Login은 ECS 배포 상태를 변경하지 않으므로 일시적 실패 시 재시도합니다.
                retry(2) {
                    sh '''
                        set -eu
                        aws ecr get-login-password --region "${AWS_REGION}" \
                          | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
                    '''
                }
            }
        }

        // Smoke Test를 통과한 동일 이미지를 ECR에 Push합니다.
        stage('ECR Push') {
            steps {
                // 동일한 고유 빌드 태그의 Push는 일시적 네트워크 실패 후 재시도해도 안전합니다.
                retry(2) {
                    sh '''
                        set -eu
                        docker push "${IMAGE_URI}"
                    '''
                }
                // Push 직후 ECR 메타데이터 조회가 잠시 지연될 수 있어 읽기 작업만 재시도합니다.
                retry(3) {
                    script {
                        env.IMAGE_DIGEST = sh(
                            script: '''
                                set -eu
                                aws ecr describe-images \
                                  --region "${AWS_REGION}" \
                                  --repository-name "${ECR_REPOSITORY}" \
                                  --image-ids imageTag="${IMAGE_TAG}" \
                                  --query 'imageDetails[0].imageDigest' \
                                  --output text
                            ''',
                            returnStdout: true
                        ).trim()
                    }
                }
                echo "Published image digest: ${env.IMAGE_DIGEST}"
            }
        }

        // 배포 전에 설정된 ECS Service와 Task Definition Family가 존재하는지 확인합니다.
        stage('ECS Deploy Dry Check') {
            steps {
                sh '''
                    set -eu
                    aws sts get-caller-identity --query Account --output text >/dev/null
                    aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].serviceName' \
                      --output text
                    aws ecs describe-task-definition \
                      --region "${AWS_REGION}" \
                      --task-definition "${ECS_TASK_FAMILY}" \
                      --query 'taskDefinition.family' \
                      --output text
                    echo "ECS deploy dry check complete for ${ECS_SERVICE_NAME} using ${IMAGE_URI}"
                '''
            }
        }

        // 현재 Task Definition을 복제하고 새 이미지가 반영된 Revision을 등록합니다.
        stage('ECS Task Definition Revision Register') {
            steps {
                script {
                    // 중복 Revision 생성을 방지하기 위해 상태 변경 명령은 의도적으로 재시도하지 않습니다.
                    env.NEW_TASK_DEFINITION_ARN = sh(
                        script: '''
                            set -eu
                            aws ecs describe-task-definition \
                              --region "${AWS_REGION}" \
                              --task-definition "${ECS_TASK_FAMILY}" \
                              --query taskDefinition \
                              --output json > task-definition-current.json

                            python3 - <<'PY'
import json
import os

image_uri = os.environ["IMAGE_URI"]
container_name = os.environ["CONTAINER_NAME"]

with open("task-definition-current.json", "r", encoding="utf-8") as f:
    current = json.load(f)

found = False
for container in current.get("containerDefinitions", []):
    if container.get("name") == container_name:
        container["image"] = image_uri
        found = True
        break

if not found:
    raise SystemExit(f"container not found in task definition: {container_name}")

allowed = [
    "family",
    "taskRoleArn",
    "executionRoleArn",
    "networkMode",
    "containerDefinitions",
    "volumes",
    "placementConstraints",
    "requiresCompatibilities",
    "cpu",
    "memory",
    "runtimePlatform",
    "ipcMode",
    "pidMode",
    "proxyConfiguration",
    "inferenceAccelerators",
    "ephemeralStorage",
]

next_def = {
    key: current[key]
    for key in allowed
    if key in current and current[key] is not None
}

with open("task-definition-new.json", "w", encoding="utf-8") as f:
    json.dump(next_def, f, indent=2)
PY

                            aws ecs register-task-definition \
                              --region "${AWS_REGION}" \
                              --cli-input-json file://task-definition-new.json \
                              --query 'taskDefinition.taskDefinitionArn' \
                              --output text
                        ''',
                        returnStdout: true
                    ).trim()
                    echo "Registered new task definition revision: ${env.NEW_TASK_DEFINITION_ARN}"
                }
            }
        }

        // API ECS Service가 새로 등록한 Task Definition Revision을 사용하도록 변경합니다.
        stage('ECS Service Update') {
            steps {
                // 배포 이력이 불명확해지는 것을 방지하기 위해 Service Update는 한 번만 실행합니다.
                sh '''
                    set -eu
                    CIRCUIT_BREAKER="$(aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].deploymentConfiguration.deploymentCircuitBreaker.[enable,rollback]' \
                      --output text)"

                    if ! printf '%s\n' "${CIRCUIT_BREAKER}" | awk '$1 == "True" && $2 == "True" { enabled = 1 } END { exit !enabled }'; then
                      echo "ECS deployment circuit breaker with rollback must be enabled before deployment: ${CIRCUIT_BREAKER}"
                      exit 1
                    fi

                    aws ecs update-service \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --service "${ECS_SERVICE_NAME}" \
                      --task-definition "${NEW_TASK_DEFINITION_ARN}" \
                      --no-cli-pager >/dev/null
                    echo "ECS service update requested: ${ECS_SERVICE_NAME}"
                '''
            }
        }

        // ECS Rolling Update가 완료되고 Service가 안정 상태가 될 때까지 기다립니다.
        stage('ECS Stable Wait') {
            options {
                // Rolling Update 시간은 허용하되 무기한 대기하지 않도록 제한합니다.
                timeout(time: 15, unit: 'MINUTES')
            }
            steps {
                sh '''
                    set -eu
                    WAIT_EXIT=0
                    set +e
                    aws ecs wait services-stable \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" || WAIT_EXIT=$?
                    set -e

                    aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].deployments[].{Status:status,RolloutState:rolloutState,TaskDefinition:taskDefinition,Desired:desiredCount,Running:runningCount,Failed:failedTasks}' \
                      --output table

                    aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].events[0:10].[createdAt,message]' \
                      --output table

                    FINAL_TASK_DEFINITION_ARN="$(aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].taskDefinition' \
                      --output text)"

                    echo "Requested task definition: ${NEW_TASK_DEFINITION_ARN}"
                    echo "Final service task definition: ${FINAL_TASK_DEFINITION_ARN}"

                    if [ "${WAIT_EXIT}" -ne 0 ]; then
                      echo "ECS service did not reach stable state. Check deployment state and recent events above."
                      exit "${WAIT_EXIT}"
                    fi

                    if [ "${FINAL_TASK_DEFINITION_ARN}" != "${NEW_TASK_DEFINITION_ARN}" ]; then
                      echo "Requested API revision is not active. ECS Circuit Breaker rollback or another service update occurred."
                      exit 1
                    fi

                    echo "ECS service is stable: ${ECS_SERVICE_NAME}"
                '''
            }
        }

        // 새 Revision 실행 여부, ALB Target 상태, 실제 API 응답을 검증합니다.
        stage('Post-Deploy Verification') {
            options {
                // ECS 안정화 이후의 검증은 짧은 시간 안에 완료되어야 합니다.
                timeout(time: 5, unit: 'MINUTES')
            }
            steps {
                sh '''
                    set -eu

                    FINAL_TASK_DEFINITION_ARN="$(aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].taskDefinition' \
                      --output text)"

                    if [ "${FINAL_TASK_DEFINITION_ARN}" != "${NEW_TASK_DEFINITION_ARN}" ]; then
                      echo "API service revision changed before post-deploy verification completed."
                      echo "Requested task definition: ${NEW_TASK_DEFINITION_ARN}"
                      echo "Final service task definition: ${FINAL_TASK_DEFINITION_ARN}"
                      exit 1
                    fi

                    RUNNING_TASK_ARNS="$(aws ecs list-tasks \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --service-name "${ECS_SERVICE_NAME}" \
                      --desired-status RUNNING \
                      --query 'taskArns' \
                      --output text)"

                    if [ -z "${RUNNING_TASK_ARNS}" ] || [ "${RUNNING_TASK_ARNS}" = "None" ]; then
                      echo "No RUNNING API tasks found."
                      exit 1
                    fi

                    UNEXPECTED_TASKS="$(aws ecs describe-tasks \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --tasks ${RUNNING_TASK_ARNS} \
                      --query "tasks[?taskDefinitionArn!='${NEW_TASK_DEFINITION_ARN}'].taskArn" \
                      --output text)"

                    if [ -n "${UNEXPECTED_TASKS}" ] && [ "${UNEXPECTED_TASKS}" != "None" ]; then
                      echo "RUNNING tasks still use an unexpected task definition: ${UNEXPECTED_TASKS}"
                      exit 1
                    fi

                    TARGET_GROUP_ARN="$(aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].loadBalancers[0].targetGroupArn' \
                      --output text)"

                    TARGET_HEALTH_STATES="$(aws elbv2 describe-target-health \
                      --region "${AWS_REGION}" \
                      --target-group-arn "${TARGET_GROUP_ARN}" \
                      --query 'TargetHealthDescriptions[].TargetHealth.State' \
                      --output text)"

                    DESIRED_COUNT="$(aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].desiredCount' \
                      --output text)"

                    HEALTHY_TARGET_COUNT="$(printf '%s\n' ${TARGET_HEALTH_STATES} \
                      | awk '$1 == "healthy" { count++ } END { print count + 0 }')"

                    # Rolling Update 직후에는 이전 Target이 잠시 draining 상태로 남을 수 있습니다.
                    # 모든 Target이 healthy인지 확인하지 않고 desiredCount 이상 healthy인지 확인합니다.
                    if [ "${HEALTHY_TARGET_COUNT}" -lt "${DESIRED_COUNT}" ]; then
                      echo "Healthy API targets (${HEALTHY_TARGET_COUNT}) are fewer than desired tasks (${DESIRED_COUNT})."
                      exit 1
                    fi

                    python3 - <<'PY'
import json
import os
import urllib.request

url = os.environ["API_HEALTH_URL"]
with urllib.request.urlopen(url, timeout=10) as response:
    payload = json.loads(response.read().decode("utf-8"))
    if response.status != 200:
        raise SystemExit(f"unexpected API health status: {response.status}")
    if payload.get("status") != "ok":
        raise SystemExit(f"unexpected API health payload: {payload}")

print(f"API post-deploy health check passed: {url} payload={payload}")
PY

                    echo "API post-deploy verification passed for ${NEW_TASK_DEFINITION_ARN}"
                '''
            }
        }

        // 감사와 장애 분석에 필요한 변경 불가능한 배포 식별 정보를 출력합니다.
        stage('Deployment Summary') {
            steps {
                echo "Repository: ${env.GIT_REPOSITORY_URL}"
                echo "Git commit: ${env.GIT_COMMIT_SHA}"
                echo "Jenkins build: ${env.BUILD_URL}"
                echo "Image URI: ${env.IMAGE_URI}"
                echo "Image digest: ${env.IMAGE_DIGEST}"
                echo "ECS service: ${env.ECS_SERVICE_NAME}"
                echo "Task definition: ${env.NEW_TASK_DEFINITION_ARN}"
            }
        }
    }

    post {
        success {
            echo "API image build completed: ${env.IMAGE_URI}"
        }
        failure {
            echo "API pipeline failed. Build: ${env.BUILD_URL}, commit: ${env.GIT_COMMIT_SHA}, image: ${env.IMAGE_URI}"
        }
        always {
            // 현재 빌드가 생성한 파일과 이미지만 선택적으로 정리합니다.
            // 다른 Jenkins Job이 같은 Host를 사용할 수 있으므로 전체 Docker prune은 실행하지 않습니다.
            sh '''
                set +e
                rm -rf .venv task-definition-current.json task-definition-new.json
                docker rm -f "api-smoke-${BUILD_NUMBER}" >/dev/null 2>&1 || true
                if [ -n "${IMAGE_URI:-}" ]; then
                  docker image rm "${IMAGE_URI}" >/dev/null 2>&1 || true
                fi
            '''
        }
    }
}
