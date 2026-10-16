"""Task CRUD + stats tests: covers POST, GET, PUT, DELETE, stats."""


def _create(client, **overrides):
    payload = {
        "title": "Write docs",
        "description": "API documentation",
        "status": "todo",
        "priority": "high",
        "assignee": "Harsha",
        "workspace": "DevOps Capstone",
    }
    payload.update(overrides)
    r = client.post("/api/tasks", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_task(client):
    task = _create(client)
    assert task["id"] >= 1
    assert task["title"] == "Write docs"
    assert task["priority"] == "high"
    assert task["workspace"] == "DevOps Capstone"


def test_list_tasks(client):
    _create(client, title="Task A")
    _create(client, title="Task B")
    r = client.get("/api/tasks")
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_get_task_by_id(client):
    created = _create(client)
    r = client.get(f"/api/tasks/{created['id']}")
    assert r.status_code == 200
    assert r.json()["title"] == "Write docs"


def test_get_missing_task_404(client):
    r = client.get("/api/tasks/99999")
    assert r.status_code == 404


def test_update_task(client):
    created = _create(client)
    r = client.put(f"/api/tasks/{created['id']}", json={"status": "done"})
    assert r.status_code == 200
    assert r.json()["status"] == "done"


def test_delete_task(client):
    created = _create(client)
    r = client.delete(f"/api/tasks/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/tasks/{created['id']}").status_code == 404


def test_stats_counts(client):
    _create(client, status="todo", priority="high")
    _create(client, status="done", priority="low")
    r = client.get("/api/tasks/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert body["todo"] >= 1
    assert body["done"] >= 1
    assert body["high_priority"] >= 1


def test_list_filter_by_status(client):
    _create(client, title="Only todo", status="todo")
    _create(client, title="Only done", status="done")
    r = client.get("/api/tasks", params={"status": "done"})
    assert r.status_code == 200
    assert all(t["status"] == "done" for t in r.json())


def test_list_filter_by_workspace(client):
    _create(client, title="Platform work", workspace="Platform Team")
    _create(client, title="Sprint work", workspace="Sprint 21")
    r = client.get("/api/tasks", params={"workspace": "Platform Team"})
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert all(t["workspace"] == "Platform Team" for t in r.json())


def test_update_task_workspace(client):
    created = _create(client)
    r = client.put(f"/api/tasks/{created['id']}", json={"workspace": "Sprint 21"})
    assert r.status_code == 200
    assert r.json()["workspace"] == "Sprint 21"
