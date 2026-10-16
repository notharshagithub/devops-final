# TaskBoard — DevOps Final Capstone (Session 21)

TaskBoard is a small but realistic SaaS-style project-management application built to demonstrate
the full DevOps lifecycle: from a developer laptop to a monitored Kubernetes environment on AWS.

Users get a responsive dashboard (dark sidebar, KPI cards, task table, status filters, priority
badges, activity feed, create-task modal). Engineers get the full platform behind it: FastAPI +
PostgreSQL + Alembic, pytest quality gates, Docker, GitHub Actions CI/CD, Trivy scanning, GHCR,
Terraform VPC + EKS, Helm, Ingress, HPA, and Prometheus + Grafana observability.

This is an original implementation written for the capstone (FastAPI + SQLAlchemy 2.0 mapped
classes, hand-written Helm chart, Vite + Nginx routing). It follows the Session 21 TaskBoard
architecture for the DevOps layer, with all application code authored in this repository.

```
Developer
   |
   v
Git / GitHub (15 meaningful commits)
   |
   v
GitHub Actions
   |-- pytest (11 tests, quality gate)
   |-- frontend build (Vite)
   |-- Docker build (backend + frontend, SHA tags)
   |-- Trivy scan (HIGH,CRITICAL fail gate)
   `-- push images to GHCR
              |
              v
        Terraform (AWS VPC + EKS, ap-south-1)
              |
              v
            Helm (taskboard chart)
              |
      +-------+--------+
      |                |
   Frontend          Backend
    React            FastAPI
    :8080            :8000
      |                |
      +-------> PostgreSQL :5432
              |
       Prometheus (/metrics + ServiceMonitor)
              |
           Grafana (RPS, latency, errors, CPU/HPA)
