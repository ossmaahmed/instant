// Scan Image: Trivy. Exit code 1 (stage fails) when a vulnerability at the
// configured severity is found. ignoreUnfixed limits that to ones with a fix.
def call(Map cfg, String service, String image) {
    withEnv(["IMAGE=${image}", "SEVERITY=${cfg.severity}", "IGNORE_UNFIXED=${cfg.ignoreUnfixed ? '1' : '0'}"]) {
        sh '''#!/bin/bash
set -euo pipefail
args=(--exit-code 1 --severity "${SEVERITY}" --no-progress)
if [ "${IGNORE_UNFIXED}" = "1" ]; then args+=(--ignore-unfixed); fi
trivy image "${args[@]}" "${IMAGE}"
'''
    }
}
