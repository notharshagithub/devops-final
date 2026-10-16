import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'

const STATUS_LABELS = { todo: 'To Do', in_progress: 'In Progress', done: 'Done' }

function badgeClass(kind, value) {
  return `badge badge-${kind}-${value.replace('_', '-')}`
}

function emptyForm() {
  return { title: '', description: '', status: 'todo', priority: 'medium', assignee: '' }
}

export default function App() {
  const [tasks, setTasks] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(emptyForm())
  const [saving, setSaving] = useState(false)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [tasksRes, statsRes] = await Promise.all([
        fetch('/api/tasks?limit=200'),
        fetch('/api/tasks/stats')
      ])
      if (!tasksRes.ok) throw new Error(`Tasks API failed: ${tasksRes.status}`)
      if (!statsRes.ok) throw new Error(`Stats API failed: ${statsRes.status}`)
      setTasks(await tasksRes.json())
      setStats(await statsRes.json())
    } catch (e) {
      setError('Backend unreachable. Start the stack with: docker compose up --build (backend :8000). ' + e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const filtered = useMemo(() => {
    return tasks.filter((t) => {
      if (statusFilter !== 'all' && t.status !== statusFilter) return false
      if (search && !(t.title + ' ' + (t.description || '')).toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [tasks, statusFilter, search])

  const activity = useMemo(() => tasks.slice(0, 6), [tasks])

  async function handleCreate(e) {
    e.preventDefault()
    if (!form.title.trim()) return
    setSaving(true)
    try {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, assignee: form.assignee || 'Unassigned' })
      })
      if (!res.ok) throw new Error(`Create failed: ${res.status}`)
      setShowModal(false)
      setForm(emptyForm())
      await fetchAll()
    } catch (err) {
      setError(String(err.message))
    } finally {
      setSaving(false)
    }
  }

  async function cycleStatus(task) {
    const order = ['todo', 'in_progress', 'done']
    const next = order[(order.indexOf(task.status) + 1) % order.length]
    await fetch(`/api/tasks/${task.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: next })
    })
    await fetchAll()
  }

  async function removeTask(id) {
    if (!confirm('Delete this task?')) return
    await fetch(`/api/tasks/${id}`, { method: 'DELETE' })
    await fetchAll()
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">◼ TaskBoard</div>
        <div className="ws-label">WORKSPACES</div>
        <nav className="ws-nav">
          {['Platform Team', 'DevOps Capstone', 'Sprint 21'].map((w, i) => (
            <button key={w} className={i === 1 ? 'ws active' : 'ws'}>{w}</button>
          ))}
        </nav>
        <div className="ws-label">PIPELINE</div>
        <div className="pipeline">
          {['Git push', 'pytest', 'Docker build', 'Trivy scan', 'GHCR push', 'Helm deploy'].map((s, i) => (
            <div key={s} className="pipe-step">
              <span className={i < 5 ? 'dot done' : 'dot pending'} />
              <span>{s}</span>
            </div>
          ))}
        </div>
        <div className="side-foot">Session 21 • DevOps Capstone</div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>Project Dashboard</h1>
            <p className="muted">Track delivery from laptop to Kubernetes</p>
          </div>
          <button className="primary" onClick={() => setShowModal(true)}>+ New Task</button>
        </header>

        <section className="kpis">
          {[
            { label: 'Total tasks', value: stats?.total ?? '—' },
            { label: 'To Do', value: stats?.todo ?? '—' },
            { label: 'In Progress', value: stats?.in_progress ?? '—' },
            { label: 'Done', value: stats?.done ?? '—' },
            { label: 'High priority', value: stats?.high_priority ?? '—' }
          ].map((k) => (
            <div key={k.label} className="kpi">
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-label">{k.label}</div>
            </div>
          ))}
        </section>

        <section className="toolbar">
          <div className="filters">
            {['all', 'todo', 'in_progress', 'done'].map((s) => (
              <button
                key={s}
                className={statusFilter === s ? 'chip active' : 'chip'}
                onClick={() => setStatusFilter(s)}
              >
                {s === 'all' ? 'All' : STATUS_LABELS[s]}
              </button>
            ))}
          </div>
          <input
            className="search"
            placeholder="Search tasks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </section>

        {loading && <div className="state">Loading tasks…</div>}
        {error && !loading && (
          <div className="state error">
            <strong>Backend error.</strong> {error}
            <div><button className="chip" onClick={fetchAll}>Retry</button></div>
          </div>
        )}

        {!loading && !error && (
          <div className="content-grid">
            <div className="table-wrap">
              <table className="tasks">
                <thead>
                  <tr><th>Task</th><th>Status</th><th>Priority</th><th>Assignee</th><th></th></tr>
                </thead>
                <tbody>
                  {filtered.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <div className="t-title">{t.title}</div>
                        <div className="t-desc">{t.description}</div>
                      </td>
                      <td><span className={badgeClass('status', t.status)}>{STATUS_LABELS[t.status]}</span></td>
                      <td><span className={badgeClass('priority', t.priority)}>{t.priority}</span></td>
                      <td className="muted">{t.assignee}</td>
                      <td className="row-actions">
                        <button title="Advance status" onClick={() => cycleStatus(t)}>▶</button>
                        <button title="Delete" onClick={() => removeTask(t.id)}>✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && <div className="state">No tasks match this filter.</div>}
            </div>

            <aside className="feed">
              <h3>Activity</h3>
              {activity.map((t) => (
                <div key={t.id} className="feed-item">
                  <span className={badgeClass('status', t.status)}>●</span>
                  <div>
                    <div className="feed-title">{t.title}</div>
                    <div className="muted small">{t.assignee} • #{t.id}</div>
                  </div>
                </div>
              ))}
              {activity.length === 0 && <div className="muted small">No activity yet.</div>}
            </aside>
          </div>
        )}

        {showModal && (
          <div className="modal-backdrop" onClick={() => setShowModal(false)}>
            <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleCreate}>
              <h2>Create task</h2>
              <label>Title<input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required maxLength={200} /></label>
              <label>Description<textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} /></label>
              <div className="form-row">
                <label>Status
                  <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                    <option value="todo">To Do</option>
                    <option value="in_progress">In Progress</option>
                    <option value="done">Done</option>
                  </select>
                </label>
                <label>Priority
                  <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </label>
              </div>
              <label>Assignee<input value={form.assignee} onChange={(e) => setForm({ ...form, assignee: e.target.value })} placeholder="Unassigned" /></label>
              <div className="modal-actions">
                <button type="button" className="chip" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="primary" disabled={saving}>{saving ? 'Saving…' : 'Create'}</button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  )
}
