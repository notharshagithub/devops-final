# TaskBoard — DevOps Final Capstone (Session 21)

TaskBoard is a small but realistic SaaS-style project-management application built to show how
real software travels from a developer laptop to a monitored Kubernetes environment on AWS.

Users get a responsive dashboard: dark sidebar, workspace navigation with live counts, KPI
cards, a task table with status filters and search, priority badges, an activity feed, a
pipeline indicator, and a create-task modal with loading and backend-error states. Engineers get
everything behind it: FastAPI + PostgreSQL + Alembic migrations, a pytest quality gate, Docker
images, GitHub Actions CI/CD, Trivy security scanning, GHCR, Terraform VPC + EKS, Helm,
Ingress, HPA autoscaling, and Prometheus + Grafana observability — plus deliberately broken
manifests for troubleshooting practice.

This is an original implementation (FastAPI + SQLAlchemy 2.0 mapped classes, hand-written Helm
chart, Vite + Nginx routing). It follows the Session 21 architecture for the DevOps layer, with
all application code authored in this repository.
/
```
Developer
   |
   v
Git / GitHub (30+ meaningful commits: feat/fix/docs/test, never "update")
   |
   v
GitHub Actions
   |-- pytest (13 tests — quality gate, red blocks everything)
   |-- frontend build (Vite)
   |-- Docker build (backend + frontend, immutable commit-SHA tags)
   |-- Trivy scan (HIGH/CRITICAL gate on actionable CVEs)
   `-- push images to GHCR
              |
              v
        Terraform (AWS VPC + EKS, ap-south-1)
              |
              v
            Helm (taskboard release)
              |
      +-------+--------+
      |                |
   Frontend          Backend
    React            FastAPI
    :8080            :8000
      |                |
      +-------> PostgreSQL :5432
              |
       Prometheus (/metrics + ServiceMonitor, target UP)
              |
           Grafana (RPS, p95 latency, error panels)
```

## Repository structure

```
.
├── frontend/                      # React 18 + Vite dashboard + Nginx proxy config
│   ├── src/App.jsx                # KPIs, table, workspace/status/search filters, modal, feed
│   ├── src/App.css                # SaaS styling + @media responsive breakpoints
│   ├── src/main.jsx               # React entrypoint
│   ├── nginx.conf                 # compose: /api,/health,/ready → backend:8000
│   └── Dockerfile                 # multi-stage: Node build → nginx-unprivileged runtime
├── backend/
│   ├── app/main.py                # FastAPI app, CORS, /health, /ready, /metrics, routers
│   ├── app/config.py              # pydantic-settings (DATABASE_URL from env)
│   ├── app/database.py            # SQLAlchemy engine, SessionLocal, get_db dependency
│   ├── app/models.py              # Task table (SQLAlchemy 2.0 Mapped)
│   ├── app/schemas.py             # Pydantic validation (status/priority/workspace rules)
│   ├── app/routers/tasks.py       # CRUD + stats + workspace/status/priority/search filters
│   ├── tests/conftest.py          # isolated SQLite test DB (never production Postgres)
│   ├── tests/test_tasks.py        # 10 CRUD/stats/filter tests
│   ├── tests/test_health.py       # 3 meta/health/metrics tests
│   ├── alembic/                   # env.py reads DATABASE_URL at runtime
│   ├── alembic/versions/          # 0001_create_tasks.py, 0002_add_workspace.py
│   ├── requirements.txt           # pinned: fastapi, uvicorn, sqlalchemy, psycopg, alembic…
│   ├── pytest.ini
│   └── Dockerfile                 # python:3.12-slim, non-root appuser, migrate-then-serve
├── docker-compose.yml             # postgres + backend + frontend with healthchecks
├── terraform/                     # versions, variables, main (VPC+EKS modules), outputs
├── helm/taskboard/                # Chart.yaml, values.yaml, values-dev.yaml, 8 templates
├── k8s/namespace.yaml             # logical isolation for the app
├── monitoring/                    # prometheus-values, grafana-values, dashboard queries
├── troubleshooting/               # broken-image.yaml + broken-service.yaml labs
├── scripts/load-test.sh           # controlled HPA load generator
├── submission/m1..m9/             # per-module evidence copies + screenshots
└── .github/workflows/ci.yml       # TEST → BUILD+SCAN+PUSH → DEPLOY
```

## Prerequisites

| Need it for | Install |
| ----------- | ------- |
| Fastest run (`docker compose up`) | Docker Engine 24+ + Compose plugin; ports 3000/8000 free |
| Backend directly | Python 3.12+, PostgreSQL 14+ (or any reachable `DATABASE_URL`) |
| Frontend directly | Node 22+, `npm install` inside `frontend/` |
| Kubernetes demo | minikube + `kubectl` + Helm 4+; Ingress via `minikube addons enable ingress` |
| AWS infrastructure | Terraform 1.6+, AWS CLI with configured credentials (`aws configure`, `ap-south-1`) |
| Evidence | A browser + terminal for the screenshot commands in each section |

## Run it locally

Fastest method — one command starts postgres + backend + frontend (each with healthchecks,
backend waits for postgres, frontend waits for backend):

```bash
docker compose up --build
# app:      http://localhost:3000
# api docs: http://localhost:8000/docs
# health:   http://localhost:8000/health
# metrics:  http://localhost:8000/metrics
docker compose down        # stop
docker compose down -v     # also delete the database volume
```

The frontend maps `3000:8080` because the unprivileged Nginx image listens on 8080 as non-root.

Backend directly:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://taskboard:taskboard@localhost:5432/taskboard'
alembic upgrade head
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/health
curl http://localhost:8000/api/tasks
```

