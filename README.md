# TaskBoard — DevOps Final Capstone (Session 21)

Small but realistic SaaS-style project-management app showing how code travels
from laptop → GitHub Actions → GHCR → Terraform AWS VPC+EKS → Helm → monitored Kubernetes.

```
Developer → Git/GitHub → Actions (pytest → build → Trivy → GHCR push) → Terraform (VPC+EKS) → Helm (frontend+backend+postgres) → Ingress → HPA → Prometheus/Grafana
```

## Stack

- Frontend: React 18 + Vite, responsive SaaS dashboard (sidebar, KPIs, task table, filters, badges, activity feed, pipeline indicator, create-task modal, loading/error states). Calls `/api/tasks` + `/api/tasks/stats`; Nginx proxies `/api`, `/health`, `/ready`, `/docs` to backend so the browser never needs the internal hostname.
- Backend: FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL. Endpoints: `GET /`, `GET /health` (liveness), `GET /ready` (readiness w/ DB check), `GET /metrics` (Prometheus), `GET/POST /api/tasks`, `GET/PUT/DELETE /api/tasks/{id}`, `GET /api/tasks/stats`. Docs at `/docs`.
- Tests: pytest, 11 tests, isolated SQLite test DB (never production Postgres).
- Docker: backend `python:3.12-slim` non-root `appuser`, runs `alembic upgrade head` then Uvicorn; frontend multi-stage Node build → `nginx-unprivileged` runtime. `docker compose up --build` starts postgres+backend+frontend.
- CI/CD: `.github/workflows/ci.yml` — TEST (pytest + frontend build) → BUILD+SCAN+PUSH (Docker both, Trivy HIGH,CRITICAL fail, push GHCR with commit-SHA tags) → DEPLOY (`helm upgrade --install`). Triggers on push to `main`.
- Security (Trivy): scans both images for HIGH/CRITICAL CVEs and fails the pipeline (`exit-code: 1`). Trivy is container scanning — one layer alongside SAST, dependency/secret scanning, runtime security. A clean scan means no known HIGH/CRITICAL CVEs in OS + language packages at scan time; a finding means fix base image / bump dep / rebuild.
- Terraform (`terraform/`, default `ap-south-1`): VPC (3 public + 3 private subnets, NAT), EKS 1.30 + managed node group. `terraform init/plan/apply/destroy`. For prod DB prefer RDS over in-cluster Postgres (tradeoff: managed backups/HA vs demo simplicity).
- Kubernetes + Helm (`k8s/namespace.yaml`, `helm/taskboard`): backend/frontend Deployments (2 replicas each), ClusterIP Services, in-cluster Postgres + PVC (demo), Ingress (`/` → frontend, `/api` → backend), HPA (backend CPU 60%, 2–6 replicas), ServiceMonitor.
- Observability (`monitoring/`): FastAPI `/metrics` → Prometheus `ServiceMonitor` → Grafana panels (RPS, p95 latency, error rate, CPU vs HPA).
- Troubleshooting (`troubleshooting/`): broken-image (ImagePullBackOff) + broken-service (no endpoints — label mismatch) labs. Load gen: `scripts/load-test.sh`.

## Run locally (fastest)

```bash
docker compose up --build
# frontend http://localhost:3000  backend http://localhost:8000/docs  health http://localhost:8000/health  metrics http://localhost:8000/metrics
docker compose down -v  # also deletes DB volume
```

Backend directly:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://taskboard:taskboard@localhost:5432/taskboard'
alembic upgrade head
uvicorn app.main:app --reload --port 8000
pytest -q
```

## Kubernetes (minikube or EKS)

```bash
kubectl apply -f k8s/namespace.yaml
helm upgrade --install taskboard ./helm/taskboard -n taskboard --create-namespace -f helm/taskboard/values-dev.yaml
kubectl get pods,svc,hpa,ingress -n taskboard
# Ingress host: taskboard.local (add to /etc/hosts for minikube/dev)
./scripts/load-test.sh http://taskboard.local/api/tasks 500
kubectl get hpa -n taskboard -w
```

Troubleshooting labs:

```bash
kubectl apply -f troubleshooting/broken-image.yaml
kubectl get pods -n taskboard; kubectl describe pod <name>; kubectl get events --sort-by=.lastTimestamp -n taskboard
kubectl apply -f troubleshooting/broken-service.yaml
kubectl get svc,endpoints -n taskboard; kubectl get pods --show-labels -n taskboard
```

## Terraform AWS

```bash
cd terraform
terraform init
terraform plan   # needs AWS creds via aws configure; no keys in repo
terraform apply
aws eks update-kubeconfig --region ap-south-1 --name taskboard-eks
terraform destroy  # required after evaluation to avoid costs
```

## Git (when ready)

```bash
git init
git add .
git commit -m "feat: TaskBoard capstone - FastAPI + React + Postgres + K8s"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO>
git push -u origin main
```

## Repo map (matches Session 21 spec)

`frontend/`, `backend/app/`, `backend/tests/`, `backend/alembic/`, `docker-compose.yml`, `terraform/`, `helm/taskboard/`, `k8s/`, `monitoring/`, `troubleshooting/`, `scripts/`, `.github/workflows/`
