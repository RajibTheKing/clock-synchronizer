"""Main window UI for the Clock Drift Synchronizer desktop application."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.data.models import NtpStats, NtpSyncResult
from app.network.sntp_client import SntpClient

SYNC_INTERVAL_SECONDS = 5

COLOR_GOOD = "#2E7D32"
COLOR_MODERATE = "#EF6C00"
COLOR_BAD = "#C62828"
COLOR_PRIMARY = "#3F51B5"
COLOR_PRIMARY_CONTAINER = "#E1E4FB"
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


class NtpWorker(QObject):
    """Runs a blocking NTP request on a background thread."""

    finished = Signal(object)

    def __init__(self, client: SntpClient) -> None:
        super().__init__()
        self._client = client

    def run(self) -> None:
        result = self._client.request_time()
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Clock Drift Synchronizer")

        self.sntp_client = SntpClient()
        self.history: list[NtpSyncResult] = []
        self.stats = NtpStats()
        self.is_syncing = False
        self.is_auto_sync_enabled = True
        self.seconds_until_next_sync = SYNC_INTERVAL_SECONDS

        self._thread: Optional[QThread] = None
        self._worker: Optional[NtpWorker] = None

        self._build_ui()
        self._refresh_stats_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)

        self._perform_sync()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_title_bar())

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(16)
        root.addWidget(body, 1)

        body_layout.addWidget(self._build_stats_card())
        body_layout.addWidget(self._build_controls_row())
        body_layout.addWidget(self._build_history_header())

        self.history_list = QListWidget()
        self.history_list.setFrameShape(QFrame.NoFrame)
        self.history_list.setSpacing(6)
        self.history_list.setSelectionMode(QListWidget.NoSelection)
        self.history_list.setStyleSheet("QListWidget { background: transparent; border: none; }")
        body_layout.addWidget(self.history_list, 1)

        self.empty_label = QLabel("No NTP sync entries yet.\nPress 'Sync Now' or wait for auto-sync.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 14px;")
        body_layout.addWidget(self.empty_label, 1)

        self._refresh_history_ui()

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background-color: {COLOR_PRIMARY_CONTAINER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 14, 16, 14)

        title = QLabel("Clock Drift Synchronizer")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)
        layout.addStretch(1)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setFlat(True)
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.setStyleSheet(f"color: {COLOR_BAD}; font-weight: 600; border: none;")
        self.clear_button.clicked.connect(self._on_clear_history)
        layout.addWidget(self.clear_button)

        return bar

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

    def _build_controls_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sync_button = QPushButton("Sync Now")
        self.sync_button.setCursor(Qt.PointingHandCursor)
        self.sync_button.setMinimumHeight(40)
        self.sync_button.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_PRIMARY}; color: white; border-radius: 8px;"
            " font-weight: 600; padding: 0 16px; }"
            "QPushButton:disabled { background-color: #9FA8DA; }"
        )
        self.sync_button.clicked.connect(self._on_manual_sync)
        layout.addWidget(self.sync_button, 1)

        layout.addSpacing(16)

        self.auto_sync_checkbox = QCheckBox("Auto 5s")
        self.auto_sync_checkbox.setChecked(True)
        self.auto_sync_checkbox.stateChanged.connect(self._on_toggle_auto_sync)
        layout.addWidget(self.auto_sync_checkbox)

        return row

    def _build_history_header(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        self.history_title_label = QLabel("Sync History (0)")
        self.history_title_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        layout.addWidget(self.history_title_label)
        layout.addStretch(1)

        self.next_sync_label = QLabel()
        layout.addWidget(self.next_sync_label)

        return row

    # ------------------------------------------------------------- actions
    def _on_manual_sync(self) -> None:
        self.seconds_until_next_sync = SYNC_INTERVAL_SECONDS
        self._perform_sync()

    def _on_toggle_auto_sync(self, _state: int) -> None:
        self.is_auto_sync_enabled = self.auto_sync_checkbox.isChecked()
        if self.is_auto_sync_enabled:
            self.seconds_until_next_sync = SYNC_INTERVAL_SECONDS
        self._update_next_sync_label()

    def _on_clear_history(self) -> None:
        self.history = []
        self.stats = NtpStats()
        self._refresh_history_ui()
        self._refresh_stats_ui()

    def _on_tick(self) -> None:
        if self.is_auto_sync_enabled and not self.is_syncing:
            self.seconds_until_next_sync -= 1
            if self.seconds_until_next_sync <= 0:
                self.seconds_until_next_sync = SYNC_INTERVAL_SECONDS
                self._perform_sync()
            else:
                self._update_next_sync_label()

    def _perform_sync(self) -> None:
        if self.is_syncing:
            return
        self.is_syncing = True
        self._update_controls()

        self._thread = QThread(self)
        self._worker = NtpWorker(self.sntp_client)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_sync_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_sync_finished(self, result: NtpSyncResult) -> None:
        self.history.insert(0, result)
        self.stats = NtpStats.from_results(self.history)
        self.is_syncing = False
        self._update_controls()
        self._refresh_history_ui()
        self._refresh_stats_ui()

    # --------------------------------------------------------------- render
    def _update_controls(self) -> None:
        self.sync_button.setEnabled(not self.is_syncing)
        self.sync_button.setText("Syncing..." if self.is_syncing else "Sync Now")
        self._update_next_sync_label()

    def _update_next_sync_label(self) -> None:
        if self.is_auto_sync_enabled:
            self.next_sync_label.setText(f"Next sync in {self.seconds_until_next_sync}s")
            self.next_sync_label.setStyleSheet(f"color: {COLOR_PRIMARY}; font-weight: 600;")
        else:
            self.next_sync_label.setText("Auto-sync paused")
            self.next_sync_label.setStyleSheet(f"color: {COLOR_OUTLINE};")

    def _refresh_stats_ui(self) -> None:
        stats = self.stats
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

    def _refresh_history_ui(self) -> None:
        self.history_title_label.setText(f"Sync History ({len(self.history)})")
        self.clear_button.setVisible(bool(self.history))

        self.history_list.clear()
        self.history_list.setVisible(bool(self.history))
        self.empty_label.setVisible(not self.history)

        for result in self.history:
            item = QListWidgetItem()
            widget = self._build_history_item_widget(result)
            item.setSizeHint(widget.sizeHint())
            self.history_list.addItem(item)
            self.history_list.setItemWidget(item, widget)

    @staticmethod
    def _build_history_item_widget(result: NtpSyncResult) -> QWidget:
        card = QFrame()
        bg = "#FFFFFF" if result.is_success else "#FCECEC"
        card.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border-radius: 10px; border: 1px solid #E2E2E8; }}"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)

        left_col = QVBoxLayout()
        time_str = datetime.fromtimestamp(result.timestamp_ms / 1000).strftime("%H:%M:%S")

        top_row = QHBoxLayout()
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot_color = get_drift_color(result.offset_ms) if result.is_success else COLOR_BAD
        dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 5px;")
        top_row.addWidget(dot)
        time_label = QLabel(time_str)
        time_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        top_row.addWidget(time_label)
        top_row.addStretch(1)
        left_col.addLayout(top_row)

        subtitle_text = f"Server: {result.server_used}" if result.is_success else (result.error_message or "Failed")
        subtitle = QLabel(subtitle_text)
        subtitle.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 11px;")
        subtitle.setWordWrap(True)
        left_col.addWidget(subtitle)

        layout.addLayout(left_col, 1)

        if result.is_success:
            right_col = QVBoxLayout()
            right_col.setAlignment(Qt.AlignRight)
            offset_label = QLabel(format_offset(result.offset_ms))
            offset_label.setAlignment(Qt.AlignRight)
            offset_label.setStyleSheet(
                f"font-size: 16px; font-weight: 800; color: {get_drift_color(result.offset_ms)};"
            )
            rtt_label = QLabel(f"RTT: {result.round_trip_delay_ms:.0f} ms")
            rtt_label.setAlignment(Qt.AlignRight)
            rtt_label.setStyleSheet(f"color: {COLOR_OUTLINE}; font-size: 10px;")
            right_col.addWidget(offset_label)
            right_col.addWidget(rtt_label)
            layout.addLayout(right_col)
        else:
            error_label = QLabel("ERROR")
            error_label.setStyleSheet(f"color: {COLOR_BAD}; font-weight: 700;")
            layout.addWidget(error_label)

        return card

    def closeEvent(self, event) -> None:
        self.timer.stop()
        try:
            if self._thread is not None and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2000)
        except RuntimeError:
            pass  # background thread's C++ object was already torn down
        super().closeEvent(event)
