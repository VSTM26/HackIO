# AEP HackOHI/O 2026 AI Outage Concierge — Solution Architecture & Technical Documentation

**AEP Challenge**: HackOHI/O 2026 AI Outage Concierge  
**Repository**: `AEP_Project/storm-assistant`  
**Mobile Application**: `android_app` (`StormAlert.apk`)  
**Status**: Fully Implemented, Integrated, and Verified (192 Passing Tests)

---

## 1. Executive Summary

During major storm events, electric utility customers experience anxiety, lack of actionable preparation information, and uncertainty regarding when power will return. Utilities often struggle to balance engineering realities with customer communication.

The **AEP AI Outage Concierge** delivers an end-to-end, trustworthy customer experience powered by:
1. **Verified Official Challenge Data**: Real electrical infrastructure layers (`Customer_Clip`, `Transformer_Clip`, `arcos_prod_damage`, `matched_upstream.txt`) and labor standards (`Install_Labor_HackOHIO.xlsx`).
2. **Honest, Explainable Outage Risk**: Physics-informed vulnerability heuristics that transparently separate risk magnitude from confidence, incorporate overhead vs underground construction resilience, and provide explicit fallback when data is insufficient.
3. **Labor-Grounded Restoration (ETR)**: Estimated Time of Restoration grounded directly in standard utility Compatible Units (CUs), the official **4.5x Indirect Labor Multiplier (ILM)**, access adders, and upstream dependency sequencing.
4. **Dedicated Customer Portal (`/customer`)**: An intuitive, accessible customer experience that distinguishes confirmed operational facts, model estimates, and personalized actions.
5. **Real-Time Multi-Platform Simulation & Alerting**: Operator Control Center (`/operator`), Public Threat Monitor (`/user`), and a native Android application (`StormAlert.apk`) receiving real-time heads-up alerts.

---

## 2. Ingestion & Data Architecture

The ingestion pipeline (`data/challenge/ingest.py`) processes the official challenge datasets reproducibly without modifying raw archives:

```
AEP_Project/storm-assistant/data/challenge/
├── raw/
│   ├── Data1.zip                   # Customer_Clip, Hospitals, Fire, ARCOS damage, Fuses
│   ├── Data2.zip                   # Transformer_Clip, Reclosers, Switches
│   ├── matched_upstream.zip        # matched_upstream.txt (117,599 topological chains)
│   └── Install_Labor_HackOHIO.xlsx # Standard CU labor hours & 4.5 ILM multiplier
├── curated_demo_grid.json          # Curated slice for Circuit 0000027 (Elliston / Salem, VA)
├── INGESTION_REPORT.md             # Comprehensive data quality audit
├── labor_model.py                  # Official labor workbook parsing engine
└── ingest.py                       # Ingestion & coordinate normalization pipeline
```

### Coordinate Normalization (EPSG:3857 -> EPSG:4326)
- **Problem**: Public safety layers (`Hospitals_Medic_Pairwis_Clip`, `Fire_Stations_E_Pairwis_Clip`, `Ambulance_Servi_Pairwis_Clip`) were projected in **Web Mercator (EPSG:3857)** in meter coordinates (e.g., $X = -8917822.98, Y = 4493825.75$), whereas electrical network shapefiles were in **WGS84 (EPSG:4326)** latitude/longitude.
- **Solution**: The ingestion engine applies exact spherical Mercator inverse projection math:
  $$\text{lon} = \left(\frac{X}{20037508.34}\right) \times 180^\circ$$
  $$\text{lat} = \frac{180^\circ}{\pi} \left(2 \arctan\left(\exp\left(\frac{Y \pi}{20037508.34}\right)\right) - \frac{\pi}{2}\right)$$
  Successfully normalizing hospital and emergency response coordinates to the Roanoke/Salem geographic area (~37.25°N, -80.11°W).

### Topological Dependency Parsing
- `matched_upstream.txt` contains 117,599 variable-length upstream supply paths:
  $$\text{Premise} \rightarrow \text{Transformer} \rightarrow \text{Isolating Devices (Fuses/Reclosers)} \rightarrow \text{Circuit Breaker / Substation}$$
