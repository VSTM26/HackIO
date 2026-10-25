# AEP HackOHI/O 2026 — AI Outage Concierge

**Team**: Jace Joseph, Atharva Sati, Shaun Thomas, Teja Mathukumalli  
**Challenge**: AEP AI Outage Concierge (HackOHI/O 2026)  
**Status**: Fully Integrated & Verified (**192 Passing Tests**)

---

## ⚡ Overview

The **AEP AI Outage Concierge** is an end-to-end, multi-platform storm outage management and customer communication system designed for electric utilities. Grounded in official AEP engineering datasets, standard Compatible Unit (CU) labor workbooks, and electrical topology dependencies, it bridges the gap between field engineering realities and empathetic, transparent customer communication.

### 🌟 Key Capabilities
- **Dedicated Customer Portal (`/customer`)**: Anonymized premise search, live power status, explainable outage-risk band and confidence, labor-grounded restoration range (ETR), upstream dependency explanations, and personalized preparation checklists.
- **Operator Control Center (`/operator`)**: Interactive Leaflet GIS map with storm path drawing, velocity controls, real-time grid asset monitoring, and scenario damage injection.
- **Public Threat Display (`/user`)**: Real-time high-contrast monitor with storm trajectory countdowns and grid advisory alerts.
- **Native Android Mobile App (`android_app`)**: Standalone Android application receiving real-time heads-up emergency notifications and outage alerts.
- **Labor-Grounded Restoration Model**: Direct implementation of AEP's `Install_Labor_HackOHIO.xlsx` with standard Compatible Units (poles, transformers, cutouts), access adders (backyard, off-road, hand-dig), and the official **4.5x Indirect Labor Multiplier (ILM)**.
- **Official Data Ingestion Pipeline**: 100.0% topological match on Circuit `0000027` (Roanoke / Elliston, VA) linking premises to transformers, reclosers, fuses, and circuit breakers, with Web Mercator (EPSG:3857) to WGS84 (EPSG:4326) coordinate normalization.

---

## 🚀 Quick Start Guide

### 1. Run the Test Suite (192 Tests)
```bash
pytest AEP_Project/storm-assistant -v
```

### 2. Launch the Outage Concierge Simulator Server
```bash
uvicorn apps.simulator.server:app --app-dir AEP_Project/storm-assistant --host 0.0.0.0 --port 8000
```
- **Customer Portal**: [http://localhost:8000/customer](http://localhost:8000/customer)
- **Operator Simulator**: [http://localhost:8000/operator](http://localhost:8000/operator)
- **Public Threat Board**: [http://localhost:8000/user](http://localhost:8000/user)
- **Direct APK Download**: [http://localhost:8000/download-apk](http://localhost:8000/download-apk)

### 3. Launch the Streamlit Analytics Dashboard
```bash
streamlit run AEP_Project/storm-assistant/apps/web/dashboard.py --server.port 8501
```
- **Dashboard UI**: [http://localhost:8501](http://localhost:8501)

### 4. Install the Android Mobile App
Download [`StormAlert.apk`](StormAlert.apk) and install on any Android 8.0+ device to receive real-time storm warnings and grid outage alerts.

---

## 📚 Project Documentation

- **[Demo Walkthrough Script](AEP_Project/storm-assistant/docs/DEMO_WALKTHROUGH.md)**: 8-stage step-by-step demonstration journey.
- **[Challenge Solution Architecture](AEP_Project/storm-assistant/docs/CHALLENGE_SOLUTION.md)**: Complete technical specification, risk model heuristics, and labor restoration math.
- **[Data Ingestion Quality Report](AEP_Project/storm-assistant/data/challenge/INGESTION_REPORT.md)**: Audit of record counts, coordinate transforms, and privacy safeguards.
- **[Integration Report](AEP_Project/storm-assistant/INTEGRATION_REPORT.md)**: Details on merged modules, SMS guardrails, and lifecycle states.
