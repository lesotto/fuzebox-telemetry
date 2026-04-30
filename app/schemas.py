"""Pydantic schemas — same v1 surface."""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class StartExecutionRequest(BaseModel):
    execution_id: str
    tenant_id: Optional[str] = None
    agent_id: Optional[str] = None
    task_type: Optional[str] = None
    skill_id: Optional[str] = None
    parent_execution_id: Optional[str] = None
    uop_score: float = 0.0
    gsti_score: float = 0.0
    coordination_tax: float = 0.0
    governance_class: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelCallRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_provider: str = ""
    model_name: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolCallRequest(BaseModel):
    tool_name: str
    latency_ms: int = 0
    success: bool = True
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HumanStepRequest(BaseModel):
    operator_id: Optional[str] = None
    step_type: Optional[str] = None
    latency_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillRequest(BaseModel):
    skill_id: str
    executor: Literal["human", "agent", "hybrid"]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OutcomeRequest(BaseModel):
    success: bool
    outcome_value: float = 0.0
    risk_score: float = 0.0
    human_intervention: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UEFDecisionRequest(BaseModel):
    task: Dict[str, Any]
    skills_required: List[str] = Field(default_factory=list)
    candidate_paths: List[str] = Field(default_factory=list)
    context_bundle: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    execution_id: Optional[str] = None