Frontend directly (Vite proxies `/api`, `/health`, `/ready` to `localhost:8000`):

```bash
cd frontend
npm install
npm run dev -- --port 3000 --host
```

## Backend API in detail

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/` | Service name, version, docs pointer |
| GET | `/health` | Liveness: process alive, no DB touch |
| GET | `/ready` | Readiness: `SELECT 1` → `READY`, else 503 `NOT_READY` |
| GET | `/metrics` | Prometheus exposition (request counters, latency histograms, Python runtime) |
| GET | `/api/tasks` | List, `?workspace=&status=&priority=&search=&limit=&offset=` |
| GET | `/api/tasks/stats` | KPI aggregates (total/todo/in_progress/done/high_priority) |
| GET | `/api/tasks/{id}` | One task or 404 |
| POST | `/api/tasks` | Create (201), validated by Pydantic |
| PUT | `/api/tasks/{id}` | Partial update (status cycling, reassignment, workspace move) |
| DELETE | `/api/tasks/{id}` | Delete (204) or 404 |

Swagger UI lives at `/docs` whenever the backend runs.

**Why `/health`?** A container can be alive while the app is broken. Kubernetes uses this cheap,
DB-free liveness probe to decide when to restart a Pod.

**Why `/ready`?** Readiness answers a different question — can this Pod serve traffic *now*? It
runs `SELECT 1`; only `READY` Pods receive Service endpoints, so deploys and DB outages never
route traffic into a dead backend.

**Why `/metrics`?** Prometheus needs machine-readable counters. `prometheus-fastapi-instrumentator`
exposes `http_requests_total`, `http_request_duration_seconds_*` plus Python GC/memory stats for
scraping (see Monitoring).

**Task model** (`app/models.py`): `id`, `title(200)`, `description`, `status`
(`todo|in_progress|done`), `priority` (`low|medium|high`), `assignee`, `workspace` (`Platform
Team|DevOps Capstone|Sprint 21`), `created_at`, `updated_at`. Rules are enforced twice: Pydantic
patterns at the API boundary, defaults/constraints at the DB layer.

## Frontend in detail

`src/App.jsx` is closer to a real SaaS dashboard than a tutorial CRUD page:

- Dark sidebar with workspace navigation — All + 3 workspaces with **live counts computed from
  the full task list**, so numbers never shift when you click (single fetch, all filtering local)
- Dashboard header, 5 KPI cards fed by `/api/tasks/stats`
- Task table: status badges, priority badges, workspace badge, assignee, per-row status-advance
  (▶ cycles todo→in_progress→done) with pending state, delete with confirm — both with inline
  error feedback and quiet refresh (no full-page flash)
- Status filter chips + search + "Showing X of Y tasks" line; empty results name the exact active
  filters with a "Clear all filters" button, so tasks can never silently disappear
- Create-task modal (title/status/priority/workspace/assignee): on success it jumps to the new
  task's workspace, clears hiding filters, and shows a green confirmation banner
- Activity feed (latest tasks), pipeline indicator (Git push → Helm deploy), loading state, and a
  backend-error state with Retry
- Responsive CSS: sidebar/KPIs/table collapse to a single column on mobile (`@media`)

The browser only calls relative `/api/tasks` and `/api/tasks/stats` — it never knows the backend
hostname. Vite's dev proxy handles it locally, Nginx in Docker/Compose, Ingress in Kubernetes.

## Testing in detail (first quality gate)

```bash
cd backend
pytest -q    # 13 passed
pytest -v    # per-test output for the submission screenshot
```

13 tests across 8 behaviors: `/` meta, `/health` UP, `/metrics` Prometheus format, task create,
list, get-by-id, 404, status update, workspace update, delete, stats counts, status filter,
workspace filter. Flow enforced by CI:

```
Bad code → pytest fails → pipeline stops → no broken image is promoted
```

Isolation: `tests/conftest.py` overrides `get_db` with a SQLite session
(`test_taskboard.db`, dropped/recreated per test) — production Postgres is never touched.
`pytest.ini` pins `testpaths = tests`.

## Git and GitHub

```bash
git init && git add .
git commit -m "feat: TaskBoard capstone - FastAPI + React + Postgres + K8s"
git branch -M main
git remote add origin https://github.com/notharshagithub/devops-final.git
git push -u origin main
```

History keeps 30+ meaningful commits (`feat(backend)`, `feat(db)`, `test(backend)`,
`feat(frontend)`, `fix(frontend)`, `feat(docker)`, `feat(helm)`, `feat(terraform)`,
`feat(ci)`, `fix(ci)`, `fix(security)`, `docs(...)`) — never "update"/"fix"/"test".
`.gitignore` excludes `.env`, `__pycache__`, `node_modules`, `.venv` (plus
`terraform.tfvars`, `.terraform/`, `*.tfstate*`, `frontend/dist/`). Concepts: Git is version
control, GitHub the remote platform, commits immutable checkpoints, branches isolated lines of
development, pull requests controlled review.

## Docker in detail

Backend image: `python:3.12-slim` → system `curl` for healthchecks → `pip install` →
copies `alembic.ini`/`alembic/`/`app/` → creates non-root `appuser (10001)` → `EXPOSE 8000` →
entry `alembic upgrade head && uvicorn …` so the schema is always current before serving.

```bash
docker build -t taskboard-backend:local ./backend
docker run --rm -p 8000:8000 \
  -e DATABASE_URL='postgresql+psycopg://taskboard:taskboard@host.docker.internal:5432/taskboard' \
  taskboard-backend:local
