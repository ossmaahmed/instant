# Barbershop on Kubernetes (EKS: instant-eks, us-east-1)

Plain YAML, applied with `kubectl apply -f`. One folder per component. Nothing has been applied to any cluster by this package. It has not been run on a cluster yet.

## Folders
```
k8s-eks/
  namespace/          barbershop namespace
  storageclass/       StorageClass barbershop-db (EBS gp3, ebs.csi.aws.com)
  postgres/           statefulset.yaml, service.yaml (headless, name "db"), configmap.yaml, secret.yaml
  identity-api/       deployment.yaml, service.yaml, configmap.yaml, secret.yaml
  booking-api/        deployment.yaml, service.yaml, configmap.yaml, secret.yaml
  web/                deployment.yaml, service.yaml, pvc.yaml, configmap.yaml, secret.yaml
  gateway/            deployment.yaml, service.yaml, configmap.yaml (nginx routing)
  network-policies/   00-default-deny.yaml, 01-allow-dns.yaml, then one file per component
  ingress/            ingress.yaml (AWS ALB to the gateway), later phase
  prereqs/            notes files for the AWS Load Balancer Controller and NetworkPolicy support (see below)
```
Storage: postgres gets its EBS volume from `volumeClaimTemplates` in its StatefulSet, web gets one from `web/pvc.yaml`, both through StorageClass `barbershop-db`. No hand-made PersistentVolumes.

## Before you apply: edit these
1. Images are already set to your Docker Hub images (public, tag `latest`): `osamaahmed123456/barbershop-gateway`, `-web`, `-booking-api`, `-identity-api`. The gateway init container uses the same gateway image. `latest` can change when you push again; pin a tag (for example `v1.0.0`) if you want a repeatable deploy.
2. Every `secret.yaml`: replace each `CHANGE_ME` on your own PC. `BOOKING_DB_PASSWORD` and `IDENTITY_DB_PASSWORD` in `postgres/secret.yaml` must equal `DB_PASSWORD` in `booking-api/secret.yaml` and `identity-api/secret.yaml`. `web/secret.yaml` SECRET_KEY should be a long random string. Do not commit or send the edited files.

## Point kubectl at the cluster (PowerShell)
Keep your default context as docker-desktop and use a separate kubeconfig for EKS:
```
aws eks update-kubeconfig --name instant-eks --region us-east-1 --kubeconfig "$HOME\.kube\config-instant" --alias instant-eks
$k = @('--kubeconfig',"$HOME\.kube\config-instant",'--context','instant-eks')
kubectl @k get nodes
```
Run every kubectl command below with `@k` so nothing lands on the local cluster. Re-run the `$k = ...` line in each new PowerShell window.

## Apply order (from inside k8s-eks)
The network policies go right after the namespace, so deny-all is already in place when the pods start. `ingress/` and `prereqs/` are left out of this first run.
```
kubectl @k apply -f .\namespace\
kubectl @k apply -f .\storageclass\
kubectl @k apply -f .\network-policies\
kubectl @k apply -f .\postgres\
kubectl @k apply -f .\identity-api\
kubectl @k apply -f .\booking-api\
kubectl @k apply -f .\web\
kubectl @k apply -f .\gateway\
kubectl @k -n barbershop get pods,pvc
```
Open the site with a port-forward, as you did locally:
```
kubectl @k -n barbershop port-forward svc/gateway 8000:8000
```
then browse to `http://localhost:8000/`. Not yet tested on this cluster: the gateway policy only admits the two load balancer subnets, so check that the port-forward works with the policies in place. If it does not, tell me what you see before changing any policy. Create the owner account with `createsuperuser` in the identity-api pod, typing the password only at its prompt.

Later, when you want the ALB: install the AWS Load Balancer Controller (see below), then `kubectl @k apply -f .\ingress\` and open `http://<ADDRESS>/` once the Ingress shows an ADDRESS. Do not apply `ingress/` before the controller exists.

## What the cluster must already have
- `ingress/ingress.yaml` needs the AWS Load Balancer Controller. Your Terraform created its IAM role but not the controller. Check: `kubectl -n kube-system get deployment aws-load-balancer-controller`. If missing, `prereqs/alb-controller-values.yaml` has the values for the official Helm chart (https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html).
- NetworkPolicy is only enforced if the VPC CNI add-on has network policy on (VPC CNI 1.21 or later, kernel 5.10 or later). Check: `kubectl -n kube-system get ds aws-node -o jsonpath='{.spec.template.spec.containers[*].name}'` should list `aws-network-policy-agent`. If not, `prereqs/vpc-cni-network-policy.tf.txt` shows the Terraform change (https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy-configure.html). Until then the policies do nothing and the app still works.

## Notes
- Five components: web, identity-api, booking-api, gateway, postgres. web is one site for customers and the shop owner.
- web runs 1 replica with a PVC (its sessions are in a local SQLite file). identity-api and booking-api run 1 replica because each start runs migrations.
- The gateway answers `/healthz` itself, so the ALB health check proves nginx is up, not the apps. web has no /healthz, so it uses TCP probes.
- The gateway policy admits port 8000 from the two public subnets (10.0.1.0/24 and 10.0.2.0/24, from your Terraform output). That limits by address range, not by identity. Change it if your subnets differ.
- The StorageClass uses reclaimPolicy Retain: the EBS volumes (gp3, 5Gi for postgres and 1Gi for web) are billed while they exist. Deleting a PVC or the namespace leaves the volume in place and still billed; the app does not get its data back automatically. Plan any cleanup and backup deliberately.
- HTTPS later needs a domain, an ACM certificate and a small web settings change, or form posts return 403.
- Checked offline only: the previous revision's 30 resources passed `kubeconform -strict` for Kubernetes 1.33. This revision changed only image lines, comments and this README; every YAML file still parses. Not run on a cluster.
