"""SQLite persistence — same schema as the v1 spec, packaged for single-file deploy.

The path defaults to ``data.db`` in the project root so publish_website
snapshots survive redeploys.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Generator

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.types import JSON

# On Render, persistent disk is mounted at /var/data and survives redeploys.
# Locally and on plain hosts, fall back to ./data.db in the project root.
_DEFAULT_SQLITE_PATH = "/var/data/data.db" if os.path.isdir("/var/data") else "./data.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Execution(Base):
    __tablename__ = "executions"

    execution_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    agent_id = Column(String, index=True)
    task_type = Column(String, index=True)
    skill_id = Column(String, index=True)
    parent_execution_id = Column(String, ForeignKey("executions.execution_id"), nullable=True)

    model_provider = Column(String)
    model_name = Column(String)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(BigInteger, default=0)
    prompt_tokens = Column(BigInteger, default=0)
    completion_tokens = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)

    success = Column(Boolean, nullable=True)
    outcome_value = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    human_intervention = Column(Boolean, default=False)

    uop_score = Column(Float, default=0.0)
    gsti_score = Column(Float, default=0.0)
    coordination_tax = Column(Float, default=0.0)
    governance_class = Column(String)

    metadata_json = Column(JSON, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    ended_at = Column(DateTime, nullable=True)


class ModelCall(Base):
    __tablename__ = "model_calls"

    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("executions.execution_id"), index=True, nullable=False)
    tenant_id = Column(String, index=True)
    model_provider = Column(String)
    model_name = Column(String, index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_type = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("executions.execution_id"), index=True, nullable=False)
    tenant_id = Column(String, index=True)
    tool_name = Column(String, index=True)
    latency_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_type = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class HumanStep(Base):
    __tablename__ = "human_steps"

    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("executions.execution_id"), index=True, nullable=False)
    tenant_id = Column(String)
    operator_id = Column(String)
    step_type = Column(String)
    latency_ms = Column(Integer, default=0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class SkillInvocation(Base):
    __tablename__ = "skill_invocations"

    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("executions.execution_id"), index=True, nullable=False)
    tenant_id = Column(String, index=True)
    skill_id = Column(String, index=True, nullable=False)
    executor = Column(String, nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class UEFDecision(Base):
    __tablename__ = "uef_decisions"

    decision_id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("executions.execution_id"), nullable=True)
    tenant_id = Column(String)
    selected_path = Column(String)
    confidence = Column(Float)
    path_scores = Column(JSON, default=dict)
    skill_plan = Column(JSON, default=list)
    governance_reqs = Column(JSON, default=list)
    expected_metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
