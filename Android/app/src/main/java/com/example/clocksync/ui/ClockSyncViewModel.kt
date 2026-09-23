package com.example.clocksync.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.clocksync.data.NtpStats
import com.example.clocksync.data.NtpSyncResult
import com.example.clocksync.network.SntpClient
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ClockSyncUiState(
    val history: List<NtpSyncResult> = emptyList(),
    val stats: NtpStats = NtpStats(),
    val isSyncing: Boolean = false,
    val isAutoSyncEnabled: Boolean = true,
    val secondsUntilNextSync: Int = ClockSyncViewModel.SYNC_INTERVAL_SECONDS
)

class ClockSyncViewModel(
    private val sntpClient: SntpClient = SntpClient()
) : ViewModel() {

    private val _uiState = MutableStateFlow(ClockSyncUiState())
    val uiState: StateFlow<ClockSyncUiState> = _uiState.asStateFlow()

    private var timerJob: Job? = null

    init {
        startSyncLoop()
        // Perform initial sync on launch
        performSync()
    }

    private fun startSyncLoop() {
        timerJob?.cancel()
        timerJob = viewModelScope.launch {
            while (true) {
                delay(1000L)
                val currentState = _uiState.value

                if (currentState.isAutoSyncEnabled && !currentState.isSyncing) {
                    val nextSeconds = currentState.secondsUntilNextSync - 1
                    if (nextSeconds <= 0) {
                        _uiState.update { it.copy(secondsUntilNextSync = SYNC_INTERVAL_SECONDS) }
                        performSync()
                    } else {
                        _uiState.update { it.copy(secondsUntilNextSync = nextSeconds) }
                    }
                }
            }
        }
    }

    fun triggerManualSync() {
        viewModelScope.launch {
            _uiState.update { it.copy(secondsUntilNextSync = SYNC_INTERVAL_SECONDS) }
            performSync()
        }
    }

    fun toggleAutoSync() {
        _uiState.update { current ->
            val newAutoSync = !current.isAutoSyncEnabled
            current.copy(
                isAutoSyncEnabled = newAutoSync,
                secondsUntilNextSync = if (newAutoSync) SYNC_INTERVAL_SECONDS else current.secondsUntilNextSync
            )
        }
    }

    fun clearHistory() {
        _uiState.update {
            it.copy(
                history = emptyList(),
                stats = NtpStats()
            )
        }
    }

    private fun performSync() {
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true) }

            val result = sntpClient.requestTime()

            _uiState.update { current ->
                val newHistory = listOf(result) + current.history
                val newStats = NtpStats.fromResults(newHistory)
                current.copy(
                    history = newHistory,
                    stats = newStats,
                    isSyncing = false
                )
            }
        }
    }

    companion object {
        const val SYNC_INTERVAL_SECONDS = 5
    }
}