```

Frontend image (multi-stage, build tooling never reaches runtime):

```
Node 22 (npm ci + vite build → static dist/)
  ↓
nginx-unprivileged:1.27-alpine + apk upgrade + dist/ + nginx.conf (runs as nginx, :8080)
```

```bash
docker build -t taskboard-frontend:local ./frontend
```

Both images run non-root (verified via `docker inspect`: `appuser` / UID 101). Compose wires
three healthchecked services; backend waits for postgres, frontend waits for backend.

## CI/CD in detail (automation backbone, runs on every push to `main`)

`.github/workflows/ci.yml` — three stages:

1. **TEST**: checkout → Python 3.12 → `pip install` → `pytest -q` (fails the build on red) →
   Node 22 → `npm ci` → `npm run build`.
2. **BUILD + SCAN + PUSH** (push events only): GHCR login → `docker build` backend + frontend
   tagged by commit SHA → Trivy scans both (`HIGH,CRITICAL`, `ignore-unfixed`, `exit-code: 1`)
   → `docker push` both to GHCR.
3. **DEPLOY**: Helm + kubeconfig from `KUBE_CONFIG_DATA` secret → `helm upgrade --install`
   with `--set images.*.tag=${{ github.sha }}`; without the secret it skips gracefully with a
   message so the pipeline stays green sans cluster.

SHA tagging (never `latest`) gives traceability: `commit A → image A`, so any running container
maps 1:1 back to source and rollbacks are exact.

## Security scanning in detail (non-negotiable gate)

Pipeline step: `aquasecurity/trivy-action@v0.36.0` on both images, `severity: HIGH,CRITICAL`,
`exit-code: 1` — a finding blocks GHCR push and the deploy. Real history from this repo: the
first backend scan found 48 HIGHs in Debian 13.7 with **no published fix** plus 6 fixable HIGHs
(`python-multipart` 0.0.20 path-traversal/DoS CVE-2026-24486/42561/53539, `starlette` 0.47.3
DoS/SSRF CVE-2025-62727/48818/54283). We upgraded to `python-multipart` 0.0.32, FastAPI 0.143.2
(starlette 1.8.0) and instrumentator 8.1.0 — Python findings went to zero (verified with a local
Trivy run: Python 0, OS 48 unfixed) — and set `ignore-unfixed: true` so the gate fails only on
actionable CVEs. Blocking delivery on unfixable OS findings would freeze all releases with no
remediation path; that flag is standard Trivy practice, not a weakened gate. Trivy is container
scanning — one layer alongside SAST, dependency/secret scanning, and runtime security.

## Terraform in detail (real AWS, code not console)

`terraform/` (default region `ap-south-1`): `versions.tf` (AWS provider ~> 5.0, default tags),
`variables.tf` (region, cluster_name, vpc_cidr), `main.tf` (official `vpc` 5.8.1 + `eks` 20.24.0
modules), `outputs.tf` (VPC ID, subnets, cluster endpoint, kubeconfig command),
`terraform.tfvars.example` (copy, never commit real values):

```
AWS
 ├── VPC 10.0.0.0/16 + DNS hostnames
 ├── 3× public subnets (ALB/Ingress, kubernetes.io/role/elb)
 ├── 3× private subnets (EKS nodes, kubernetes.io/role/internal-elb)
 ├── NAT gateway (single, demo) 
 └── EKS 1.30 + managed node group (t3.medium, min 1 / desired 2 / max 3, public endpoint)
