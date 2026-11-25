// Update Manifests: points each service's deployment at the image pushed in
// this run. Only `image:` lines that belong to the service are rewritten (the
// Docker Hub name barbershop-<service> or the ECR tag prefix <service>-), so
// the gateway's init container and main container both change and nothing
// else does. The run fails if the number of rewritten lines is not the number
// of image lines in the file.
def call(Map cfg, Map images) {
    for (String svc : images.keySet()) {
        withEnv(["SVC=${svc}", "IMAGE=${images[svc]}", "MANIFEST_DIR=${cfg.manifestDir}"]) {
            sh '''#!/bin/bash
set -euo pipefail
f="${MANIFEST_DIR}/${SVC}/deployment.yaml"
[ -f "$f" ] || { echo "missing $f"; exit 1; }
expected=$(grep -cE '^[[:space:]]*image:' "$f")
sed -i -E "s#^([[:space:]]*image:[[:space:]]*)[^[:space:]]*(barbershop-${SVC}|instant-app:${SVC}-)[^[:space:]]*#\\1${IMAGE}#" "$f"
actual=$(grep -cF "${IMAGE}" "$f")
if [ "$expected" != "$actual" ]; then
  echo "${f}: ${expected} image line(s), ${actual} rewritten. Refusing to continue."
  exit 1
fi
echo "${f}: ${actual} image line(s) now ${IMAGE}"
'''
        }
    }
}
