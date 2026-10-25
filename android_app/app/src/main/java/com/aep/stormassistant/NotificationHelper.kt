package com.aep.stormassistant

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

class NotificationHelper(private val context: Context) {

    companion object {
        const val CHANNEL_ID = "aep_storm_critical_alerts"
        const val CHANNEL_NAME = "Critical Grid Alerts & Storm Warnings"
        const val CHANNEL_DESC = "Urgent notifications for severe weather impacts, substation warnings, and power outages."
    }

    init {
        createNotificationChannel()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            val audioAttributes = AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_EVENT)
                .build()

            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = CHANNEL_DESC
                enableLights(true)
                lightColor = Color.parseColor("#FFB81C")
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 500, 250, 500)
                setSound(alarmSound, audioAttributes)
                lockscreenVisibility = NotificationCompat.VISIBILITY_PUBLIC
            }

            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    fun showAlertNotification(alert: AlertModel) {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("alert_id", alert.id)
        }

        val pendingIntent = PendingIntent.getActivity(
            context,
            alert.id.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val defaultSoundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)

        val notificationBuilder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(alert.title)
            .setContentText(alert.message)
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .bigText("${alert.message}\n\nSubstation: ${alert.substation}\nSeverity: ${alert.severity}")
                    .setSummaryText("Storm Assistant Grid Telemetry")
            )
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setColor(Color.parseColor("#003087"))
            .setAutoCancel(true)
            .setSound(defaultSoundUri)
            .setVibrate(longArrayOf(0, 500, 250, 500))
            .setContentIntent(pendingIntent)

        val notificationManager = NotificationManagerCompat.from(context)
        try {
            notificationManager.notify(alert.id.hashCode(), notificationBuilder.build())
        } catch (e: SecurityException) {
            e.printStackTrace()
        }
    }

    fun showTestNotification() {
        val testAlert = AlertModel(
            id = "test_" + System.currentTimeMillis(),
            title = "⚡ Grid Warning: Maple Ridge Substation",
            message = "Predicted storm impact at 8:15 PM. Please prepare backup power!",
            severity = "CRITICAL",
            substation = "Maple Ridge Substation",
            impactCustomers = 4250,
            eta = "8:15 PM"
        )
        showAlertNotification(testAlert)
    }
}