```

```bash
cd terraform
terraform init
terraform plan     # needs AWS credentials — non-empty infra plan, no errors
terraform apply
aws eks update-kubeconfig --region ap-south-1 --name taskboard-eks
terraform destroy  # REQUIRED after evaluation — runaway bills are yours, not the course's
```

Classroom Postgres runs in-cluster via the chart; **production should use RDS** (managed backups,
HA, patching) — the in-cluster DB is a zero-cost demo tradeoff. Never commit AWS keys: grading
rejects any secrets in history; use `aws configure` / env / IAM roles.

## Kubernetes in detail

```bash
kubectl apply -f k8s/namespace.yaml
helm upgrade --install taskboard ./helm/taskboard -n taskboard --create-namespace \
  -f helm/taskboard/values-dev.yaml
kubectl get pods,svc,hpa,ingress -n taskboard
```

Helm concepts used: Chart (`Chart.yaml`), values (`values.yaml` + `values-dev.yaml` overrides),
templates, release (`taskboard`), `upgrade --install` / `rollback`.

- **Deployments** (2 replicas each): dead Pods get replaced automatically. Backend carries
  liveness (`/health`) + readiness (`/ready`) probes, `runAsNonRoot: 10001`, CPU/memory requests
  (HPA needs them), a `wait-for-postgres` initContainer (`pg_isready`), and Prometheus scrape
  annotations. Frontend gets its Nginx config from a templated ConfigMap pointing at the
  release's backend Service with request-time DNS (boots cleanly even if backends aren't ready).
- **Services** (both `ClusterIP`): Pods are ephemeral; `taskboard-backend:8000` and
  `taskboard-frontend:80` give stable DNS. Frontend reaches the backend only through Services.
- **PostgreSQL** (demo): Deployment + Service + 5Gi PVC (see RDS note above).
- **ServiceMonitor** (optional via `monitoring.serviceMonitor.enabled`): for clusters with the
  Prometheus operator; off by default on bare minikube (no CRDs), on with kube-prometheus-stack.

## Ingress

`taskboard.local/` → frontend, `taskboard.local/api` → backend (class `nginx`). An Ingress
resource is only configuration — a controller (ingress-nginx, AWS LB Controller) implements it:

```bash
minikube addons enable ingress
echo "$(minikube ip) taskboard.local" | sudo tee -a /etc/hosts
curl http://taskboard.local/api/tasks/stats   # stats JSON proves /api routing
```

(Lesson learned here: a `rewrite-target: /` annotation once collapsed `/api/*` to `/` — removed,
both apps serve their native paths.)

## HPA (autoscaling)

Backend scales on CPU: requests 100m, target 60%, min 2, max 6.

```
low traffic → 2 Pods → high CPU → 3 → 4 … → 6
```

```bash
kubectl get hpa -n taskboard
kubectl get hpa -n taskboard -w
./scripts/load-test.sh http://taskboard.local/api/tasks 500
```

Needs Metrics Server; a single `/health` won't move CPU — use the load script for the demo.

## Monitoring in detail

Prometheus scrapes FastAPI `/metrics` via the chart's ServiceMonitor (plus Pod annotations as
fallback). Install with `monitoring/prometheus-values.yaml` (kube-prometheus-stack) and
`monitoring/grafana-values.yaml`:

```bash
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f monitoring/prometheus-values.yaml
curl http://<backend>:8000/metrics   # HELP/TYPE exposition format
```

Grafana (`admin` / `taskboard-admin`) panels to build (queries in
`monitoring/grafana-dashboard-notes.yaml`):

1. RPS by handler: `sum(rate(http_requests_total[5m])) by (handler)`
2. p95 latency: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (handler, le))`
3. Error rate: `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`
4. CPU vs replicas: `container_cpu_usage_seconds_total{pod=~"taskboard-backend-.*"}` beside
   `kube_deployment_status_replicas{deployment="taskboard-backend"}`

These answer: request volume per endpoint, slowest endpoint, error growth, traffic presence, CPU
pressure, and whether HPA is responding.

## Troubleshooting lab in detail

Broken image (wrong tag):

```bash
kubectl apply -f troubleshooting/broken-image.yaml
kubectl get pods -n taskboard
kubectl describe pod <name> -n taskboard
kubectl get events --sort-by=.lastTimestamp -n taskboard
# ImagePullBackOff → describe shows bad image/tag → fix:
kubectl set image deployment/taskboard-backend backend=<correct-image> -n taskboard
```

Broken Service (selector matches nothing):

```bash
kubectl apply -f troubleshooting/broken-service.yaml
kubectl get svc,endpoints -n taskboard
kubectl get pods --show-labels -n taskboard
# No endpoints → selector labels match no Pods → fix selector.
# Lesson: Services select Pods by labels. No match = no endpoints = no traffic.
```

## Final demo script (15 steps)

1. Open the app (`:3000` or `taskboard.local`), create a task. 2. Swagger `/docs` CRUD. 3. Show
the Postgres `tasks` table. 4. Commit a small change. 5. Watch the Actions pipeline go green.
6. Show both SHA-tagged images. 7. Show the Trivy step log. 8. Show GHCR package pages.
9. Show `terraform/` VPC+EKS code. 10. `kubectl get pods,svc` all Running. 11. `helm list`.
12. Open the app via Ingress. 13. `kubectl get hpa`. 14. Prometheus Targets UP + Grafana panel.
15. Break a Service/image and fix it live.

## Configuration

| Variable | Default | Used by |
| -------- | ------- | ------- |
| `DATABASE_URL` | `postgresql+psycopg://taskboard:taskboard@localhost:5432/taskboard` | backend, Alembic |
| Backend | :8000 (Uvicorn; liveness `/health`, readiness `/ready`) | probes, HPA |
| Frontend | :8080 in container → :3000 on host | Nginx, Compose |
| Postgres | `taskboard/taskboard@postgres:5432/taskboard` | Compose, Helm |
| AWS region | `ap-south-1` | Terraform |
| Grafana | `admin` / `taskboard-admin` | monitoring values |

## Evidence screenshots

Each image below is stored under `submission/` and tagged with its module.

### M1 — running application

![M1 dashboard with tasks, filters and activity](submission/m1/Screenshot_2026-10-16_12-02-47.png)
*M1 — dashboard at `localhost:3000`: KPIs, status filter with search, task table, activity feed.*

![M1 full board across workspaces](submission/m1/Screenshot_2026-10-16_12-06-49.png)
*M1 — full board: 5 tasks across Platform Team / DevOps Capstone / Sprint 21 with badges.*

Additional M1 dashboard views: `submission/m1/Screenshot_2026-10-16_12-02-54.png`,
`submission/m1/Screenshot_2026-10-16_12-03-00.png`,
`submission/m1/Screenshot_2026-10-16_12-03-19.png`.

### M2 — pytest green

![M2 13 passed](submission/m2/backend/Screenshot_2026-10-16_12-13-05.png)
*M2 — `pytest -v`: 13 passed covering health, metrics, CRUD, stats and filters (isolated SQLite DB).*
Second angle: `submission/m2/backend/Screenshot_2026-10-16_12-13-12.png`.

### M3 — commit history

![M3 meaningful commits](submission/m3/Screenshot_2026-10-16_12-15-57.png)
*M3 — `git log --oneline`: 25+ meaningful `feat/fix/docs/test` commits, never "update".*

### M4 — Docker stack

![M4 compose up build](submission/m4/Screenshot_2026-10-16_13-02-50.png)
*M4 — `docker compose up --build`: postgres pulled, both images built, all containers created.*

![M4 app on localhost:3000](submission/m4/Screenshot_2026-10-16_13-08-15.png)
*M4 — dashboard served from the containerized stack at `localhost:3000`.*

### M5 — green pipeline and registry

![M5 green Actions run](submission/m5/Screenshot_2026-10-16_13-30-39.png)
*M5 — TaskBoard CI/CD run Success: Test, Build + Trivy scan + Push to GHCR, Deploy via Helm.*

![M5 GHCR SHA tags](submission/m5/Screenshot_2026-10-16_13-36-02.png)
*M5 — GHCR `taskboard-backend` package page: immutable commit-SHA tags, no `latest`.*

### M6 — Trivy gate

![M6 Trivy scan job](submission/m6/Screenshot_2026-10-16_13-37-31.png)
*M6 — Trivy scan steps passing on both images (`HIGH,CRITICAL`, actionable findings only).*
Written explanation: `submission/m6/explanation.txt`.

### M8 — app through Ingress

![M8 Ingress dashboard](submission/m9/Screenshot_2026-10-16_15-39-04.png)
*M8 — dashboard served through Ingress at `http://taskboard.local/` (stored under M9 folder).*

### M9 — observability

![M9 metrics endpoint](submission/m9/Screenshot_2026-10-16_15-54-39.png)
*M9 — `curl <backend>/metrics`: Prometheus exposition (`HELP`/`TYPE` + samples).*

![M9 Prometheus target UP](submission/m9/Screenshot_2026-10-16_15-57-34.png)
*M9 — Prometheus Targets: `serviceMonitor/taskboard/taskboard-backend/0`, 2/2 UP.*

Still to capture: Grafana dashboard panel with a live query (e.g.
`sum(rate(http_requests_total[5m])) by (handler)`) → save into `submission/m9/`.
Pending cluster shots: M7 (`terraform plan`, AWS console, `terraform destroy`) and M8
(`kubectl get pods/svc`, `helm list`) — captured during those live sessions.

## Quick start

### Option A: Docker Compose (fastest)
```bash
cd /home/harsha/Documents/devops/proj2
docker compose up --build
```
- App: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

Stop with `docker compose down`.

### Option B: Kubernetes (minikube)
```bash
# 1) Build images
docker build -t taskboard-backend:local ./backend
docker build -t taskboard-frontend:local ./frontend

# 2) Load into minikube
minikube image load taskboard-backend:local
minikube image load taskboard-frontend:local

# 3) Deploy with Helm
helm upgrade --install taskboard ./helm/taskboard -n taskboard --create-namespace \
  --set images.backend.repository=taskboard-backend --set images.backend.tag=local \
  --set images.frontend.repository=taskboard-frontend --set images.frontend.tag=local

# 4) Verify
kubectl get pods -n taskboard
# Wait until all pods are Running

# 5) Access via Ingress (add to /etc/hosts if needed)
echo "$(minikube ip) taskboard.local" | sudo tee -a /etc/hosts
# App: http://taskboard.local/
# API: http://taskboard.local/api/tasks/stats
```