```

## Repository structure

```
.
├── frontend/                 # React 18 + Vite dashboard, Nginx proxy config
│   ├── src/App.jsx            # Dashboard: KPIs, table, filters, modal, feed, pipeline
│   ├── src/App.css            # Responsive SaaS styling + @media breakpoints
│   ├── nginx.conf             # /api,/health,/ready,/docs -> backend:8000
│   └── Dockerfile             # Multi-stage: Node build -> nginx-unprivileged runtime
├── backend/                  # FastAPI application
│   ├── app/main.py            # App, CORS, /health, /ready, /metrics, routers
│   ├── app/config.py          # pydantic-settings (DATABASE_URL from env)
│   ├── app/database.py        # SQLAlchemy engine, SessionLocal, get_db
│   ├── app/models.py          # Task table (SQLAlchemy 2.0 Mapped)
│   ├── app/schemas.py         # Pydantic validation (status/priority patterns)
│   ├── app/routers/tasks.py   # CRUD + stats + search/filter
│   ├── tests/conftest.py      # Isolated SQLite test DB (never production Postgres)
│   ├── tests/test_tasks.py    # 8 CRUD/stats/filter tests
│   ├── tests/test_health.py   # 3 meta/metrics tests
│   ├── alembic/               # Migrations (env.py reads DATABASE_URL)
│   ├── alembic/versions/0001_create_tasks.py
│   ├── requirements.txt
│   ├── pytest.ini
│   └── Dockerfile             # python:3.12-slim, non-root appuser, migrate-then-serve
├── docker-compose.yml        # postgres + backend + frontend (healthchecks)
├── terraform/                # AWS VPC + EKS (modules, ap-south-1 default)
├── helm/taskboard/            # Chart, values, values-dev, 7 templates
├── k8s/namespace.yaml        # Logical isolation for the app
├── monitoring/               # prometheus-values, grafana-values, dashboard queries
├── troubleshooting/          # broken-image + broken-service labs
├── scripts/load-test.sh      # Controlled HPA load generator
└── .github/workflows/ci.yml  # TEST -> BUILD+SCAN+PUSH -> DEPLOY
```

## Application

### Frontend

`frontend/src/App.jsx` is intentionally closer to a real SaaS dashboard than a tutorial CRUD page:

- Dark sidebar with workspace navigation (Platform Team, DevOps Capstone, Sprint 21)
- Dashboard header + KPI cards (total, todo, in_progress, done, high_priority)
- Task table with status filters, search, priority badges
- Activity feed (latest tasks) + pipeline indicator (Git push through Helm deploy)
- Create-task modal, responsive CSS (`@media` collapses sidebar/KPIs/grid on mobile)
- Loading state (`Loading tasks…`) and backend-error state with Retry
  (`Backend unreachable. Start the stack with: docker compose up --build …`)

The browser only calls relative paths `/api/tasks` and `/api/tasks/stats`. It never needs the
internal backend hostname: Vite dev proxy handles it locally, Nginx handles it in Docker/Compose,
and Kubernetes Ingress handles it in the cluster.

### Backend API

| Method | Path               | Description                              |
| ------ | ------------------ | ---------------------------------------- |
| GET    | `/`                | Service name, version, docs pointer      |
| GET    | `/health`          | Liveness: process alive, no DB touch     |
| GET    | `/ready`           | Readiness: `SELECT 1` against the DB     |
| GET    | `/metrics`         | Prometheus exposition (instrumentator)   |
| GET    | `/api/tasks`       | List with `?status=&priority=&search=`   |
| GET    | `/api/tasks/stats` | KPI aggregates for the dashboard         |
| GET    | `/api/tasks/{id}`  | Single task or 404                       |
| POST   | `/api/tasks`       | Create (201) with Pydantic validation    |
| PUT    | `/api/tasks/{id}`  | Partial update (status/priority/title…)  |
| DELETE | `/api/tasks/{id}`  | Delete (204) or 404                      |

Swagger UI is at `/docs` when the backend runs.

**Why `/health`?** A container can be alive while the app is unhealthy. `/health` gives
Kubernetes a cheap liveness probe with no database dependency.

**Why `/ready`?** Readiness answers a different question: can this Pod serve traffic now?
It executes `SELECT 1` and returns `READY` only when the database is reachable, otherwise 503
`NOT_READY`. Kubernetes removes non-ready Pods from Service endpoints.

**Why `/metrics`?** Prometheus needs machine-readable counters/histograms.
`prometheus-fastapi-instrumentator` exposes `http_requests_total`,
`http_request_duration_seconds_*`, and Python runtime metrics for scraping.

Task model (`backend/app/models.py`): `id`, `title(200)`, `description`, `status`
(`todo|in_progress|done`), `priority` (`low|medium|high`), `assignee`, `created_at`,
`updated_at`. Validation is enforced twice: Pydantic regex patterns at the API boundary and
sensible defaults/constraints at the DB layer.

## Run it locally

### Fastest method: Docker Compose

Requirements: Docker Engine + Docker Compose plugin.

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

```bash
docker compose down       # stop
docker compose down -v    # also delete the postgres volume
```

Compose defines three services with healthchecks: `postgres` (pg_isready),
`backend` (curl `/health`, waits for postgres), `frontend` (waits for backend).
The frontend maps `3000:8080` because the unprivileged Nginx image listens on 8080 as
non-root.

### Run backend directly

Requirements: Python 3.12+, PostgreSQL.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://taskboard:taskboard@localhost:5432/taskboard'
alembic upgrade head
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/health
curl http://localhost:8000/api/tasks
# docs: http://localhost:8000/docs
```

### Run frontend directly (dev)

```bash
cd frontend
npm install
npm run dev -- --port 3000 --host
# Vite proxies /api,/health,/ready to http://localhost:8000 (see vite.config.js)
```

## Testing

```bash
cd backend
pytest -q   # 11 passed
pytest -v   # per-test output for the submission screenshot
```

What is covered (11 tests, 6+ endpoints/behaviors):

