// Scan Image: Trivy. Exit code 1 (stage fails) when a vulnerability at the
// configured severity is found. ignoreUnfixed limits that to ones with a fix.
//
// Trivy's cache and temp files go to <workspace>@tmp on the agent that runs the
// scan, on disk. The scan stops before downloading anything if that folder is
// on a RAM-backed filesystem (tmpfs/ramfs) or has less than scanMinFreeMb free.
// The free-space number is a guard chosen for this pipeline, not a Trivy requirement.
def call(Map cfg, String service, String image) {
    withEnv(["IMAGE=${image}", "SERVICE=${service}", "SEVERITY=${cfg.severity}",
             "IGNORE_UNFIXED=${cfg.ignoreUnfixed ? '1' : '0'}", "MIN_FREE_MB=${cfg.scanMinFreeMb}"]) {
        timeout(time: 20, unit: 'MINUTES') {
            sh '''#!/bin/bash
set -euo pipefail
base="${WORKSPACE_TMP:-${WORKSPACE}@tmp}"
cache_dir="${base}/trivy-cache"
run_root="${base}/trivy-tmp"
tmp_dir="${run_root}/${BUILD_TAG:-build-$$}-${SERVICE}"
mkdir -p "${cache_dir}" "${tmp_dir}"
# Remove only the temp folder this scan created. The cache is kept for the next scan.
trap 'rm -rf -- "${tmp_dir}"' EXIT

for d in "${cache_dir}" "${tmp_dir}"; do
  fstype="$(df -PT "${d}" | awk 'NR==2 {print $2}')"
  free_mb="$(df -Pm "${d}" | awk 'NR==2 {print $4}')"
  echo "Scan storage: ${d} filesystem=${fstype} free=${free_mb}MiB (guard: at least ${MIN_FREE_MB}MiB, not RAM-backed)"
  case "${fstype}" in
    tmpfs|ramfs|devtmpfs)
      echo "ERROR: ${d} is on a RAM-backed filesystem (${fstype}). Scan not started." >&2
      exit 1 ;;
  esac
  if [ "${free_mb}" -lt "${MIN_FREE_MB}" ]; then
    echo "ERROR: only ${free_mb}MiB free for ${d}, below the guard of ${MIN_FREE_MB}MiB. Scan not started." >&2
    exit 1
  fi
done

export TMPDIR="${tmp_dir}"
args=(--cache-dir "${cache_dir}" --timeout 10m --exit-code 1 --severity "${SEVERITY}" --no-progress)
if [ "${IGNORE_UNFIXED}" = "1" ]; then args+=(--ignore-unfixed); fi
trivy image "${args[@]}" "${IMAGE}"
'''
        }
    }
}
