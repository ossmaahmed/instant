# Monitoring: Prometheus + Grafana (plain YAML, namespace `monitoring`)

Status: files only. Nothing here has been applied to any cluster. Checked on a laptop (see "What was checked"), not on `instant-eks`.

## What you get
One Grafana dashboard, "Barbershop: everything", and 19 alert rules.

| Area | What is measured | Where it comes from |
|---|---|---|
| Site | requests/s, responses by status code, errors (5xx), latency p50/p95, per service (web, booking-api, identity-api) | `django-prometheus` in each Django service |
| Bookings | bookings by status and source, created in last 24h, confirmed ahead today and next 7 days | PostgreSQL, through aggregate views (counts only) |
| PostgreSQL | up/down, connections vs limit, database sizes, transactions, deadlocks | postgres-exporter |
| Kubernetes | pod ready, restarts, OOM kills, CPU and memory per pod, memory vs limit, volume usage, pods per node vs node limit | kube-state-metrics, kubelet (cAdvisor) |
| Nodes | CPU, memory, disk used per node | node-exporter |

Alert rules show up in Grafana (Alerting > Alert rules) and in Prometheus (Alerts). **Nothing is sent anywhere.** No email, Telegram, Slack or WhatsApp is configured. You see an alert only by opening Grafana.

## What is NOT covered
- Gateway (nginx) requests, status codes and latency. Open-source nginx does not expose them. Errors are seen per Django service instead. If the gateway pod is down you see it as "pod not ready", not as 502 counts.
- The public Cloudflare URL: whether it works right now. The `CloudflaredPodRecentlyStarted` alert only says the pod restarted, so the URL may have changed.
- Node network traffic (node-exporter runs as a normal pod, not on the host network).
- Why a booking was refused (for example the one-booking-per-day rule). Counts of bookings are covered, refusal reasons are not.
- History longer than 7 days, or surviving a Prometheus pod restart (see "Storage").
- Logs and traces. This is metrics only.

## Folders
```
monitoring/
  namespace/          namespace monitoring
  rbac/               read-only ClusterRoles for Prometheus and kube-state-metrics
  prometheus/         configmap.yaml (scrape config), rules.yaml (alert rules), deployment.yaml, service.yaml
  kube-state-metrics/ deployment.yaml, service.yaml
  node-exporter/      daemonset.yaml (one pod per node)
  postgres-exporter/  deployment.yaml, service.yaml, configmap.yaml (booking queries), monitoring-role.sql
  grafana/            deployment.yaml, service.yaml, datasource.yaml, dashboards-provider.yaml, dashboards.yaml
  network-policies/   default deny + one file per component
```
Not part of the Argo CD Application (it lists only the five Deployment files). Apply with `kubectl apply -f`, like the rest of `k8s-eks/`.

## Changes outside this folder
- `app/web`, `app/booking-api`, `app/identity-api`: `django-prometheus` added (requirements and middleware), a new `gunicorn.conf.py`, and the entrypoint now starts gunicorn with `-c gunicorn.conf.py`. **The worker count is unchanged (2 workers).** The workers write counters to small files in `/tmp/prometheus-multiproc` and the master process adds them up, so a scrape shows the whole pod. Metrics are served on port **9102**, never on the app port, and the gateway does not route to it.
- `k8s-eks/web|booking-api|identity-api/deployment.yaml`: a declared container port `metrics` (9102). No other change.
- `k8s-eks/network-policies/web|booking-api|identity-api.yaml`: one extra ingress rule each, allowing only Prometheus (namespace `monitoring`, label `app=prometheus`) to port 9102. `postgres.yaml`: one extra rule allowing only `postgres-exporter` to port 5432.

