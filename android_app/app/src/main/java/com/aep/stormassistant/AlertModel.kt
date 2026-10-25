package com.aep.stormassistant

import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class AlertModel(
    val id: String,
    val title: String,
    val message: String,
    val severity: String = "WARNING",
    val substation: String = "Regional Grid",
    val timestamp: String = "",
    val impactCustomers: Int = 0,
    val eta: String = ""
) {
    companion object {
        fun fromJsonObject(obj: JSONObject): AlertModel {
            val title = when {
                obj.has("title") -> obj.optString("title")
                obj.has("headline") -> obj.optString("headline")
                obj.has("type") -> "⚡ " + obj.optString("type").replace("_", " ").uppercase()
                else -> "⚡ Grid Alert"
            }

            val message = when {
                obj.has("message") -> obj.optString("message")
                obj.has("body") -> obj.optString("body")
                obj.has("description") -> obj.optString("description")
                obj.has("details") -> obj.optString("details")
                else -> "Grid status update received from Storm Assistant telemetry."
            }

            val id = when {
                obj.has("id") -> obj.optString("id")
                obj.has("alert_id") -> obj.optString("alert_id")
                obj.has("notification_id") -> obj.optString("notification_id")
                else -> (title + message).hashCode().toString()
            }

            val rawSeverity = when {
                obj.has("severity") -> obj.optString("severity")
                obj.has("priority") -> obj.optString("priority")
                obj.has("level") -> obj.optString("level")
                title.contains("CRITICAL", true) || title.contains("OUTAGE", true) -> "CRITICAL"
                title.contains("RESTORED", true) -> "RESTORED"
                else -> "WARNING"
            }.uppercase()

            val severity = when {
                rawSeverity.contains("CRIT") || rawSeverity.contains("HIGH") -> "CRITICAL"
                rawSeverity.contains("RESTORE") -> "RESTORED"
                rawSeverity.contains("INFO") || rawSeverity.contains("ADVIS") -> "ADVISORY"
                else -> "WARNING"
            }

            val substation = when {
                obj.has("substation") -> obj.optString("substation")
                obj.has("location") -> obj.optString("location")
                obj.has("station") -> obj.optString("station")
                else -> extractSubstation(title + " " + message)
            }

            val timestamp = when {
                obj.has("timestamp") -> obj.optString("timestamp")
                obj.has("created_at") -> obj.optString("created_at")
                obj.has("time") -> obj.optString("time")
                else -> SimpleDateFormat("h:mm a, MMM d", Locale.getDefault()).format(Date())
            }

            val impactCustomers = when {
                obj.has("impact_customers") -> obj.optInt("impact_customers")
                obj.has("customers_affected") -> obj.optInt("customers_affected")
                obj.has("customers") -> obj.optInt("customers")
                else -> 0
            }

            val eta = when {
                obj.has("eta") -> obj.optString("eta")
                obj.has("estimated_restoration") -> obj.optString("estimated_restoration")
                else -> ""
            }

            return AlertModel(
                id = id,
                title = title,
                message = message,
                severity = severity,
                substation = substation,
                timestamp = timestamp,
                impactCustomers = impactCustomers,
                eta = eta
            )
        }

        private fun extractSubstation(text: String): String {
            val regex = Regex("([A-Za-z0-9 ]+ (Substation|Station|Feeder|Sector))", RegexOption.IGNORE_CASE)
            val match = regex.find(text)
            return match?.value?.trim() ?: "AEP Transmission Grid"
        }

        fun parseAlerts(jsonContent: String): List<AlertModel> {
            val alerts = mutableListOf<AlertModel>()
            val trimmed = jsonContent.trim()

            try {
                if (trimmed.startsWith("[")) {
                    val arr = JSONArray(trimmed)
                    for (i in 0 until arr.length()) {
                        val item = arr.optJSONObject(i)
                        if (item != null) {
                            alerts.add(fromJsonObject(item))
                        }
                    }
                } else if (trimmed.startsWith("{")) {
                    val root = JSONObject(trimmed)
                    val arrayCandidates = listOf("notifications", "alerts", "data", "events", "results")
                    var arrayFound = false

                    for (candidate in arrayCandidates) {
                        if (root.has(candidate)) {
                            val arr = root.optJSONArray(candidate)
                            if (arr != null) {
                                for (i in 0 until arr.length()) {
                                    val item = arr.optJSONObject(i)
                                    if (item != null) {
                                        alerts.add(fromJsonObject(item))
                                    }
                                }
                                arrayFound = true
                                break
                            }
                        }
                    }

                    if (!arrayFound) {
                        // Might be a single alert object
                        alerts.add(fromJsonObject(root))
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }

            return alerts
        }
    }
}
