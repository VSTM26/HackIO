# AEP HackOHI/O 2026 AI Outage Concierge — End-to-End Demo Walkthrough

A structured, repeatable 8-step demonstration script showcasing the AI Outage Concierge system from pre-storm prediction through customer personalization, mobile alerting, labor-grounded restoration, and grid re-energization.

---

## Quick Launch Checklist

Ensure the background services are active:
1. **Simulator & Customer Portal**: `http://localhost:8000` (FastAPI / Uvicorn)
   - Customer Concierge: [http://localhost:8000/customer](http://localhost:8000/customer)
   - Operator Control Center: [http://localhost:8000/operator](http://localhost:8000/operator)
   - Public Threat Board: [http://localhost:8000/user](http://localhost:8000/user)
   - Android APK Download: [http://localhost:8000/download-apk](http://localhost:8000/download-apk)
2. **Streamlit Analytics Dashboard**: [http://localhost:8501](http://localhost:8501)

---

## The 8-Step Customer Journey Demonstration

### Step 1: Pre-Storm Monitoring & Baseline Health
1. Open the **Operator Control Center** at `http://localhost:8000/operator`.
2. Notice the active data source: **Verified AEP Challenge Dataset (Circuit 0000027, Elliston / Salem, VA)**.
3. Observe the storm center tracking across the region. All distribution feeders and transformers begin in **NORMAL SERVICE** state.
4. Open the **Customer Portal** in a side-by-side tab at `http://localhost:8000/customer`.
5. Select customer premise `PREM-VA-58784` (Life Support Customer, Overhead service).
   - **Operational Fact**: Power is flowing normally; voltage within nominal thresholds.
   - **Priority Tier**: Tier 1: Life Support Emergency (Medical Priority registered).
   - **Upstream Dependency Status**: All upstream devices (fuses, electronic reclosers, circuit breakers) verified closed and energized.

---

### Step 2: Explainable Outage Risk Forecast
1. On the **Customer Portal**, review the **Outage-Risk Assessment** card:
   - **Risk Score & Band**: Calculated live based on storm proximity ($d \le \text{radius}$ vs $d \le 2.2 \times \text{radius}$), wind gust velocity, and asset construction.
   - **Confidence Level**: High Confidence (based on direct radar envelope alignment).
2. Review the **Key Contributing Signals**:
   - Explicitly notes: *Overhead distribution service exposed to surrounding tree canopy and flying debris*.
   - Explicitly notes: *Power flows through upstream protective devices on the supply path*.
3. Contrast with an **Underground Premise**:
   - In the Quick Picks, click `PREM-VA-57282` (Underground Feeder).
   - Observe how the risk score immediately drops by ~85%:
     * *Underground electrical service shields equipment from falling branches and high winds*.
     * Confirms transparent physical vulnerability heuristics rather than fabricated black-box predictions.

---

### Step 3: Storm Progression & Proactive Warning Trigger
1. Return to the **Operator Control Center** (`/operator`).
2. Scrub the **Storm Progress Slider** forward or click **▶ Play Along Path**.
3. As the storm wind envelope intersects the distribution circuit:
   - The Public Board (`/user`) flashes amber with an **APPROACHING THREAT** alert.
   - The notification engine evaluates throttle rules and consent:
     * Dispatches automated `predicted_hit` alert to eligible premises.
     * Mobile app receives: `⚡ PREPARE: Elliston Feeder in Storm Path around 8:45 PM. Please prepare backup power and charge medical devices.`
4. In the Customer Portal, observe the **Personalized Actions** checklist:
   - For life-support premise `PREM-VA-58784`:
     * *Medical Priority Alert: Verify backup oxygen/battery power systems are fully charged.*
     * *Have emergency caregiver and regional utility priority contact numbers on hand.*

---

### Step 4: Asset Fault Injection & Network Dependency Trip
1. In the **Interactive Scenario Controls** (at the top of `/customer` or in `/operator`):
   - Click **Blow Upstream Fuse** or **Damage Transformer**.
2. Immediately observe the cascaded network reaction:
   - Operational Status shifts to **OUTAGE CONFIRMED** (Red status badge).
   - Upstream Supply Hierarchy updates:
     * `1 upstream distribution asset(s) faulted on supply path. Must be repaired and energized before customer service can be safely restored.`
   - Demonstrates strict electrical topology from `matched_upstream.txt`: customer restoration is mathematically blocked until the upstream spine is cleared.

---

### Step 5: Labor-Grounded Restoration Range (ETR)
1. On the Customer Portal, examine the **Estimated Restoration (ETR)** card:
   - Shows a transparent, bounded interval: **Earliest**, **Most Likely**, and **Latest** restoration times.
2. Review the **Labor Unit Breakdown** (grounded in `Install_Labor_HackOHIO.xlsx`):
   - **Direct Compatible Unit (CU) Hours**: Unit install/remove rates for pole, transformer, and cutout hardware.
   - **Indirect Labor Multiplier (ILM = 4.5x)**: Explicitly explains the 4.5x multiplier applied for drive time, site setup, and tailboard safety briefings.
   - **Access Adders**: Incorporates confined property / backyard access adders (+0.5h direct).
3. Review the **Assumptions & Missing Information** section:
   - Clearly states what is known (field damage ticket registered) vs uninspected (subsurface soil conditions, gate obstructions).

---

### Step 6: Dynamic Scenario Tuning (Crew Dispatch & Access)
1. On the scenario bar, change **Crews** from `1 Crew` to `3 Crews`.
2. Notice the restoration calculation dynamically update in real time:
   - Field labor hours are re-scheduled with realistic multi-crew coordination efficiency.
   - The Most Likely restoration time shifts earlier.
   - Both the Customer Portal and Operator Display update instantaneously via WebSockets without page reload.

---

### Step 7: Android Mobile Notification Verification
1. Open the native Android app (installed via `StormAlert.apk`) or test via the mobile polling endpoint:
   - `GET http://localhost:8000/api/alerts/poll?since_id=0`
2. Notice the structured alert payload:
   - Unique event UUID for deduplication across restarts.
   - Clean title, body text, and ETA in minutes.
   - Immediate heads-up system notification with vibration and sound.
3. In the Customer Portal, check **Recent Notifications**:
   - Verifies the audit trail of all messages sent to that specific premise.

---

### Step 8: Grid Repair, Switching & Feeder Energization
1. Click **Restore & Energize** on the scenario controls.
2. Observe the full system transition:
   - Active damage tickets are cleared.
   - Upstream reclosers and switches are verified closed.
   - Power status transitions back to **NORMAL SERVICE** (Green).
   - Restoration card updates: `Service Operational — All Upstream Assets Energized`.
   - Dispatch logs record a final `power_restored` confirmation message.
3. Switch to the **Streamlit Dashboard** (`http://localhost:8501`) to view the complete replay audit log, asset tree status, and historical timeline scrubbing.
