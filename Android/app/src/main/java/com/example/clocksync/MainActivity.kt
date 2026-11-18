package com.example.clocksync

import android.os.Bundle
import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.core.content.ContextCompat
import com.example.clocksync.service.ClockSyncService
import com.example.clocksync.ui.ClockSyncState
import kotlinx.coroutines.flow.update
import com.example.clocksync.ui.ClockSyncScreen
import com.example.clocksync.ui.theme.ClockSyncTheme

class MainActivity : ComponentActivity() {
    private val requestNotifications = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        setContent {
            ClockSyncTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    ClockSyncScreen()
                }
            }

        }
    }

    override fun onStart() {
        super.onStart()
        try {
            ContextCompat.startForegroundService(this, Intent(this, ClockSyncService::class.java))
        } catch (e: IllegalStateException) {
            ClockSyncState.mutableState.update { it.copy(serviceError = "Unable to start synchronization: ${e.message}") }
        } catch (e: SecurityException) {
            ClockSyncState.mutableState.update { it.copy(serviceError = "Unable to start synchronization: ${e.message}") }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun MainActivityPreview() {
    ClockSyncTheme {
        ClockSyncScreen()
    }
}
