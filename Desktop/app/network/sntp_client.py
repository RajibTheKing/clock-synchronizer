"""SNTP client for measuring system clock drift against NTP servers."""
from __future__ import annotations

import time
from typing import List, Optional

import ntplib

from app.data.models import NtpSyncResult

DEFAULT_NTP_SERVERS = [
    "time.google.com",
    "time.cloudflare.com",
    "time.facebook.com",
    "time.apple.com",
    "time.windows.com",
    "pool.ntp.org",
    "time.nist.gov",
]
DEFAULT_TIMEOUT_SECONDS = 3


class SntpClient:
    """Queries NTP servers over UDP port 123 to measure clock offset and delay."""

    def __init__(
        self,
        ntp_servers: Optional[List[str]] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._ntp_servers = ntp_servers or DEFAULT_NTP_SERVERS
        self._timeout = timeout

    def request_time(self) -> NtpSyncResult:
        """Queries the configured NTP servers in order, falling back on failure."""
        last_error: Optional[Exception] = None

        for host in self._ntp_servers:
            try:
                return self._query_server(host)
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI, not fatal
                last_error = exc

        return NtpSyncResult(
            is_success=False,
            error_message=str(last_error) if last_error else "Failed to connect to NTP servers",
        )

    def get_ntp_offset(self, server="pool.ntp.org", timeout=5):
        client = ntplib.NTPClient()
        response = client.request(server, version=3, timeout=timeout)

        # offset = how far your system clock is from true time (seconds)
        # positive = your clock is ahead, negative = your clock is behind
        offset = response.offset * 1000  # Convert to milliseconds

        return offset

    @property
    def servers(self) -> List[str]:
        return list(self._ntp_servers)

    def query_server(self, host: str) -> NtpSyncResult:
        """Queries a single server; failures are returned as unsuccessful results."""
        try:
            return self._query_server(host)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI, not fatal
            return NtpSyncResult(is_success=False, server_used=host, error_message=str(exc))

    def _query_server(self, host: str) -> NtpSyncResult:
        client = ntplib.NTPClient()
        response = client.request(host, version=3, timeout=self._timeout)

        return NtpSyncResult(
            timestamp_ms=int(time.time() * 1000),
            offset_ms=response.offset * 1000,
            round_trip_delay_ms=abs(response.delay * 1000),
            server_used=host,
            is_success=True,
        )
