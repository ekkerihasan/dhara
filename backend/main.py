"""FastAPI app for Flow 1: start a review, answer the agent's question, approve the draft.

Runs live in memory, keyed by run id; uploaded documents are never written to disk.
The agent runs in the background after each request returns, so the frontend polls
GET /api/runs/{id} and watches the trace fill in.

    uvicorn backend.main:app --port 8000
"""
from __future__ import annotations

import base64
import binascii
import logging
import uuid
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agent.moveout import MoveoutState, approve_moveout, start_moveout
from backend.agent.baseline import start_baseline
from backend.agent.landlord import (NegotiationMessage, NegotiationRequest, NegotiationResponse,
    NegotiationState, advance_landlord, new_negotiation, prepare_message)
from backend.agent.tenant import AgentState, approve_agent, start_agent
from backend.llm.provider import chat
from backend.models import AnswerRequest, ApprovalRequest, MoveoutRequest, RunRequest, RunResponse
from backend.tools.agreement import read_agreement
from backend.ocr_api import router as ocr_router

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Dhara AI", description="Agentic tenancy copilot for Karnataka")
app.include_router(ocr_router)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["GET", "POST"], allow_headers=["*"])

RUNS: dict[str, AgentState] = {}
MOVEOUTS: dict[str, MoveoutState] = {}
provider_chat = chat  # replaced by a fake model in tests


def _agreement(request: RunRequest) -> dict[str, Any]:
    """Read the agreement from pasted text or a base64 PDF, kept in memory only."""
    if request.pdf_base64:
        try:
            document: bytes | str = base64.b64decode(request.pdf_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(400, "pdf_base64 is not valid base64") from exc
    elif request.agreement_text:
        document = request.agreement_text
    else:
        raise HTTPException(400, "Provide agreement_text or pdf_base64")
    try:
        return read_agreement(document)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _run(run_id: str) -> AgentState:
    state = RUNS.get(run_id)
    if state is None:
        raise HTTPException(404, f"No run {run_id}")
    return state


def _advance(state: AgentState) -> None:
    """Run the agent until it needs the tenant again (background task)."""
    if state.mode == "baseline":
        start_baseline(state)
    else:
        start_agent(state)
    LOGGER.info("run %s status=%s tool_calls=%s", state.id, state.status, state.tool_calls)


@app.post("/api/runs", response_model=RunResponse)
def create_run(request: RunRequest, background: BackgroundTasks,
               mode: Literal["agent", "baseline"] = "agent") -> RunResponse:
    agreement = _agreement(request)
    state = AgentState(str(uuid.uuid4()), agreement["clauses"], request.facts.model_dump(), request.language, provider_chat)
    state.mode = mode
    state.add_trace("tool_call", "read_agreement", tool="read_agreement",
                    inputs={"source": "pdf" if request.pdf_base64 else "text"},
                    output={"clauses": len(agreement["clauses"]), "redactions": agreement["redactions"]})
    RUNS[state.id] = state
    background.add_task(_advance, state)
    return state.response()


@app.get("/api/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    return _run(run_id).response()


@app.post("/api/runs/{run_id}/answer", response_model=RunResponse)
def answer(run_id: str, request: AnswerRequest, background: BackgroundTasks) -> RunResponse:
    state = _run(run_id)
    if state.status != "needs_input":
        raise HTTPException(409, "This run is not waiting for an answer")
    # A null value means the tenant does not know; the agent then proceeds with the law unresolved.
    state.unknown_facts.update(key for key, value in request.facts.items() if value is None)
    state.facts.update({key: value for key, value in request.facts.items() if value is not None})
    state.status = "running"
    background.add_task(_advance, state)
    return state.response()


@app.post("/api/runs/{run_id}/approve", response_model=RunResponse)
def approve(run_id: str, request: ApprovalRequest) -> RunResponse:
    state = _run(run_id)
    if not request.approved:
        raise HTTPException(400, "Approval must be explicit: send approved true")
    try:
        return approve_agent(state)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


# ---------- Flow 2: move-out ----------

def _moveout(review_id: str) -> MoveoutState:
    state = MOVEOUTS.get(review_id)
    if state is None:
        raise HTTPException(404, f"No move-out review {review_id}")
    return state


@app.post("/api/moveout")
def create_moveout(request: MoveoutRequest, background: BackgroundTasks) -> dict[str, Any]:
    try:
        clauses = read_agreement(request.agreement_text)["clauses"]
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    deductions = [{"id": f"D{i}", **d.model_dump()} for i, d in enumerate(request.deductions, start=1)]
    state = MoveoutState(str(uuid.uuid4()), clauses, [e.model_dump() for e in request.checklist], deductions,
                         request.facts.model_dump(), request.language, provider_chat)
    MOVEOUTS[state.id] = state
    background.add_task(start_moveout, state)
    return state.response()


@app.get("/api/moveout/{review_id}")
def get_moveout(review_id: str) -> dict[str, Any]:
    return _moveout(review_id).response()


@app.post("/api/moveout/{review_id}/approve")
def approve_moveout_review(review_id: str, request: ApprovalRequest) -> dict[str, Any]:
    state = _moveout(review_id)
    if not request.approved:
        raise HTTPException(400, "Approval must be explicit: send approved true")
    try:
        return approve_moveout(state)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


# ---------- Stretch: simulated landlord negotiation ----------
NEGOTIATIONS: dict[str, NegotiationState] = {}


def _negotiation(negotiation_id: str) -> NegotiationState:
    state = NEGOTIATIONS.get(negotiation_id)
    if state is None:
        raise HTTPException(404, "No negotiation with this id")
    return state


@app.post("/api/negotiations", response_model=NegotiationResponse)
def create_negotiation(request: NegotiationRequest, background: BackgroundTasks) -> NegotiationResponse:
    try:
        state = new_negotiation(str(uuid.uuid4()), request, provider_chat)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    NEGOTIATIONS[state.id] = state
    background.add_task(advance_landlord, state)
    return state.response()


@app.get("/api/negotiations/{negotiation_id}", response_model=NegotiationResponse)
def get_negotiation(negotiation_id: str) -> NegotiationResponse:
    return _negotiation(negotiation_id).response()


@app.post("/api/negotiations/{negotiation_id}/message", response_model=NegotiationResponse)
def negotiation_message(negotiation_id: str, request: NegotiationMessage,
                        background: BackgroundTasks) -> NegotiationResponse:
    state = _negotiation(negotiation_id)
    if not request.approved:
        raise HTTPException(400, "Explicit approval is required for each tenant proposal")
    try:
        prepare_message(state, request)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    background.add_task(advance_landlord, state)
    return state.response()