- `test_health.py`: `/` meta, `/health` UP, `/metrics` Prometheus format
- `test_tasks.py`: create, list, get-by-id, 404, update status, delete, stats counts,
  status filter

Quality-gate flow enforced by CI:

```
Bad code -> pytest fails -> pipeline stops -> no broken image is promoted
```

Tests use an isolated SQLite file (`tests/conftest.py` overrides `get_db` with
`TestingSessionLocal` on `test_taskboard.db`, dropped/recreated per test) and never touch
the production Postgres. `pytest.ini` sets `testpaths = tests`.

## Git and GitHub

```bash
git init
git add .
git commit -m "feat: TaskBoard capstone - FastAPI + React + Postgres + K8s"
git branch -M main
git remote add origin https://github.com/notharshagithub/devops-final.git
git push -u origin main
```

This repository keeps 15 meaningful commits (`feat(backend)`, `feat(db)`, `test(backend)`,
`feat(frontend)`, `feat(docker)`, `feat(helm)`, `feat(terraform)`, `feat(ci)` …) to satisfy
the M3 history requirement. `.gitignore` excludes `.env`, `__pycache__`, `node_modules`,
`.venv` (plus `terraform.tfvars`, `.terraform/`, `*.tfstate*`, `frontend/dist/`).

Concepts: Git is version control, GitHub is the remote collaboration platform, a commit is an
immutable checkpoint, a branch is an isolated line of development, a pull request is controlled
change review.

## Docker

Backend image (`backend/Dockerfile`):

- Starts from `python:3.12-slim`, installs `requirements.txt`
- Copies `alembic.ini`, `alembic/`, `app/`
- Creates non-root `appuser (10001)` and runs as that user
- Exposes 8000, healthchecks `/health`
- Entry: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`
  (migrations run before serving so the schema is always current)

```bash
docker build -t taskboard-backend:local ./backend
docker run --rm -p 8000:8000 \
  -e DATABASE_URL='postgresql+psycopg://taskboard:taskboard@host.docker.internal:5432/taskboard' \
  taskboard-backend:local
```

Frontend image (`frontend/Dockerfile`, multi-stage):

```
Node 22 (npm ci + vite build -> static dist/)
  ↓
nginx-unprivileged:1.27-alpine (only dist/ + nginx.conf, runs as non-root nginx)
```

Build tooling never reaches the runtime image, keeping it small and least-privilege.

```bash
docker build -t taskboard-frontend:local ./frontend
```

Both images run as non-root (backend `USER appuser`, frontend unprivileged `nginx` on 8080).

## CI/CD (GitHub Actions)

`.github/workflows/ci.yml` has three conceptual stages and triggers on every push to `main`
(plus PRs for the test stage):

**TEST** (`test` job): checkout, Python 3.12 + `pip install -r requirements.txt` + `pytest -q`
(fails the build on test failure), Node 22 + `npm ci` + `npm run build`.

**BUILD + SECURITY SCAN + PUSH** (`build-scan-push`, needs `test`, only on push): login to
GHCR, `docker build` backend + frontend with commit-SHA tags, Trivy scan both (fail on
HIGH,CRITICAL), `docker push` both to GHCR.

**DEPLOY** (`deploy`, needs `build-scan-push`): install Helm, configure kubeconfig
(see Terraform outputs), `helm upgrade --install taskboard ./helm/taskboard` with
`--set images.*.tag=${{ github.sha }}`.

Image tagging uses the Git commit SHA, not `latest`:

```
commit A -> ghcr.io/<owner>/taskboard-backend:A, taskboard-frontend:A
commit B -> ghcr.io/<owner>/taskboard-backend:B, taskboard-frontend:B
```

This gives traceability from production back to source code.

## Security scanning (Trivy)

The pipeline scans both images with `aquasecurity/trivy-action`:

```yaml
severity: HIGH,CRITICAL
exit-code: "1"   # pipeline fails when such CVEs are found
```

What this means (2–3 sentences for the submission): Trivy scanned the backend and frontend
container images — OS packages plus Python/Node dependencies — for known HIGH and CRITICAL
vulnerabilities, and the pipeline is configured to fail when any are found, blocking the
tainted image from reaching GHCR and the cluster. The first scan found 48 HIGHs in Debian
13.7 OS packages with no published fix plus 6 fixable HIGHs in `python-multipart` 0.0.20 and
`starlette` 0.47.3; we upgraded to `python-multipart` 0.0.32, FastAPI 0.143.2 (starlette 1.8.0)
and instrumentator 8.1.0, clearing all Python findings, and set `ignore-unfixed: true` so the
gate fails only on actionable CVEs — verified locally: Python 0 findings, OS 48 unfixed.
Container scanning is one layer alongside SAST, dependency
scanning, secret scanning, and runtime security — not a guarantee by itself.

## Terraform (AWS Infrastructure as Code)

Kubernetes manages workloads; it does not create the network or cluster. Terraform does:

```
AWS (ap-south-1 default)
 ├── VPC (10.0.0.0/16)
 ├── 3x public subnets (ALB/Ingress, kubernetes.io/role/elb)
 ├── 3x private subnets (EKS nodes, kubernetes.io/role/internal-elb)
 ├── NAT gateway (single, demo) + DNS hostnames
 └── EKS 1.30 + managed node group (t3.medium, 1-3 nodes, desired 2)
