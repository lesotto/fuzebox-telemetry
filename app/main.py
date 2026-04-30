"""FuzeBox Telemetry & Execution Intelligence — single-process deploy.

Combines:
  * the v1 API (POST /v1/...)
  * a server-rendered HTML dashboard at /
  * an "Open in Swagger" docs view at /docs
  * a "/seed" endpoint that loads sample data so reviewers can poke around
    without writing any client code
"""

from __future__ import annotations

import logging
import os
import random
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session

from .db import (
    Execution,
    HumanStep,
    ModelCall,
    SkillInvocation,
    ToolCall,
    UEFDecision,
    get_db,
    init_db,
)
from .schemas import (
    HumanStepRequest,
    ModelCallRequest,
    OutcomeRequest,
    SkillRequest,
    StartExecutionRequest,
    ToolCallRequest,
    UEFDecisionRequest,
)
from .scoring import decide_execution, execution_roi, skill_efficiency

logger = logging.getLogger("fuzebox.api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))

app = FastAPI(
    title="FuzeBox Telemetry & UEF API",
    version="1.0.0",
    description="LiteLLM measures the model call. FuzeBox measures the work.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    logger.info("FuzeBox API ready")


def verify_key(x_fuzebox_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("FUZEBOX_API_KEY", "")
    # Open access by default in this hosted demo so reviewers can use curl freely.
    if not expected:
        return
    if x_fuzebox_key != expected:
        raise HTTPException(status_code=401, detail="Invalid FuzeBox API key")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "version": app.version, "ts": datetime.utcnow().isoformat()}


# =========================================================================== #
# v1 API                                                                      #
# =========================================================================== #
@app.post("/v1/executions/start")
def start_execution(payload: StartExecutionRequest, db: Session = Depends(get_db), _=Depends(verify_key)):
    existing = db.get(Execution, payload.execution_id)
    if existing:
        return {"execution_id": existing.execution_id, "status": "already_exists"}
    data = payload.model_dump(exclude={"metadata"})
    db.add(Execution(metadata_json=payload.metadata, **data))
    db.commit()
    return {"execution_id": payload.execution_id, "status": "started"}


@app.post("/v1/executions/{execution_id}/model-call")
def record_model_call(execution_id: str, payload: ModelCallRequest, db: Session = Depends(get_db), _=Depends(verify_key)):
    e = db.get(Execution, execution_id)
    if not e:
        raise HTTPException(404, "execution not found")
    call = ModelCall(
        id=f"mc_{uuid.uuid4().hex}",
        execution_id=execution_id,
        tenant_id=e.tenant_id,
        metadata_json=payload.metadata,
        **payload.model_dump(exclude={"metadata"}),
    )
    db.add(call)
    e.model_provider = payload.model_provider or e.model_provider
    e.model_name = payload.model_name or e.model_name
    e.cost_usd = (e.cost_usd or 0) + (payload.cost_usd or 0)
    e.latency_ms = (e.latency_ms or 0) + (payload.latency_ms or 0)
    e.prompt_tokens = (e.prompt_tokens or 0) + (payload.prompt_tokens or 0)
    e.completion_tokens = (e.completion_tokens or 0) + (payload.completion_tokens or 0)
    e.total_tokens = (e.total_tokens or 0) + (payload.total_tokens or 0)
    db.commit()
    return {"status": "recorded", "model_call_id": call.id}


@app.post("/v1/executions/{execution_id}/tool-call")
def record_tool_call(execution_id: str, payload: ToolCallRequest, db: Session = Depends(get_db), _=Depends(verify_key)):
    e = db.get(Execution, execution_id)
    if not e:
        raise HTTPException(404, "execution not found")
    call = ToolCall(
        id=f"tc_{uuid.uuid4().hex}",
        execution_id=execution_id,
        tenant_id=e.tenant_id,
        metadata_json=payload.metadata,
        **payload.model_dump(exclude={"metadata"}),
    )
    db.add(call)
    db.commit()
    return {"status": "recorded", "tool_call_id": call.id}


@app.post("/v1/executions/{execution_id}/human-step")
def record_human_step(execution_id: str, payload: HumanStepRequest, db: Session = Depends(get_db), _=Depends(verify_key)):
    e = db.get(Execution, execution_id)
    if not e:
        raise HTTPException(404, "execution not found")
    step = HumanStep(
        id=f"hs_{uuid.uuid4().hex}",
        execution_id=execution_id,
        tenant_id=e.tenant_id,
        metadata_json=payload.metadata,
        **payload.model_dump(exclude={"metadata"}),
    )
    db.add(step)
    e.human_intervention = True
    db.commit()
    return {"status": "recorded", "human_step_id": step.id}


@app.post("/v1/executions/{execution_id}/skill")
def record_skill(execution_id: str, payload: SkillRequest, db: Session = Depends(get_db), _=Depends(verify_key)):
    e = db.get(Execution, execution_id)
    if not e:
        raise HTTPException(404, "execution not found")
    inv = SkillInvocation(
        id=f"si_{uuid.uuid4().hex}",
        execution_id=execution_id,
        tenant_id=e.tenant_id,
        metadata_json=payload.metadata,
        **payload.model_dump(exclude={"metadata"}),
    )
    db.add(inv)
    if not e.skill_id:
        e.skill_id = payload.skill_id
    db.commit()
    return {"status": "recorded", "skill_invocation_id": inv.id}


@app.post("/v1/executions/{execution_id}/outcome")
def record_outcome(execution_id: str, payload: OutcomeRequest, db: Session = Depends(get_db), _=Depends(verify_key)):
    e = db.get(Execution, execution_id)
    if not e:
        raise HTTPException(404, "execution not found")
    e.success = payload.success
    e.outcome_value = payload.outcome_value
    e.risk_score = payload.risk_score
    e.human_intervention = bool(e.human_intervention) or payload.human_intervention
    e.ended_at = datetime.utcnow()
    md = dict(e.metadata_json or {})
    md["outcome_metadata"] = payload.metadata
    e.metadata_json = md
    db.commit()
    return {
        "status": "completed",
        "execution_id": execution_id,
        "execution_roi": execution_roi(e.outcome_value or 0, e.cost_usd or 0, e.coordination_tax or 0, e.risk_score or 0),
    }


@app.post("/v1/executions/{execution_id}/end")
def end_execution(execution_id: str, db: Session = Depends(get_db), _=Depends(verify_key)):
    e = db.get(Execution, execution_id)
    if not e:
        raise HTTPException(404, "execution not found")
    if not e.ended_at:
        e.ended_at = datetime.utcnow()
        db.commit()
    return {"status": "ended", "execution_id": execution_id}


@app.get("/v1/executions/{execution_id}")
def get_execution(execution_id: str, db: Session = Depends(get_db), _=Depends(verify_key)):
    e = db.get(Execution, execution_id)
    if not e:
        raise HTTPException(404, "execution not found")
    return _serialize_execution(e)


@app.post("/v1/uef/decide")
def uef_decide(payload: UEFDecisionRequest, db: Session = Depends(get_db), _=Depends(verify_key)):
    decision = decide_execution(
        payload.task, payload.skills_required, payload.candidate_paths, payload.context_bundle, payload.constraints
    )
    db.add(
        UEFDecision(
            decision_id=decision["decision_id"],
            execution_id=payload.execution_id,
            selected_path=decision["selected_path"],
            confidence=decision["confidence"],
            path_scores=decision["path_scores"],
            skill_plan=decision["skill_plan"],
            governance_reqs=decision["governance_requirements"],
            expected_metrics=decision["expected_metrics"],
        )
    )
    db.commit()
    return decision


# =========================================================================== #
# Dashboard JSON endpoints                                                    #
# =========================================================================== #
@app.get("/v1/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), _=Depends(verify_key)):
    total = db.query(func.count(Execution.execution_id)).scalar() or 0
    successes = db.query(func.count(Execution.execution_id)).filter(Execution.success.is_(True)).scalar() or 0
    cost = db.query(func.coalesce(func.sum(Execution.cost_usd), 0)).scalar() or 0
    value = db.query(func.coalesce(func.sum(Execution.outcome_value), 0)).scalar() or 0
    coord = db.query(func.coalesce(func.sum(Execution.coordination_tax), 0)).scalar() or 0
    risk = db.query(func.coalesce(func.sum(Execution.risk_score), 0)).scalar() or 0
    avg_lat = db.query(func.coalesce(func.avg(Execution.latency_ms), 0)).scalar() or 0
    human = db.query(func.count(Execution.execution_id)).filter(Execution.human_intervention.is_(True)).scalar() or 0
    return {
        "total_executions": int(total),
        "success_rate": (successes / total) if total else 0.0,
        "total_cost_usd": float(cost),
        "total_outcome_value": float(value),
        "total_coordination_tax": float(coord),
        "total_risk_score": float(risk),
        "net_execution_value": float(value) - float(cost) - float(coord) - float(risk),
        "avg_latency_ms": float(avg_lat),
        "human_intervention_rate": (human / total) if total else 0.0,
    }


@app.get("/v1/dashboard/skills")
def dashboard_skills(db: Session = Depends(get_db), _=Depends(verify_key)):
    rows = (
        db.query(
            Execution.skill_id,
            func.count(Execution.execution_id).label("executions"),
            func.coalesce(func.avg(case((Execution.success.is_(True), 1.0), else_=0.0)), 0).label("success_rate"),
            func.coalesce(func.avg(Execution.cost_usd), 0).label("avg_cost"),
            func.coalesce(func.avg(Execution.latency_ms), 0).label("avg_latency"),
            func.coalesce(func.avg(Execution.coordination_tax), 0).label("avg_coord"),
            func.coalesce(func.avg(Execution.outcome_value), 0).label("avg_value"),
        )
        .filter(Execution.skill_id.isnot(None))
        .group_by(Execution.skill_id)
        .all()
    )
    out = []
    for r in rows:
        sr = float(r.success_rate or 0)
        cost = float(r.avg_cost or 0)
        out.append(
            {
                "skill_id": r.skill_id,
                "executions": int(r.executions),
                "success_rate": sr,
                "avg_cost_usd": cost,
                "avg_latency_ms": float(r.avg_latency or 0),
                "avg_coordination_tax": float(r.avg_coord or 0),
                "avg_outcome_value": float(r.avg_value or 0),
                "skill_efficiency": skill_efficiency(sr, cost),
            }
        )
    return out


@app.get("/v1/dashboard/models")
def dashboard_models(db: Session = Depends(get_db), _=Depends(verify_key)):
    rows = (
        db.query(
            ModelCall.model_name,
            ModelCall.model_provider,
            func.count(ModelCall.id).label("calls"),
            func.coalesce(func.sum(ModelCall.cost_usd), 0).label("total_cost"),
            func.coalesce(func.avg(ModelCall.cost_usd), 0).label("avg_cost"),
            func.coalesce(func.avg(ModelCall.latency_ms), 0).label("avg_latency"),
            func.coalesce(func.sum(ModelCall.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.avg(case((ModelCall.success.is_(True), 1.0), else_=0.0)), 0).label("success_rate"),
        )
        .group_by(ModelCall.model_name, ModelCall.model_provider)
        .all()
    )
    return [
        {
            "model_name": r.model_name,
            "model_provider": r.model_provider,
            "calls": int(r.calls),
            "total_cost_usd": float(r.total_cost),
            "avg_cost_usd": float(r.avg_cost),
            "avg_latency_ms": float(r.avg_latency),
            "total_tokens": int(r.total_tokens),
            "success_rate": float(r.success_rate),
        }
        for r in rows
    ]


@app.get("/v1/dashboard/executors")
def dashboard_executors(db: Session = Depends(get_db), _=Depends(verify_key)):
    rows = (
        db.query(
            SkillInvocation.executor,
            func.count(func.distinct(SkillInvocation.execution_id)).label("executions"),
            func.coalesce(func.avg(case((Execution.success.is_(True), 1.0), else_=0.0)), 0).label("success_rate"),
            func.coalesce(func.avg(Execution.cost_usd), 0).label("avg_cost"),
            func.coalesce(func.avg(Execution.latency_ms), 0).label("avg_latency"),
            func.coalesce(func.avg(Execution.outcome_value), 0).label("avg_value"),
        )
        .join(Execution, Execution.execution_id == SkillInvocation.execution_id)
        .group_by(SkillInvocation.executor)
        .all()
    )
    return [
        {
            "executor": r.executor,
            "executions": int(r.executions),
            "success_rate": float(r.success_rate),
            "avg_cost_usd": float(r.avg_cost),
            "avg_latency_ms": float(r.avg_latency),
            "avg_outcome_value": float(r.avg_value),
        }
        for r in rows
    ]


@app.get("/v1/dashboard/coordination-tax")
def dashboard_coordination_tax(db: Session = Depends(get_db), _=Depends(verify_key)):
    rows = (
        db.query(
            Execution.skill_id,
            SkillInvocation.executor,
            func.count(Execution.execution_id).label("executions"),
            func.coalesce(func.avg(Execution.coordination_tax), 0).label("avg_coord"),
        )
        .join(SkillInvocation, SkillInvocation.execution_id == Execution.execution_id)
        .filter(Execution.skill_id.isnot(None))
        .group_by(Execution.skill_id, SkillInvocation.executor)
        .all()
    )
    return [
        {
            "skill_id": r.skill_id,
            "executor": r.executor,
            "executions": int(r.executions),
            "avg_coordination_tax": float(r.avg_coord),
        }
        for r in rows
    ]


@app.get("/v1/dashboard/executions")
def dashboard_executions(limit: int = 50, db: Session = Depends(get_db), _=Depends(verify_key)):
    rows = db.query(Execution).order_by(desc(Execution.started_at)).limit(limit).all()
    return [_serialize_execution(e, brief=True) for e in rows]


def _serialize_execution(e: Execution, brief: bool = False) -> Dict[str, Any]:
    base = {
        "execution_id": e.execution_id,
        "agent_id": e.agent_id,
        "task_type": e.task_type,
        "skill_id": e.skill_id,
        "model_name": e.model_name,
        "cost_usd": float(e.cost_usd or 0),
        "latency_ms": int(e.latency_ms or 0),
        "success": e.success,
        "outcome_value": float(e.outcome_value or 0),
        "execution_roi": execution_roi(e.outcome_value or 0, e.cost_usd or 0, e.coordination_tax or 0, e.risk_score or 0),
        "started_at": e.started_at.isoformat() if e.started_at else None,
    }
    if brief:
        return base
    base.update(
        {
            "tenant_id": e.tenant_id,
            "model_provider": e.model_provider,
            "prompt_tokens": int(e.prompt_tokens or 0),
            "completion_tokens": int(e.completion_tokens or 0),
            "total_tokens": int(e.total_tokens or 0),
            "risk_score": float(e.risk_score or 0),
            "human_intervention": bool(e.human_intervention),
            "uop_score": float(e.uop_score or 0),
            "gsti_score": float(e.gsti_score or 0),
            "coordination_tax": float(e.coordination_tax or 0),
            "governance_class": e.governance_class,
            "ended_at": e.ended_at.isoformat() if e.ended_at else None,
            "metadata": e.metadata_json or {},
        }
    )
    return base


# =========================================================================== #
# Sample-data seeder — lets reviewers fill the dashboard in one click         #
# =========================================================================== #
SKILLS = [
    ("brake_diagnosis", "diagnostic"),
    ("oil_change_intake", "intake"),
    ("warranty_lookup", "lookup"),
    ("upsell_recommendation", "advisory"),
    ("safety_recall_check", "compliance"),
]
MODELS = [
    ("openai", "gpt-4o-mini", 0.005, 0.015),
    ("openai", "gpt-4o", 0.03, 0.08),
    ("anthropic", "claude-3-5-sonnet", 0.018, 0.05),
    ("anthropic", "claude-3-5-haiku", 0.004, 0.012),
    ("google", "gemini-1.5-pro", 0.02, 0.05),
]
EXECUTORS = ["agent", "agent", "agent", "hybrid", "hybrid", "human"]
TENANTS = ["dealer_001", "dealer_002", "dealer_003"]


@app.post("/v1/dev/seed")
def seed(count: int = 60, db: Session = Depends(get_db), _=Depends(verify_key)):
    """Insert ``count`` synthetic executions covering a realistic spread."""
    rng = random.Random(int(time.time()))
    now = datetime.utcnow()
    inserted = 0
    for i in range(count):
        skill_id, task_type = rng.choice(SKILLS)
        provider, model_name, cost_lo, cost_hi = rng.choice(MODELS)
        executor = rng.choice(EXECUTORS)
        tenant = rng.choice(TENANTS)
        risk_level = rng.choices(["low", "medium", "high"], weights=[5, 4, 1])[0]
        coord_tax = round(rng.uniform(0.05, 0.35), 3)
        uop = round(rng.uniform(0.55, 0.92), 3)
        gsti = round(rng.uniform(0.45, 0.88), 3)
        cost = round(rng.uniform(cost_lo, cost_hi), 4)
        latency = rng.randint(250, 4500)
        success = rng.random() < (0.95 if executor != "agent" else 0.88)
        outcome_value = round(rng.uniform(8, 80), 2) if success else 0.0
        risk_score = round(rng.uniform(0.0, 0.3), 3)
        started_at = now - timedelta(minutes=rng.randint(0, 60 * 24 * 5))
        ended_at = started_at + timedelta(milliseconds=latency)

        eid = f"exec_seed_{uuid.uuid4().hex[:10]}"
        e = Execution(
            execution_id=eid,
            tenant_id=tenant,
            agent_id=f"agent_{rng.randint(1, 5)}",
            task_type=task_type,
            skill_id=skill_id,
            model_provider=provider,
            model_name=model_name,
            cost_usd=cost,
            latency_ms=latency,
            prompt_tokens=rng.randint(120, 800),
            completion_tokens=rng.randint(60, 400),
            total_tokens=rng.randint(200, 1200),
            success=success,
            outcome_value=outcome_value,
            risk_score=risk_score,
            human_intervention=executor != "agent",
            uop_score=uop,
            gsti_score=gsti,
            coordination_tax=coord_tax,
            governance_class="safety_relevant" if risk_level == "high" else "standard",
            started_at=started_at,
            ended_at=ended_at,
            metadata_json={"risk_level": risk_level, "seeded": True},
        )
        db.add(e)
        db.add(
            SkillInvocation(
                id=f"si_{uuid.uuid4().hex}",
                execution_id=eid,
                tenant_id=tenant,
                skill_id=skill_id,
                executor=executor,
                metadata_json={},
            )
        )
        db.add(
            ModelCall(
                id=f"mc_{uuid.uuid4().hex}",
                execution_id=eid,
                tenant_id=tenant,
                model_provider=provider,
                model_name=model_name,
                prompt_tokens=e.prompt_tokens,
                completion_tokens=e.completion_tokens,
                total_tokens=e.total_tokens,
                cost_usd=cost,
                latency_ms=latency,
                success=success,
                metadata_json={"seeded": True},
            )
        )
        if rng.random() < 0.6:
            db.add(
                ToolCall(
                    id=f"tc_{uuid.uuid4().hex}",
                    execution_id=eid,
                    tenant_id=tenant,
                    tool_name=rng.choice(["vehicle_scan_api", "warranty_db", "parts_lookup", "tech_calendar"]),
                    latency_ms=rng.randint(80, 800),
                    success=success,
                    metadata_json={"seeded": True},
                )
            )
        if executor != "agent":
            db.add(
                HumanStep(
                    id=f"hs_{uuid.uuid4().hex}",
                    execution_id=eid,
                    tenant_id=tenant,
                    operator_id=f"tech_{rng.randint(1, 12)}",
                    step_type=rng.choice(["approve", "review", "override"]),
                    latency_ms=rng.randint(15_000, 240_000),
                    metadata_json={"seeded": True},
                )
            )
        inserted += 1
    db.commit()
    return {"status": "seeded", "inserted": inserted}


@app.post("/v1/dev/reset")
def reset(db: Session = Depends(get_db), _=Depends(verify_key)):
    """Wipe all telemetry — handy for testing."""
    for table in (HumanStep, SkillInvocation, ModelCall, ToolCall, UEFDecision, Execution):
        db.query(table).delete()
    db.commit()
    return {"status": "reset"}


# =========================================================================== #
# HTML dashboard                                                              #
# =========================================================================== #
@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    summary = dashboard_summary(db=db)
    skills = dashboard_skills(db=db)
    models = dashboard_models(db=db)
    executors = dashboard_executors(db=db)
    coord = dashboard_coordination_tax(db=db)
    recent = dashboard_executions(limit=20, db=db)

    # Build coordination-tax pivot (skill x executor)
    skills_index = sorted({c["skill_id"] for c in coord})
    executors_index = sorted({c["executor"] for c in coord})
    coord_pivot = {s: {ex: None for ex in executors_index} for s in skills_index}
    for c in coord:
        coord_pivot[c["skill_id"]][c["executor"]] = c["avg_coordination_tax"]
    coord_max = max((c["avg_coordination_tax"] for c in coord), default=0.001) or 0.001

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "summary": summary,
            "skills": skills,
            "models": models,
            "executors": executors,
            "coord_skills": skills_index,
            "coord_executors": executors_index,
            "coord_pivot": coord_pivot,
            "coord_max": coord_max,
            "recent": recent,
            "now": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        },
    )


@app.get("/api")
def api_redirect():
    return RedirectResponse("/docs")
