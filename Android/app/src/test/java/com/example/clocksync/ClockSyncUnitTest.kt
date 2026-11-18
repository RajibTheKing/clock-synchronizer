package com.example.clocksync

import com.example.clocksync.data.NtpStats
import com.example.clocksync.data.NtpSyncResult
import com.example.clocksync.network.SntpClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ClockSyncUnitTest {

    @Test
    fun ntpStats_emptyList_returnsDefaultStats() {
        val stats = NtpStats.fromResults(emptyList())

        assertEquals(0.0, stats.averageOffsetLast10, 0.001)
        assertNull(stats.minOffset)
        assertNull(stats.maxOffset)
        assertEquals(0, stats.totalSyncs)
        assertEquals(0, stats.successCount)
    }

    @Test
    fun ntpStats_calculatesAverageLast10AndMinMaxCorrectly() {
        val results = listOf(
            NtpSyncResult(offsetMs = 10L, isSuccess = true),
            NtpSyncResult(offsetMs = -20L, isSuccess = true),
            NtpSyncResult(offsetMs = 30L, isSuccess = true),
            NtpSyncResult(offsetMs = -40L, isSuccess = true),
            NtpSyncResult(offsetMs = 50L, isSuccess = true),
            NtpSyncResult(offsetMs = -60L, isSuccess = true),
            NtpSyncResult(offsetMs = 70L, isSuccess = true),
            NtpSyncResult(offsetMs = -80L, isSuccess = true),
            NtpSyncResult(offsetMs = 90L, isSuccess = true),
            NtpSyncResult(offsetMs = -100L, isSuccess = true),
            NtpSyncResult(offsetMs = 500L, isSuccess = true) // 11th entry, should not be in last 10
        )

        val stats = NtpStats.fromResults(results)

        // Last 10 successful entries in list order are first 10 items
        // Sum of offsets = 10 - 20 + 30 - 40 + 50 - 60 + 70 - 80 + 90 - 100 = -50
        // Avg = -50 / 10 = -5.0
        assertEquals(-5.0, stats.averageOffsetLast10, 0.001)

        // The lowest signed offset is -100L.
        assertEquals(-100L, stats.minOffset)

        // The highest signed offset is 500L.
        assertEquals(500L, stats.maxOffset)

        assertEquals(11, stats.totalSyncs)
        assertEquals(11, stats.successCount)
    }

    @Test
    fun ntpStats_ignoresFailedAttemptsInAverageAndMinMax() {
        val results = listOf(
            NtpSyncResult(offsetMs = 15L, isSuccess = true),
            NtpSyncResult(offsetMs = 0L, isSuccess = false, errorMessage = "Timeout"),
            NtpSyncResult(offsetMs = -25L, isSuccess = true)
        )

        val stats = NtpStats.fromResults(results)

        assertEquals(-5.0, stats.averageOffsetLast10, 0.001) // (15 + -25)/2 = -5.0
        assertEquals(-25L, stats.minOffset)
        assertEquals(15L, stats.maxOffset)
        assertEquals(3, stats.totalSyncs)
        assertEquals(2, stats.successCount)
    }

    @Test
    fun sntpClient_defaultConfiguration_usesPoolNtpOrg() {
        val servers = SntpClient.DEFAULT_NTP_SERVERS
        assertEquals(listOf("pool.ntp.org"), servers)
    }

    @Test
    fun sntpClient_rejectsRoundTripDelaysAbove100Milliseconds() {
        assertTrue(SntpClient.isAcceptableDelay(100))
        assertFalse(SntpClient.isAcceptableDelay(101))
    }

    @Test
    fun ntpStats_calculatesRollingMediansAndMeansIgnoringFailures() {
        val results = (1L..21L).map { NtpSyncResult(offsetMs = it, isSuccess = true) }
            .toMutableList()
        results.add(0, NtpSyncResult(offsetMs = 1000, isSuccess = false))

        val stats = NtpStats.fromResults(results)

        assertEquals(5.5, stats.averageOffsetLast10, 0.001)
        assertEquals(5.5, stats.medianOffsetLast10, 0.001)
        assertEquals(10.5, stats.averageOffsetLast20, 0.001)
        assertEquals(10.5, stats.medianOffsetLast20, 0.001)
        assertEquals(21, stats.successCount)
        assertEquals(22, stats.totalSyncs)
    }

    @Test
    fun ntpStats_calculatesOddMedianFromSuccessfulOffsets() {
        val stats = NtpStats.fromResults(listOf(
            NtpSyncResult(offsetMs = -8),
            NtpSyncResult(offsetMs = 30),
            NtpSyncResult(offsetMs = 5)
        ))

        assertEquals(5.0, stats.medianOffsetLast10, 0.001)
        assertEquals(5.0, stats.medianOffsetLast20, 0.001)
    }
}