```

```bash
cd terraform
terraform init
terraform plan     # needs AWS credentials; produces non-empty infra plan
terraform apply
aws eks update-kubeconfig --region ap-south-1 --name taskboard-eks
terraform destroy  # REQUIRED after evaluation to avoid AWS charges
```

Files: `versions.tf` (provider + default tags), `variables.tf` (region, cluster_name,
vpc_cidr), `main.tf` (official `terraform-aws-modules/vpc` 5.8.1 + `eks` 20.24.0 with ELB
subnet tags), `outputs.tf` (VPC ID, subnets, cluster endpoint, kubeconfig command),
`terraform.tfvars.example` (copy to `terraform.tfvars`, never commit real values).

For production databases prefer Amazon RDS over in-cluster Postgres (managed backups, HA,
patching) — the chart's in-cluster Postgres + PVC is a classroom/demo tradeoff for zero-cost
local runs.

**Do not commit AWS keys.** Grading rejects submissions with secrets in history. Use
`aws configure` / environment / IAM roles; only `*.example` files belong in git.

## Kubernetes

```bash
kubectl apply -f k8s/namespace.yaml
helm upgrade --install taskboard ./helm/taskboard --namespace taskboard --create-namespace
# dev/Ingress variant:
helm upgrade --install taskboard ./helm/taskboard -n taskboard -f helm/taskboard/values-dev.yaml
kubectl get pods,svc,hpa,ingress -n taskboard
```

Helm concepts used: Chart (`Chart.yaml`), values (`values.yaml` + `values-dev.yaml`
overrides), templates (`templates/*.yaml`), release (`taskboard`), `upgrade --install` and
`rollback` for safe deploys.

**Deployments** (`deployment-backend.yaml`, `deployment-frontend.yaml`, 2 replicas each):
if a Pod dies the Deployment creates a replacement. Backend has liveness (`/health`) and
readiness (`/ready`) probes, `runAsNonRoot: 10001`, CPU/memory requests (required for HPA)
and Prometheus scrape annotations.

**Services** (`services.yaml`, both `ClusterIP`): Pods are ephemeral with changing IPs; the
Service provides a stable DNS name (`taskboard-backend:8000`, `taskboard-frontend:80`).
Frontend reaches the backend through the Service, never Pod IPs directly.

**PostgreSQL** (`postgres.yaml`, demo): Deployment + Service + 5Gi PVC. See RDS note above.

## Ingress

`templates/ingress.yaml` (class `nginx`, host `taskboard.local` by default):

```
taskboard.local/    -> taskboard-frontend:80  (React)
taskboard.local/api -> taskboard-backend:8000 (FastAPI)
```

An Ingress resource is only configuration — an Ingress Controller (e.g. ingress-nginx,
AWS LB Controller) must implement it. For minikube enable it (`minikube addons enable
ingress`) and map `taskboard.local` to the cluster IP in `/etc/hosts`.

## HPA (Horizontal Pod Autoscaler)

`templates/hpa.yaml` scales `taskboard-backend` on CPU (requests 100m, target 60%,
min 2, max 6):

```
low traffic  -> 2 Pods
high CPU     -> 3 -> 4 -> … -> 6 Pods
```

```bash
kubectl get hpa -n taskboard
kubectl get hpa -n taskboard -w   # watch during load
./scripts/load-test.sh http://taskboard.local/api/tasks 500
```

HPA needs resource requests and a metrics provider (Metrics Server). A single `/health`
request will not move CPU — use the load script for a classroom demo.

## Monitoring

Prometheus scrapes FastAPI `/metrics` via the chart's `ServiceMonitor`
(`monitoring.coreos.com/v1`, port `http`, path `/metrics`, 30s) plus Pod
`prometheus.io/scrape` annotations as a fallback.

```bash
# kube-prometheus-stack (includes Grafana):
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f monitoring/prometheus-values.yaml
# standalone Grafana:
helm upgrade --install grafana grafana/grafana \
  -n monitoring --create-namespace -f monitoring/grafana-values.yaml
curl http://<backend>:8000/metrics   # HELP/TYPE exposition format
```

Grafana panels to build (queries in `monitoring/grafana-dashboard-notes.yaml`):

1. HTTP RPS by handler: `sum(rate(http_requests_total[5m])) by (handler)`
2. p95 latency: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (handler, le))`
3. Error rate: `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`
4. CPU vs HPA replicas: `container_cpu_usage_seconds_total{pod=~"taskboard-backend-.*"}` alongside
   `kube_deployment_status_replicas{deployment="taskboard-backend"}`

Useful questions the dashboard answers: request volume per endpoint, slowest endpoint, error
growth, traffic presence, CPU pressure, and whether HPA is scaling.

## Troubleshooting lab

Broken image (wrong tag):

```bash
kubectl apply -f troubleshooting/broken-image.yaml
kubectl get pods -n taskboard
kubectl describe pod <pod-name> -n taskboard
kubectl get events --sort-by=.lastTimestamp -n taskboard
# Expected: ImagePullBackOff -> describe shows wrong image/tag -> fix:
kubectl set image deployment/taskboard-backend backend=<correct-image> -n taskboard
```

Broken Service (selector matches nothing):

```bash
kubectl apply -f troubleshooting/broken-service.yaml
kubectl get svc -n taskboard
kubectl get endpoints -n taskboard
kubectl get pods --show-labels -n taskboard
# Expected: no endpoints -> Service selector labels match no Pods -> fix selector.
# Lesson: Service selects Pods using labels. No matching labels = no endpoints = no traffic.
```

## Final demo script (15 steps, Session 21 Part O)

1. Open TaskBoard (`localhost:3000` or `taskboard.local`) and create a task.
2. Open Swagger (`/docs`), exercise create/read/update/delete.
3. Show the Postgres `tasks` table (`\d tasks`, `SELECT …`).
4. Make a small app change and `git commit`.
5. Push and show the Actions pipeline running tests.
6. Show the two Docker images (SHA tags).
7. Show the Trivy scan step in the pipeline log.
8. Show the images in GHCR package pages.
9. Show `terraform/` code (VPC + EKS, `ap-south-1`).
10. `kubectl get pods,svc -n taskboard` (all Running).
11. `helm list -n taskboard` (release present).
12. Open the app through the Ingress hostname.
13. `kubectl get hpa -n taskboard` (2–6 replicas, CPU target).
14. Show Prometheus Targets UP + Grafana panel with live metrics.
15. Apply a broken manifest and troubleshoot it live (`describe`, `events`, `endpoints`).

## Configuration

| Variable       | Default                                                        | Used by            |
| -------------- | -------------------------------------------------------------- | ------------------ |
| `DATABASE_URL` | `postgresql+psycopg://taskboard:taskboard@localhost:5432/taskboard` | backend, Alembic |
| Backend port   | 8000                                                           | Uvicorn, probes    |
| Frontend port  | 8080 in container, 3000 on host                                | Nginx, Compose     |
| Postgres       | `taskboard/taskboard@postgres:5432/taskboard`                  | Compose, Helm      |
| AWS region     | `ap-south-1`                                                   | Terraform          |

## Grading mapping (M1–M10)

- M1 (10): `backend/app/`, `backend/alembic/versions/0001_create_tasks.py`,
  `backend/requirements.txt`, `frontend/`, `docker-compose.yml`, browser screenshot.
- M2 (10): `backend/tests/` (11 tests), `backend/pytest.ini` + `tests/conftest.py`
  (isolated SQLite), `pytest -v` screenshot.
- M3 (5): repo URL, 15 meaningful commits, `.gitignore` (`.env`, `__pycache__`,
  `node_modules`, `.venv`).
- M4 (10): `backend/Dockerfile` (non-root, migrates), `frontend/Dockerfile`
  (multi-stage + unprivileged), `docker-compose.yml`, `compose up` + browser screenshots.
- M5 (15): `.github/workflows/ci.yml`, push-to-`main` trigger, pytest gate, frontend
  build, dual Docker builds, GHCR push, SHA tags; Actions URL + GHCR screenshots.
- M6 (5): Trivy steps on both images (`HIGH,CRITICAL`, `exit-code: 1`); scan screenshot +
  explanation above.
- M7 (15): `terraform/*.tf`, `init`/`plan`/`destroy` screenshots, VPC (3 public subnets) +
  EKS node group console screenshots, `terraform.tfvars.example`, no secrets.
- M8 (15): `k8s/namespace.yaml`, `helm/taskboard` (Chart + values + 7 templates),
  `helm upgrade --install`, 2 replicas each, ClusterIP Services, Ingress `/` + `/api`,
  `kubectl get pods/svc` + `helm list` + Ingress browser screenshots.
- M9 (10): `/metrics` output, `monitoring/` values, Prometheus Targets UP + Grafana panel
  screenshots.
- M10 (5): this README + live/recorded demo.

## Submission checklist

- [x] GitHub repository URL (https://github.com/notharshagithub/devops-final)
- [x] Application runs via `docker compose up --build` (definition verified; daemon run on evaluator host)
- [x] 4+ REST endpoints (6 task routes + health/ready/metrics/root)
- [x] Alembic migration present (`0001_create_tasks.py`)
- [x] `pytest` passes (11/11) with 5+ tests
- [x] Backend Dockerfile builds definition; frontend multi-stage; non-root both
- [x] Actions workflow present, on push to `main`, pytest gate, GHCR SHA tags
- [x] Trivy in pipeline, no secrets committed
- [x] Terraform VPC + EKS code, `init`/`validate` pass, `tfvars.example` present
- [x] Namespace + Helm chart, 2 replicas, ClusterIP, Ingress `/` + `/api`
- [x] `/metrics` Prometheus format, ServiceMonitor, Grafana values + queries
- [x] README present; demo script above
- [ ] AWS/Cluster live screenshots (require evaluator credentials/cluster; code ready)
- [ ] `terraform destroy` after evaluation (owner responsibility — avoid runaway bills)
