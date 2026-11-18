package com.example.clocksync

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.clocksync.data.NtpSyncResult
import com.example.clocksync.service.mqttPayload
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class MqttPayloadTest {
    @Test
    fun payloadMatchesDesktopContract() {
        val result = NtpSyncResult(
            timestampMs = 123456789,
            offsetMs = -7,
            roundTripDelayMs = 25,
            serverUsed = "pool.ntp.org",
            networkConnection = "Wi-Fi (SSID unavailable)"
        )
        val payload = mqttPayload(result, "02:12:34:56:78:90")
        val expected = JSONObject(
            """{"device_mac":"02:12:34:56:78:90","client_type":"remote_control","timestamp_ms":123456789,"offset_ms":-7,"round_trip_delay_ms":25,"server_used":"pool.ntp.org","is_success":true,"error_message":null,"network_connection":"Wi-Fi (SSID unavailable)"}"""
        )

        assertEquals(expected.length(), payload.length())
        val keys = expected.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            assertTrue("Missing key $key", payload.has(key))
            assertEquals("Mismatch for $key", expected.get(key).toString(), payload.get(key).toString())
        }
    }
}
