"""Excel/CSV multi-sheet import endpoints.

Workflow:
  1. POST /imports/preview — upload file, get parsed payload + row errors (no DB write).
  2. POST /imports/commit  — apply payload in a single transaction, idempotent by import_id.
  3. GET  /imports/template — download the 4-sheet example workbook.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import UserPrincipal, get_current_user
from app.models.basis import BasisForward
from app.models.cbot import CBOTDerivative
from app.models.enums import PositionStatus
from app.models.events import TradeEvent
from app.models.fx import FXDerivative
from app.models.physical import PhysicalFixation, PhysicalFrame
from app.services.events import log_trade_event
from app.services.imports import (
    ImportPayload,
    parse_workbook,
)

router = APIRouter(prefix="/imports", tags=["imports"])


class ImportPreviewResponse(BaseModel):
    rows_by_sheet: dict[str, int]
    errors: list[dict[str, Any]]
    valid_count: int
    invalid_count: int


class ImportCommitResponse(BaseModel):
    status: str
    import_id: UUID
    inserted: dict[str, int]


def _detail(title: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    body: dict[str, object] = {"type": "about:blank", "title": title}
    if extra:
        body.update(extra)
    return body


async def _already_applied(session: AsyncSession, import_id: UUID) -> bool:
    stmt = (
        select(TradeEvent)
        .where(
            TradeEvent.event_type == "open",
            TradeEvent.payload["import_id"].as_string() == str(import_id),
        )
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return row is not None


def _payload_to_preview(payload: ImportPayload) -> ImportPreviewResponse:
    return ImportPreviewResponse(
        rows_by_sheet={
            "physical_frames": len(payload.frames),
            "physical_fixations": len(payload.fixations),
            "cbot": len(payload.cbot),
            "basis": len(payload.basis),
            "fx": len(payload.fx),
        },
        errors=[
            {"sheet": e.sheet, "row_index": e.row_index, "errors": e.errors} for e in payload.errors
        ],
        valid_count=payload.valid_count,
        invalid_count=payload.invalid_count,
    )


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    file: Annotated[UploadFile, File(...)],
) -> ImportPreviewResponse:
    content = await file.read()
    payload = parse_workbook(content)
    return _payload_to_preview(payload)


@router.post(
    "/commit",
    response_model=ImportCommitResponse,
    status_code=status.HTTP_200_OK,
)
async def commit_import(
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    import_id: Annotated[UUID, ...],
    file: Annotated[UploadFile, File(...)],
) -> ImportCommitResponse:
    # Idempotency: if this import_id has already been applied, short-circuit.
    if await _already_applied(session, import_id):
        return ImportCommitResponse(
            status="already_applied",
            import_id=import_id,
            inserted={"frames": 0, "fixations": 0, "cbot": 0, "basis": 0, "fx": 0},
        )

    content = await file.read()
    payload = parse_workbook(content)

    if payload.errors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail(
                "import has row errors",
                {
                    "errors": [
                        {"sheet": e.sheet, "row_index": e.row_index, "errors": e.errors}
                        for e in payload.errors
                    ]
                },
            ),
        )

    frame_ref_to_id: dict[str, UUID] = {}
    inserted = {"frames": 0, "fixations": 0, "cbot": 0, "basis": 0, "fx": 0}

    try:
        # 1. Frames first so fixations can resolve their parent by frame_ref.
        for ref, fr_in in payload.frames:
            frame = PhysicalFrame(
                user_id=principal.id,
                commodity=fr_in.commodity,
                side=fr_in.side,
                quantity_tons=fr_in.quantity_tons,
                delivery_start=fr_in.delivery_start,
                delivery_end=fr_in.delivery_end,
                counterparty=fr_in.counterparty,
                notes=fr_in.notes,
                status=PositionStatus.OPEN,
            )
            session.add(frame)
            await session.flush()
            if ref:
                frame_ref_to_id[ref] = frame.id
            await log_trade_event(
                session,
                user_id=principal.id,
                event_type="open",
                instrument_table="physical_frames",
                instrument_id=frame.id,
                quantity=frame.quantity_tons,
                payload={"import_id": str(import_id), "source": "excel"},
            )
            inserted["frames"] += 1

        # 2. Fixations — need a resolved frame_id.
        for parsed in payload.fixations:
            if parsed.frame_ref is None or parsed.frame_ref not in frame_ref_to_id:
                raise ValueError(f"fixation references unknown frame_ref={parsed.frame_ref!r}")
            fx = PhysicalFixation(
                frame_id=frame_ref_to_id[parsed.frame_ref],
                fixation_mode=parsed.fixation.fixation_mode,
                quantity_tons=parsed.fixation.quantity_tons,
                fixation_date=parsed.fixation.fixation_date,
                cbot_fixed=parsed.fixation.cbot_fixed,
                basis_fixed=parsed.fixation.basis_fixed,
                fx_fixed=parsed.fixation.fx_fixed,
                reference_cbot_contract=parsed.fixation.reference_cbot_contract,
                notes=parsed.fixation.notes,
            )
            session.add(fx)
            await session.flush()
            await log_trade_event(
                session,
                user_id=principal.id,
                event_type="fill",
                instrument_table="physical_frames",
                instrument_id=frame_ref_to_id[parsed.frame_ref],
                quantity=fx.quantity_tons,
                payload={
                    "import_id": str(import_id),
                    "source": "excel",
                    "fixation_id": str(fx.id),
                    "mode": fx.fixation_mode.value,
                },
            )
            inserted["fixations"] += 1

        # 3. CBOT
        for cin in payload.cbot:
            row = CBOTDerivative(
                user_id=principal.id,
                commodity=cin.commodity,
                instrument=cin.instrument,
                side=cin.side,
                contract=cin.contract,
                quantity_contracts=cin.quantity_contracts,
                trade_date=cin.trade_date,
                trade_price=cin.trade_price,
                maturity_date=cin.maturity_date,
                option_type=cin.option_type,
                strike=cin.strike,
                barrier_type=cin.barrier_type,
                barrier_level=cin.barrier_level,
                rebate=cin.rebate,
                counterparty=cin.counterparty,
                notes=cin.notes,
                status=PositionStatus.OPEN,
            )
            session.add(row)
            await session.flush()
            await log_trade_event(
                session,
                user_id=principal.id,
                event_type="open",
                instrument_table="cbot_derivatives",
                instrument_id=row.id,
                quantity=row.quantity_contracts,
                price=row.trade_price,
                payload={"import_id": str(import_id), "source": "excel"},
            )
            inserted["cbot"] += 1

        # 4. Basis
        for bin_ in payload.basis:
            row_b = BasisForward(
                user_id=principal.id,
                commodity=bin_.commodity,
                side=bin_.side,
                quantity_tons=bin_.quantity_tons,
                trade_date=bin_.trade_date,
                basis_price=bin_.basis_price,
                delivery_date=bin_.delivery_date,
                reference_cbot_contract=bin_.reference_cbot_contract,
                counterparty=bin_.counterparty,
                notes=bin_.notes,
                status=PositionStatus.OPEN,
            )
            session.add(row_b)
            await session.flush()
            await log_trade_event(
                session,
                user_id=principal.id,
                event_type="open",
                instrument_table="basis_forwards",
                instrument_id=row_b.id,
                quantity=row_b.quantity_tons,
                price=row_b.basis_price,
                payload={"import_id": str(import_id), "source": "excel"},
            )
            inserted["basis"] += 1

        # 5. FX
        for fx_in in payload.fx:
            row_f = FXDerivative(
                user_id=principal.id,
                instrument=fx_in.instrument,
                side=fx_in.side,
                notional_usd=fx_in.notional_usd,
                trade_date=fx_in.trade_date,
                trade_rate=fx_in.trade_rate,
                maturity_date=fx_in.maturity_date,
                option_type=fx_in.option_type,
                strike=fx_in.strike,
                barrier_type=fx_in.barrier_type,
                barrier_level=fx_in.barrier_level,
                rebate=fx_in.rebate,
                counterparty=fx_in.counterparty,
                notes=fx_in.notes,
                status=PositionStatus.OPEN,
            )
            session.add(row_f)
            await session.flush()
            await log_trade_event(
                session,
                user_id=principal.id,
                event_type="open",
                instrument_table="fx_derivatives",
                instrument_id=row_f.id,
                quantity=row_f.notional_usd,
                price=row_f.trade_rate,
                payload={"import_id": str(import_id), "source": "excel"},
            )
            inserted["fx"] += 1

        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail("import commit failed", {"error": str(exc)}),
        ) from exc

    return ImportCommitResponse(status="committed", import_id=import_id, inserted=inserted)


_TEMPLATE_PATH = Path(__file__).resolve().parents[4] / "docs" / "example_import.xlsx"


@router.get("/template")
async def download_template() -> FileResponse:
    """Download the 4-sheet example workbook. Unauthenticated for convenience."""
    if not _TEMPLATE_PATH.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=_detail(
                "template missing",
                {"hint": "run `uv run python scripts/generate_import_template.py`"},
            ),
        )
    return FileResponse(
        _TEMPLATE_PATH,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="example_import.xlsx",
    )
