"""Agreed MVP Agent HTTP API."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from fileforge.agent.service import TaskConflict, TaskService

router = APIRouter(prefix="/api/agent/tasks")
_service = TaskService()
_running: set[asyncio.Task] = set()


def get_service() -> TaskService:
    return _service


async def _body(request: Request, fields: set[str]) -> dict[str, str]:
    try:
        data = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    if (
        not isinstance(data, dict)
        or set(data) != fields
        or any(
            not isinstance(data[key], str) or not data[key].strip() for key in fields
        )
    ):
        raise HTTPException(status_code=400, detail="Invalid Agent request fields")
    return data


async def _approve_body(request: Request) -> dict:
    """Accept only the Package risk flag added to the existing approval body."""
    try:
        data = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    if (
        type(data) is not dict
        or set(data) - {"preview_id", "accept_incomplete"}
        or type(data.get("preview_id")) is not str
        or not data["preview_id"].strip()
        or ("accept_incomplete" in data and type(data["accept_incomplete"]) is not bool)
    ):
        raise HTTPException(status_code=400, detail="Invalid Agent request fields")
    return data


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.post("", status_code=202)
async def create_task(
    request: Request, service: TaskService = Depends(get_service)
) -> dict:
    data = await _body(request, {"user_goal", "workspace"})
    try:
        task = service.create(data["user_goal"], data["workspace"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not create task") from exc
    job = asyncio.create_task(asyncio.to_thread(service.run, task["task_id"]))
    _running.add(job)
    job.add_done_callback(_running.discard)
    return task


@router.get("/{task_id}")
async def get_task(task_id: str, service: TaskService = Depends(get_service)) -> dict:
    try:
        return service.snapshot(task_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/{task_id}/approve")
async def approve_task(
    task_id: str,
    request: Request,
    service: TaskService = Depends(get_service),
) -> dict:
    data = await _approve_body(request)
    try:
        return await asyncio.to_thread(
            service.decide,
            task_id,
            data["preview_id"],
            approve=True,
            accept_incomplete=data.get("accept_incomplete", False),
        )
    except KeyError as exc:
        raise _not_found(exc) from exc
    except TaskConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/reject")
async def reject_task(
    task_id: str,
    request: Request,
    service: TaskService = Depends(get_service),
) -> dict:
    data = await _body(request, {"preview_id"})
    try:
        return service.decide(task_id, data["preview_id"], approve=False)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except TaskConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{task_id}/report")
async def get_report(task_id: str, service: TaskService = Depends(get_service)) -> dict:
    try:
        return service.report(task_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except TaskConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
