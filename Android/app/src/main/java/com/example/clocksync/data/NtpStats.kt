package com.example.clocksync.data

import kotlin.math.abs

/**
 * Summary statistics computed across synchronization history.
 *
 * @param averageOffsetLast10 Mean offset in milliseconds across the last 10 successful syncs.
 * @param bestOffset Smallest magnitude (absolute value) clock offset recorded in history.
 * @param worstOffset Largest magnitude (absolute value) clock offset recorded in history.
 * @param totalSyncs Total number of sync attempts performed.
 * @param successCount Number of successful sync attempts.
 */
data class NtpStats(
    val averageOffsetLast10: Double = 0.0,
    val bestOffset: Long? = null,
    val worstOffset: Long? = null,
    val totalSyncs: Int = 0,
    val successCount: Int = 0
) {
    companion object {
        fun fromResults(results: List<NtpSyncResult>): NtpStats {
            val successfulResults = results.filter { it.isSuccess }
            if (successfulResults.isEmpty()) {
                return NtpStats(totalSyncs = results.size, successCount = 0)
            }

            // Average drift based on last 10 successful syncs
            val last10 = successfulResults.take(10)
            val avg = last10.map { it.offsetMs }.average()

            // Best offset = minimum absolute drift
            val best = successfulResults.minByOrNull { abs(it.offsetMs) }?.offsetMs

            // Worst offset = maximum absolute drift
            val worst = successfulResults.maxByOrNull { abs(it.offsetMs) }?.offsetMs

            return NtpStats(
                averageOffsetLast10 = avg,
                bestOffset = best,
                worstOffset = worst,
                totalSyncs = results.size,
                successCount = successfulResults.size
            )
        }
    }
}
