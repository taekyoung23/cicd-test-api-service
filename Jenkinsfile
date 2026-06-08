pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
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
    }

    stages {
        // Checkout the webhook-triggering commit and derive an immutable image tag.
        stage('Source Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_SHORT_SHA = sh(
                        script: 'git rev-parse --short=7 HEAD',
                        returnStdout: true
                    ).trim()
                    env.IMAGE_TAG = "build-${env.BUILD_NUMBER}-${env.GIT_SHORT_SHA}"
                }
                echo "Image tag: ${env.IMAGE_TAG}"
            }
        }

        // Validate imports and run repository tests when test files are present.
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

        // Build the API image once using the Jenkins build number and commit SHA.
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

        // Start the built image locally and verify the API health endpoint.
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

        // Authenticate Docker to the shared ECR registry before publishing.
        stage('ECR Login') {
            steps {
                sh '''
                    set -eu
                    aws ecr get-login-password --region "${AWS_REGION}" \
                      | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
                '''
            }
        }

        // Publish the exact image that passed the smoke test.
        stage('ECR Push') {
            steps {
                sh '''
                    set -eu
                    docker push "${IMAGE_URI}"
                '''
            }
        }

        // Confirm the configured ECS service and task family exist before deployment.
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

        // Clone the active task definition and register a revision using the new image.
        stage('ECS Task Definition Revision Register') {
            steps {
                script {
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

        // Point the API ECS service at the newly registered task definition revision.
        stage('ECS Service Update') {
            steps {
                sh '''
                    set -eu
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

        // Block until ECS completes the rolling deployment and reaches steady state.
        stage('ECS Stable Wait') {
            steps {
                sh '''
                    set -eu
                    aws ecs wait services-stable \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}"
                    aws ecs describe-services \
                      --region "${AWS_REGION}" \
                      --cluster "${ECS_CLUSTER_NAME}" \
                      --services "${ECS_SERVICE_NAME}" \
                      --query 'services[0].events[0:5].[createdAt,message]' \
                      --output table
                    echo "ECS service is stable: ${ECS_SERVICE_NAME}"
                '''
            }
        }
    }

    post {
        success {
            echo "API image build completed: ${env.IMAGE_URI}"
        }
        failure {
            echo 'API build pipeline failed. Check Jenkins console output for the failing stage.'
        }
        always {
            sh '''
                set +e
                rm -rf .venv
            '''
        }
    }
}
