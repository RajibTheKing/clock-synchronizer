"""Data models for NTP synchronization results and statistics."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from statistics import mean
from typing import List, Optional


@dataclass
class NtpSyncResult:
    """Represents the result of a single NTP clock drift calculation.

    offset_ms: Clock drift in milliseconds. Positive = local clock is ahead
    of true time, negative = local clock is behind true time.
    """

    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    offset_ms: float = 0.0
    round_trip_delay_ms: float = 0.0
    server_used: str = ""
    is_success: bool = True
    error_message: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class NtpStats:
    """Summary statistics computed across synchronization history."""

    average_offset_last10: float = 0.0
    min_offset: Optional[float] = None
    max_offset: Optional[float] = None
    min_avg_offset_last10: Optional[float] = None
    max_avg_offset_last10: Optional[float] = None
    total_syncs: int = 0
    success_count: int = 0

    @classmethod
    def from_results(cls, results: List[NtpSyncResult]) -> "NtpStats":
        successful = [r for r in results if r.is_success]
        if not successful:
            return cls(total_syncs=len(results), success_count=0)

        last10 = successful[:10]
        avg = mean(r.offset_ms for r in last10)
        min_offset = min(r.offset_ms for r in successful)
        max_offset = max(r.offset_ms for r in successful)

        # Rolling "Avg Drift (Last 10)" as it would have appeared after each
        # sync in chronological order, used to find its session min/max.
        chronological = list(reversed(successful))
        rolling_averages = [
            mean(r.offset_ms for r in chronological[max(0, i - 9):i + 1])
            for i in range(len(chronological))
        ]
        min_avg_last10 = min(rolling_averages)
        max_avg_last10 = max(rolling_averages)

        return cls(
            average_offset_last10=avg,
            min_offset=min_offset,
            max_offset=max_offset,
            min_avg_offset_last10=min_avg_last10,
            max_avg_offset_last10=max_avg_last10,
            total_syncs=len(results),
            success_count=len(successful),
        )