- For target Circuit `0000027`, **1,166 out of 1,166 premises (100.0%)** matched their upstream dependency chain.
- Electrical connectivity is determined strictly by verified equipment identifiers, never inferred solely from geographic proximity.

### Privacy Safeguards
- **Zero PII Exposure**: Customer names, phone numbers, and exact street numbers are excluded from customer-facing payloads.
- **Anonymized Identifiers**: Premise identifiers are masked to anonymized tokens (e.g., `PREM-VA-58784`).
- **Generalized Locations**: Responses reference neighborhood feeder zones and city regions (`Elliston, VA`), preventing exposure of sensitive facility coordinates.

---

## 3. Honest & Explainable Outage Risk Model

Located in `analytics/predictive/grounded_risk.py`.

### Methodology & Transparency
- **No False Claims**: The project explicitly documents that `train.py` is a synthetic benchmark testing harness, not trained or calibrated on real historical outcomes. In real utility operations, storm damage tickets (ARCOS) do not provide negative non-outage controls or uniform telemetry across all circuits.
- **Physical Vulnerability Heuristic**: Risk is calculated using observable, defensible signals:
  1. **Geospatial Proximity**:
     - Direct Hit Envelope ($d \le \text{radius}$): maximum exposure.
     - Peripheral Watch Envelope ($d \le 2.2 \times \text{radius}$): linear decay function.
     - Outside Envelope ($d > 2.2 \times \text{radius}$): baseline ambient risk ($\le 0.05$).
  2. **Wind Gust Intensity**:
     - $< 35\text{ mph}$: light sway, low hazard.
     - $35 - 50\text{ mph}$: limb-break threshold, moderate hazard.
     - $> 50\text{ mph}$: severe structural pole & conductor stress.
  3. **Construction Type Resilience**:
     - Overhead (`kind_of_se == 'Overhead'`): full vulnerability to falling branches and wind sway.
     - Underground (`kind_of_se == 'Underground'`): ~85% reduction in storm-induced faults.
  4. **Upstream Equipment Depth**:
     - Series protective equipment depth multiplier: more upstream devices increase the statistical likelihood of trip events along the supply spine.
  5. **Separation of Magnitude and Confidence**:
     - High risk score does not imply high confidence. Confidence is determined by distance certainty and radar alignment.
  6. **Explicit Insufficient-Data Fallback**:
     - If premise coordinates or storm trajectory are missing, the engine returns an explicit `insufficient_data` state with an actionable explanation, never returning a fabricated score.

---

## 4. Labor-Grounded Restoration Model (ETR)

Located in `data/challenge/labor_model.py` and `analytics/predictive/labor_etr.py`.

Grounded directly in the official challenge workbook `Install_Labor_HackOHIO.xlsx`:

### Compatible Unit (CU) Direct Labor
- **Poles**: Small (2.706h), Medium (3.430h), Large (4.521h).
- **Transformers**: 10-25 kVA (1.994h), 50 kVA (2.136h), 100 kVA (2.224h).
- **Protective Cutouts & Switches**: Fuse Cutout (0.384h), Recloser (1.098h), Switch (2.768h).
- **Structural**: Crossarms (0.586h), Brackets (0.871h), Anchors (0.516h).

### Indirect Labor Multiplier (ILM = 4.5x)
As mandated by AEP:
$$\text{Total Labor Hours} = (\text{Direct CU Hours} + \text{Access Adders}) \times 4.5$$
Accounting for drive time, site staging, hazard mitigation, tailboard safety meetings, and switching coordination.

### Access Adders
- Backyard Confined Property Access: $+0.5\text{h}$
- Off-Road / Track Access: $+0.5\text{h}$
- Remote Location Adder: $+1.312\text{h}$
- Manual Excavation (Hand Dig): $+1.5\text{h/cu ft}$
- Difficult Excavation (Rock Hole): $+4.0\text{h/cu ft}$

### Upstream Network Dependency Rule
A customer premise cannot be energized until:
1. The customer's direct service drop/meter is intact.
2. The customer's distribution transformer is energized.
3. All upstream protective devices (fuses, reclosers, switches) and the circuit breaker are closed.

