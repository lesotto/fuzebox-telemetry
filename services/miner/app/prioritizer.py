"""Mining job prioritizer.

Tiers `(tenant, skill)` pairs into HOURLY / DAILY / WEEKLY based on
volume × economic_exposure. Used by the miner scheduler.

Defaults from the prompt:
  - Top 500 by score    -> HOURLY
  - Next 5_000          -> DAILY
  - Long tail           -> WEEKLY
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Tier(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass(frozen=True)
class SkillStat:
    tenant: str
    skill: str
    volume_30d: int
    economic_exposure_usd: float

    @property
    def score(self) -> float:
        return self.volume_30d * self.economic_exposure_usd


@dataclass(frozen=True)
class Assignment:
    tenant: str
    skill: str
    tier: Tier
    score: float


def prioritize(
    stats: list[SkillStat],
    *,
    hourly_top: int = 500,
    daily_top: int = 5_000,
) -> list[Assignment]:
    ordered = sorted(stats, key=lambda s: -s.score)
    out: list[Assignment] = []
    for idx, s in enumerate(ordered):
        if idx < hourly_top:
            tier = Tier.HOURLY
        elif idx < hourly_top + daily_top:
            tier = Tier.DAILY
        else:
            tier = Tier.WEEKLY
        out.append(Assignment(tenant=s.tenant, skill=s.skill, tier=tier, score=s.score))
    return out


__all__ = ["Assignment", "SkillStat", "Tier", "prioritize"]
