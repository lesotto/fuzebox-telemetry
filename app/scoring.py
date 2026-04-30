"""UEF scorer + derived metrics (same as v1 spec)."""

from __future__ import annotations
import uuid
from typing import Any, Dict, Iterable, List, Tuple


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


_RISK = {"low": 0.1, "medium": 0.3, "high": 0.7}


def score_path(path, task, ctx, constraints) -> Tuple[float, Dict[str, float]]:
    uop = float(ctx.get("uop_score", 0.5))
    gsti = float(ctx.get("gsti_score", 0.5))
    coord = float(ctx.get("coordination_tax", 0.1))
    risk_level = str(task.get("risk_level", "medium")).lower()
    outcome_value = float(task.get("outcome_value", 1.0))
    rw = _RISK.get(risk_level, 0.3)

    if path == "human":
        cap, runtime = 0.75 + 0.20 * uop, 0.45
        econ = clamp(outcome_value / 100.0) - 0.25
        gov = 0.90 if risk_level in ("medium", "high") else 0.70
        risk_pen = rw * 0.35
        gw, uw = 0.25, 0.25
    elif path == "hybrid":
        cap, runtime = 0.85, 0.75
        econ = clamp(outcome_value / 100.0) - 0.15
        gov = 0.95
        risk_pen = rw * 0.20
        gw, uw = 0.20, 0.15
    else:  # any agent path
        cap, runtime = 0.70, 0.85
        econ = clamp(outcome_value / 100.0)
        gov = 0.55 if risk_level == "high" else 0.75
        risk_pen = rw * 0.45
        gw, uw = 0.05, 0.05

    components = {
        "capability_fit": cap,
        "gsti_value": gw * gsti,
        "uop_value": uw * uop,
        "coordination_tax": coord,
        "governance_score": gov,
        "runtime_fit": runtime,
        "economic_value": econ,
        "risk_penalty": risk_pen,
    }
    score = cap + components["gsti_value"] + components["uop_value"] - coord + gov + runtime + econ - risk_pen
    return round(score, 4), components


def decide_execution(task, skills_required: Iterable[str], candidate_paths: List[str], ctx, constraints) -> Dict[str, Any]:
    if not candidate_paths:
        candidate_paths = ["openai_agent", "anthropic_agent", "human", "hybrid"]
    scored = {p: score_path(p, task, ctx, constraints) for p in candidate_paths}
    path_scores = {p: s for p, (s, _) in scored.items()}
    selected = max(path_scores, key=path_scores.get)

    def executor_for(p: str) -> str:
        return "human" if p == "human" else ("hybrid" if p == "hybrid" else "agent")

    return {
        "decision_id": f"dec_{uuid.uuid4().hex[:12]}",
        "selected_path": selected,
        "confidence": clamp(path_scores[selected] / 4.0),
        "path_scores": path_scores,
        "path_components": {p: comps for p, (_, comps) in scored.items()},
        "skill_plan": [
            {"skill_id": s, "executor": executor_for(selected), "reason": "UEF v1 scorer"}
            for s in (list(skills_required) or ["unknown_skill"])
        ],
        "governance_requirements": ["audit_log", "trace_retention", "human_override_available"],
        "expected_metrics": {
            "score": path_scores[selected],
            "risk_level": task.get("risk_level", "medium"),
            "estimated_outcome_value": task.get("outcome_value", 0),
        },
    }


def execution_roi(outcome_value: float, cost_usd: float, coord: float, risk: float) -> float:
    return (outcome_value or 0) - (cost_usd or 0) - (coord or 0) - (risk or 0)


def skill_efficiency(success_rate: float, cost_per_execution: float):
    if not cost_per_execution:
        return None
    return success_rate / cost_per_execution
