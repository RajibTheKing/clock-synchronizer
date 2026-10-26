package com.example.clocksync.data

/**
 * Summary statistics computed across synchronization history.
 *
 * @param averageOffsetLast10 Mean offset in milliseconds across the last 10 successful syncs.
 * @param minOffset Lowest signed clock offset recorded in history.
 * @param maxOffset Highest signed clock offset recorded in history.
 * @param totalSyncs Total number of sync attempts performed.
 * @param successCount Number of successful sync attempts.
 */
data class NtpStats(
    val averageOffsetLast10: Double = 0.0,
    val minOffset: Long? = null,
    val maxOffset: Long? = null,
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

            val minOffset = successfulResults.minOf { it.offsetMs }
            val maxOffset = successfulResults.maxOf { it.offsetMs }

            return NtpStats(
                averageOffsetLast10 = avg,
                minOffset = minOffset,
                maxOffset = maxOffset,
                totalSyncs = results.size,
                successCount = successfulResults.size
            )
        }
    }
}
