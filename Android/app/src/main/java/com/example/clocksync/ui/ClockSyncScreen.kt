package com.example.clocksync.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.clocksync.data.NtpSyncResult
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.abs

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ClockSyncScreen(
    viewModel: ClockSyncViewModel = viewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Clock Drift Synchronizer",
                        fontWeight = FontWeight.Bold
                    )
                },
                actions = {
                    if (uiState.history.isNotEmpty()) {
                        IconButton(onClick = { viewModel.clearHistory() }) {
                            Text(
                                text = "Clear",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.error
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer
                )
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Top Summary Dashboard
            StatsDashboardCard(uiState = uiState)

            // Controls Row (Sync Now + Auto Sync Switch)
            ControlsRow(
                uiState = uiState,
                onSyncNow = { viewModel.triggerManualSync() },
                onToggleAutoSync = { viewModel.toggleAutoSync() }
            )

            // Sync History Section Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Sync History (${uiState.history.size})",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                if (uiState.isAutoSyncEnabled) {
                    Text(
                        text = "Next sync in ${uiState.secondsUntilNextSync}s",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Medium
                    )
                } else {
                    Text(
                        text = "Auto-sync paused",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.outline
                    )
                }
            }

            // History List
            if (uiState.history.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "No NTP sync entries yet.\nPress 'Sync Now' or wait for auto-sync.",
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(
                        items = uiState.history,
                        key = { it.id }
                    ) { item ->
                        NtpResultCard(item = item)
                    }
                }
            }
        }
    }
}

@Composable
private fun StatsDashboardCard(uiState: ClockSyncUiState) {
    val stats = uiState.stats

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "Clock Drift Statistics",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = FontWeight.Bold
            )

            // Primary Highlight: Average Drift over last 10
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Avg Drift (Last 10)",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.outline
                    )
                    val avgFormatted = if (stats.successCount > 0) {
                        String.format(Locale.getDefault(), "%.1f ms", stats.averageOffsetLast10)
                    } else {
                        "N/A"
                    }
                    Text(
                        text = avgFormatted,
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.ExtraBold,
                        color = getDriftColor(stats.averageOffsetLast10.toLong())
                    )
                }

                // Sync counts badge
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "Successful Syncs",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.outline
                    )
                    Text(
                        text = "${stats.successCount} / ${stats.totalSyncs}",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            // Secondary Stats: Best & Worst
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                StatTile(
                    label = "Best Offset",
                    value = stats.bestOffset?.let { formatOffset(it) } ?: "-- ms",
                    color = stats.bestOffset?.let { getDriftColor(it) } ?: MaterialTheme.colorScheme.onSurface
                )
                StatTile(
                    label = "Worst Offset",
                    value = stats.worstOffset?.let { formatOffset(it) } ?: "-- ms",
                    color = stats.worstOffset?.let { getDriftColor(it) } ?: MaterialTheme.colorScheme.onSurface
                )
            }
        }
    }
}

@Composable
private fun StatTile(label: String, value: String, color: Color) {
    Column {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.outline
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.Bold,
            color = color
        )
    }
}

@Composable
private fun ControlsRow(
    uiState: ClockSyncUiState,
    onSyncNow: () -> Unit,
    onToggleAutoSync: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Button(
            onClick = onSyncNow,
            enabled = !uiState.isSyncing,
            modifier = Modifier.weight(1f)
        ) {
            if (uiState.isSyncing) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Syncing...")
            } else {
                Text("Sync Now")
            }
        }

        Spacer(modifier = Modifier.width(16.dp))

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "Auto 5s",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium
            )
            Switch(
                checked = uiState.isAutoSyncEnabled,
                onCheckedChange = { onToggleAutoSync() }
            )
        }
    }
}

@Composable
private fun NtpResultCard(item: NtpSyncResult) {
    val timeFormatted = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date(item.timestampMs))

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (item.isSuccess) {
                MaterialTheme.colorScheme.surface
            } else {
                MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.4f)
            }
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(if (item.isSuccess) getDriftColor(item.offsetMs) else Color.Red)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = timeFormatted,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = if (item.isSuccess) "Server: ${item.serverUsed}" else (item.errorMessage ?: "Failed"),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            if (item.isSuccess) {
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = formatOffset(item.offsetMs),
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.ExtraBold,
                        color = getDriftColor(item.offsetMs)
                    )
                    Text(
                        text = "RTT: ${item.roundTripDelayMs} ms",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline
                    )
                }
            } else {
                Text(
                    text = "ERROR",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.error,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

private fun formatOffset(offsetMs: Long): String {
    val sign = if (offsetMs >= 0) "+" else ""
    return "$sign$offsetMs ms"
}

@Composable
private fun getDriftColor(offsetMs: Long): Color {
    val absOffset = abs(offsetMs)
    return when {
        absOffset < 20 -> Color(0xFF2E7D32) // Green for excellent accuracy
        absOffset < 100 -> Color(0xFFEF6C00) // Orange for moderate drift
        else -> Color(0xFFC62828) // Red for high drift
    }
}
