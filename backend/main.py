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
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agent.tenant import AgentState, approve_agent, start_agent
from backend.llm.provider import chat
from backend.models import AnswerRequest, ApprovalRequest, RunRequest, RunResponse
from backend.tools.agreement import read_agreement

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Dhara AI", description="Agentic tenancy copilot for Karnataka")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["GET", "POST"], allow_headers=["*"])

RUNS: dict[str, AgentState] = {}
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
    start_agent(state)
    LOGGER.info("run %s status=%s tool_calls=%s", state.id, state.status, state.tool_calls)


@app.post("/api/runs", response_model=RunResponse)
def create_run(request: RunRequest, background: BackgroundTasks) -> RunResponse:
    agreement = _agreement(request)
    state = AgentState(str(uuid.uuid4()), agreement["clauses"], request.facts.model_dump(), request.language, provider_chat)
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
    state.facts.update(request.facts)
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
