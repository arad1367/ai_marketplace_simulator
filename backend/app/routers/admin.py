"""Admin-only endpoints: list runs and stream raw-log CSV exports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..auth import AuthenticatedUser, require_admin
from ..csv_export import iter_csv
from ..database import SupabaseNotConfiguredError
from ..schemas import RunListItem
from ..services import (
    fetch_recent_runs,
    fetch_run_record,
    iter_log_rows,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/runs", response_model=list[RunListItem])
async def list_runs(
    _admin: AuthenticatedUser = Depends(require_admin),
) -> list[RunListItem]:
    """Return recent runs for the admin dashboard."""
    try:
        rows = fetch_recent_runs(limit=200)
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return [RunListItem(**row) for row in rows]


@router.get("/download-all-csv")
async def download_all_csv(
    _admin: AuthenticatedUser = Depends(require_admin),
) -> StreamingResponse:
    """Stream **every** run's logs as one combined CSV (admin only).

    This is the single, unified research dataset: all runs across all users in
    one file, with the ``run_id`` column distinguishing them. Rows are streamed
    page-by-page so the export scales to very large datasets.
    """
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"all_simulation_logs_{stamp}.csv"
    return StreamingResponse(
        iter_csv(iter_log_rows(None)),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/run/{run_id}/download-csv")
async def download_csv(
    run_id: str,
    _admin: AuthenticatedUser = Depends(require_admin),
) -> StreamingResponse:
    """Stream all raw log rows for a single run as a CSV download (admin only)."""
    record = fetch_run_record(run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found."
        )

    filename = f"{run_id}_logs.csv"
    return StreamingResponse(
        iter_csv(iter_log_rows(run_id)),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
