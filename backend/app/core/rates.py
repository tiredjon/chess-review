"""Лимит «N/период» из конфига: `30/hour`, `10/minute`, `5/30s`, `100/d`."""

import re
from dataclasses import dataclass

_UNITS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "h": 3600,
    "hour": 3600,
    "d": 86400,
    "day": 86400,
}
_RATE_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d*)\s*([a-z]+?)s?\s*$")


@dataclass(frozen=True, slots=True)
class Rate:
    limit: int
    period_s: int

    @classmethod
    def parse(cls, value: str) -> "Rate":
        match = _RATE_RE.match(value.lower())
        if match is None or match.group(3) not in _UNITS:
            raise ValueError(f"Лимит должен быть вида N/период (30/hour, 5/30s): {value!r}")
        limit, count, unit = int(match.group(1)), int(match.group(2) or 1), match.group(3)
        if limit < 1 or count < 1:
            raise ValueError(f"Лимит и период должны быть ≥ 1: {value!r}")
        return cls(limit=limit, period_s=count * _UNITS[unit])
