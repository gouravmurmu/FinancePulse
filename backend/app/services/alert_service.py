"""Anomaly scans (public) and user alert rules and events (filtered by user id).

Both run in a scheduled job after the market data refresh; nothing here is
real-time. Rule evaluation uses the latest stored daily close.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.analytics import anomalies as an
from app.analytics.conventions import periods_per_year
from app.core.errors import AppError
from app.data.universe import DEFAULT_BENCHMARK
from app.models import AlertEvent, AlertRule, AnomalyFlag
from app.services import market_data as md

MAX_RULES = 50
MAX_EVENTS_SHOWN = 200
# Enough daily history for the 252-day baseline plus the correlation window.
SCAN_HISTORY_DAYS = 3 * 365
VOL_WINDOW = an.VOL_WINDOW

KIND_LABELS = {
    "return": "Unusual daily move",
    "volume": "Unusual trading volume",
    "volatility": "Volatility spike",
    "correlation": "Correlation shift",
}
RULE_LABELS = {
    "price_above": "Price rises above",
    "price_below": "Price falls below",
    "move_pct": "Daily move of at least",
    "volatility_above": "20-day volatility above",
    "anomaly": "Any statistical anomaly",
}


def _f(x: Any) -> float | None:
    return None if x is None else float(x)


# --- anomaly scan ------------------------------------------------------------


def benchmark_for(inst: md.InstrumentInfo) -> str | None:
    if inst.asset_class in ("index", "fx"):
        return None
    bench = inst.attributes.get("benchmark") or DEFAULT_BENCHMARK.get(inst.region)
    return bench if bench and bench != inst.id else None


def scan_instrument(
    session: Session, inst: md.InstrumentInfo, since: date, today: date
) -> list[an.Anomaly]:
    start = today - timedelta(days=SCAN_HISTORY_DAYS)
    bars = md.load_bars(session, inst.id, start)
    if bars.empty:
        return []
    bench_id = benchmark_for(inst)
    bench = md.load_bars(session, bench_id, start)["close"] if bench_id else None
    volume = bars["volume"] if bars["volume"].notna().sum() > an.MIN_HISTORY else None
    return an.detect(bars["close"], volume, bench, since=since)


def store_anomalies(session: Session, instrument_id: str, found: list[an.Anomaly]) -> int:
    if not found:
        return 0
    rows = [
        {
            "instrument_id": instrument_id,
            "observed_at": a.observed_at,
            "kind": a.kind,
            "value": a.value,
            "baseline": a.baseline if math.isfinite(a.baseline) else None,
            "zscore": round(a.zscore, 4),
            "threshold": a.threshold,
        }
        for a in found
    ]
    stmt = (
        insert(AnomalyFlag)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_anomalies_key")
        .returning(AnomalyFlag.id)
    )
    # rowcount is unreliable for multi-row inserts, so count what came back.
    return len(session.execute(stmt).all())


def describe_anomaly(a: AnomalyFlag | an.Anomaly, periods: int = 252) -> str:
    value, baseline, z = float(a.value), _f(a.baseline), float(a.zscore)
    if a.kind == "return":
        return f"Moved {value:+.1%} in a day, {abs(z):.1f}× the usual spread of daily moves"
    if a.kind == "volume":
        times = value / baseline if baseline else None
        return f"Volume about {times:.1f}× the usual level" if times else "Volume far above usual"
    if a.kind == "volatility":
        # Stored as daily standard deviation; shown annualised like everywhere else.
        k = math.sqrt(periods)
        usual = f" (usual {(baseline or 0) * k:.0%})" if baseline else ""
        return f"20-day volatility jumped to {value * k:.0%} annualised{usual}"
    return f"60-day correlation with its benchmark moved from {baseline or 0:.2f} to {value:.2f}"


def anomaly_out(a: AnomalyFlag, periods: int = 252) -> dict[str, Any]:
    return {
        "instrument_id": a.instrument_id,
        "observed_at": a.observed_at.isoformat(),
        "kind": a.kind,
        "label": KIND_LABELS[a.kind],
        "description": describe_anomaly(a, periods),
        "value": float(a.value),
        "baseline": _f(a.baseline),
        "zscore": float(a.zscore),
        "threshold": float(a.threshold),
    }


def list_anomalies(
    session: Session, instrument_id: str | None, days: int, limit: int = 100
) -> list[dict[str, Any]]:
    since = datetime.now(UTC).date() - timedelta(days=days)
    stmt = select(AnomalyFlag).where(AnomalyFlag.observed_at >= since)
    if instrument_id:
        stmt = stmt.where(AnomalyFlag.instrument_id == instrument_id)
    stmt = stmt.order_by(AnomalyFlag.observed_at.desc(), func.abs(AnomalyFlag.zscore).desc())
    classes = {i.id: i.asset_class for i in md.list_instruments(session)}
    return [
        anomaly_out(a, periods_per_year(classes.get(a.instrument_id, "equity")))
        for a in session.scalars(stmt.limit(limit))
    ]


# --- rules -------------------------------------------------------------------


def _validate(kind: str, threshold: float | None) -> float | None:
    if kind == "anomaly":
        return None
    if threshold is None or not math.isfinite(threshold) or threshold <= 0:
        raise AppError("invalid_threshold", "Enter a threshold above zero", 422)
    if kind == "move_pct" and threshold > 1:
        raise AppError("invalid_threshold", "A daily move threshold must be 100% or less", 422)
    if kind == "volatility_above" and threshold > 5:
        raise AppError("invalid_threshold", "Volatility threshold must be 500% or less", 422)
    return threshold


def rule_out(rule: AlertRule, inst: md.InstrumentInfo | None = None) -> dict[str, Any]:
    return {
        "id": rule.id,
        "instrument_id": rule.instrument_id,
        "instrument_name": inst.name if inst else rule.instrument_id,
        "currency": inst.currency if inst else None,
        "kind": rule.kind,
        "label": RULE_LABELS[rule.kind],
        "threshold": _f(rule.threshold),
        "active": rule.active,
        "condition_met": rule.last_state,
        "last_evaluated_on": rule.last_evaluated_on.isoformat() if rule.last_evaluated_on else None,
        "created_at": rule.created_at,
    }


def _rule(session: Session, user_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRule:
    rule = session.scalar(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user_id)
    )
    if rule is None:
        raise AppError("not_found", "Alert not found", 404)
    return rule


def list_rules(session: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rules = session.scalars(
        select(AlertRule).where(AlertRule.user_id == user_id).order_by(AlertRule.created_at)
    ).all()
    by_id = {i.id: i for i in md.list_instruments(session)}
    return [rule_out(r, by_id.get(r.instrument_id)) for r in rules]


def create_rule(
    session: Session, user_id: uuid.UUID, instrument_id: str, kind: str, threshold: float | None
) -> dict[str, Any]:
    inst = md.get_instrument(session, instrument_id)
    count = session.scalar(
        select(func.count()).select_from(AlertRule).where(AlertRule.user_id == user_id)
    )
    if (count or 0) >= MAX_RULES:
        raise AppError("limit_reached", f"You can have up to {MAX_RULES} alerts", 422)
    rule = AlertRule(
        user_id=user_id,
        instrument_id=inst.id,
        kind=kind,
        threshold=_validate(kind, threshold),
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule_out(rule, inst)


def update_rule(
    session: Session,
    user_id: uuid.UUID,
    rule_id: uuid.UUID,
    threshold: float | None,
    active: bool | None,
) -> dict[str, Any]:
    rule = _rule(session, user_id, rule_id)
    if threshold is not None:
        rule.threshold = _validate(rule.kind, threshold)  # type: ignore[assignment]
        rule.last_state = None
    if active is not None:
        rule.active = active
        if active:
            rule.last_state = None
    session.commit()
    session.refresh(rule)
    return rule_out(rule, md.get_instrument(session, rule.instrument_id))


def delete_rule(session: Session, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    session.delete(_rule(session, user_id, rule_id))
    session.commit()


# --- events ------------------------------------------------------------------


def event_out(e: AlertEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "rule_id": e.rule_id,
        "instrument_id": e.instrument_id,
        "observed_at": e.observed_at.isoformat(),
        "message": e.message,
        "details": e.details,
        "read": e.read_at is not None,
        "created_at": e.created_at,
    }


def list_events(session: Session, user_id: uuid.UUID, unread_only: bool) -> dict[str, Any]:
    stmt = select(AlertEvent).where(AlertEvent.user_id == user_id)
    if unread_only:
        stmt = stmt.where(AlertEvent.read_at.is_(None))
    events = session.scalars(
        stmt.order_by(AlertEvent.created_at.desc()).limit(MAX_EVENTS_SHOWN)
    ).all()
    unread = session.scalar(
        select(func.count())
        .select_from(AlertEvent)
        .where(AlertEvent.user_id == user_id, AlertEvent.read_at.is_(None))
    )
    return {"events": [event_out(e) for e in events], "unread": unread or 0}


def mark_read(session: Session, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> int:
    stmt = (
        update(AlertEvent)
        .where(AlertEvent.user_id == user_id, AlertEvent.read_at.is_(None))
        .values(read_at=func.now())
    )
    if ids is not None:
        stmt = stmt.where(AlertEvent.id.in_(ids))
    n = session.execute(stmt).rowcount or 0
    session.commit()
    return n


# --- evaluation (job) --------------------------------------------------------


def _fmt_price(v: float, ccy: str) -> str:
    sym = {"USD": "$", "INR": "₹"}.get(ccy)
    return f"{sym}{v:,.2f}" if sym else f"{v:,.4g} {ccy}"


def evaluate_rule(
    rule: AlertRule,
    inst: md.InstrumentInfo,
    close: pd.Series,
    anomalies_on_day: list[AnomalyFlag],
) -> tuple[bool | None, str | None, dict[str, Any]]:
    """Returns (condition now, message if the rule fires, details)."""
    close = close.dropna().astype(float)
    if close.empty:
        return None, None, {}
    last = float(close.iloc[-1])
    thr = _f(rule.threshold)
    name = inst.name
    if rule.kind in ("price_above", "price_below") and thr is not None:
        met = last >= thr if rule.kind == "price_above" else last <= thr
        word = "above" if rule.kind == "price_above" else "below"
        price, level = _fmt_price(last, inst.currency), _fmt_price(thr, inst.currency)
        msg = f"{name} closed at {price}, {word} your level of {level}"
        fires = met and rule.last_state is not True
        return met, msg if fires else None, {"close": last, "threshold": thr}
    if rule.kind == "move_pct" and thr is not None:
        if len(close) < 2:
            return None, None, {}
        move = last / float(close.iloc[-2]) - 1
        met = abs(move) >= thr
        msg = f"{name} moved {move:+.2%} on the day (your trigger is ±{thr:.1%})"
        # A move is a one-day event, so it fires on every qualifying day.
        return met, msg if met else None, {"close": last, "move": move, "threshold": thr}
    if rule.kind == "volatility_above" and thr is not None:
        rets = close.pct_change().dropna().tail(VOL_WINDOW)
        if len(rets) < VOL_WINDOW:
            return None, None, {}
        vol = float(rets.std() * math.sqrt(periods_per_year(inst.asset_class)))
        met = vol >= thr
        msg = f"{name} 20-day volatility is {vol:.1%} a year, above your {thr:.0%}"
        fires = met and rule.last_state is not True
        return met, msg if fires else None, {"volatility": vol, "threshold": thr}
    if rule.kind == "anomaly":
        met = bool(anomalies_on_day)
        if not met:
            return False, None, {}
        first = anomalies_on_day[0]
        extra = f" (+{len(anomalies_on_day) - 1} more)" if len(anomalies_on_day) > 1 else ""
        detail = describe_anomaly(first, periods_per_year(inst.asset_class))
        msg = f"{name}: {KIND_LABELS[first.kind].lower()}. {detail}{extra}"
        return True, msg, {"kinds": [a.kind for a in anomalies_on_day]}
    return None, None, {}


def evaluate_rules(session: Session) -> dict[str, int]:
    """Evaluate every active rule on its instrument's latest close. Idempotent:
    a rule is evaluated at most once per trading date."""
    rules = session.scalars(select(AlertRule).where(AlertRule.active)).all()
    by_inst: dict[str, list[AlertRule]] = {}
    for r in rules:
        by_inst.setdefault(r.instrument_id, []).append(r)
    start = datetime.now(UTC).date() - timedelta(days=90)
    fired = evaluated = 0
    for inst_id, inst_rules in by_inst.items():
        try:
            inst = md.get_instrument(session, inst_id)
        except AppError:
            continue
        bars = md.load_bars(session, inst_id, start)
        if bars.empty:
            continue
        day = bars.index[-1].date()
        flags = list(
            session.scalars(
                select(AnomalyFlag)
                .where(AnomalyFlag.instrument_id == inst_id, AnomalyFlag.observed_at == day)
                .order_by(func.abs(AnomalyFlag.zscore).desc())
            )
        )
        for rule in inst_rules:
            if rule.last_evaluated_on == day:
                continue
            met, message, details = evaluate_rule(rule, inst, bars["close"], flags)
            evaluated += 1
            if message:
                stmt = (
                    insert(AlertEvent)
                    .values(
                        id=uuid.uuid4(),
                        rule_id=rule.id,
                        user_id=rule.user_id,
                        instrument_id=inst_id,
                        observed_at=day,
                        message=message[:300],
                        details=details,
                    )
                    .on_conflict_do_nothing(constraint="uq_alert_events_rule_date")
                    .returning(AlertEvent.id)
                )
                fired += len(session.execute(stmt).all())
            rule.last_state = met
            rule.last_evaluated_on = day
        session.commit()
    return {"rules": len(rules), "evaluated": evaluated, "fired": fired}
