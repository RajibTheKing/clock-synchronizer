package com.example.clocksync.network

import com.example.clocksync.data.NtpSyncResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.apache.commons.net.ntp.NTPUDPClient
import org.apache.commons.net.ntp.TimeInfo
import java.net.InetAddress
import kotlin.math.abs

/**
 * An SNTP client built using Apache Commons Net [NTPUDPClient].
 * Queries NTP servers over UDP port 123 to measure system clock drift offset (in milliseconds) and network delay.
 */
class SntpClient(
    private val ntpServers: List<String> = DEFAULT_NTP_SERVERS,
    private val timeoutMs: Int = DEFAULT_TIMEOUT_MS
) {

    /**
     * Executes an NTP query against the configured list of NTP servers with fallback.
     *
     * @return [NtpSyncResult] containing calculated offset, round-trip delay, and metadata.
     */
    suspend fun requestTime(): NtpSyncResult = withContext(Dispatchers.IO) {
        var lastError: Exception? = null

        for (host in ntpServers) {
            try {
                val result = queryServer(host, timeoutMs)
                return@withContext result
            } catch (e: Exception) {
                lastError = e
            }
        }

        NtpSyncResult(
            isSuccess = false,
            errorMessage = lastError?.localizedMessage ?: "Failed to connect to NTP servers"
        )
    }

    /**
     * Directly queries a single NTP server and returns the clock drift offset in milliseconds.
     * Equivalent to Python's `ntplib.NTPClient().request(server).offset * 1000`.
     *
     * @param server NTP server host (e.g., "pool.ntp.org").
     * @param timeoutMs Timeout in milliseconds for the NTP query.
     * @return Clock drift offset in milliseconds (positive = system clock behind NTP time).
     */
    @Suppress("DEPRECATION")
    suspend fun getNtpOffset(
        server: String = "pool.ntp.org",
        timeoutMs: Int = DEFAULT_TIMEOUT_MS
    ): Long = withContext(Dispatchers.IO) {
        NTPUDPClient().use { client ->
            client.defaultTimeout = timeoutMs
            client.open()
            val address = InetAddress.getByName(server)
            val timeInfo: TimeInfo = client.getTime(address)
            timeInfo.computeDetails()
            timeInfo.offset ?: 0L
        }
    }

    @Suppress("DEPRECATION")
    private fun queryServer(host: String, timeoutMs: Int): NtpSyncResult {
        return NTPUDPClient().use { client ->
            client.defaultTimeout = timeoutMs
            client.open()
            val address = InetAddress.getByName(host)
            val timeInfo: TimeInfo = client.getTime(address)
            timeInfo.computeDetails()

            val offset = timeInfo.offset ?: 0L
            val delay = timeInfo.delay ?: 0L

            NtpSyncResult(
                timestampMs = timeInfo.returnTime,
                offsetMs = offset,
                roundTripDelayMs = abs(delay),
                serverUsed = host,
                isSuccess = true
            )
        }
    }

    companion object {
        val DEFAULT_NTP_SERVERS = listOf(
            "pool.ntp.org"
        )
        const val DEFAULT_TIMEOUT_MS = 3000
    }
}
