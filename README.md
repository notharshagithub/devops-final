# TaskBoard — DevOps Final Capstone (Session 21)

TaskBoard is a SaaS-style project-management app built to show the full DevOps lifecycle:
code travels from a laptop to a monitored Kubernetes environment on AWS.

Users get a responsive dashboard (dark sidebar, workspaces with live counts, KPI cards, task
table, status filters, search, priority badges, activity feed, create-task modal). Engineers get
everything behind it: FastAPI + PostgreSQL + Alembic, pytest gates, Docker, GitHub Actions,
Trivy scans, GHCR, Terraform VPC + EKS, Helm, Ingress, HPA, and Prometheus + Grafana.

This is an original implementation (FastAPI + SQLAlchemy 2.0, hand-written Helm chart, Vite +
Nginx routing) following the Session 21 architecture for the DevOps layer.

```
GitHub → Actions (pytest → build → Trivy → GHCR push) → Terraform (VPC+EKS) → Helm → Ingress → HPA → Prometheus/Grafana
```

## Stack

| Layer        | Tech                                                                 |
| ------------ | -------------------------------------------------------------------- |
| Frontend     | React 18 + Vite, Nginx (`/api` → backend, so the browser needs no backend hostname) |
| Backend      | FastAPI, SQLAlchemy 2.0, Alembic, Pydantic validation, `/docs` Swagger |
| Database     | PostgreSQL (`tasks` table, 2 migrations)                             |
| Tests        | pytest, 13 tests on an isolated SQLite DB (never production Postgres) |
| Containers   | Backend `python:3.12-slim` as `appuser`; frontend multi-stage Node → `nginx-unprivileged` |
| CI/CD        | GitHub Actions: TEST → BUILD+SCAN+PUSH → DEPLOY, images tagged by commit SHA |
| Security     | Trivy on both images; fails on actionable HIGH/CRITICAL (`ignore-unfixed`) |
| AWS          | Terraform VPC (3 public + 3 private subnets, NAT) + EKS 1.30 (`ap-south-1`) |
| Kubernetes   | Helm chart: 2× backend + 2× frontend, ClusterIP Services, Postgres + PVC, Ingress (`/` → frontend, `/api` → backend), HPA (CPU 60%, 2–6), ServiceMonitor |
| Monitoring   | kube-prometheus-stack scraping `/metrics`; Grafana panels (RPS, p95, errors) |

## Prerequisites

| Need it for | Install |
| ----------- | ------- |
| `docker compose up` (fastest run) | Docker Engine 24+ + Compose plugin, ports 3000/8000 free |
| Backend directly | Python 3.12+, PostgreSQL 14+ (or set any `DATABASE_URL`), `pip install -r backend/requirements.txt` |
| Frontend directly | Node 22+, `npm install` in `frontend/` |
| Kubernetes | minikube + `kubectl` + Helm 4+ (Ingress via `minikube addons enable ingress`) |
| AWS | Terraform 1.6+, AWS CLI with configured credentials (`aws configure`, region `ap-south-1`) |
| Screenshots | Any browser + terminal that can run the commands below |

## Run it

```bash
docker compose up --build
# app http://localhost:3000 · api http://localhost:8000/docs · health http://localhost:8000/health
```

Backend directly:

```bash
cd backend && pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://taskboard:taskboard@localhost:5432/taskboard'
alembic upgrade head && uvicorn app.main:app --port 8000
pytest -q   # 13 passed — quality gate: red tests block every image
```

Kubernetes (minikube):

```bash
minikube start --driver=docker
minikube image load taskboard-backend:local taskboard-frontend:local
helm upgrade --install taskboard ./helm/taskboard -n taskboard --create-namespace \
  --set images.backend.repository=taskboard-backend --set images.backend.tag=local \
  --set images.frontend.repository=taskboard-frontend --set images.frontend.tag=local \
  --set monitoring.serviceMonitor.enabled=false   # true on EKS with the operator
minikube addons enable ingress
echo "$(minikube ip) taskboard.local" | sudo tee -a /etc/hosts
# app: http://taskboard.local/ · api: http://taskboard.local/api/tasks/stats
```