If an upstream device fails, repair sequencing enforces upstream repairs before downstream re-energization can occur.

---

## 5. Customer Experience (`/customer`)

The customer portal is designed to provide clear, accessible, and actionable information:

1. **Confirmed Operational Facts**:
   - Current power status with accessible visual badges (not relying only on color).
   - Priority tier (Tier 1: Life Support Emergency vs Tier 2: Standard Residential).
   - Upstream electrical supply hierarchy status in plain language.
2. **Explainable Outage Risk**:
   - Risk band and percentage gauge.
   - Confidence assessment.
   - Bulleted list of contributing physical signals.
   - Sensitivity analysis ("What could change this assessment").
3. **Labor-Grounded Restoration Bounds**:
   - Earliest, Most Likely, and Latest restoration times.
   - Itemized labor hours breakdown (CU hours, 4.5x ILM, crew allocation).
   - Transparent assumptions and missing site information.
4. **Personalized Preparation Checklist**:
   - Medical priority alerts for life-support customers (oxygen backup battery checks, utility emergency lines).
   - Food safety guidance and communication backup recommendations.
5. **Alert Eligibility & Audit Trail**:
   - Consent status, quiet hours exemption rules, and throttle safeguards.
   - Audit history of recent alerts dispatched to this premise.

---

## 6. Dual-Display Simulator & Mobile Android APK

### Real-time Multi-Interface Architecture
- **Operator Control Center (`/operator`)**: Interactive Leaflet map with storm path drawing, velocity/gust controls, and real-time asset threat monitoring.
- **Public Threat Board (`/user`)**: Full-screen public display with high-contrast emergency banners and approaching threat countdowns.
- **Customer Portal (`/customer`)**: Focused, mobile-responsive customer interface.
- **WebSocket Synchronization (`/ws`)**: All client displays synchronize instantly when storms advance or damage tickets are injected.
- **Native Android APK (`StormAlert.apk`)**: Standalone Android application built with AGP and Gradle, featuring `POST_NOTIFICATIONS`, high-priority heads-up notification channels, vibration, and background API polling (`/api/alerts/poll`).

---

## 7. Verification & Test Suite Summary

The test suite contains **192 passing tests**:

```
=========================== short test summary info ===========================
PASSED tests/test_challenge_ingestion.py::test_mercator_to_wgs84_reprojection
PASSED tests/test_challenge_ingestion.py::test_challenge_pipeline_runs_and_verifies
PASSED tests/test_grounded_risk.py::test_haversine_distance
PASSED tests/test_grounded_risk.py::test_overhead_vs_underground_risk_differential
PASSED tests/test_grounded_risk.py::test_distance_decay_and_confidence
PASSED tests/test_grounded_risk.py::test_insufficient_data_fallback
PASSED tests/test_labor_etr.py::test_labor_model_cu_hours_and_ilm_multiplier
PASSED tests/test_labor_etr.py::test_access_adders_applied
PASSED tests/test_labor_etr.py::test_labor_etr_upstream_dependency_resolution
PASSED tests/test_simulator_fixes.py::test_android_polling_alias
PASSED tests/test_simulator_fixes.py::test_customer_portal_routes
PASSED tests/test_simulator_fixes.py::test_multi_storm_worst_case_aggregation
PASSED tests/test_simulator_fixes.py::test_input_validation_coordinates
... [179 baseline storm replay, lifecycle, messaging, and audit tests] ...
============================= 192 passed in 4.67s =============================
```

---

## 8. Running the Application

### 1. Run Test Suite
```bash
pytest AEP_Project/storm-assistant -v
```

### 2. Start the Simulator Server
```bash
uvicorn apps.simulator.server:app --app-dir AEP_Project/storm-assistant --host 0.0.0.0 --port 8000
```
- Customer Portal: `http://localhost:8000/customer`
- Operator Simulator: `http://localhost:8000/operator`
- Public Threat Board: `http://localhost:8000/user`
- Android APK Download: `http://localhost:8000/download-apk`

### 3. Start the Streamlit Analytics Dashboard
```bash
streamlit run AEP_Project/storm-assistant/apps/web/dashboard.py --server.port 8501
```
- Streamlit UI: `http://localhost:8501`
