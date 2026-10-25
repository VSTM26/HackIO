# AEP Challenge Data Ingestion & Quality Audit Report

**AEP HackOHI/O 2026 AI Outage Concierge Challenge**  
*Processed: Verified Challenge Datasets*

---

## 1. Raw Dataset Summary & Record Counts

| Dataset Archive | Layer / File | Raw Record Count | Coordinate System | Notes |
|---|---|---|---|---|
| `Data1.zip` | `Customer_Clip.shp` | 117,642 | WGS84 (EPSG:4326) | Service points with circuit, transformer & life support flags |
| `Data1.zip` | `Hospitals_Medic_Pairwis_Clip.shp` | 5 | Web Mercator (EPSG:3857) | Converted to WGS84 |
| `Data1.zip` | `Fire_Stations_E_Pairwis_Clip.shp` | 37 | Web Mercator (EPSG:3857) | Converted to WGS84 |
| `Data1.zip` | `arcos_prod_damage_09_28_Clip.shp` | 1,659 | WGS84 (EPSG:4326) | Helene damage reports (APCO district) |
| `Data2.zip` | `Transformer_Clip.shp` | 26,959 | WGS84 (EPSG:4326) | Distribution transformers with kVA sizing |
| `matched_upstream.zip` | `matched_upstream.txt` | 117,599 | N/A (Graph Topology) | Tab-delimited variable-length upstream chain |
| `Install_Labor_HackOHIO.xlsx` | 5 Sheets | 96 CNC, 90 CUs | N/A (Labor Workbook) | Baseline CUs + 4.5 Indirect Labor Multiplier |

---

## 2. Coordinate Transformation & Normalization

- **Issue**: Public safety shapefiles (`Hospitals`, `Fire_Stations`, `Ambulance`) were projected in **Web Mercator (EPSG:3857)** with meter coordinates (e.g., `X = -8917822.98, Y = 4493825.75`), while electrical network shapefiles (`Customer_Clip`, `Transformer_Clip`, `arcos_prod_damage`) were in **WGS84 (EPSG:4326)** latitude/longitude.
- **Normalization**: Applied exact spherical Mercator inverse projection math:
  $$\text{lon} = \left(\frac{X}{20037508.34}\right) \times 180^\circ$$
  $$\text{lat} = \frac{180^\circ}{\pi} \left(2 \arctan\left(\exp\left(\frac{Y \pi}{20037508.34}\right)\right) - \frac{\pi}{2}\right)$$
- **Total coordinates normalized**: **15** critical facilities successfully reprojected to Roanoke/Salem geographic coordinates (~37.25°N, -80.11°W).

---

## 3. Curated Circuit 0000027 Demonstration Slice

- **Target Circuit**: Circuit `0000027` (Elliston / Salem / Roanoke, VA)
- **Premises Ingested**: **1,166**
- **Upstream Topology Match Rate**: **100.0%** (Every premise has a verified upstream dependency chain to its service transformer, protective reclosers/fuses, and circuit breaker).
- **Service Construction Types**:
  - Overhead: **776** premises (tree fall & wind gust exposure)
  - Underground: **390** premises (high storm resilience)
- **Life Support / Medical Priority Customers**: **4** verified LS premises.

---

## 4. Privacy & Anonymization Safeguards

1. **Premise Identifiers**: Raw premise numbers are masked to anonymized tokens (e.g. `PREM-VA-57282`) for customer-facing interfaces.
2. **Customer Names & Contact Details**: No customer names, phone numbers, or billing data are ingested or exposed.
3. **Street Addresses**: Exact house numbers are removed; customer responses only reference general city/region (`Elliston, VA`) and feeder segment.
4. **Facility Security**: Critical infrastructure coordinates are generalized to public emergency responder zones.
