# Ehgez Dorak (احجز دورك) — Barbershop Booking + Full DevOps Pipeline

## 1. What the project is, and the problem it solves

An Arabic-language booking web app for a single barbershop with one barber. Instead of phone calls and WhatsApp messages (double bookings, forgotten appointments, manual scheduling), customers book from a link: they see services and prices, pick a free slot, and book with just a name and phone number — no account needed. The shop owner gets a private dashboard to set working hours, close days, manage services and prices, and track bookings.

The repository is also a complete DevOps training/portfolio project: the app is containerized microservices, provisioned on AWS with Terraform, configured with Ansible, built and scanned by Jenkins, deployed to EKS by Argo CD (GitOps), and monitored with Prometheus + Grafana.

## 2. Technologies and versions

| Area | Stack |
|---|---|
| Application | Python 3.12 · Django 5.2 · Django REST Framework 3.18 · Gunicorn 23 · PostgreSQL 16 · Nginx (stable-alpine) · HTML/CSS/JS with Django templates (no React) |
| Containers | Docker · Docker Compose v2 · one Dockerfile per service |
| Kubernetes | Plain-YAML manifests on Amazon EKS (`instant-eks`, us-east-1) · Argo CD v3.6.3 (manual sync) |
| CI | Jenkins on EC2 (Amazon Linux 2023, Java 17) with the `instant-lib` shared library (`vars/`) · Trivy image scanning (fails on HIGH/CRITICAL) |
| Infrastructure | Terraform >= 1.10 (AWS provider ~> 5.0) · Ansible roles (docker, java, jenkins, trivy) |
| Monitoring | Prometheus v3.5.0 · Grafana 12.2.0 · node-exporter · kube-state-metrics · postgres-exporter v0.17.1 · django-prometheus |
| Registry / access | AWS ECR · public HTTPS via Cloudflare Quick Tunnel (cloudflared 2026.10.7) |

## 3. Requirements and dependencies

- **Local run:** Docker Desktop with Compose v2 (Windows/macOS/Linux).
- **AWS infrastructure:** an AWS account, Terraform >= 1.10, AWS CLI, kubectl, and an S3 bucket named `backend` (us-east-1) for Terraform state.
- **Jenkins host:** created by Terraform, then configured by Ansible from a control machine with the `amazon.aws` collection and `boto3`/`botocore` installed, plus SSH access with the EC2 private key.
- Python dependencies are per service in `app/<service>/requirements.txt`; nothing needs to be installed on the host for the Docker run.

## 4. Install and run, in order

**A. Run locally (Docker Compose):**

```sh
git clone https://github.com/ossmaahmed/instant.git
cd instant/app
# create a .env file with the variables from section 5 (the three passwords are required)
docker compose up --build
docker compose exec identity-api python manage.py createsuperuser   # one-time owner account
```

Site: http://127.0.0.1:8000/ — owner login: http://127.0.0.1:8000/owner/login/

**B. Create the AWS infrastructure:** review `terraform/terraform.tfvars` (set `jenkins_access_cidr` to your IP, set `jenkins_key_name`), then from `terraform/`: `terraform init && terraform plan && terraform apply`. Then configure Jenkins from `ansible/`: `ansible-galaxy collection install -r requirements.yml && ansible-playbook site.yml --private-key <ec2-key>.pem`.

**C. Deploy to EKS:** point kubectl at the cluster (`aws eks update-kubeconfig --name instant-eks --region us-east-1`), fill the `CHANGE_ME` values in the `k8s-eks/*/secret.yaml` files locally (never commit them), then apply the folders in the order given in `k8s-eks/README.md` (namespace → storageclass → network-policies → postgres → identity-api → booking-api → web → gateway).

**D. CI/CD:** a Jenkins "Build Now" runs the root `Jenkinsfile`: build changed service images → Trivy scan → push to ECR → update image tags in `k8s-eks/` and push to GitHub. Argo CD (`argocd-application.yaml`) then shows the cluster OutOfSync, and a manual **Sync** rolls out the change.

**E. Monitoring:** apply the `monitoring/` folder following `monitoring/README.md` (namespace, policies, secrets, then components; open Grafana via port-forward).

## 5. Environment variables (no secret values here)

Local `.env` in `app/`:

| Variable | Purpose | Default |
|---|---|---|
| `POSTGRES_PASSWORD` | PostgreSQL superuser password | required |
| `BOOKING_DB_PASSWORD` | booking database role password | required |
| `IDENTITY_DB_PASSWORD` | identity database role password | required |
| `WEB_SECRET_KEY` | Django secret key for the web service | required |
| `SEED_DEMO` | load demo services/hours on first start | `true` |
| `CUSTOMER_CUTOFF_MINUTES` | how long before a slot guests may change/cancel | `120` |
| `LOCKOUT_MINUTES` | lockout after failed logins/lookups | `15` |
| `SLOT_STEP_MINUTES` | booking slot step | `30` |
| `WEB_DB_PATH` | optional path for the web session store | in-container |

On Kubernetes the same values live in the `k8s-eks/*/secret.yaml` files as `CHANGE_ME` placeholders, filled locally and never committed. Monitoring adds two secrets created with `kubectl` (Grafana admin password, postgres-exporter password) — see `monitoring/README.md`.

## 6. How to use it — main features

- **Guest:** open the link → see services and prices → pick a slot (today + 2 days ahead) → book with name and phone → manage the booking later with the booking code + phone number (change or cancel up to 2 hours before).
- **Owner** (separate `/owner/` UI, no link on customer pages): weekly working-hours template with per-date exceptions and holidays, blocked periods, services and price management, bookings dashboard (cancel, mark visit done, add a manual booking), password change, automatic lockout after 10 failed attempts.
- **Guarantee:** double booking is impossible — occupied minutes are unique database rows written in the same transaction as the booking.

## 7. Demo and screenshots

- Local: http://127.0.0.1:8000/ (owner: `/owner/login/`).
- On EKS: `kubectl port-forward svc/gateway 8000:8000`, then http://localhost:8000/.
- Temporary public HTTPS link: a Cloudflare Quick Tunnel pod serves the site at a `trycloudflare.com` URL (free, no domain, no account). The URL changes when the pod restarts — see `k8s-eks/cloudflared/README.md`. No permanent demo link yet.

## 8. Running the tests

Each service has its own Django test suite (run from its folder, needs the requirements installed):

```sh
cd app/booking-api  && python manage.py test   # 49 tests, incl. a PostgreSQL double-booking concurrency test
cd app/identity-api && python manage.py test   # 8 tests (tokens, lockout, password change)
cd app/web          && python manage.py test   # 26 tests (views, sessions, metrics)
```

There is also a gateway smoke test: `app/scripts/smoke-gateway.sh`. In CI, the Trivy scan in the Jenkins pipeline acts as a quality gate and fails the build on any HIGH or CRITICAL finding.

---

Detailed docs live next to each part: `app/README.md` (architecture, booking rules), `k8s-eks/README.md` (cluster apply order), `terraform/README.md`, `ansible/README.md`, `monitoring/README.md`.