Terraform (needs AWS credentials; `destroy` afterwards to avoid charges):

```bash
cd terraform && terraform init && terraform plan && terraform apply
aws eks update-kubeconfig --region ap-south-1 --name taskboard-eks
terraform destroy
```

## API

`GET /` · `GET /health` (liveness, no DB) · `GET /ready` (readiness, `SELECT 1` → 503 if DB down) ·
`GET /metrics` (Prometheus) · `GET/POST /api/tasks` (`?workspace=&status=&priority=&search=`) ·
`GET /api/tasks/stats` (KPI aggregates) · `GET/PUT/DELETE /api/tasks/{id}`

Task fields: title, description, status (`todo|in_progress|done`), priority (`low|medium|high`),
assignee, workspace (`Platform Team|DevOps Capstone|Sprint 21`), timestamps.

## How each DevOps piece works here

- **CI/CD** (`.github/workflows/ci.yml`, on push to `main`): pytest + `npm run build` must pass;
  then both images build, Trivy scans them, and they push to GHCR as
  `ghcr.io/<owner>/taskboard-<backend|frontend>:<commit-sha>` — immutable tags trace any
  container back to its exact commit. Deploy runs Helm when a `KUBE_CONFIG_DATA` secret exists,
  otherwise skips with a message so the pipeline stays green without a cluster.
- **Security**: first scan found 6 fixable HIGHs (`python-multipart` path-traversal/DoS,
  `starlette` DoS/SSRF) — cleared via `python-multipart` 0.0.32, FastAPI 0.143.2, instrumentator
  8.1.0. Remaining Debian HIGHs have no published fix, so the gate uses `ignore-unfixed` and
  fails only on remediable CVEs. Never commit AWS keys — grading rejects secrets in history.
- **Kubernetes**: Deployments self-heal dead Pods; Services give stable DNS; backend waits for
  Postgres via initContainer; liveness `/health` + readiness `/ready` probes; HPA scales backend
  2–6 replicas — demo with `./scripts/load-test.sh http://taskboard.local/api/tasks 500`.
- **Monitoring** (`monitoring/`): ServiceMonitor → Prometheus targets UP → Grafana
  (`admin`/`taskboard-admin`) panel e.g. `sum(rate(http_requests_total[5m])) by (handler)`.
- **Troubleshooting** (`troubleshooting/`): `broken-image.yaml` (ImagePullBackOff → `describe`,
  `events`) and `broken-service.yaml` (selector matches nothing → no endpoints → fix labels).

## Demo script (15 steps)

App → create task · `/docs` CRUD · Postgres `tasks` table · commit + push → green pipeline →
SHA images → Trivy log → GHCR pages → Terraform code → `kubectl get pods,svc` Running →
`helm list` → Ingress browser → `kubectl get hpa` → Prometheus UP + Grafana panel → break a
Service/image and fix it live (`describe`, `events`, `endpoints`).

## Submission map

- M1 app: `backend/app/`, `backend/alembic/versions/`, `requirements.txt`, `frontend/`, `docker-compose.yml` → `submission/m1/`
- M2 tests: `backend/tests/`, `pytest.ini` → `submission/m2/`
- M3 git: repo URL + history (25+ meaningful commits), `.gitignore` → `submission/m3/`
- M4 docker: both Dockerfiles + compose → `submission/m4/`
- M5 pipeline: `.github/workflows/` → `submission/m5/` (+ Actions URL, GHCR screenshots)
- M6 trivy: workflow steps + scan screenshot + `submission/m6/explanation.txt`
- M7 terraform: `terraform/*.tf` + `tfvars.example` → `submission/m7/` (+ plan/apply/destroy + console screenshots)
- M8 k8s: `k8s/` + `helm/` → `submission/m8/` (+ pods/svc/helm-list/Ingress screenshots)
- M9 observability: `monitoring/` → `submission/m9/` (+ metrics/Targets/Grafana screenshots)
- M10: this README + live (or recorded, if remote) demo
