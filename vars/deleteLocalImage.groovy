// Delete Image Locally: removes the images built in this run from the agent.
// Safe to call twice and never fails the build.
def call(List images) {
    for (Object img : images) {
        withEnv(["IMAGE=${img}"]) {
            sh '''#!/bin/bash
docker rmi -f "${IMAGE}" || true
'''
        }
    }
}