## Privacy and access
- Grafana has no public address. Open it with `kubectl port-forward` (below). No sign-up, no anonymous access, no analytics, no update checks. Admin password is in a Secret you create.
- NetworkPolicy works on addresses and ports. It limits who can reach port 9102. It is not a URL filter. Port 9102 only serves metrics.
- Metrics contain counts, view names and status codes. They do not contain request paths, phone numbers or names.
- The PostgreSQL role `monitoring` can read database statistics and three aggregate views. It cannot read the `booking_booking` table (customer names and phones), write, or reach the identity database.
- Cluster permissions: read-only (`get/list/watch` on pods, nodes, volume claims, deployments, statefulsets, daemonsets, and `nodes/metrics`). No secrets, no exec, no `nodes/proxy`.
- node-exporter mounts the node's `/proc`, `/sys` and `/` **read-only** and runs as a non-root user. This is the one place with host access.
- Prometheus reads the kubelet with TLS verification off, because the kubelet certificate does not match the node IP. The call stays inside the VPC and uses the read-only token.

## Storage and resources
- Prometheus keeps 7 days, at most 1GB, on a temporary disk (`emptyDir`, limit 2Gi). If the Prometheus pod is replaced, history starts again. Dashboards and rules are in Git and are not lost. No new EBS volume, no new AWS resource, no node added.
- Requested memory: Prometheus 256Mi, Grafana 192Mi, kube-state-metrics 32Mi, postgres-exporter 32Mi, node-exporter 32Mi x 3 nodes = about 608Mi. Limits: 512, 512, 64, 64, 64 (per pod). On a laptop run Grafana used about 270MB, Prometheus about 80MB with a few targets; real cluster numbers will be higher.
- New pods: 4 + one node-exporter per node (7 on 3 nodes). t3.small nodes allow about 11 pods each (AWS VPC CNI default; confirm below). **node-exporter needs one free pod slot on every node.** If a node is full it stays Pending and the "pod slots" panel and alert show why.

## Capacity check, before applying anything
```
kubectl @k get nodes -o custom-columns=NAME:.metadata.name,PODS:.status.allocatable.pods
kubectl @k get pods -A --no-headers | Measure-Object -Line
kubectl @k get pods -A -o wide --no-headers   # count pods per node (NODE column)
kubectl @k describe nodes   # look at "Allocated resources" for memory requests
```
Go ahead only if every node has at least 1 free pod slot and the total free slots are at least 7. Memory: each node should keep roughly 400Mi of requests free. If not, stop and tell me. Do not add a node without deciding it on purpose, it costs money.

## Apply order
1. Build and deploy the three app images with metrics first (Jenkins Build Now for web, booking-api, identity-api; commit the manifest tags; Argo CD sync). Until then the Prometheus app targets show DOWN and `AppTargetDown` fires. That is expected.
2. Apply the barbershop policy and deployment edits. Review the Argo CD diff before Sync: it should show only the added `metrics` port on the three Deployments. Apply the policies: `kubectl @k apply -f .\network-policies\`.
3. Monitoring namespace, policies first (deny-all is in place before pods start):
```
kubectl @k apply -f .\monitoring\namespace\
kubectl @k apply -f .\monitoring\network-policies\
kubectl @k apply -f .\monitoring\rbac\
```
4. Secrets. Create them yourself. Do not paste passwords in chat.
```
# Grafana admin password: you choose it (typed hidden)
$p = Read-Host "Grafana admin password" -AsSecureString
$g = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($p))
kubectl @k -n monitoring create secret generic grafana-secret --from-literal=admin-password=$g

