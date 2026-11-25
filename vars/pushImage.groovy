// Push Image: pushes the tag built for this run.
def call(Map cfg, String service, String image) {
    withEnv(["IMAGE=${image}"]) {
        sh '''#!/bin/bash
set -euo pipefail
docker push "${IMAGE}"
'''
    }
}
