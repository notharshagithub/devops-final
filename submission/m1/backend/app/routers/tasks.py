"""Task CRUD + stats endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get_task_or_404(task_id: int, db: Session) -> models.Task:
    task = db.get(models.Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("", response_model=List[schemas.TaskResponse])
def list_tasks(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    priority: Optional[str] = Query(default=None),
    workspace: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List tasks with optional filters."""
    stmt = select(models.Task).order_by(models.Task.id.desc())
    if status_filter:
        stmt = stmt.where(models.Task.status == status_filter)
    if priority:
        stmt = stmt.where(models.Task.priority == priority)
    if workspace:
        stmt = stmt.where(models.Task.workspace == workspace)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(models.Task.title.ilike(like), models.Task.description.ilike(like))
        )
    stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


@router.get("/stats", response_model=schemas.StatsResponse)
def task_stats(db: Session = Depends(get_db)):
    """Aggregate counts for dashboard KPI cards."""
    total = db.scalar(select(func.count()).select_from(models.Task)) or 0
    todo = db.scalar(select(func.count()).select_from(models.Task).where(models.Task.status == "todo")) or 0
    in_progress = (
        db.scalar(
            select(func.count()).select_from(models.Task).where(models.Task.status == "in_progress")
        )
        or 0
    )
    done = db.scalar(select(func.count()).select_from(models.Task).where(models.Task.status == "done")) or 0
    high_priority = (
        db.scalar(
            select(func.count()).select_from(models.Task).where(models.Task.priority == "high")
        )
        or 0
    )
    return {
        "total": total,
        "todo": todo,
        "in_progress": in_progress,
        "done": done,
        "high_priority": high_priority,
    }


@router.get("/{task_id}", response_model=schemas.TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return _get_task_or_404(task_id, db)


@router.post("", response_model=schemas.TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    task = models.Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=schemas.TaskResponse)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = _get_task_or_404(task_id, db)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = _get_task_or_404(task_id, db)
    db.delete(task)
    db.commit()
    return None
