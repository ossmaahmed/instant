// Logs docker in to the ECR registry with the agent's AWS identity (the Jenkins
// instance role). No registry password is stored anywhere.
def call(Map cfg) {
    String host = cfg.registry.split('/')[0]
    withEnv(["REGISTRY_HOST=${host}", "AWS_REGION=${cfg.region}"]) {
        sh '''#!/bin/bash
set -euo pipefail
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${REGISTRY_HOST}"
'''
    }
}
