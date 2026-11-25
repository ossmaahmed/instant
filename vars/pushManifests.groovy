// Push Manifests: one commit with every manifest change from this run, pushed to
// the branch with the Jenkins credential. If the branch moved, rebase and retry
// (3 tries). The token is read from the environment by a git credential helper;
// it is never put on a command line or in the repository.
def call(Map cfg, Map images) {
    String tags = images.keySet().join(', ')
    withEnv([
        "REPO_URL=${cfg.gitRepoUrl}",
        "BRANCH=${cfg.gitBranch}",
        "MANIFEST_DIR=${cfg.manifestDir}",
        "COMMIT_MSG=ci: update image tags for ${tags} (build #${env.BUILD_NUMBER})"
    ]) {
        withCredentials([usernamePassword(credentialsId: cfg.gitCredentialsId,
                                          usernameVariable: 'GIT_USER',
                                          passwordVariable: 'GIT_TOKEN')]) {
            sh '''#!/bin/bash
set -euo pipefail
helper='!f() { echo "username=${GIT_USER}"; echo "password=${GIT_TOKEN}"; }; f'
git config user.name "jenkins-ci"
git config user.email "jenkins-ci@users.noreply.github.com"
git add -- "${MANIFEST_DIR}"
if git diff --cached --quiet; then
  echo "No manifest change to commit."
  exit 0
fi
git commit -m "${COMMIT_MSG}"
tries=0
until git -c credential.helper="${helper}" push "${REPO_URL}" "HEAD:refs/heads/${BRANCH}"; do
  tries=$((tries + 1))
  if [ "${tries}" -ge 3 ]; then
    echo "Push failed after ${tries} tries."
    exit 1
  fi
  git -c credential.helper="${helper}" fetch "${REPO_URL}" "${BRANCH}"
  git rebase FETCH_HEAD
done
'''
        }
    }
}
