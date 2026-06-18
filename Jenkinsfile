def slackDisplay(value) {
    return value == null || value.toString().trim() == '' ? 'N/A' : value.toString()
}

def sendSlackNotification(String title, Map details) {
    String messageFile = ".slack-message-${env.BUILD_NUMBER ?: 'unknown'}.txt"
    String payloadFile = ".slack-payload-${env.BUILD_NUMBER ?: 'unknown'}.json"
    try {
        String body = ([title] + details.collect { key, value ->
            "*${key}:* ${slackDisplay(value)}"
        }).join('\n')
        writeFile(file: messageFile, text: body)
        withCredentials([
            string(credentialsId: 'slack-webhook-url', variable: 'SLACK_WEBHOOK_URL')
        ]) {
            int slackStatus = sh(
                returnStatus: true,
                script: """
                    set +x
                    set -e
                    python3 - '${messageFile}' '${payloadFile}' <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as message_file:
    message = message_file.read()

with open(sys.argv[2], "w", encoding="utf-8") as payload_file:
    json.dump({"text": message}, payload_file)
PY
                    curl --fail --silent --show-error --connect-timeout 5 --max-time 10 \
                      --header 'Content-Type: application/json' \
                      --data-binary @'${payloadFile}' \
                      "\${SLACK_WEBHOOK_URL}" >/dev/null
                """
            )
            if (slackStatus == 0) {
                echo 'Slack notification sent'
            } else {
                echo "Slack notification failed but ignored. Exit code: ${slackStatus}"
            }
        }
    } catch (Exception ignored) {
        echo 'Slack notification failed but ignored'
    } finally {
        try {
            sh(returnStatus: true, script: "rm -f '${messageFile}' '${payloadFile}'")
        } catch (Exception ignored) {
            echo 'Slack notification payload cleanup failed but ignored'
        }
    }
}

def readTrivySummary(String serviceType) {
    Map summary = [
        status        : 'TRIVY_SCAN_INCOMPLETE',
        high_count    : 'N/A',
        critical_count: 'N/A'
    ]
    String resultPath = ".trivy-result-${serviceType}-${env.BUILD_NUMBER ?: 'unknown'}.json"
    try {
        if (fileExists(resultPath)) {
            String parsedText = sh(
                returnStdout: true,
                script: """
                    python3 - '${resultPath}' <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as result_file:
    data = json.load(result_file)

print(f"status={data.get('status', 'TRIVY_SCAN_INCOMPLETE')}")
print(f"high_count={data.get('high_count', 'N/A')}")
print(f"critical_count={data.get('critical_count', 'N/A')}")
PY
                """
            ).trim()
            parsedText.split('\\n').each { line ->
                int separator = line.indexOf('=')
                if (separator > 0) {
                    String key = line.substring(0, separator)
                    String value = line.substring(separator + 1)
                    if (summary.containsKey(key)) {
                        summary[key] = value?.trim() ? value.trim() : summary[key]
                    }
                }
            }
        } else {
            echo "Trivy summary file not found: ${resultPath}; using incomplete defaults."
        }
    } catch (Exception error) {
        echo "Unable to read Trivy summary from ${resultPath}; using incomplete defaults. Reason: ${error.getClass().getSimpleName()}: ${error.getMessage()}"
    }
    return summary
}

def trivySlackDetails(String serviceType) {
    Map trivy = readTrivySummary(serviceType)
    return [
        'Trivy'          : trivy.status,
        'Trivy HIGH'     : trivy.high_count,
        'Trivy CRITICAL' : trivy.critical_count,
        'Trivy Mode'     : 'WARNING',
        'Trivy Gate'     : 'NOT_APPLIED',
        'Trivy Report'   : 'Jenkins Artifact 확인'
    ]
}

def readEcsServiceRevisionSafely(String serviceName) {
    try {
        return sh(
            script: """
                set -eu
                aws ecs describe-services \
                  --region '${env.AWS_REGION}' \
                  --cluster '${env.ECS_CLUSTER_NAME}' \
                  --services '${serviceName}' \
                  --query 'services[0].taskDefinition' \
                  --output text
            """,
            returnStdout: true
        ).trim()
    } catch (Exception ignored) {
        echo 'Unable to read final ECS revision for Slack notification; ignored.'
        return 'UNKNOWN'
    }
}

