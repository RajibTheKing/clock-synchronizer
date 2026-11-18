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
    val medianOffsetLast10: Double = 0.0,
    val averageOffsetLast20: Double = 0.0,
    val medianOffsetLast20: Double = 0.0,
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
            val last20 = successfulResults.take(20)

            val minOffset = successfulResults.minOf { it.offsetMs }
            val maxOffset = successfulResults.maxOf { it.offsetMs }

            return NtpStats(
                averageOffsetLast10 = avg,
                medianOffsetLast10 = median(last10.map { it.offsetMs }),
                averageOffsetLast20 = last20.map { it.offsetMs }.average(),
                medianOffsetLast20 = median(last20.map { it.offsetMs }),
                minOffset = minOffset,
                maxOffset = maxOffset,
                totalSyncs = results.size,
                successCount = successfulResults.size
            )
        }

        private fun median(values: List<Long>): Double {
            val sorted = values.sorted()
            val middle = sorted.size / 2
            return if (sorted.size % 2 == 0) {
                (sorted[middle - 1].toDouble() + sorted[middle].toDouble()) / 2
            } else {
                sorted[middle].toDouble()
            }
        }
    }
}
