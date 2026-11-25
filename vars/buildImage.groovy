// Build Image: docker build of <service>/Dockerfile, tagged for the registry.
def call(Map cfg, String service, String image, String sha) {
    withEnv(["SVC=${service}", "IMAGE=${image}", "SHA=${sha}"]) {
        sh '''#!/bin/bash
set -euo pipefail
docker build --pull \
  --label "org.opencontainers.image.revision=${SHA}" \
  --label "org.opencontainers.image.source=https://github.com/ossmaahmed/instant" \
  -t "${IMAGE}" "./${SVC}"
'''
    }
}