def maskSensitiveText(String text) {
    if (text == null) {
        return 'N/A'
    }
    String masked = text
    masked = masked.replaceAll(/arn:aws:[A-Za-z0-9_:\\/+=,.@-]+/, '[MASKED_ARN]')
    masked = masked.replaceAll(/(?<![0-9])[0-9]{12}(?![0-9])/, '[MASKED_ACCOUNT]')
    masked = masked.replaceAll(/[0-9]{12}\.dkr\.ecr\.[A-Za-z0-9-]+\.amazonaws\.com\/[A-Za-z0-9._\/-]+(:[A-Za-z0-9._-]+)?/, '[MASKED_ECR_URI]')
    masked = masked.replaceAll(/https?:\/\/hooks\.slack\.com\/[A-Za-z0-9\/+_-]+/, '[MASKED_SLACK_WEBHOOK]')
    masked = masked.replaceAll(/https?:\/\/[^\\s"']*X-Amz-Signature=[^\\s"']+/, '[MASKED_PRESIGNED_URL]')
    masked = masked.replaceAll(/(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]+/, '[MASKED_GITHUB_TOKEN]')
    masked = masked.replaceAll(/A[KS]IA[0-9A-Z]{16}/, '[MASKED_AWS_KEY]')
    masked = masked.replaceAll(/(?i)(password|passwd|pwd|secret|token|authorization|credential)(\\s*[:=]\\s*)[^\\s,'"}]+/, '$1$2[MASKED_SECRET]')
    masked = masked.replaceAll(/(?i)(db[_-]?(host|user|password)|database[_-]?url)(\\s*[:=]\\s*)[^\\s,'"}]+/, '$1$3[MASKED_DB]')
    masked = masked.replaceAll(/https:\/\/sqs\.[A-Za-z0-9-]+\.amazonaws\.com\/[0-9]{12}\/[A-Za-z0-9._-]+/, '[MASKED_QUEUE_URL]')
    masked = masked.replaceAll(/s3:\/\/[^\\s,'"}]+/, '[MASKED_S3_PATH]')
    masked = masked.replaceAll(/(?<![0-9])(?:10|172\\.(?:1[6-9]|2[0-9]|3[0-1])|192\\.168)\\.[0-9]{1,3}\\.[0-9]{1,3}(?![0-9])/, '[MASKED_IP]')
    masked = masked.replaceAll(/(?<![0-9])(?:[0-9]{1,3}\\.){3}[0-9]{1,3}(?![0-9])/, '[MASKED_IP]')
    masked = masked.replaceAll(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/, '[MASKED_EMAIL]')
    return masked
}

def truncateText(String text, int maxLength = 12000) {
    if (text == null) {
        return 'N/A'
    }
    if (text.length() <= maxLength) {
        return text
    }
    return text.substring(text.length() - maxLength)
}

def collectConsoleLogTail(int lineCount = 200) {
    try {
        return maskSensitiveText(truncateText(currentBuild.rawBuild.getLog(lineCount).join('\n')))
    } catch (Exception ignored) {
        echo 'AI failure summary: Jenkins console log tail collection failed but ignored.'
        return 'LOG_COLLECTION_FAILED'
    }
}

def runMaskedCommand(String command, int maxLength = 8000) {
    try {
        String output = sh(script: command, returnStdout: true).trim()
        return maskSensitiveText(truncateText(output, maxLength))
    } catch (Exception ignored) {
        return 'LOG_COLLECTION_FAILED'
    }
}

def collectApiAwsDiagnostics() {
    String serviceEvents = runMaskedCommand("""
        set +e
        aws ecs describe-services \
          --region '${env.AWS_REGION}' \
          --cluster '${env.ECS_CLUSTER_NAME}' \
          --services '${env.ECS_SERVICE_NAME}' \
          --query 'services[0].events[0:8].[createdAt,message]' \
          --output text
    """)
    String targetHealth = runMaskedCommand("""
        set +e
        TARGET_GROUP_ARN=\$(aws ecs describe-services \
          --region '${env.AWS_REGION}' \
          --cluster '${env.ECS_CLUSTER_NAME}' \
          --services '${env.ECS_SERVICE_NAME}' \
          --query 'services[0].loadBalancers[0].targetGroupArn' \
          --output text 2>/dev/null)
        if [ -n "\${TARGET_GROUP_ARN}" ] && [ "\${TARGET_GROUP_ARN}" != "None" ]; then
          aws elbv2 describe-target-health \
            --region '${env.AWS_REGION}' \
            --target-group-arn "\${TARGET_GROUP_ARN}" \
            --query 'TargetHealthDescriptions[].{Target:Target.Id,State:TargetHealth.State,Reason:TargetHealth.Reason,Description:TargetHealth.Description}' \
            --output text
        else
          echo 'TARGET_GROUP_UNAVAILABLE'
        fi
    """)
    String logGroupName = "/ecs/${env.ECS_CLUSTER_NAME.replace('-cluster', '')}-api"
    String cloudWatchLogs = runMaskedCommand("""
        set +e
        START_TIME=\$(( \$(date +%s%3N) - 600000 ))
        aws logs filter-log-events \
          --region '${env.AWS_REGION}' \
          --log-group-name '${logGroupName}' \
          --start-time "\${START_TIME}" \
          --limit 30 \
          --query 'events[].message' \
          --output text
    """)
    return [
        service_events  : serviceEvents,
        target_health   : targetHealth,
        cloudwatch_logs : cloudWatchLogs
    ]
}

def buildAiFailurePrompt(String serviceName, Map context) {
    String contextJson = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(context))
    return """너는 SecureVoiceGuard CI/CD 장애 분석 보조 에이전트다.

아래 정보는 Jenkins Pipeline 실패 이후 수집된 메타데이터와 마스킹된 로그다.
제공된 정보 안에서만 판단하고, 확정 원인이 아니라 "추정 원인"으로 표현해라.
민감정보, 계정 ID, ARN, IP, URL, Secret, Token, DB 정보, Queue URL, S3 경로는 출력하지 마라.
Jenkins console log tail이 LOG_COLLECTION_FAILED이면 Slack 요약에 언급하지 마라. 이것은 배포 실패 원인이 아니라 보조 로그 수집 제한이다.
Trivy Mode가 WARNING이고 Gate가 NOT_APPLIED이면 Trivy findings를 배포 실패 원인이나 Next Action으로 쓰지 마라.
내부 테스트 관련 파라미터나 테스트 맥락을 암시하는 표현은 출력하지 마라.
Rollback 결과가 RECOVERY_VERIFIED이면 baseline revision으로 정상 복구된 것으로 표현해라.
Rollback 결과가 ROLLBACK_FAILED이면 수동 복구 확인이 필요하다고 표현해라.
Rollback 결과가 ROLLBACK_NOT_REQUIRED이면 rollback이 필요 없는 실패로 표현해라.
Slack 운영 알림용으로 짧고 실무적으로 작성해라.

출력 형식:

Likely Cause:
<1~2문장. 실패 stage 기준의 추정 원인만 작성>

Rollback Status:
<rollback result와 복구 여부를 1문장으로 작성>

Next Action:
<운영자가 다음에 확인할 위치만 1~2문장으로 작성>

서비스: ${serviceName}
입력 데이터:
${contextJson}
"""
}

def writeAiFailureSummaryArtifact(String serviceType, Map summary) {
    String artifactPath = ".ai-failure-summary-${serviceType}-${env.BUILD_NUMBER ?: 'unknown'}.json"
    try {
        writeFile(
            file: artifactPath,
            text: groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(summary))
        )
    } catch (Exception ignored) {
        echo "AI failure summary: unable to write ${artifactPath}; ignored."
    }
    return artifactPath
}

def fallbackLikelyCause(String failedStage) {
    if ((failedStage ?: '').contains('POST_DEPLOY_VERIFICATION')) {
        return 'Post-Deploy Verification 단계에서 API 검증 실패가 감지되었습니다.'
    }
    if ((failedStage ?: '').contains('SERVICE_STABILIZATION')) {
        return 'ECS 서비스 안정화 단계에서 배포 실패가 감지되었습니다.'
    }
    return 'Jenkins Pipeline 실행 중 배포 실패가 감지되었습니다.'
}

def fallbackRollbackStatusText(String rollbackStatus) {
    switch (rollbackStatus ?: 'N/A') {
        case 'RECOVERY_VERIFIED':
            return 'RECOVERY_VERIFIED — baseline revision으로 정상 복구되었습니다.'
        case 'ROLLBACK_FAILED':
            return 'RECOVERY_FAILED — 수동 복구 확인이 필요합니다.'
        case 'EXTERNAL_UPDATE_DETECTED':
            return 'MANUAL_REVIEW_REQUIRED — 외부 업데이트가 감지되어 수동 확인이 필요합니다.'
        case 'ROLLBACK_NOT_REQUIRED':
            return 'NOT_REQUIRED'
        case 'ROLLBACK_NOT_COMPLETED':
            return 'NOT_COMPLETED — rollback 완료 여부 확인이 필요합니다.'
        default:
            return rollbackStatus ?: 'N/A'
    }
}

def fallbackNextAction(String rollbackStatus) {
    switch (rollbackStatus ?: 'N/A') {
        case 'ROLLBACK_FAILED':
            return '즉시 ECS Service Events, stopped task reason, ALB Target Health, 현재 task definition revision을 확인하고 baseline revision으로 수동 rollback을 검토하세요.'
        case 'ROLLBACK_NOT_REQUIRED':
            return '실패한 Jenkins stage의 build/test/docker/ecr 로그를 확인하세요.'
        default:
            return 'ALB Target Health, ECS Task Logs, ECS Service Events, /api/health 응답을 우선 확인하세요.'
    }
}

def invokeBedrockFailureSummary(String serviceType, String prompt, Map metadata) {
    String modelId = params.BEDROCK_MODEL_ID ?: env.BEDROCK_MODEL_ID
    if (modelId == null || modelId.trim() == '') {
        Map skipped = [
            enabled          : true,
            provider         : 'bedrock',
            status           : 'BEDROCK_SKIPPED_EMPTY_MODEL_ID',
            error            : 'BEDROCK_MODEL_ID is not configured',
            failed_stage     : metadata.failed_stage ?: 'N/A',
            rollback_status  : metadata.rollback_status ?: 'N/A',
            summary_for_slack: 'AI Failure Summary skipped: BEDROCK_MODEL_ID is not configured.',
            masked           : true
        ]
        writeAiFailureSummaryArtifact(serviceType, skipped)
        return skipped
    }

    String promptFile = ".ai-failure-prompt-${serviceType}-${env.BUILD_NUMBER ?: 'unknown'}.txt"
    String requestFile = ".ai-failure-request-${serviceType}-${env.BUILD_NUMBER ?: 'unknown'}.json"
    String responseFile = ".ai-failure-response-${serviceType}-${env.BUILD_NUMBER ?: 'unknown'}.json"
    String errorFile = ".ai-failure-error-${serviceType}-${env.BUILD_NUMBER ?: 'unknown'}.log"
    String runtimeSummaryFile = ".ai-failure-runtime-summary-${serviceType}-${env.BUILD_NUMBER ?: 'unknown'}.json"
    String propertiesFile = ".ai-failure-summary-${serviceType}-${env.BUILD_NUMBER ?: 'unknown'}.properties"
    writeFile(file: promptFile, text: maskSensitiveText(truncateText(prompt, 12000)))

    int status = sh(
        returnStatus: true,
        script: """
            set +x
            set +e
            python3 - '${promptFile}' '${requestFile}' <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as prompt_file:
    prompt = prompt_file.read()

# Bedrock model id/region/model access must be verified in the target AWS account.
# This request body uses the Anthropic Claude Messages API schema.
with open(sys.argv[2], "w", encoding="utf-8") as request_file:
    json.dump({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 700,
        "temperature": 0.2,
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        }]
    }, request_file)
PY
            rm -f '${responseFile}' '${errorFile}' '${runtimeSummaryFile}' '${propertiesFile}'
            timeout 30 aws bedrock-runtime invoke-model \
              --region "\${BEDROCK_REGION:-${env.AWS_REGION}}" \
              --model-id '${modelId}' \
              --content-type 'application/json' \
              --accept 'application/json' \
              --cli-binary-format raw-in-base64-out \
              --body "fileb://${requestFile}" \
              '${responseFile}' >/dev/null 2>'${errorFile}'
            BEDROCK_STATUS=\$?
            BEDROCK_MODEL_ID_FOR_SUMMARY='${modelId}' python3 - '${responseFile}' '${runtimeSummaryFile}' '${errorFile}' '${propertiesFile}' "\${BEDROCK_STATUS}" <<'PY'
import json
import os
import sys

response_path, summary_path, error_path, properties_path, status = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
summary_text = ""
error = ""
status_name = "SUMMARY_FAILED"
section_labels = ["Likely Cause", "Rollback Status", "Next Action"]

def read_error():
    try:
        with open(error_path, "r", encoding="utf-8", errors="replace") as error_file:
            return error_file.read().strip()
    except Exception:
        return ""

def classify_error(message):
    lowered = message.lower()
    if "accessdenied" in lowered or "not authorized" in lowered or "unauthorized" in lowered:
        return "BEDROCK_ACCESS_DENIED"
    if "validationexception" in lowered or "validation" in lowered:
        return "BEDROCK_VALIDATION_ERROR"
    return "BEDROCK_INVOKE_FAILED"

def extract_sections(text):
    sections = {label: "" for label in section_labels}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        matched = None
        for label in section_labels:
            if line.lower().startswith(label.lower() + ":"):
                matched = label
                remainder = line[len(label) + 1:].strip()
                sections[label] = remainder
                break
        if matched:
            current = matched
            continue
        if current and line:
            if sections[current]:
                sections[current] += " "
            sections[current] += line
    return sections

if status == "0":
    try:
        with open(response_path, "r", encoding="utf-8") as response_file:
            response = json.load(response_file)
        if isinstance(response.get("content"), list) and response["content"]:
            summary_text = response["content"][0].get("text", "")
        elif isinstance(response.get("output"), dict):
            content = response["output"].get("message", {}).get("content", [])
            if content:
                summary_text = content[0].get("text", "")
        elif response.get("generation"):
            summary_text = response.get("generation", "")
        if not summary_text:
            error = "Bedrock response parsing failed"
            status_name = "BEDROCK_RESPONSE_PARSE_FAILED"
        else:
            status_name = "SUMMARY_CREATED"
    except Exception as exc:
        error = f"Bedrock response parsing failed: {exc}"
        status_name = "BEDROCK_RESPONSE_PARSE_FAILED"
else:
    stderr_text = read_error()
    error = f"Bedrock invoke-model failed with exit code {status}"
    if stderr_text:
        error = f"{error}: {stderr_text[:1200]}"
    status_name = classify_error(stderr_text)

sections = extract_sections(summary_text) if summary_text else {label: "" for label in section_labels}
payload = {
    "enabled": True,
    "provider": "bedrock",
    "model": os.environ.get("BEDROCK_MODEL_ID_FOR_SUMMARY", "configured-via-jenkins-parameter"),
    "status": status_name,
    "invoke_exit_code": status,
    "summary_for_slack": summary_text if summary_text else "AI Failure Summary failed. Check Jenkins console and AWS deployment logs manually.",
    "likely_cause": sections.get("Likely Cause", ""),
    "rollback_status_text": sections.get("Rollback Status", ""),
    "next_action": sections.get("Next Action", ""),
    "error": error,
    "masked": True,
}
with open(summary_path, "w", encoding="utf-8") as summary_file:
    json.dump(payload, summary_file, indent=2, ensure_ascii=False)
with open(properties_path, "w", encoding="utf-8") as properties_file:
    for key in ["enabled", "provider", "model", "status", "invoke_exit_code", "summary_for_slack", "likely_cause", "rollback_status_text", "next_action", "error", "masked"]:
        value = payload.get(key, "")
        value = str(value).replace("\\r", "\\\\r").replace("\\n", "\\\\n")
        properties_file.write(f"{key}={value}\\n")
PY
            exit 0
        """
    )
    Map parsed = [
        enabled          : true,
        provider         : 'bedrock',
        status           : 'SUMMARY_FAILED',
        invoke_exit_code : 'N/A',
        error            : "AI summary shell wrapper failed with exit code ${status}",
        summary_for_slack: 'AI Failure Summary failed. Check Jenkins console and AWS deployment logs manually.',
        likely_cause     : fallbackLikelyCause(metadata.failed_stage ?: 'N/A'),
        rollback_status_text: fallbackRollbackStatusText(metadata.rollback_status ?: 'N/A'),
        next_action      : fallbackNextAction(metadata.rollback_status ?: 'N/A'),
        masked           : true
    ]
    try {
        if (fileExists(errorFile)) {
            String bedrockError = maskSensitiveText(truncateText(readFile(errorFile), 1200))
            if (bedrockError?.trim()) {
                echo "AI failure summary: Bedrock stderr summary: ${bedrockError.trim()}"
            }
        }
        if (fileExists(propertiesFile)) {
            Map fromProperties = [:]
            readFile(propertiesFile).split('\\n').each { line ->
                int separator = line.indexOf('=')
                if (separator > 0) {
                    String key = line.substring(0, separator)
                    String value = line.substring(separator + 1)
                    fromProperties[key] = value.replace('\\n', '\n').replace('\\r', '\r')
                }
            }
            parsed = fromProperties
            parsed.enabled = parsed.enabled == 'true'
            parsed.masked = parsed.masked == 'true'
        }
    } catch (Exception error) {
        echo "AI failure summary: unable to parse summary properties; using failed fallback. Reason: ${error.getClass().getSimpleName()}: ${error.getMessage()}"
    }
    echo "AI failure summary: shell wrapper exit code=${status}, Bedrock invoke exit code=${parsed.invoke_exit_code ?: 'N/A'}, summary status=${parsed.status ?: 'N/A'}, error=${maskSensitiveText(truncateText(parsed.error ?: 'N/A', 1200))}"
    parsed.failed_stage = metadata.failed_stage ?: 'N/A'
    parsed.likely_cause = parsed.likely_cause ?: fallbackLikelyCause(parsed.failed_stage)
    parsed.evidence = metadata.evidence ?: 'N/A'
    parsed.impact = metadata.impact ?: 'N/A'
    parsed.rollback_status = metadata.rollback_status ?: 'N/A'
    parsed.rollback_status_text = parsed.rollback_status_text ?: fallbackRollbackStatusText(parsed.rollback_status)
    parsed.next_action = parsed.next_action ?: fallbackNextAction(parsed.rollback_status)
    parsed.masked = true
    writeAiFailureSummaryArtifact(serviceType, parsed)
    sh(returnStatus: true, script: "rm -f '${promptFile}' '${requestFile}' '${responseFile}' '${runtimeSummaryFile}' '${propertiesFile}' '${errorFile}'")
    return parsed
}

def sendAiFailureSummarySlack(String title, Map summary, Map details) {
    sendSlackNotification(title, [
        Service            : details.service ?: 'N/A',
        Job                : env.JOB_NAME,
        Build              : env.BUILD_NUMBER,
        'Failed Stage'     : details.failed_stage ?: 'N/A',
        'AI Summary Status': summary.status ?: 'N/A',
        'Likely Cause'     : summary.likely_cause ?: fallbackLikelyCause(details.failed_stage ?: 'N/A'),
        'Rollback Status'  : summary.rollback_status_text ?: fallbackRollbackStatusText(details.rollback_status ?: 'N/A'),
        'Next Action'      : summary.next_action ?: fallbackNextAction(details.rollback_status ?: 'N/A'),
        Jenkins            : maskSensitiveText(env.BUILD_URL ?: 'N/A')
    ])
}

def generateApiAiFailureSummary() {
    try {
        Map trivy = readTrivySummary('api')
        Map diagnostics = collectApiAwsDiagnostics()
        String rollbackStatus = env.SERVICE_UPDATE_REQUESTED == 'true' ?
            (env.API_ROLLBACK_RESULT ?: 'ROLLBACK_NOT_COMPLETED') : 'ROLLBACK_NOT_REQUIRED'
        String impact = env.SERVICE_UPDATE_REQUESTED == 'true' ?
            'ECS Service Update 이후 실패하여 rollback 결과 확인이 필요합니다.' :
            'ECS Service Update 전 실패이므로 운영 서비스 변경은 없습니다.'
        Map context = [
            job_name                    : env.JOB_NAME,
            build_number                : env.BUILD_NUMBER,
            build_url                   : maskSensitiveText(env.BUILD_URL ?: 'N/A'),
            git_commit                  : env.GIT_COMMIT_SHA ?: env.GIT_SHORT_SHA ?: 'N/A',
            git_short_sha               : env.GIT_SHORT_SHA ?: 'N/A',
            image_uri                   : maskSensitiveText(env.IMAGE_URI ?: 'N/A'),
            image_digest                : env.IMAGE_DIGEST ?: 'N/A',
            deploy_phase                : env.DEPLOY_PHASE ?: 'N/A',
            service_update_requested    : env.SERVICE_UPDATE_REQUESTED ?: 'false',
            baseline_task_definition    : maskSensitiveText(env.PREVIOUS_TASK_DEFINITION_ARN ?: 'N/A'),
            requested_task_definition   : maskSensitiveText(env.NEW_TASK_DEFINITION_ARN ?: 'N/A'),
            final_task_definition       : maskSensitiveText(env.API_FINAL_TASK_DEFINITION_ARN ?: readEcsServiceRevisionSafely(env.ECS_SERVICE_NAME)),
            rollback_result             : rollbackStatus,
            trivy_status                : trivy.status,
            trivy_high_count            : trivy.high_count,
            trivy_critical_count        : trivy.critical_count,
            trivy_mode                  : 'WARNING',
            trivy_gate                  : 'NOT_APPLIED',
            jenkins_console_log_tail    : collectConsoleLogTail(),
            ecs_service_events          : diagnostics.service_events,
            alb_target_health           : diagnostics.target_health,
            cloudwatch_logs_tail        : diagnostics.cloudwatch_logs
        ]
        Map metadata = [
            failed_stage    : env.DEPLOY_PHASE ?: 'N/A',
            rollback_status : rollbackStatus,
            impact          : impact,
            evidence        : diagnostics.service_events ?: 'N/A'
        ]
        Map summary = invokeBedrockFailureSummary('api', buildAiFailurePrompt('API Service', context), metadata)
        sendAiFailureSummarySlack(':mag: API AI Failure Summary', summary, [
            service        : 'API Service',
            failed_stage   : env.DEPLOY_PHASE ?: 'N/A',
            rollback_status: rollbackStatus
        ])
    } catch (Exception ignored) {
        echo 'AI failure summary for API failed but ignored.'
        writeAiFailureSummaryArtifact('api', [
            enabled          : true,
            provider         : 'bedrock',
            status           : 'SUMMARY_FAILED',
            error            : 'AI failure summary failed before or during helper execution',
            summary_for_slack: 'AI Failure Summary failed. Check Jenkins console and AWS deployment logs manually.',
            masked           : true
        ])
    }
}

pipeline {
    agent any

    options {
        // 장애 분석을 위해 로그에 시간을 기록하고, 동일 Job의 배포가 동시에 실행되지 않도록 합니다.
        timestamps()
        disableConcurrentBuilds()
        // Jenkins 저장공간이 계속 증가하지 않도록 최근 빌드 이력 20개만 보관합니다.
        buildDiscarder(logRotator(numToKeepStr: '20'))
        // Workspace Checkout은 Source Checkout Stage에서 Shallow Clone으로 한 번만 수행합니다.
        skipDefaultCheckout(true)
        // 명령 또는 AWS 배포가 장시간 멈춰 있으면 전체 Pipeline을 종료합니다.
        timeout(time: 30, unit: 'MINUTES')
    }

    parameters {
        choice(
            name: 'ROLLBACK_TEST_MODE',
            choices: ['NONE', 'API_VERIFY_FAIL'],
            description: 'API automatic rollback verification only'
        )
        string(
            name: 'BEDROCK_MODEL_ID',
            defaultValue: '',
            description: 'Optional Bedrock model id for AI Failure Summary. Leave empty to skip AI summary.'
        )
    }

    environment {
        DOCKER_BUILDKIT = '1'
        TRIVY_IMAGE = 'aquasec/trivy:0.71.0'
        TRIVY_REPORT_DIR = 'trivy-reports'
        DEPLOYMENT_SUMMARY_DIR = 'deployment-summaries'
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
                checkout([
                    $class: 'GitSCM',
                    branches: scm.branches,
                    userRemoteConfigs: scm.userRemoteConfigs,
                    extensions: [[
                        $class: 'CloneOption',
                        shallow: true,
                        depth: 1,
                        noTags: true,
                        timeout: 10
                    ]]
                ])
                script {
                    env.SERVICE_UPDATE_REQUESTED = 'false'
                    env.DEPLOY_PHASE = 'PRE_DEPLOY'
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
                      python -m pip install -r requirements-test.txt
                      python -m pytest
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

        // Smoke Test를 통과한 로컬 이미지를 ECR Push 전에 Scan하고 결과를 경고로 기록합니다.
        stage('Trivy Image Scan - Warning Mode') {
            steps {
                sh '''
                    set -u

                    REPORT_FILE="trivy-api-${BUILD_NUMBER}.json"
                    REPORT_PATH="${TRIVY_REPORT_DIR}/${REPORT_FILE}"
                    TRIVY_RESULT_PATH=".trivy-result-api-${BUILD_NUMBER}.json"
                    TRIVY_CONTAINER_NAME="trivy-api-${BUILD_NUMBER}"

                    mkdir -p "${TRIVY_REPORT_DIR}" .trivy-cache
                    rm -f "${REPORT_PATH}"
                    python3 - "${TRIVY_RESULT_PATH}" <<'PY'
import json
import sys

with open(sys.argv[1], "w", encoding="utf-8") as result_file:
    json.dump({
        "status": "TRIVY_SCAN_INCOMPLETE",
        "high_count": "N/A",
        "critical_count": "N/A",
    }, result_file)
PY
                    docker rm -f "${TRIVY_CONTAINER_NAME}" >/dev/null 2>&1 || true

                    cleanup() {
                      docker rm -f "${TRIVY_CONTAINER_NAME}" >/dev/null 2>&1 || true
                    }
                    trap cleanup EXIT

                    echo "Starting API image vulnerability scan in Warning Mode."
                    echo "Scan target: ${IMAGE_URI}"
                    echo "Severity: HIGH,CRITICAL"
                    echo "Trivy image: ${TRIVY_IMAGE}"

                    set +e
                    timeout --signal=TERM 5m docker run --rm \
                      --name "${TRIVY_CONTAINER_NAME}" \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      -v "${PWD}/.trivy-cache:/root/.cache/trivy" \
                      -v "${PWD}/${TRIVY_REPORT_DIR}:/reports" \
                      "${TRIVY_IMAGE}" \
                      image \
                      --scanners vuln \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      --format json \
                      --output "/reports/${REPORT_FILE}" \
                      "${IMAGE_URI}"
                    TRIVY_STATUS=$?

                    if [ "${TRIVY_STATUS}" -ne 0 ] || [ ! -s "${REPORT_PATH}" ]; then
                      echo "TRIVY_SCAN_INCOMPLETE"
                      echo "WARNING: Trivy execution or vulnerability DB download failed. Deployment will continue."
                      exit 0
                    fi

                    REPORT_PATH="${REPORT_PATH}" TRIVY_RESULT_PATH="${TRIVY_RESULT_PATH}" python3 - <<'PY'
import json
import os

report_path = os.environ["REPORT_PATH"]
result_path = os.environ["TRIVY_RESULT_PATH"]

with open(report_path, "r", encoding="utf-8") as report_file:
    report = json.load(report_file)

counts = {"HIGH": 0, "CRITICAL": 0}

for result in report.get("Results", []):
    for vulnerability in result.get("Vulnerabilities") or []:
        severity = vulnerability.get("Severity")
        if severity in counts:
            counts[severity] += 1

total = counts["HIGH"] + counts["CRITICAL"]

if total:
    status = "TRIVY_SCAN_COMPLETED_WITH_FINDINGS"
else:
    status = "TRIVY_SCAN_COMPLETED_NO_FINDINGS"

with open(result_path, "w", encoding="utf-8") as result_file:
    json.dump({
        "status": status,
        "high_count": counts["HIGH"],
        "critical_count": counts["CRITICAL"],
    }, result_file)

print(status)
print(f"HIGH={counts['HIGH']}")
print(f"CRITICAL={counts['CRITICAL']}")
print("Warning Mode: vulnerabilities do not block deployment.")
PY
                    REPORT_STATUS=$?
                    if [ "${REPORT_STATUS}" -ne 0 ]; then
                      echo "TRIVY_SCAN_INCOMPLETE"
                      echo "WARNING: Trivy report parsing failed. Deployment will continue."
                    fi
                    exit 0
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
                    env.PREVIOUS_TASK_DEFINITION_ARN = sh(
                        script: '''
                            set -eu
                            aws ecs describe-services \
                              --region "${AWS_REGION}" \
                              --cluster "${ECS_CLUSTER_NAME}" \
                              --services "${ECS_SERVICE_NAME}" \
                              --query 'services[0].taskDefinition' \
                              --output text
                        ''',
                        returnStdout: true
                    ).trim()
                    if (!env.PREVIOUS_TASK_DEFINITION_ARN || env.PREVIOUS_TASK_DEFINITION_ARN == 'None') {
                        error('Unable to capture the API rollback baseline task definition.')
                    }
                    env.PREVIOUS_IMAGE_URI = sh(
                        script: '''
                            set -eu
                            aws ecs describe-task-definition \
                              --region "${AWS_REGION}" \
                              --task-definition "${PREVIOUS_TASK_DEFINITION_ARN}" \
                              --query "taskDefinition.containerDefinitions[?name=='${CONTAINER_NAME}'].image | [0]" \
                              --output text
                        ''',
                        returnStdout: true
                    ).trim()
                    env.PREVIOUS_DESIRED_COUNT = sh(
                        script: '''
                            set -eu
                            aws ecs describe-services \
                              --region "${AWS_REGION}" \
                              --cluster "${ECS_CLUSTER_NAME}" \
                              --services "${ECS_SERVICE_NAME}" \
                              --query 'services[0].desiredCount' \
                              --output text
                        ''',
                        returnStdout: true
                    ).trim()
                    if (!env.PREVIOUS_IMAGE_URI || env.PREVIOUS_IMAGE_URI == 'None') {
                        error('Unable to capture the API rollback baseline image URI.')
                    }
                    if (!env.PREVIOUS_DESIRED_COUNT || env.PREVIOUS_DESIRED_COUNT == 'None') {
                        error('Unable to capture the API rollback baseline desired count.')
                    }
                    echo "Captured API rollback baseline: ${env.PREVIOUS_TASK_DEFINITION_ARN}"
                    echo "Previous API image: ${env.PREVIOUS_IMAGE_URI}"
                    echo "Previous API desired count: ${env.PREVIOUS_DESIRED_COUNT}"

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
                script {
                    env.DEPLOY_PHASE = 'ECS_SERVICE_UPDATE'
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
                    '''

                    env.SERVICE_UPDATE_REQUESTED = 'true'
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
        }

        // ECS Rolling Update가 완료되고 Service가 안정 상태가 될 때까지 기다립니다.
        stage('ECS Stable Wait') {
            options {
                // Rolling Update 시간은 허용하되 무기한 대기하지 않도록 제한합니다.
                timeout(time: 15, unit: 'MINUTES')
            }
            steps {
                script {
                    env.DEPLOY_PHASE = 'SERVICE_STABILIZATION_FAILED'
                }
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
                script {
                    env.DEPLOY_PHASE = 'POST_DEPLOY_VERIFICATION_FAILED'
                }
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

                    if [ "${ROLLBACK_TEST_MODE:-NONE}" = "API_VERIFY_FAIL" ]; then
                      echo "Intentional API verification failure for rollback test."
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
                script {
                    env.DEPLOY_PHASE = 'DEPLOY_SUCCESS'
                }
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
                echo "Previous task definition: ${env.PREVIOUS_TASK_DEFINITION_ARN}"
                echo "Previous image: ${env.PREVIOUS_IMAGE_URI}"
                echo "Previous desired count: ${env.PREVIOUS_DESIRED_COUNT}"
                echo "New task definition: ${env.NEW_TASK_DEFINITION_ARN}"
                echo "New image: ${env.IMAGE_URI}"
            }
        }
    }

    post {
        success {
            echo "API image build completed: ${env.IMAGE_URI}"
            echo "Deployment result: DEPLOY_SUCCESS"
            script {
                sendSlackNotification(':white_check_mark: API deployment succeeded', [
                    Result                 : 'SUCCESS',
                    Job                    : env.JOB_NAME,
                    Build                  : env.BUILD_NUMBER,
                    Commit                 : env.GIT_COMMIT_SHA ?: env.GIT_SHORT_SHA,
                    'Image URI'            : env.IMAGE_URI,
                    'Image Digest'         : env.IMAGE_DIGEST,
                    'ECS Service'          : env.ECS_SERVICE_NAME,
                    'New Task Definition'  : env.NEW_TASK_DEFINITION_ARN,
                    'Jenkins Build URL'    : env.BUILD_URL
                ] + trivySlackDetails('api'))
            }
        }
        unsuccessful {
            echo "API pipeline did not complete successfully. Build: ${env.BUILD_URL}, commit: ${env.GIT_COMMIT_SHA}, image: ${env.IMAGE_URI}"
            script {
                boolean rollbackNeeded = env.SERVICE_UPDATE_REQUESTED == 'true' && env.DEPLOY_PHASE != 'DEPLOY_SUCCESS'
                sendSlackNotification(':x: API deployment failed', [
                    Result                 : 'FAILED',
                    Job                    : env.JOB_NAME,
                    Build                  : env.BUILD_NUMBER,
                    Commit                 : env.GIT_COMMIT_SHA ?: env.GIT_SHORT_SHA,
                    'Deploy Phase'         : env.DEPLOY_PHASE,
                    'Service Update State' : env.SERVICE_UPDATE_REQUESTED == 'true' ? 'AFTER_ECS_SERVICE_UPDATE' : 'BEFORE_ECS_SERVICE_UPDATE',
                    'Image URI'            : env.IMAGE_URI,
                    'ECS Service'          : env.ECS_SERVICE_NAME,
                    'Rollback Needed'      : rollbackNeeded,
                    'Jenkins Build URL'    : env.BUILD_URL
                ] + trivySlackDetails('api'))

                if (env.DEPLOY_PHASE == 'DEPLOY_SUCCESS') {
                    echo "Rollback skipped: API deployment verification already succeeded."
                } else if (env.SERVICE_UPDATE_REQUESTED != 'true') {
                    echo "Rollback skipped: API service was not updated by this build."
                } else {
                    int rollbackStatus = sh(
                        returnStatus: true,
                        script: '''
                            set -u

                            print_diagnostics() {
                              aws ecs describe-services \
                                --region "${AWS_REGION}" \
                                --cluster "${ECS_CLUSTER_NAME}" \
                                --services "${ECS_SERVICE_NAME}" \
                                --query 'services[0].deployments[].{Status:status,RolloutState:rolloutState,Reason:rolloutStateReason,TaskDefinition:taskDefinition,Desired:desiredCount,Running:runningCount,Failed:failedTasks}' \
                                --output table || true
                              aws ecs describe-services \
                                --region "${AWS_REGION}" \
                                --cluster "${ECS_CLUSTER_NAME}" \
                                --services "${ECS_SERVICE_NAME}" \
                                --query 'services[0].events[0:10].[createdAt,message]' \
                                --output table || true
                            }

                            verify_api_health() {
                              TARGET_GROUP_ARN="$(aws ecs describe-services \
                                --region "${AWS_REGION}" \
                                --cluster "${ECS_CLUSTER_NAME}" \
                                --services "${ECS_SERVICE_NAME}" \
                                --query 'services[0].loadBalancers[0].targetGroupArn' \
                                --output text)" || return 1
                              DESIRED_COUNT="$(aws ecs describe-services \
                                --region "${AWS_REGION}" \
                                --cluster "${ECS_CLUSTER_NAME}" \
                                --services "${ECS_SERVICE_NAME}" \
                                --query 'services[0].desiredCount' \
                                --output text)" || return 1
                              RUNNING_COUNT="$(aws ecs describe-services \
                                --region "${AWS_REGION}" \
                                --cluster "${ECS_CLUSTER_NAME}" \
                                --services "${ECS_SERVICE_NAME}" \
                                --query 'services[0].runningCount' \
                                --output text)" || return 1
                              case "${DESIRED_COUNT}:${RUNNING_COUNT}" in
                                *[!0-9:]*)
                                  echo "Rollback verification failed: Invalid Desired/Running Count values: desired=${DESIRED_COUNT}, running=${RUNNING_COUNT}"
                                  return 1
                                  ;;
                              esac
                              if [ "${RUNNING_COUNT}" -ne "${DESIRED_COUNT}" ]; then
                                echo "Rollback verification failed: Running Count (${RUNNING_COUNT}) does not match Desired Count (${DESIRED_COUNT})."
                                return 1
                              fi

                              for attempt in 1 2 3 4 5; do
                                HEALTHY_TARGET_COUNT="$(aws elbv2 describe-target-health \
                                  --region "${AWS_REGION}" \
                                  --target-group-arn "${TARGET_GROUP_ARN}" \
                                  --query 'length(TargetHealthDescriptions[?TargetHealth.State==`healthy`])' \
                                  --output text 2>/dev/null || printf '0')"
                                if [ "${HEALTHY_TARGET_COUNT}" -ge "${DESIRED_COUNT}" ] && \
                                   python3 -c 'import json, os, urllib.request; r=urllib.request.urlopen(os.environ["API_HEALTH_URL"], timeout=10); p=json.loads(r.read().decode("utf-8")); raise SystemExit(0 if r.status == 200 and p.get("status") == "ok" else 1)' 2>/dev/null; then
                                  return 0
                                fi
                                echo "Waiting for rolled back API health... attempt=${attempt}"
                                sleep 10
                              done
                              return 1
                            }

                            echo "Rollback trigger: ${DEPLOY_PHASE}"
                            echo "Previous revision: ${PREVIOUS_TASK_DEFINITION_ARN}"
                            echo "Previous image: ${PREVIOUS_IMAGE_URI}"
                            echo "Previous desired count: ${PREVIOUS_DESIRED_COUNT}"
                            echo "Requested revision: ${NEW_TASK_DEFINITION_ARN}"
                            echo "Requested image: ${IMAGE_URI}"

                            CURRENT_TASK_DEFINITION_ARN="$(aws ecs describe-services \
                              --region "${AWS_REGION}" \
                              --cluster "${ECS_CLUSTER_NAME}" \
                              --services "${ECS_SERVICE_NAME}" \
                              --query 'services[0].taskDefinition' \
                              --output text)" || {
                                echo "Rollback result: ROLLBACK_FAILED (unable to read current revision)"
                                exit 1
                              }

                            echo "Current revision before rollback: ${CURRENT_TASK_DEFINITION_ARN}"
                            if [ "${CURRENT_TASK_DEFINITION_ARN}" = "${PREVIOUS_TASK_DEFINITION_ARN}" ]; then
                              echo "Rollback action: PREVIOUS_REVISION_ALREADY_ACTIVE"
                              ROLLBACK_RESULT="PREVIOUS_REVISION_RECOVERY_VERIFIED"
                            elif [ "${CURRENT_TASK_DEFINITION_ARN}" = "${NEW_TASK_DEFINITION_ARN}" ]; then
                              echo "Rollback action: JENKINS_EXPLICIT_ROLLBACK"
                              ROLLBACK_RESULT="JENKINS_ROLLBACK_SUCCESS"
                              aws ecs update-service \
                                --region "${AWS_REGION}" \
                                --cluster "${ECS_CLUSTER_NAME}" \
                                --service "${ECS_SERVICE_NAME}" \
                                --task-definition "${PREVIOUS_TASK_DEFINITION_ARN}" \
                                --no-cli-pager >/dev/null || {
                                  echo "Rollback result: ROLLBACK_FAILED (update-service failed)"
                                  print_diagnostics
                                  exit 1
                                }
                            else
                              echo "Rollback result: EXTERNAL_UPDATE_DETECTED"
                              echo "Automatic rollback stopped to avoid overwriting another deployment."
                              print_diagnostics
                              exit 2
                            fi

                            aws ecs wait services-stable \
                              --region "${AWS_REGION}" \
                              --cluster "${ECS_CLUSTER_NAME}" \
                              --services "${ECS_SERVICE_NAME}" || {
                                echo "Rollback result: ROLLBACK_FAILED (service did not stabilize)"
                                print_diagnostics
                                exit 1
                              }

                            FINAL_TASK_DEFINITION_ARN="$(aws ecs describe-services \
                              --region "${AWS_REGION}" \
                              --cluster "${ECS_CLUSTER_NAME}" \
                              --services "${ECS_SERVICE_NAME}" \
                              --query 'services[0].taskDefinition' \
                              --output text)"
                            if [ "${FINAL_TASK_DEFINITION_ARN}" != "${PREVIOUS_TASK_DEFINITION_ARN}" ]; then
                              echo "Rollback result: ROLLBACK_FAILED (unexpected final revision: ${FINAL_TASK_DEFINITION_ARN})"
                              print_diagnostics
                              exit 1
                            fi

                            if ! verify_api_health; then
                              echo "Rollback result: ROLLBACK_FAILED (rolled back API health verification failed)"
                              print_diagnostics
                              exit 1
                            fi

                            echo "Rollback result: ${ROLLBACK_RESULT}"
                            echo "Final revision: ${FINAL_TASK_DEFINITION_ARN}"
                        '''
                    )
                    if (rollbackStatus != 0) {
                        echo "API rollback handling did not complete successfully. Exit code: ${rollbackStatus}"
                    }
                    env.API_ROLLBACK_RESULT = rollbackStatus == 0 ? 'RECOVERY_VERIFIED' :
                        (rollbackStatus == 2 ? 'EXTERNAL_UPDATE_DETECTED' : 'ROLLBACK_FAILED')
                    env.API_FINAL_TASK_DEFINITION_ARN = readEcsServiceRevisionSafely(env.ECS_SERVICE_NAME)
                    sendSlackNotification(':warning: API rollback result', [
                        'Rollback Needed'      : true,
                        'Rollback Attempted'   : true,
                        'Rollback Result'      : env.API_ROLLBACK_RESULT,
                        'Requested Revision'   : env.NEW_TASK_DEFINITION_ARN,
                        'Baseline Revision'    : env.PREVIOUS_TASK_DEFINITION_ARN,
                        'Final Revision'       : env.API_FINAL_TASK_DEFINITION_ARN,
                        'Baseline Restored'    : env.API_FINAL_TASK_DEFINITION_ARN == env.PREVIOUS_TASK_DEFINITION_ARN,
                        'ECS Service'          : env.ECS_SERVICE_NAME,
                        'Deploy Phase'         : env.DEPLOY_PHASE,
                        'Jenkins Build URL'    : env.BUILD_URL
                    ])
                }
                generateApiAiFailureSummary()
            }
        }
        always {
            archiveArtifacts(
                artifacts: "trivy-reports/trivy-api-${env.BUILD_NUMBER}.json",
                allowEmptyArchive: true,
                fingerprint: true
            )
            // 현재 빌드가 생성한 파일과 이미지만 선택적으로 정리합니다.
            // 다른 Jenkins Job이 같은 Host를 사용할 수 있으므로 전체 Docker prune은 실행하지 않습니다.
            sh '''
                set +e
                rm -f "trivy-reports/trivy-api-${BUILD_NUMBER}.json"
                rm -rf .venv task-definition-current.json task-definition-new.json
                docker rm -f "api-smoke-${BUILD_NUMBER}" >/dev/null 2>&1 || true
                if [ -n "${IMAGE_URI:-}" ]; then
                  docker image rm "${IMAGE_URI}" >/dev/null 2>&1 || true
                fi
            '''
        }
        cleanup {
            script {
                env.SUMMARY_BUILD_RESULT = currentBuild.currentResult ?: 'UNKNOWN'
                env.SUMMARY_DEPLOY_RESULT = env.DEPLOY_PHASE == 'DEPLOY_SUCCESS' ?
                    'DEPLOY_SUCCESS' :
                    (env.SERVICE_UPDATE_REQUESTED == 'true' ?
                        'DEPLOY_FAILED_AFTER_SERVICE_UPDATE' : 'DEPLOY_FAILED_BEFORE_SERVICE_UPDATE')
                env.SUMMARY_FINAL_REVISION = env.API_FINAL_TASK_DEFINITION_ARN ?:
                    (env.DEPLOY_PHASE == 'DEPLOY_SUCCESS' ? env.NEW_TASK_DEFINITION_ARN : 'N/A')
                env.SUMMARY_ROLLBACK_HANDLING_EXECUTED =
                    env.SERVICE_UPDATE_REQUESTED == 'true' && env.DEPLOY_PHASE != 'DEPLOY_SUCCESS' ? 'true' : 'false'

                int summaryStatus = sh(
                    returnStatus: true,
                    script: '''
                        set +e
                        mkdir -p "${DEPLOYMENT_SUMMARY_DIR}"
                        python3 - <<'PY'
import datetime
import json
import os

def value(name):
    result = os.environ.get(name)
    return result if result else "N/A"

trivy = {
    "status": "TRIVY_SCAN_INCOMPLETE",
    "high_count": "N/A",
    "critical_count": "N/A",
}
trivy_path = f".trivy-result-api-{value('BUILD_NUMBER')}.json"
try:
    with open(trivy_path, "r", encoding="utf-8") as trivy_file:
        trivy.update(json.load(trivy_file))
except Exception:
    pass
trivy.update({
    "report_path": f"trivy-reports/trivy-api-{value('BUILD_NUMBER')}.json",
    "gate_enabled": False,
    "gate_policy": "WARNING_ONLY",
    "gate_result": "NOT_APPLIED",
})

ai_failure_summary = {
    "enabled": True,
    "provider": "bedrock",
    "status": "SUMMARY_NOT_CREATED",
    "masked": True,
}
ai_summary_path = f".ai-failure-summary-api-{value('BUILD_NUMBER')}.json"
try:
    with open(ai_summary_path, "r", encoding="utf-8") as ai_summary_file:
        ai_failure_summary.update(json.load(ai_summary_file))
except Exception:
    pass

summary = {
    "schema_version": "1.0",
    "service_type": "api",
    "job_name": value("JOB_NAME"),
    "build_number": value("BUILD_NUMBER"),
    "build_result": value("SUMMARY_BUILD_RESULT"),
    "git_commit_sha": value("GIT_COMMIT_SHA"),
    "git_short_sha": value("GIT_SHORT_SHA"),
    "image_tag": value("IMAGE_TAG"),
    "image_uri": value("IMAGE_URI"),
    "image_digest": value("IMAGE_DIGEST"),
    "ecs_cluster": value("ECS_CLUSTER_NAME"),
    "ecs_service": value("ECS_SERVICE_NAME"),
    "task_definition_family": value("ECS_TASK_FAMILY"),
    "baseline_revision": value("PREVIOUS_TASK_DEFINITION_ARN"),
    "requested_revision": value("NEW_TASK_DEFINITION_ARN"),
    "final_revision": value("SUMMARY_FINAL_REVISION"),
    "deploy_phase": value("DEPLOY_PHASE"),
    "deploy_result": value("SUMMARY_DEPLOY_RESULT"),
    "rollback_handling_executed": value("SUMMARY_ROLLBACK_HANDLING_EXECUTED"),
    "rollback_result": value("API_ROLLBACK_RESULT"),
    "trivy": {
        "mode": "WARNING",
        **trivy,
    },
    "ai_failure_summary": ai_failure_summary,
    "ecr_push_executed": value("IMAGE_DIGEST") != "N/A",
    "ecs_deploy_executed": value("SERVICE_UPDATE_REQUESTED") == "true",
    "build_url": value("BUILD_URL"),
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}

summary_path = (
    f"{value('DEPLOYMENT_SUMMARY_DIR')}/"
    f"deployment-summary-api-{value('BUILD_NUMBER')}.json"
)
with open(summary_path, "w", encoding="utf-8") as summary_file:
    json.dump(summary, summary_file, indent=2)
PY
                    '''
                )
                if (summaryStatus != 0) {
                    echo "WARNING: API deployment summary generation failed. Existing build result is unchanged."
                } else {
                    try {
                        archiveArtifacts(
                            artifacts: "deployment-summaries/deployment-summary-api-${env.BUILD_NUMBER}.json",
                            fingerprint: true
                        )
                    } catch (Exception ignored) {
                        echo "WARNING: API deployment summary archive failed. Existing build result is unchanged."
                    }
                }
                sh(
                    returnStatus: true,
                    script: '''
                        rm -f \
                          "deployment-summaries/deployment-summary-api-${BUILD_NUMBER}.json" \
                          ".trivy-result-api-${BUILD_NUMBER}.json" \
                          ".ai-failure-summary-api-${BUILD_NUMBER}.json"
                    '''
                )
            }
        }
    }
}
