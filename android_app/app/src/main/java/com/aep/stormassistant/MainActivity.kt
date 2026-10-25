package com.aep.stormassistant

import android.Manifest
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.materialswitch.MaterialSwitch
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var prefs: SharedPreferences
    private lateinit var notificationHelper: NotificationHelper
    private lateinit var alertAdapter: AlertAdapter

    // UI elements
    private lateinit var etServerUrl: EditText
    private lateinit var btnSaveUrl: Button
    private lateinit var rgEndpoint: RadioGroup
    private lateinit var tvTelemetryStatus: TextView
    private lateinit var switchAutoPoll: MaterialSwitch
    private lateinit var btnTestNotification: Button
    private lateinit var btnPollNow: Button
    private lateinit var btnSimulateAlert: Button
    private lateinit var tvAlertCount: TextView
    private lateinit var btnClearFeed: TextView
    private lateinit var rvAlerts: RecyclerView
    private lateinit var layoutEmptyFeed: LinearLayout
    private lateinit var viewStatusDot: View
    private lateinit var tvStatusText: TextView

    // State & Polling
    private var pollingJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.Main)
    private val seenAlertIds = mutableSetOf<String>()
    private val alertList = mutableListOf<AlertModel>()
    private var simulationIndex = 0

    // Notification Permission Request (Android 13+)
    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            if (isGranted) {
                Toast.makeText(this, "Notification permission granted!", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "Notification permission needed for storm warnings", Toast.LENGTH_LONG).show()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = getSharedPreferences("aep_storm_prefs", Context.MODE_PRIVATE)
        notificationHelper = NotificationHelper(this)

        initViews()
        setupListeners()
        loadSavedConfig()
        checkNotificationPermission()

        // Add initial welcome/demo notification
        seedInitialAlerts()

        // Start auto-polling if enabled
        if (switchAutoPoll.isChecked) {
            startPolling()
        }
    }

    private fun initViews() {
        etServerUrl = findViewById(R.id.etServerUrl)
        btnSaveUrl = findViewById(R.id.btnSaveUrl)
        rgEndpoint = findViewById(R.id.rgEndpoint)
        tvTelemetryStatus = findViewById(R.id.tvTelemetryStatus)
        switchAutoPoll = findViewById(R.id.switchAutoPoll)
        btnTestNotification = findViewById(R.id.btnTestNotification)
        btnPollNow = findViewById(R.id.btnPollNow)
        btnSimulateAlert = findViewById(R.id.btnSimulateAlert)
        tvAlertCount = findViewById(R.id.tvAlertCount)
        btnClearFeed = findViewById(R.id.btnClearFeed)
        rvAlerts = findViewById(R.id.rvAlerts)
        layoutEmptyFeed = findViewById(R.id.layoutEmptyFeed)
        viewStatusDot = findViewById(R.id.viewStatusDot)
        tvStatusText = findViewById(R.id.tvStatusText)

        // Setup RecyclerView
        rvAlerts.layoutManager = LinearLayoutManager(this)
        alertAdapter = AlertAdapter(this, alertList) { clickedAlert ->
            Toast.makeText(this, "${clickedAlert.title}\n${clickedAlert.substation}", Toast.LENGTH_SHORT).show()
        }
        rvAlerts.adapter = alertAdapter
    }

    private fun setupListeners() {
        btnSaveUrl.setOnClickListener {
            val url = etServerUrl.text.toString().trim()
            if (url.isNotEmpty()) {
                prefs.edit().putString("server_url", url).apply()
                Toast.makeText(this, "Backend URL saved: $url", Toast.LENGTH_SHORT).show()
                pollBackend()
            }
        }

        rgEndpoint.setOnCheckedChangeListener { _, checkedId ->
            val endpoint = if (checkedId == R.id.rbAlertsPoll) "/api/alerts/poll" else "/api/notifications"
            prefs.edit().putString("endpoint", endpoint).apply()
            pollBackend()
        }

        btnTestNotification.setOnClickListener {
            notificationHelper.showTestNotification()
            Toast.makeText(this, "Test warning notification dispatched!", Toast.LENGTH_SHORT).show()
        }

        btnPollNow.setOnClickListener {
            pollBackend()
        }

        btnSimulateAlert.setOnClickListener {
            simulateStormAlert()
        }

        btnClearFeed.setOnClickListener {
            alertList.clear()
            alertAdapter.clear()
            updateFeedVisibility()
            updateStatusText("Feed cleared", StatusType.IDLE)
        }

        switchAutoPoll.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean("auto_poll", isChecked).apply()
            if (isChecked) {
                startPolling()
            } else {
                stopPolling()
                updateStatusText("Polling Paused", StatusType.IDLE)
            }
        }
    }

    private fun loadSavedConfig() {
        val savedUrl = prefs.getString("server_url", "http://172.31.92.101:8000") ?: "http://172.31.92.101:8000"
        etServerUrl.setText(savedUrl)

        val savedEndpoint = prefs.getString("endpoint", "/api/notifications") ?: "/api/notifications"
        if (savedEndpoint.contains("poll")) {
            rgEndpoint.check(R.id.rbAlertsPoll)
        } else {
            rgEndpoint.check(R.id.rbNotifications)
        }

        val autoPoll = prefs.getBoolean("auto_poll", true)
        switchAutoPoll.isChecked = autoPoll

        // Restore seen alert IDs
        val savedSeen = prefs.getStringSet("seen_ids", emptySet())
        if (savedSeen != null) {
            seenAlertIds.addAll(savedSeen)
        }
    }

    private fun checkNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun startPolling() {
        stopPolling()
        pollingJob = scope.launch {
            while (isActive) {
                pollBackend()
                delay(5000) // Poll every 5 seconds
            }
        }
    }

    private fun stopPolling() {
        pollingJob?.cancel()
        pollingJob = null
    }

    private fun pollBackend() {
        val baseUrl = etServerUrl.text.toString().trim().removeSuffix("/")
        val endpoint = if (rgEndpoint.checkedRadioButtonId == R.id.rbAlertsPoll) "/api/alerts/poll" else "/api/notifications"
        val fullUrl = "$baseUrl$endpoint"

        updateStatusText("POLLING...", StatusType.POLLING)
        tvTelemetryStatus.text = "Polling: $fullUrl"

        scope.launch {
            val result = withContext(Dispatchers.IO) {
                fetchAlertsFromUrl(fullUrl)
            }

            val currentTime = SimpleDateFormat("h:mm:ss a", Locale.getDefault()).format(Date())

            when (result) {
                is FetchResult.Success -> {
                    val alerts = result.alerts
                    var newAlertCount = 0

                    for (alert in alerts) {
                        if (!seenAlertIds.contains(alert.id)) {
                            seenAlertIds.add(alert.id)
                            newAlertCount++
                            // Dispatch high importance system notification!
                            notificationHelper.showAlertNotification(alert)
                            alertList.add(0, alert)
                        } else {
                            // Check if alert is already in UI feed
                            if (alertList.none { it.id == alert.id }) {
                                alertList.add(alert)
                            }
                        }
                    }

                    // Save seen IDs
                    prefs.edit().putStringSet("seen_ids", seenAlertIds).apply()

                    alertAdapter.notifyDataSetChanged()
                    updateFeedVisibility()
                    updateStatusText("CONNECTED", StatusType.CONNECTED)
                    tvTelemetryStatus.text = "Last synced: $currentTime | HTTP 200 OK (${alerts.size} alerts, $newAlertCount new)"
                }

                is FetchResult.Error -> {
                    updateStatusText("OFFLINE", StatusType.ERROR)
                    tvTelemetryStatus.text = "Last sync failed at $currentTime: ${result.message}"
                }
            }
        }
    }

    private fun fetchAlertsFromUrl(urlStr: String): FetchResult {
        var connection: HttpURLConnection? = null
        return try {
            val url = URL(urlStr)
            connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 4000
            connection.readTimeout = 4000
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "StormAssistant-Android/1.0")

            val responseCode = connection.responseCode
            if (responseCode in 200..299) {
                val reader = BufferedReader(InputStreamReader(connection.inputStream))
                val sb = StringBuilder()
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    sb.append(line)
                }
                reader.close()

                val responseBody = sb.toString()
                val parsed = AlertModel.parseAlerts(responseBody)
                FetchResult.Success(parsed)
            } else {
                FetchResult.Error("HTTP $responseCode: ${connection.responseMessage}")
            }
        } catch (e: Exception) {
            FetchResult.Error(e.message ?: "Connection error")
        } finally {
            connection?.disconnect()
        }
    }

    private fun simulateStormAlert() {
        val simulations = listOf(
            AlertModel(
                id = "sim_${System.currentTimeMillis()}_1",
                title = "⚡ Grid Warning: Maple Ridge Substation",
                message = "Predicted storm impact at 8:15 PM. Feeder lines 14A & 14B under heavy wind threat. Prepare backup power!",
                severity = "CRITICAL",
                substation = "Maple Ridge Substation",
                impactCustomers = 4250,
                eta = "8:15 PM"
            ),
            AlertModel(
                id = "sim_${System.currentTimeMillis()}_2",
                title = "⚠️ High Risk: Scioto Valley Transmission",
                message = "Severe thunderstorm front approaching. Voltage fluctuations detected on 138kV bus.",
                severity = "WARNING",
                substation = "Scioto Valley Station",
                impactCustomers = 2800,
                eta = "8:45 PM"
            ),
            AlertModel(
                id = "sim_${System.currentTimeMillis()}_3",
                title = "⚡ Outage Alert: Pine River Feeder 08",
                message = "Tree limb down on primary distribution circuit. Repair crew dispatched; hazardous conditions.",
                severity = "CRITICAL",
                substation = "Pine River Substation",
                impactCustomers = 1120,
                eta = "9:30 PM"
            ),
            AlertModel(
                id = "sim_${System.currentTimeMillis()}_4",
                title = "✅ Grid Restored: Oak Creek Circuit",
                message = "Automated sectionalizing restored power to 3,400 customers. All feeders energized.",
                severity = "RESTORED",
                substation = "Oak Creek Substation",
                impactCustomers = 3400,
                eta = "Restored"
            )
        )

        val selected = simulations[simulationIndex % simulations.size]
        simulationIndex++

        // Dispatch heads-up notification
        notificationHelper.showAlertNotification(selected)
        seenAlertIds.add(selected.id)
        prefs.edit().putStringSet("seen_ids", seenAlertIds).apply()

        alertList.add(0, selected)
        alertAdapter.notifyItemInserted(0)
        rvAlerts.scrollToPosition(0)
        updateFeedVisibility()

        Toast.makeText(this, "Simulated alert sent & notified!", Toast.LENGTH_SHORT).show()
    }

    private fun seedInitialAlerts() {
        if (alertList.isEmpty()) {
            val welcomeAlert = AlertModel(
                id = "init_welcome_1",
                title = "⚡ Grid Warning: Maple Ridge Substation",
                message = "Predicted storm impact at 8:15 PM. Please prepare backup power!",
                severity = "CRITICAL",
                substation = "Maple Ridge Substation",
                impactCustomers = 4250,
                eta = "8:15 PM"
            )
            alertList.add(welcomeAlert)
            seenAlertIds.add(welcomeAlert.id)
            alertAdapter.notifyDataSetChanged()
        }
        updateFeedVisibility()
    }

    private fun updateFeedVisibility() {
        tvAlertCount.text = "${alertList.size} ALERTS"
        if (alertList.isEmpty()) {
            rvAlerts.visibility = View.GONE
            layoutEmptyFeed.visibility = View.VISIBLE
        } else {
            rvAlerts.visibility = View.VISIBLE
            layoutEmptyFeed.visibility = View.GONE
        }
    }

    private fun updateStatusText(text: String, type: StatusType) {
        tvStatusText.text = text
        when (type) {
            StatusType.CONNECTED -> {
                viewStatusDot.setBackgroundResource(R.drawable.bg_status_connected)
            }
            StatusType.POLLING -> {
                viewStatusDot.setBackgroundResource(R.drawable.bg_status_polling)
            }
            StatusType.ERROR -> {
                viewStatusDot.setBackgroundResource(R.drawable.bg_status_error)
            }
            StatusType.IDLE -> {
                viewStatusDot.setBackgroundResource(R.drawable.bg_status_connected)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        stopPolling()
    }

    sealed class FetchResult {
        data class Success(val alerts: List<AlertModel>) : FetchResult()
        data class Error(val message: String) : FetchResult()
    }

    enum class StatusType {
        CONNECTED, POLLING, ERROR, IDLE
    }
}
