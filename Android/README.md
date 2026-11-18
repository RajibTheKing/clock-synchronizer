# Android clock synchronizer

Opening the app starts a foreground data-sync service. It measures the offset
against `pool.ntp.org` every five seconds and publishes successful samples with
RTT at most 100 ms to `rtsys/clockoffset_rc` on `wt.rtsys-lab.de:1883`, using
MQTT QoS 1. Samples are not queued while the broker is disconnected. The service
retries unexpected MQTT disconnections and continues when the activity is
backgrounded or dismissed from Recents. The app displays an ongoing notification
while synchronization is running; enabling notifications makes it easier to see.

The MQTT payload uses the desktop field names and `client_type` value. Android
does not expose the real hardware MAC address to ordinary apps: `device_mac` is
instead a randomly generated, MAC-shaped installation identifier. It is not
backed up and changes when app data is cleared or the app is reinstalled. The
network field reports the active transport; Wi-Fi SSIDs are not collected.
History and statistics are held in memory and reset when the process ends.

The service holds a partial wake lock while active, increasing battery usage.
Background operation and the five-second schedule are best effort: Doze,
connectivity loss, system resource limits and manufacturer restrictions can
interrupt them. On Android 15 and later, a data-sync foreground service is
limited to six hours of background execution in a 24-hour period unless the app
returns to the foreground. Opening the app again restarts synchronization.
Android's Force stop or Active apps Stop terminates the app; it does not
automatically restart after those user actions or after device reboot.

The broker connection matches the desktop's unencrypted, unauthenticated MQTT
configuration. Use a trusted network; the messages can be observed or altered
in transit.
