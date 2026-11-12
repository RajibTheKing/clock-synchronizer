"""Main window UI for the Clock Offset Synchronizer desktop application."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.data.models import NtpStats, NtpSyncResult
from app.data.result_logger import SyncResultLogger
from app.network.connection_info import get_network_connection
from app.network.sntp_client import SntpClient
from app.network.network_worker_mqtt import NetworkWorkerMqtt

HISTORY_COLUMNS = [
    "Device MAC ID",
    "Date",
    "Time",
    "RTT",
    "Clock Offset",
    "Network Connection",
]
CLOCK_OFFSET_COLUMN_INDEX = HISTORY_COLUMNS.index("Clock Offset")


def get_device_mac() -> str:
    node = f"{uuid.getnode():012X}"
    return ":".join(node[i:i + 2] for i in range(0, 12, 2))

COLOR_GOOD = "#2E7D32"
COLOR_MODERATE = "#EF6C00"
COLOR_BAD = "#C62828"
COLOR_PRIMARY = "#3F51B5"
COLOR_SURFACE_VARIANT = "#EEF0FA"
COLOR_OUTLINE = "#71767F"


def format_offset(offset_ms: float) -> str:
    sign = "+" if offset_ms >= 0 else ""
    return f"{sign}{offset_ms:.1f} ms"


def get_offset_color(offset_ms: float) -> str:
    abs_offset = abs(offset_ms)
    if abs_offset < 20:
        return COLOR_GOOD
    if abs_offset < 100:
        return COLOR_MODERATE
    return COLOR_BAD


@dataclass
class ServerTab:
    table: QTableWidget
    empty_label: QLabel
    history: list[NtpSyncResult] = field(default_factory=list)


class NtpWorker(QObject):
    """Runs a blocking NTP request on a background thread."""

    finished = Signal(object)

    def __init__(self, client: SntpClient, host: str) -> None:
        super().__init__()
        self._client = client
        self._host = host

    def run(self) -> None:
        network_connection = get_network_connection(self._host)
        result = self._client.query_server(self._host)
        result.network_connection = network_connection
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Clock Offset Synchronizer")

        self.sntp_client = SntpClient()
        self.servers = self.sntp_client.servers
        self.result_logger = SyncResultLogger(self.servers)
        self._threads: dict[str, QThread] = {}
        self._workers: dict[str, NtpWorker] = {}

        self._build_ui()
        self._refresh_stats_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(2000) # 2 second interval
        self._on_tick()

        self.network_worker_mqtt = NetworkWorkerMqtt()  # Initialize MQTT worker

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet("background-color: #FFFFFF;")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(16)
        root.addWidget(body, 1)

        self.device_mac = get_device_mac()
        body_layout.addWidget(self._build_stats_card())
        body_layout.addWidget(self._build_history_header())

        self.tabs = QTabWidget()
        self.tab_states: dict[str, ServerTab] = {}
        for host in self.servers:
            self.tab_states[host] = self._build_server_tab(host)
        self.tabs.currentChanged.connect(lambda _i: self._refresh_stats_ui())
        body_layout.addWidget(self.tabs, 1)

        self._update_status_label()

    def _build_server_tab(self, host: str) -> "ServerTab":
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)

        table = QTableWidget(0, len(HISTORY_COLUMNS))
        table.setHorizontalHeaderLabels(HISTORY_COLUMNS)
        table.setFrameShape(QFrame.NoFrame)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setVisible(False)
        layout.addWidget(table, 1)

        empty = QLabel(f"No sync entries yet for {host}.")
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 14px;")
        layout.addWidget(empty, 1)

        self.tabs.addTab(page, host)
        return ServerTab(table=table, empty_label=empty)

    def _build_stats_card(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {COLOR_SURFACE_VARIANT}; border-radius: 12px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Clock Offset Statistics")
        heading.setStyleSheet(f"color: {COLOR_OUTLINE}; font-weight: 700; font-size: 12px;")
        layout.addWidget(heading)

        # All stats live in one compact grid, grouped to the left, so they
        # stay close together instead of spreading across a wide window.
        grid = QGridLayout()
        grid.setHorizontalSpacing(36)
        grid.setVerticalSpacing(14)

        # Rows: last 10 on top, last 20 below, so the two windows are easy to compare.
        def build_stat(title: str) -> tuple[QLabel, QVBoxLayout]:
            col = QVBoxLayout()
            col.setSpacing(2)
            title_label = QLabel(title)
            title_label.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 11px;")
            value_label = QLabel("N/A")
            value_label.setStyleSheet("font-size: 24px; font-weight: 800;")
            col.addWidget(title_label)
            col.addWidget(value_label)
            return value_label, col

        self.avg_value_label, avg_col = build_stat("Mean Offset (Last 10)")
        self.avg20_value_label, avg20_col = build_stat("Mean Offset (Last 20)")
        self.median_value_label, median_col = build_stat("Median Offset (Last 10)")
        self.median20_value_label, median20_col = build_stat("Median Offset (Last 20)")
        grid.addLayout(avg_col, 0, 0)
        grid.addLayout(avg20_col, 1, 0)
        grid.addLayout(median_col, 0, 1)
        grid.addLayout(median20_col, 1, 1)

        count_col = QVBoxLayout()
        count_col.setSpacing(2)
        count_label = QLabel("Successful Syncs")
        count_label.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 11px;")
        self.count_value_label = QLabel("0 / 0")
        self.count_value_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        count_col.addWidget(count_label)
        count_col.addWidget(self.count_value_label)
        grid.addLayout(count_col, 0, 2, 2, 1)

        # Min/Max offsets are kept side by side.
        self.min_label, min_tile = self._build_stat_tile("Min")
        self.max_label, max_tile = self._build_stat_tile("Max")
        grid.addWidget(min_tile, 0, 3)
        grid.addWidget(max_tile, 0, 4)

        grid.setColumnStretch(5, 1)
        layout.addLayout(grid)

        return card

    @staticmethod
    def _build_stat_tile(title: str) -> tuple[QLabel, QWidget]:
        tile = QWidget()
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(0, 0, 0, 0)
        tile_layout.setSpacing(2)
        label = QLabel(title)
        label.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 10px;")
        value = QLabel("-- ms")
        value.setStyleSheet("font-size: 14px; font-weight: 700;")
        tile_layout.addWidget(label)
        tile_layout.addWidget(value)
        return value, tile

    def _build_history_header(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        self.history_title_label = QLabel("Sync History (0)")
        self.history_title_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        layout.addWidget(self.history_title_label)
        layout.addStretch(1)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        return row

    # ------------------------------------------------------------- actions
    def _on_tick(self) -> None:
        # One thread per server; a server still awaiting a reply is skipped
        # so requests never pile up on slow servers.
        for host in self.servers:
            if host not in self._threads:
                self._perform_sync(host)

    def _perform_sync(self, host: str) -> None:
        thread = QThread(self)
        worker = NtpWorker(self.sntp_client, host)
        worker.moveToThread(thread)
        self._threads[host] = thread
        self._workers[host] = worker
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_sync_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda h=host: self._on_thread_finished(h))
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._update_status_label()

    def _on_thread_finished(self, host: str) -> None:
        self._threads.pop(host, None)
        self._workers.pop(host, None)
        self._update_status_label()

    def _on_sync_finished(self, result: NtpSyncResult) -> None:
        self.result_logger.log(result.server_used, result)
        if self.network_worker_mqtt.is_connected and result.server_used == "pool.ntp.org":
            payload = {
                "device_mac": self.device_mac,
                "client_type": "remote_control",
                "timestamp_ms": result.timestamp_ms,
                "offset_ms": result.offset_ms,
                "round_trip_delay_ms": result.round_trip_delay_ms,
                "server_used": result.server_used,
                "is_success": result.is_success,
                "error_message": result.error_message,
                "network_connection": result.network_connection,
            }
            data = json.dumps(payload).encode('utf-8')
            self.network_worker_mqtt.send_data(data)

        state = self.tab_states[result.server_used]
        state.history.insert(0, result)
        self._refresh_history_ui(result.server_used)
        self._refresh_stats_ui()

    # --------------------------------------------------------------- render
    def _update_status_label(self) -> None:
        active = len(self._threads)
        if active:
            self.status_label.setText(f"Syncing with {active}/{len(self.servers)} servers...")
            self.status_label.setStyleSheet(f"color: {COLOR_PRIMARY}; font-weight: 600;")
        else:
            self.status_label.setText("Idle")
            self.status_label.setStyleSheet(f"color: {COLOR_OUTLINE};")

    def _refresh_stats_ui(self) -> None:
        host = self.servers[max(self.tabs.currentIndex(), 0)]
        stats = NtpStats.from_results(self.tab_states[host].history)
        if stats.success_count > 0:
            self.avg_value_label.setText(f"{stats.mean_offset_last10:.1f} ms")
            self.avg_value_label.setStyleSheet(
                f"font-size: 24px; font-weight: 800; color: {get_offset_color(stats.mean_offset_last10)};"
            )
            self.median_value_label.setText(f"{stats.median_offset_last10:.1f} ms")
            self.median_value_label.setStyleSheet(
                f"font-size: 24px; font-weight: 800; color: {get_offset_color(stats.median_offset_last10)};"
            )
            self.avg20_value_label.setText(f"{stats.mean_offset_last20:.1f} ms")
            self.avg20_value_label.setStyleSheet(
                f"font-size: 24px; font-weight: 800; color: {get_offset_color(stats.mean_offset_last20)};"
            )
            self.median20_value_label.setText(f"{stats.median_offset_last20:.1f} ms")
            self.median20_value_label.setStyleSheet(
                f"font-size: 24px; font-weight: 800; color: {get_offset_color(stats.median_offset_last20)};"
            )
        else:
            for label in (
                self.avg_value_label,
                self.median_value_label,
                self.avg20_value_label,
                self.median20_value_label,
            ):
                label.setText("N/A")
                label.setStyleSheet("font-size: 24px; font-weight: 800;")

        self.count_value_label.setText(f"{stats.success_count} / {stats.total_syncs}")

        if stats.min_offset is not None:
            self.min_label.setText(format_offset(stats.min_offset))
            self.min_label.setStyleSheet(
                f"font-size: 14px; font-weight: 700; color: {get_offset_color(stats.min_offset)};"
            )
        else:
            self.min_label.setText("-- ms")
            self.min_label.setStyleSheet("font-size: 14px; font-weight: 700;")

        if stats.max_offset is not None:
            self.max_label.setText(format_offset(stats.max_offset))
            self.max_label.setStyleSheet(
                f"font-size: 14px; font-weight: 700; color: {get_offset_color(stats.max_offset)};"
            )
        else:
            self.max_label.setText("-- ms")
            self.max_label.setStyleSheet("font-size: 14px; font-weight: 700;")

    def _refresh_history_ui(self, host: str) -> None:
        state = self.tab_states[host]
        self.history_title_label.setText(
            f"Sync History ({sum(len(t.history) for t in self.tab_states.values())})"
        )

        state.table.setVisible(bool(state.history))
        state.empty_label.setVisible(not state.history)

        state.table.setRowCount(len(state.history))
        for row, result in enumerate(state.history):
            moment = datetime.fromtimestamp(result.timestamp_ms / 1000)
            rtt = (
                f"{result.round_trip_delay_ms:.0f} ms"
                if result.is_success or result.round_trip_delay_ms > 0
                else "--"
            )
            if result.is_success:
                offset_text = format_offset(result.offset_ms)
                offset_color = get_offset_color(result.offset_ms)
            else:
                offset_text = result.error_message or "Error"
                offset_color = COLOR_BAD
            values = [
                self.device_mac,
                moment.strftime("%Y-%m-%d"),
                moment.strftime("%H:%M:%S"),
                rtt,
                offset_text,
                result.network_connection,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == CLOCK_OFFSET_COLUMN_INDEX:
                    item.setForeground(QColor(offset_color))
                state.table.setItem(row, col, item)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        for thread in list(self._threads.values()):
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(2000)
            except RuntimeError:
                pass  # background thread's C++ object was already torn down
        self.network_worker_mqtt.disconnect()  # Disconnect MQTT client on close
        super().closeEvent(event)
