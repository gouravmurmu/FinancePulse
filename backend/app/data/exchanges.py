"""Regular trading sessions for the market-status badge.

Holidays are not modelled; the UI says "regular hours" so a closed holiday
shows as open. Crypto trades 24/7.
"""

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Session:
    name: str
    timezone: str
    open: time
    close: time
    # Optional midday break (Tokyo, Hong Kong).
    break_start: time | None = None
    break_end: time | None = None


SESSIONS: dict[str, Session] = {
    "NYSE": Session("New York", "America/New_York", time(9, 30), time(16, 0)),
    "NSE": Session("India (NSE/BSE)", "Asia/Kolkata", time(9, 15), time(15, 30)),
    "LSE": Session("London", "Europe/London", time(8, 0), time(16, 30)),
    "XETRA": Session("Frankfurt", "Europe/Berlin", time(9, 0), time(17, 30)),
    "TSE": Session("Tokyo", "Asia/Tokyo", time(9, 0), time(15, 30), time(11, 30), time(12, 30)),
    "HKEX": Session(
        "Hong Kong", "Asia/Hong_Kong", time(9, 30), time(16, 0), time(12, 0), time(13, 0)
    ),
}

EXCHANGE_TO_SESSION = {
    "NYSE": "NYSE",
    "NASDAQ": "NYSE",
    "NASDAQ/NYSE": "NYSE",
    "NYSE Arca": "NYSE",
    "COMEX": "NYSE",
    "NSE": "NSE",
    "BSE": "NSE",
    "LSE": "LSE",
    "XETRA": "XETRA",
    "TSE": "TSE",
    "HKEX": "HKEX",
}


def is_open(session: Session, now: datetime) -> bool:
    local = now.astimezone(ZoneInfo(session.timezone))
    if local.weekday() >= 5:
        return False
    t = local.time()
    if not (session.open <= t < session.close):
        return False
    in_break = (
        session.break_start is not None
        and session.break_end is not None
        and session.break_start <= t < session.break_end
    )
    return not in_break
