package com.example.clocksync.data

import java.util.UUID

/**
 * Represents the result of a single NTP clock drift calculation.
 *
 * @param id Unique identifier for this sync entry.
 * @param timestampMs System timestamp when the synchronization occurred.
 * @param offsetMs Calculated clock drift offset in milliseconds (NTP Time - System Time).
 *                 Positive value indicates system clock is behind NTP time.
 *                 Negative value indicates system clock is ahead of NTP time.
 * @param roundTripDelayMs Network round-trip latency in milliseconds.
 * @param serverUsed Address of the NTP server queried.
 * @param isSuccess True if sync succeeded; false if an error/timeout occurred.
 * @param errorMessage Failure reason if [isSuccess] is false.
 */
data class NtpSyncResult(
    val id: String = UUID.randomUUID().toString(),
    val timestampMs: Long = System.currentTimeMillis(),
    val offsetMs: Long = 0L,
    val roundTripDelayMs: Long = 0L,
    val serverUsed: String = "",
    val isSuccess: Boolean = true,
    val errorMessage: String? = null
)
