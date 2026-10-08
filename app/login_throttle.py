from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

WINDOW = timedelta(minutes=5)
MAX_FAILURES = 5
_BLOCKED = defaultdict(deque)
_LOCK = Lock()


def _key(username: str, client: str) -> str:
    return f"{client}|{username.strip().lower()}"


def _prune(events: deque, now: datetime) -> None:
    cutoff = now - WINDOW
    while events and events[0] <= cutoff:
        events.popleft()


def is_blocked(username: str, client: str, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    key = _key(username, client)
    with _LOCK:
        events = _BLOCKED[key]
        _prune(events, now)
        if not events:
            _BLOCKED.pop(key, None)
            return False
        return len(events) >= MAX_FAILURES


def record_failure(username: str, client: str, now: datetime | None = None) -> None:
    now = now or datetime.utcnow()
    key = _key(username, client)
    with _LOCK:
        events = _BLOCKED[key]
        _prune(events, now)
        events.append(now)


def clear_failures(username: str, client: str) -> None:
    with _LOCK:
        _BLOCKED.pop(_key(username, client), None)
