# M1 — Application: Frontend + Backend + Database (10 points)

Copies of the exact files the rubric asks for. All copies verified identical to the live
project files (see verification log in chat).

## Contents

| Rubric item | Copy location |
| ----------- | ------------- |
| `backend/app/` — models, schemas, routes, database config | `backend/app/` |
| `backend/alembic/versions/` — migration files | `backend/alembic/versions/` (`0001_create_tasks.py`, `0002_add_workspace.py`) |
| `backend/requirements.txt` | `backend/requirements.txt` |
| `frontend/` — all frontend source files | `frontend/` (src, index.html, vite.config.js, nginx.conf, package.json) |
| `docker-compose.yml` — working stack definition | `docker-compose.yml` |

## Grading criteria covered

- [x] FastAPI backend starts and responds to `/health` (2) — verified live `{"status":"UP"}`
- [x] 4+ REST endpoints GET/POST/PUT/DELETE (3) — 6 task routes + stats
- [x] PostgreSQL + Alembic table (2) — `tasks` table, version `0002_add_workspace`
- [x] React frontend renders + API calls (2) — `:3000` HTTP 200, 5 API call sites
- [x] Responsive usable UI (1) — sidebar/KPIs/table/modal + `@media` breakpoint

## Screenshots (add here)

Drop your files in this folder with these names:

1. `screenshot-app-browser.png` — running application in the browser (`http://localhost:3000`)
   (or `recording-app-demo.mp4` — short screen recording instead)
