"""Process miner.

Wraps PM4Py's Inductive Miner when available and falls back to a deterministic
variant-graph + alpha-style algorithm otherwise. The fallback is enough to:

- Recover exact-match variants from a synthetic log.
- Compute basic activity transition statistics (frequency, mean wait).
- Power the Sprint 3 demo and tests without making PM4Py a hard dep.

Inputs are XES-like dicts:

    {"case_id": "c1", "activity": "extract", "timestamp": datetime, "resource": "agent", ...}

Outputs land in `MinedArtifact`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class Event:
    case_id: str
    activity: str
    timestamp: datetime
    resource: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Variant:
    sequence: tuple[str, ...]
    case_count: int
    case_ids: list[str]


@dataclass
class TransitionStats:
    src: str
    dst: str
    count: int
    mean_wait_s: float
    p95_wait_s: float


@dataclass
class MinedArtifact:
    tenant: str
    skill: str
    n_cases: int
    variants: list[Variant]
    transitions: list[TransitionStats]
    petri_net: dict[str, Any] | None  # set when PM4Py is installed
    subsampled: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "tenant": self.tenant,
            "skill": self.skill,
            "n_cases": self.n_cases,
            "variants": [
                {"sequence": list(v.sequence), "case_count": v.case_count, "case_ids": v.case_ids}
                for v in self.variants
            ],
            "transitions": [asdict(t) for t in self.transitions],
            "petri_net": self.petri_net,
            "subsampled": self.subsampled,
        }


def _has_pm4py() -> bool:
    try:
        import pm4py  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(int(len(sorted_values) * p), len(sorted_values) - 1)
    return sorted_values[idx]


def _build_variants(events: list[Event]) -> list[Variant]:
    by_case: dict[str, list[Event]] = defaultdict(list)
    for e in events:
        by_case[e.case_id].append(e)
    variants: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for case_id, evs in by_case.items():
        evs.sort(key=lambda e: e.timestamp)
        seq = tuple(e.activity for e in evs)
        variants[seq].append(case_id)
    out = [
        Variant(sequence=seq, case_count=len(case_ids), case_ids=case_ids)
        for seq, case_ids in variants.items()
    ]
    out.sort(key=lambda v: -v.case_count)
    return out


def _build_transitions(events: list[Event]) -> list[TransitionStats]:
    by_case: dict[str, list[Event]] = defaultdict(list)
    for e in events:
        by_case[e.case_id].append(e)
    waits: dict[tuple[str, str], list[float]] = defaultdict(list)
    for evs in by_case.values():
        evs.sort(key=lambda e: e.timestamp)
        for a, b in zip(evs, evs[1:], strict=False):
            waits[(a.activity, b.activity)].append((b.timestamp - a.timestamp).total_seconds())

    out: list[TransitionStats] = []
    for (src, dst), values in waits.items():
        values.sort()
        out.append(
            TransitionStats(
                src=src,
                dst=dst,
                count=len(values),
                mean_wait_s=sum(values) / len(values),
                p95_wait_s=_percentile(values, 0.95),
            )
        )
    out.sort(key=lambda t: -t.count)
    return out


def _try_pm4py(events: list[Event]) -> dict[str, Any] | None:
    if not _has_pm4py():
        return None
    try:  # pragma: no cover — exercised when PM4Py is installed in CI
        import pandas as pd  # type: ignore[import-not-found]
        import pm4py  # type: ignore[import-not-found]

        df = pd.DataFrame(
            [
                {
                    "case:concept:name": e.case_id,
                    "concept:name": e.activity,
                    "time:timestamp": e.timestamp,
                    "org:resource": e.resource,
                }
                for e in events
            ]
        )
        log = pm4py.format_dataframe(df)
        net, im, fm = pm4py.discover_petri_net_inductive(log)
        return {
            "places": [str(p.name) for p in net.places],
            "transitions": [str(t.name) for t in net.transitions],
            "initial_marking_keys": [str(k) for k in im.keys()],
            "final_marking_keys": [str(k) for k in fm.keys()],
        }
    except Exception:
        return None


def mine(
    events: Iterable[Event],
    *,
    tenant: str,
    skill: str,
    subsample_threshold: int = 1_000_000,
) -> MinedArtifact:
    """Run the miner against a stream of events.

    If `len(events)` exceeds `subsample_threshold` we deterministically subsample
    to 25% and tag the artifact `subsampled=true`.
    """

    events_list = list(events)
    subsampled = False
    if len(events_list) > subsample_threshold:
        events_list = events_list[:: 4]
        subsampled = True

    variants = _build_variants(events_list)
    transitions = _build_transitions(events_list)
    petri_net = _try_pm4py(events_list)

    case_ids = {e.case_id for e in events_list}
    return MinedArtifact(
        tenant=tenant,
        skill=skill,
        n_cases=len(case_ids),
        variants=variants,
        transitions=transitions,
        petri_net=petri_net,
        subsampled=subsampled,
    )


def synth_log(
    *,
    n_cases: int,
    variants: dict[tuple[str, ...], float],
    base_time: datetime | None = None,
    step: timedelta = timedelta(seconds=10),
) -> list[Event]:
    """Build a deterministic synthetic event log over a set of variants.

    `variants` maps activity sequence -> probability (must sum to 1).
    """

    base_time = base_time or datetime(2026, 5, 3, 12, 0, tzinfo=None)
    cumulative: list[tuple[float, tuple[str, ...]]] = []
    running = 0.0
    for seq, prob in variants.items():
        running += prob
        cumulative.append((running, seq))

    events: list[Event] = []
    for i in range(n_cases):
        # Deterministic "random" pick.
        u = ((i * 1103515245 + 12345) % 0x7FFFFFFF) / 0x7FFFFFFF
        seq: tuple[str, ...] = cumulative[-1][1]
        for thresh, candidate in cumulative:
            if u <= thresh:
                seq = candidate
                break
        case_id = f"case-{i:05d}"
        ts = base_time
        for activity in seq:
            events.append(
                Event(case_id=case_id, activity=activity, timestamp=ts, resource="agent")
            )
            ts = ts + step
    return events


__all__ = [
    "Event",
    "MinedArtifact",
    "TransitionStats",
    "Variant",
    "mine",
    "synth_log",
]