# Password for the database monitoring role: random, never shown
$m = -join ((48..57)+(97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
kubectl @k -n monitoring create secret generic postgres-exporter-secret --from-literal=password=$m
```
5. Create the read-only database role (touches the live database; run once; read `postgres-exporter/monitoring-role.sql` first). The postgres Secret holds the superuser password, the pod name is `postgres-0`:
```
Get-Content .\monitoring\postgres-exporter\monitoring-role.sql | kubectl @k -n barbershop exec -i postgres-0 -- psql -U postgres -d booking -v ON_ERROR_STOP=1 -v monitoring_pw=$m -f -
```
(`$m` is visible only briefly in that pod's process list.) Check: `kubectl @k -n barbershop exec postgres-0 -- psql -U postgres -d booking -c "\du monitoring"`.
6. The components:
```
kubectl @k apply -f .\monitoring\prometheus\
kubectl @k apply -f .\monitoring\kube-state-metrics\
kubectl @k apply -f .\monitoring\node-exporter\
kubectl @k apply -f .\monitoring\postgres-exporter\
kubectl @k apply -f .\monitoring\grafana\
kubectl @k -n monitoring get pods
```
7. Open Grafana and Prometheus (separate PowerShell windows):
```
kubectl @k -n monitoring port-forward svc/grafana 3000:3000
kubectl @k -n monitoring port-forward svc/prometheus 9090:9090
```
Grafana: http://localhost:3000 (user `admin`). Prometheus targets: http://localhost:9090/targets. All targets should be UP.

## Checks after applying
- Targets UP: barbershop-apps (3), kube-state-metrics, node-exporter (3), postgres, kubelet-cadvisor and kubelet (one per node).
- If the Kubernetes API or kubelet targets time out, the NetworkPolicy address ranges are the first suspect: confirm the VPC CIDR (`10.0.0.0/16` in terraform) and the service CIDR (`kubectl @k get svc kubernetes -n default`, expected 172.20.x.x) and adjust `monitoring/network-policies/prometheus.yaml` and `kube-state-metrics.yaml`.
- Is NetworkPolicy really enforced? See the check in `k8s-eks/README.md` (aws-network-policy-agent). Then test: `kubectl @k -n monitoring run np-test --rm -it --restart=Never --image=busybox:1.36 -- wget -T 3 -qO- http://<web pod IP>:9102/metrics`. In an enforcing cluster this times out (that pod is not Prometheus and has default deny). If it returns metrics, the policies are not enforced and the metrics port is open to the cluster.
- Metrics port not on the app port: `curl http://localhost:8000/metrics` through a gateway port-forward must be 404.

## Changing the config
Edit the file, apply it, wait about a minute, then reload without restarting:
```
kubectl @k -n monitoring exec deploy/prometheus -- wget -qO- --post-data= http://localhost:9090/-/reload
```
Dashboards: edit `grafana/dashboards.yaml`, apply, then `kubectl @k -n monitoring rollout restart deploy/grafana` (Grafana keeps nothing important).

## Remove it again
```
kubectl @k delete namespace monitoring
kubectl @k delete clusterrole prometheus-read kube-state-metrics-read
kubectl @k delete clusterrolebinding prometheus-read kube-state-metrics-read
kubectl @k -n barbershop exec postgres-0 -- psql -U postgres -d booking -c "DROP SCHEMA monitoring CASCADE; DROP OWNED BY monitoring; DROP ROLE monitoring;"
```
The extra policy rules and the `metrics` container port in barbershop are harmless to leave.

## What was checked, and what was not
Checked on a laptop: all 43 manifests parse and pass `kubeconform` (Kubernetes 1.32 schemas); the Prometheus config and the alert rules pass `promtool`; alert rules fire correctly in `promtool test rules` for target down, 5xx ratio and database down; the three Django services ran with 2 gunicorn workers and a new automated test proves the metrics endpoint counts every worker (41 requests in, 41 counted); the full test suites pass (booking-api 49 tests on SQLite and on real PostgreSQL 16 with 0 skipped; identity-api 8; web 26); the database role cannot read the booking table; postgres-exporter returned the booking counts; Prometheus scraped the three services, node-exporter and postgres-exporter; Grafana 12.2.0 loaded the provisioned datasource and dashboard and 34 panel queries returned data.
Not checked, because it needs the cluster: kube-state-metrics, kubelet/cAdvisor and node-exporter on real nodes, any NetworkPolicy behaviour (enforcement is unverified), pod capacity, Argo CD sync of the changed Deployments, and the Jenkins build of the new images (Trivy scan, image size). Panels for those show "no data" locally by design.
