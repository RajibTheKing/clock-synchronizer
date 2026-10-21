"""Main window UI for the Clock Drift Synchronizer desktop application."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
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
from app.network.sntp_client import SntpClient

HISTORY_COLUMNS = ["Device MAC ID", "Date", "Time", "RTT", "Clock Drift"]


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


def get_drift_color(offset_ms: float) -> str:
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
        result = self._client.query_server(self._host)
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Clock Drift Synchronizer")

        self.sntp_client = SntpClient()
        self.servers = self.sntp_client.servers
        self._next_index = 0
        self.current_server: Optional[str] = None
        self.is_syncing = False

        self._thread: Optional[QThread] = None
        self._worker: Optional[NtpWorker] = None

        self._build_ui()
        self._refresh_stats_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)
        self._on_tick()

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

        heading = QLabel("Clock Drift Statistics")
        heading.setStyleSheet(f"color: {COLOR_OUTLINE}; font-weight: 700; font-size: 12px;")
        layout.addWidget(heading)

        top_row = QHBoxLayout()
        avg_col = QVBoxLayout()
        avg_label = QLabel("Avg Drift (Last 10)")
        avg_label.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 11px;")
        self.avg_value_label = QLabel("N/A")
        self.avg_value_label.setStyleSheet("font-size: 24px; font-weight: 800;")
        avg_col.addWidget(avg_label)
        avg_col.addWidget(self.avg_value_label)
        top_row.addLayout(avg_col)
        top_row.addStretch(1)

        count_col = QVBoxLayout()
        count_col.setAlignment(Qt.AlignRight)
        count_label = QLabel("Successful Syncs")
        count_label.setAlignment(Qt.AlignRight)
        count_label.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 11px;")
        self.count_value_label = QLabel("0 / 0")
        self.count_value_label.setAlignment(Qt.AlignRight)
        self.count_value_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        count_col.addWidget(count_label)
        count_col.addWidget(self.count_value_label)
        top_row.addLayout(count_col)
        layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        self.best_label, best_tile = self._build_stat_tile("Best Offset")
        self.worst_label, worst_tile = self._build_stat_tile("Worst Offset")
        bottom_row.addWidget(best_tile)
        bottom_row.addStretch(1)
        bottom_row.addWidget(worst_tile)
        layout.addLayout(bottom_row)

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
        if self.is_syncing:
            return
        host = self.servers[self._next_index]
        self._next_index = (self._next_index + 1) % len(self.servers)
        self._perform_sync(host)

    def _perform_sync(self, host: str) -> None:
        self.is_syncing = True
        self.current_server = host
        self._update_status_label()

        self._thread = QThread(self)
        self._worker = NtpWorker(self.sntp_client, host)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_sync_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_sync_finished(self, result: NtpSyncResult) -> None:
        state = self.tab_states[result.server_used]
        state.history.insert(0, result)
        self.is_syncing = False
        self._update_status_label()
        self._refresh_history_ui(result.server_used)
        self._refresh_stats_ui()

    # --------------------------------------------------------------- render
    def _update_status_label(self) -> None:
        if self.is_syncing and self.current_server:
            self.status_label.setText(f"Syncing with {self.current_server}...")
            self.status_label.setStyleSheet(f"color: {COLOR_PRIMARY}; font-weight: 600;")
        else:
            upcoming = self.servers[self._next_index]
            self.status_label.setText(f"Next: {upcoming}")
            self.status_label.setStyleSheet(f"color: {COLOR_OUTLINE};")

    def _refresh_stats_ui(self) -> None:
        host = self.servers[max(self.tabs.currentIndex(), 0)]
        stats = NtpStats.from_results(self.tab_states[host].history)
        if stats.success_count > 0:
            self.avg_value_label.setText(f"{stats.average_offset_last10:.1f} ms")
            self.avg_value_label.setStyleSheet(
                f"font-size: 24px; font-weight: 800; color: {get_drift_color(stats.average_offset_last10)};"
            )
        else:
            self.avg_value_label.setText("N/A")
            self.avg_value_label.setStyleSheet("font-size: 24px; font-weight: 800;")

        self.count_value_label.setText(f"{stats.success_count} / {stats.total_syncs}")

        if stats.best_offset is not None:
            self.best_label.setText(format_offset(stats.best_offset))
            self.best_label.setStyleSheet(
                f"font-size: 14px; font-weight: 700; color: {get_drift_color(stats.best_offset)};"
            )
        else:
            self.best_label.setText("-- ms")
            self.best_label.setStyleSheet("font-size: 14px; font-weight: 700;")

        if stats.worst_offset is not None:
            self.worst_label.setText(format_offset(stats.worst_offset))
            self.worst_label.setStyleSheet(
                f"font-size: 14px; font-weight: 700; color: {get_drift_color(stats.worst_offset)};"
            )
        else:
            self.worst_label.setText("-- ms")
            self.worst_label.setStyleSheet("font-size: 14px; font-weight: 700;")

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
            if result.is_success:
                rtt = f"{result.round_trip_delay_ms:.0f} ms"
                drift = format_offset(result.offset_ms)
                drift_color = get_drift_color(result.offset_ms)
            else:
                rtt = "--"
                drift = result.error_message or "Error"
                drift_color = COLOR_BAD
            values = [
                self.device_mac,
                moment.strftime("%Y-%m-%d"),
                moment.strftime("%H:%M:%S"),
                rtt,
                drift,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == len(values) - 1:
                    item.setForeground(QColor(drift_color))
                state.table.setItem(row, col, item)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        try:
            if self._thread is not None and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2000)
        except RuntimeError:
            pass  # background thread's C++ object was already torn down
        super().closeEvent(event)
