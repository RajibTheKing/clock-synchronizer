package com.example.clocksync.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.example.clocksync.MainActivity
import com.example.clocksync.R
import com.example.clocksync.data.NtpStats
import com.example.clocksync.data.NtpSyncResult
import com.example.clocksync.network.SntpClient
import com.example.clocksync.ui.ClockSyncState
import com.example.clocksync.ui.SYNC_INTERVAL_SECONDS
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken
import org.eclipse.paho.client.mqttv3.MqttAsyncClient
import org.eclipse.paho.client.mqttv3.MqttCallback
import org.eclipse.paho.client.mqttv3.MqttConnectOptions
import org.eclipse.paho.client.mqttv3.MqttException
import org.eclipse.paho.client.mqttv3.MqttMessage
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence
import org.json.JSONObject

internal fun mqttPayload(result: NtpSyncResult, deviceId: String): JSONObject = JSONObject()
    .put("device_mac", deviceId)
    .put("client_type", "remote_control")
    .put("timestamp_ms", result.timestampMs)
    .put("offset_ms", result.offsetMs)
    .put("round_trip_delay_ms", result.roundTripDelayMs)
    .put("server_used", result.serverUsed)
    .put("is_success", result.isSuccess)
    .put("error_message", result.errorMessage ?: JSONObject.NULL)
    .put("network_connection", result.networkConnection)

