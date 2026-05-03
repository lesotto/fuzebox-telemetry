"""Prioritizer: tier assignment by volume × exposure."""

from __future__ import annotations

from services.miner.app.prioritizer import SkillStat, Tier, prioritize


def test_tiers_assigned_in_order() -> None:
    stats = [
        SkillStat(tenant="acme", skill="hot", volume_30d=10_000, economic_exposure_usd=100.0),
        SkillStat(tenant="acme", skill="warm", volume_30d=1_000, economic_exposure_usd=10.0),
        SkillStat(tenant="acme", skill="cold", volume_30d=10, economic_exposure_usd=1.0),
    ]
    out = prioritize(stats, hourly_top=1, daily_top=1)
    by_skill = {a.skill: a.tier for a in out}
    assert by_skill["hot"] == Tier.HOURLY
    assert by_skill["warm"] == Tier.DAILY
    assert by_skill["cold"] == Tier.WEEKLY


def test_default_thresholds() -> None:
    stats = [
        SkillStat(tenant="t", skill=f"s{i}", volume_30d=i, economic_exposure_usd=1.0)
        for i in range(6_000)
    ]
    out = prioritize(stats)
    tiers = [a.tier for a in out]
    assert tiers.count(Tier.HOURLY) == 500
    assert tiers.count(Tier.DAILY) == 5_000
    assert tiers.count(Tier.WEEKLY) == 500


def test_score_ordering() -> None:
    stats = [
        SkillStat(tenant="t", skill="a", volume_30d=10, economic_exposure_usd=10.0),  # score 100
        SkillStat(tenant="t", skill="b", volume_30d=1, economic_exposure_usd=1000.0),  # score 1000
    ]
    out = prioritize(stats, hourly_top=1, daily_top=10)
    assert out[0].skill == "b"
    assert out[0].tier == Tier.HOURLY
