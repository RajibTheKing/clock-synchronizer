"""Utilities for identifying the network interface used for an NTP request."""
from __future__ import annotations

import re
import socket
import subprocess
import sys
from typing import Optional

from PySide6.QtNetwork import QNetworkInterface


def _interface_for_host(host: str) -> Optional[QNetworkInterface]:
    try:
        addresses = socket.getaddrinfo(host, 123, type=socket.SOCK_DGRAM)
    except OSError:
        return None

    local_address: Optional[str] = None
    for family, socket_type, protocol, _, address in addresses:
        try:
            with socket.socket(family, socket_type, protocol) as route_socket:
                route_socket.connect(address)
                local_address = route_socket.getsockname()[0]
                break
        except OSError:
            continue

    if not local_address:
        return None

    for interface in QNetworkInterface.allInterfaces():
        if any(
            entry.ip().toString() == local_address
            for entry in interface.addressEntries()
        ):
            return interface
    return None


def _run_command(arguments: list[str]) -> str:
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def _wifi_ssid(interface_name: str) -> Optional[str]:
    if sys.platform == "win32":
        output = _run_command(["netsh", "wlan", "show", "interfaces"])
        sections = re.split(r"(?=^\s*Name\s*:)", output, flags=re.MULTILINE)
        for section in sections:
            name = re.search(r"^\s*Name\s*:\s*(.+?)\s*$", section, re.MULTILINE)
            state = re.search(
                r"^\s*State\s*:\s*connected\s*$",
                section,
                re.MULTILINE | re.IGNORECASE,
            )
            ssid = re.search(r"^\s*SSID\s*:\s*(.+?)\s*$", section, re.MULTILINE)
            if name and name.group(1) == interface_name and state and ssid:
                return ssid.group(1)
        return None

    if sys.platform == "darwin":
        output = _run_command(
            ["networksetup", "-getairportnetwork", interface_name]
        )
        prefix = "Current Wi-Fi Network:"
        for line in output.splitlines():
            if line.startswith(prefix):
                return line[len(prefix):].strip() or None
        return None

    output = _run_command(["iwgetid", interface_name, "--raw"])
    if output:
        return output

    output = _run_command(
        [
            "nmcli",
            "--terse",
            "--fields",
            "IN-USE,SSID",
            "device",
            "wifi",
            "list",
            "ifname",
            interface_name,
        ]
    )
    for line in output.splitlines():
        if line.startswith("*:"):
            return line[2:].replace("\\:", ":").replace("\\\\", "\\").strip() or None
    return None


def get_network_connection(host: str) -> str:
    """Return the routed interface type and Wi-Fi SSID for an NTP host."""
    interface = _interface_for_host(host)
    if interface is None:
        return "Unknown"

    interface_type = interface.type()
    if interface_type == QNetworkInterface.InterfaceType.Wifi:
        ssid = _wifi_ssid(interface.name())
        return f"Wi-Fi ({ssid})" if ssid else "Wi-Fi (SSID unavailable)"
    if interface_type == QNetworkInterface.InterfaceType.Ethernet:
        return "Ethernet"

    return interface.humanReadableName() or "Unknown"
