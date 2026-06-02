pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        string(name: 'AWS_REGION', defaultValue: 'ap-northeast-2', description: 'AWS region for ECR')
        string(name: 'AWS_ACCOUNT_ID', defaultValue: '455535733131', description: 'AWS account ID that owns the ECR repository')
        string(name: 'ECR_REPOSITORY', defaultValue: 'voice-api-service', description: 'ECR repository name for the API image')
        booleanParam(name: 'RUN_PYTEST', defaultValue: true, description: 'Run pytest when tests are present')
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false, description: 'Push the image to ECR after BuildKit build')
    }

    environment {
        DOCKER_BUILDKIT = '1'
        APP_ENV = 'ci'
        INPUT_BUCKET = 'ci-placeholder-input-bucket'
        RESULT_BUCKET = 'ci-placeholder-result-bucket'
    }

    stages {
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
                    if [ "${RUN_PYTEST}" = "true" ]; then
                      if find . -maxdepth 3 -type f \\( -name "test_*.py" -o -name "*_test.py" \\) | grep -q .; then
                        pip install pytest
                        pytest
                      else
                        echo "No pytest test files found. Skipping pytest."
                      fi
                    fi
                '''
            }
        }

        stage('BuildKit Image Build') {
            steps {
                script {
                    if (!params.AWS_ACCOUNT_ID?.trim()) {
                        error('AWS_ACCOUNT_ID parameter is required to build the ECR image URI.')
                    }
                    env.ECR_REGISTRY = "${params.AWS_ACCOUNT_ID}.dkr.ecr.${params.AWS_REGION}.amazonaws.com"
                    env.IMAGE_URI = "${env.ECR_REGISTRY}/${params.ECR_REPOSITORY}:${env.IMAGE_TAG}"
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

        stage('ECR Login') {
            when {
                expression { return params.PUSH_IMAGE }
            }
            steps {
                sh '''
                    set -eu
                    aws ecr get-login-password --region "${AWS_REGION}" \
                      | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
                '''
            }
        }

        stage('ECR Push') {
            when {
                expression { return params.PUSH_IMAGE }
            }
            steps {
                sh '''
                    set -eu
                    docker push "${IMAGE_URI}"
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