class ClockSyncService : Service() {
    private val exceptionHandler = CoroutineExceptionHandler { _, error ->
        Log.e(TAG, "Clock synchronization stopped unexpectedly", error)
        ClockSyncState.mutableState.update {
            it.copy(serviceError = "Clock synchronization stopped: ${error.message}")
        }
        stopSelf()
    }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO + exceptionHandler)
    private val syncMutex = Mutex()
    private val sntp = SntpClient()
    private lateinit var mqtt: MqttAsyncClient
    private lateinit var deviceId: String
    private var wakeLock: PowerManager.WakeLock? = null
    private var started = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Clock synchronization", NotificationManager.IMPORTANCE_LOW)
            )
        }
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Clock synchronization is running")
            .setContentText("Measuring clock offset and sending MQTT updates")
            .setContentIntent(openApp)
            .setOngoing(true)
            .build()
        try {
            startForeground(NOTIFICATION_ID, notification)
            deviceId = loadDeviceId()
            mqtt = MqttAsyncClient(BROKER, "clocksync-${deviceId.replace(":", "")}", MemoryPersistence())
            mqtt.setCallback(object : MqttCallback {
                override fun connectionLost(cause: Throwable?) {
                    Log.w(TAG, "MQTT connection lost", cause)
                    ClockSyncState.mutableState.update { it.copy(mqttStatus = "Disconnected; reconnecting") }
                }

                override fun messageArrived(topic: String?, message: MqttMessage?) = Unit
                override fun deliveryComplete(token: IMqttDeliveryToken?) {
                    Log.d(TAG, "MQTT sample acknowledged")
                }
            })
            wakeLock = (getSystemService(POWER_SERVICE) as PowerManager)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "$packageName:clock-sync")
                .also { it.acquire() }
            started = true
            ClockSyncState.mutableState.update {
                it.copy(isServiceRunning = true, deviceId = deviceId, serviceError = null)
            }
            scope.launch { maintainConnection() }
            scope.launch { syncLoop() }
        } catch (e: MqttException) {
            failStart(e)
        } catch (e: IllegalStateException) {
            failStart(e)
        } catch (e: SecurityException) {
            failStart(e)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!started) return START_NOT_STICKY
        when (intent?.action) {
            ACTION_SYNC -> scope.launch { sync() }
            ACTION_TOGGLE_AUTO -> ClockSyncState.mutableState.update {
                it.copy(isAutoSyncEnabled = !it.isAutoSyncEnabled, secondsUntilNextSync = SYNC_INTERVAL_SECONDS)
            }
            ACTION_CLEAR_HISTORY -> ClockSyncState.mutableState.update {
                it.copy(history = emptyList(), stats = NtpStats())
            }
        }
        return START_STICKY
    }

    private suspend fun syncLoop() {
        scope.launch { sync() }
        while (scope.isActive) {
            delay(1000)
            var due = false
            ClockSyncState.mutableState.update {
                if (!it.isAutoSyncEnabled || it.isSyncing) it else {
                    val remaining = it.secondsUntilNextSync - 1
                    due = remaining <= 0
                    it.copy(secondsUntilNextSync = if (due) SYNC_INTERVAL_SECONDS else remaining)
                }
            }
            if (due) scope.launch { sync() }
        }
    }

    private suspend fun sync() {
        if (!syncMutex.tryLock()) return
        try {
            ClockSyncState.mutableState.update { it.copy(isSyncing = true, secondsUntilNextSync = SYNC_INTERVAL_SECONDS) }
            val result = sntp.requestTime().copy(networkConnection = networkConnection())
            if (result.isSuccess) publish(result)
            ClockSyncState.mutableState.update {
                val history = listOf(result) + it.history
                it.copy(history = history, stats = NtpStats.fromResults(history), isSyncing = false)
            }
        } catch (e: CancellationException) {
            throw e
        } finally {
            ClockSyncState.mutableState.update { it.copy(isSyncing = false) }
            syncMutex.unlock()
        }
    }

    private suspend fun maintainConnection() {
        var retrySeconds = 1L
        while (scope.isActive) {
            if (!mqtt.isConnected) {
                ClockSyncState.mutableState.update { it.copy(mqttStatus = "Connecting") }
                try {
                    val options = MqttConnectOptions().apply {
                        isCleanSession = true
                        connectionTimeout = 10
                        keepAliveInterval = 20
                        isAutomaticReconnect = true
                    }
                    mqtt.connect(options).waitForCompletion(6000)
                    ClockSyncState.mutableState.update { it.copy(mqttStatus = "Connected") }
                    retrySeconds = 1
                } catch (e: MqttException) {
                    Log.w(TAG, "MQTT connection failed", e)
                    ClockSyncState.mutableState.update { it.copy(mqttStatus = "Disconnected; reconnecting") }
                    delay(retrySeconds * 1000)
                    retrySeconds = (retrySeconds * 2).coerceAtMost(5)
                }
            } else {
                ClockSyncState.mutableState.update { it.copy(mqttStatus = "Connected") }
                delay(1000)
            }
        }
    }

    private fun publish(result: NtpSyncResult) {
        val payload = mqttPayload(result, deviceId)
        try {
            if (!mqtt.isConnected) {
                val options = MqttConnectOptions().apply {
                    isCleanSession = true
                    connectionTimeout = 5
                    keepAliveInterval = 10
                    isAutomaticReconnect = true
                }
                mqtt.connect(options).waitForCompletion(5000)
            }
            val message = MqttMessage(payload.toString().toByteArray(Charsets.UTF_8)).apply { qos = 1 }
            val token = mqtt.publish(TOPIC, message)
            token.waitForCompletion(5000)
            ClockSyncState.mutableState.update { it.copy(mqttStatus = "Connected") }
        } catch (e: Exception) {
            Log.w(TAG, "MQTT publish failed", e)
            ClockSyncState.mutableState.update { it.copy(mqttStatus = "Publish failed: ${e.message}") }
        }
    }

    private fun networkConnection(): String {
        val connectivity = getSystemService(ConnectivityManager::class.java)
        val capabilities = connectivity.getNetworkCapabilities(connectivity.activeNetwork) ?: return "Unknown"
        return when {
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "Wi-Fi (SSID unavailable)"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "Cellular"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "Ethernet"
            else -> "Unknown"
        }
    }

    private fun loadDeviceId(): String {
        val preferences = getSharedPreferences("clock_sync_identity", MODE_PRIVATE)
        preferences.getString("device_id", null)?.let { return it }
        val random = UUID.randomUUID().toString().replace("-", "").take(12)
        val firstByte = (random.substring(0, 2).toInt(16) and 0xfc) or 0x02
        val hex = "%02X%s".format(firstByte, random.substring(2).uppercase())
        val id = hex.chunked(2).joinToString(":")
        check(preferences.edit().putString("device_id", id).commit()) { "Could not save installation ID" }
        return id
    }

    private fun failStart(error: Exception) {
        Log.e(TAG, "Unable to start clock synchronization", error)
        ClockSyncState.mutableState.update { it.copy(serviceError = "Unable to start synchronization: ${error.message}") }
        stopSelf()
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        Log.w(TAG, "Android stopped the data-sync service after its background time limit")
        ClockSyncState.mutableState.update {
            it.copy(serviceError = "Background time limit reached. Open the app to restart synchronization.")
        }
        stopSelf()
    }

    override fun onDestroy() {
        started = false
        scope.cancel()
        if (::mqtt.isInitialized) {
            try {
                mqtt.close(true)
            } catch (e: MqttException) {
                Log.w(TAG, "Unable to close MQTT client", e)
            }
        }
        wakeLock?.let { if (it.isHeld) it.release() }
        ClockSyncState.mutableState.update {
            it.copy(isServiceRunning = false, isSyncing = false, mqttStatus = "Disconnected")
        }
        super.onDestroy()
    }

    companion object {
        const val ACTION_SYNC = "com.example.clocksync.SYNC"
        const val ACTION_TOGGLE_AUTO = "com.example.clocksync.TOGGLE_AUTO"
        const val ACTION_CLEAR_HISTORY = "com.example.clocksync.CLEAR_HISTORY"
        private const val TAG = "ClockSyncService"
        private const val CHANNEL_ID = "clock_sync"
        private const val NOTIFICATION_ID = 1
        private const val BROKER = "tcp://wt.rtsys-lab.de:1883"
        private const val TOPIC = "rtsys/clockoffset_rc"
    }
}
