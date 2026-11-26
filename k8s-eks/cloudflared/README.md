# Cloudflare Quick Tunnel (temporary public HTTPS link)

Free temporary HTTPS access to the site, no domain and no Cloudflare account.
A `cloudflared` pod inside the cluster dials OUT to Cloudflare; nothing listens
publicly. Docs: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

Know before you apply:

- The URL is random (`https://<random>.trycloudflare.com`), public, and NOT
  permanent. Every cloudflared restart creates a new one (see "URL changed").
- Cloudflare is the TLS middleman: its edge can technically see all traffic,
  including the owner password.
- Cloudflare marks Quick Tunnels for testing/development, not production.
- Secure cookies are turned on for the public URL. Owner login over
  http://localhost:8000 (kubectl port-forward) may stop working; use the HTTPS
  URL for owner admin.
- Tunnel traffic leaves AWS, so it adds NAT processing ($0.045/GB) and data
  transfer out ($0.09/GB beyond the 100 GB/month free aggregate). Small demo
  traffic is cents, not zero.

## First-time apply (from the repo root, PowerShell)

```powershell
kubectl apply -f k8s-eks/network-policies/cloudflared.yaml
kubectl apply -f k8s-eks/network-policies/gateway.yaml
kubectl apply -f k8s-eks/gateway/configmap.yaml
kubectl apply -f k8s-eks/gateway/service.yaml
kubectl apply -f argocd-application.yaml
kubectl -n barbershop rollout restart deploy/gateway
```

Then in Argo CD: SYNC the app so it picks up `cloudflared/deployment.yaml`
(and the gateway deployment's new port entry). Wait for the pod to run, then
read the URL:

```powershell
kubectl -n barbershop logs deploy/cloudflared | Select-String trycloudflare
```

Before touching the web config, confirm the web pod runs the image built
from the `app/web/config/settings.py` commit on main (Jenkins builds it after
that push). The old image ignores the new env keys, so the secure flags below
only take effect on the new image. Applying them in the wrong order leaves the
site half-secure or breaks login during the rollout.

```powershell
kubectl -n barbershop get deploy web -o jsonpath='{.spec.template.spec.containers[0].image}'
# tag must be from a build AFTER the settings.py commit
```

Put the printed hostname into `k8s-eks/web/configmap.yaml` (the file in Git
stays the source of truth), then apply and restart web:

```powershell
# in k8s-eks/web/configmap.yaml set:
#   ALLOWED_HOSTS: "localhost,127.0.0.1,<host>"
#   CSRF_TRUSTED_ORIGINS: "https://<host>"
#   TRUST_X_FORWARDED_PROTO: "true"
#   SESSION_COOKIE_SECURE: "true"
#   CSRF_COOKIE_SECURE: "true"
kubectl apply -f k8s-eks/web/configmap.yaml
kubectl -n barbershop rollout restart deploy/web
```

Verify: open the https URL, place a booking, log in as owner over the URL,
then re-check http://localhost:8000 via port-forward.

## URL changed (cloudflared restarted)

1. `kubectl -n barbershop logs deploy/cloudflared | Select-String trycloudflare`
2. Update the two `<host>` values in `k8s-eks/web/configmap.yaml`.
3. `kubectl apply -f k8s-eks/web/configmap.yaml`
4. `kubectl -n barbershop rollout restart deploy/web`

The old URL is dead from the restart until step 4 finishes.

## Rollback

```powershell
kubectl -n barbershop delete deploy/cloudflared
git checkout -- k8s-eks/web/configmap.yaml   # back to the pre-tunnel values
kubectl apply -f k8s-eks/web/configmap.yaml
kubectl -n barbershop rollout restart deploy/web
```

Then remove `cloudflared/deployment.yaml` from `argocd-application.yaml`'s
include list and re-apply it, so Argo stops tracking the tunnel.
