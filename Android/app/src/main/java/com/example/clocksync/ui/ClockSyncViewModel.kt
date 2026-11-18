package com.example.clocksync.ui

import android.app.Application
import android.content.Intent
import androidx.lifecycle.AndroidViewModel
import com.example.clocksync.data.NtpStats
import com.example.clocksync.data.NtpSyncResult
import com.example.clocksync.service.ClockSyncService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

data class ClockSyncUiState(
    val history: List<NtpSyncResult> = emptyList(),
    val stats: NtpStats = NtpStats(),
    val isSyncing: Boolean = false,
    val isAutoSyncEnabled: Boolean = true,
    val secondsUntilNextSync: Int = SYNC_INTERVAL_SECONDS,
    val isServiceRunning: Boolean = false,
    val mqttStatus: String = "Disconnected",
    val deviceId: String = "",
    val serviceError: String? = null
)

const val SYNC_INTERVAL_SECONDS = 5

object ClockSyncState {
    val mutableState = MutableStateFlow(ClockSyncUiState())
    val state = mutableState.asStateFlow()
}

class ClockSyncViewModel(application: Application) : AndroidViewModel(application) {
    val uiState = ClockSyncState.state

    private fun sendAction(action: String) {
        getApplication<Application>().startService(
            Intent(getApplication(), ClockSyncService::class.java).setAction(action)
        )
    }

    fun triggerManualSync() = sendAction(ClockSyncService.ACTION_SYNC)
    fun toggleAutoSync() = sendAction(ClockSyncService.ACTION_TOGGLE_AUTO)
    fun clearHistory() = sendAction(ClockSyncService.ACTION_CLEAR_HISTORY)
}
