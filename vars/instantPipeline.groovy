// Shared Library entry point: runs the six stages for every service that changed.
//
//   Build Image -> Scan Image -> Push Image -> Delete Image Locally
//     -> Update Manifests -> Push Manifests
//
// Inside Build, Scan and Push the services run as parallel branches. Manifests
// are only updated when every changed service built, scanned and pushed.
def call(Map config = [:]) {
    Map cfg = [
        services        : ['gateway', 'web', 'booking-api', 'identity-api'],
        registry        : '',
        region          : 'us-east-1',
        gitRepoUrl      : '',
        gitBranch       : 'main',
        gitCredentialsId: 'github',
        serviceDir      : '',          // folder that holds the service folders ('' = repo root)
        manifestDir     : 'k8s',
        severity        : 'HIGH,CRITICAL',
        scanMinFreeMb   : 2048,        // Scan Image refuses to start with less free disk than this (MiB)
        ignoreUnfixed   : false,
        agentLabel      : ''
    ] + config

    if (!cfg.registry || !cfg.gitRepoUrl) {
        error('instantPipeline: registry and gitRepoUrl are required')
    }

    // One run at a time: two runs must not push manifests to the same branch together.
    properties([disableConcurrentBuilds()])

    node(cfg.agentLabel) {
        Map images = [:]          // service -> full image reference, for this run
        boolean cleaned = false
        try {
            checkout scm
            String sha = sh(returnStdout: true, script: 'git rev-parse --short=7 HEAD').trim()
            List changed = changedServices(cfg)
            if (changed.isEmpty()) {
                echo 'No service folder changed since the last successful build. Nothing to do.'
                return
            }
            echo "Services to build: ${changed.join(', ')}"
            for (String svc : changed) {
                images[svc] = "${cfg.registry}:${svc}-${env.BUILD_NUMBER}-${sha}".toString()
            }

            stage('Build Image') {
                runPerService(changed) { String svc -> buildImage(cfg, svc, images[svc], sha) }
            }
            stage('Scan Image') {
                // One scan at a time: parallel Trivy runs share one DB download and one cache.
                runSequentially(changed) { String svc -> scanImage(cfg, svc, images[svc]) }
            }
            stage('Push Image') {
                ecrLogin(cfg)
                runPerService(changed) { String svc -> pushImage(cfg, svc, images[svc]) }
            }
            stage('Delete Image Locally') {
                deleteLocalImage(images.values() as List)
                cleaned = true
            }
            stage('Update Manifests') {
                updateManifests(cfg, images)
            }
            stage('Push Manifests') {
                pushManifests(cfg, images)
            }
        } finally {
            // A failed scan or push must not leave images on the agent.
            if (!cleaned && !images.isEmpty()) {
                deleteLocalImage(images.values() as List)
            }
        }
    }
}

// Runs body(service) for every service as a parallel branch; all branches finish
// and report before the stage fails.
private void runPerService(List services, Closure body) {
    Map branches = [:]
    for (String s : services) {
        String svc = s
        branches[svc] = { body(svc) }
    }
    branches.failFast = false
    parallel branches
}

// Runs body(service) one after another. Every service is tried, then the stage
// fails if any of them failed. A user abort or a timeout stops immediately.
private void runSequentially(List services, Closure body) {
    List failed = []
    for (String s : services) {
        String svc = s
        try {
            body(svc)
        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
            throw e
        } catch (Exception e) {
            echo "${svc} failed: ${e.message}"
            failed << svc
        }
    }
    if (!failed.isEmpty()) {
        error("Failed for: ${failed.join(', ')}")
    }
}
