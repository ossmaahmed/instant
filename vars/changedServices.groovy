// Returns the services whose folder changed since the last successful build.
// First run, or a missing/unreachable previous commit: all services.
// A commit that only touches k8s/ (the pipeline's own manifest commit) changes
// no service folder, so it builds nothing. That is what stops build loops.
def call(Map cfg) {
    List all = cfg.services
    String prev = (env.GIT_PREVIOUS_SUCCESSFUL_COMMIT ?: '').trim()
    if (!(prev ==~ /^[0-9a-f]{40}$/)) {
        return all
    }
    int known = sh(returnStatus: true, script: "git cat-file -e '${prev}^{commit}'")
    if (known != 0) {
        echo "Previous successful commit ${prev} is not in this checkout. Building all services."
        return all
    }
    String out = sh(returnStdout: true, script: "git diff --name-only '${prev}' HEAD").trim()
    List files = out ? out.split('\n') as List : []
    List changed = []
    for (String svc : all) {
        boolean hit = false
        for (String f : files) {
            if (f.startsWith(svc + '/')) {
                hit = true
            }
        }
        if (hit) {
            changed << svc
        }
    }
    return changed
}
