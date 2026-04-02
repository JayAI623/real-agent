---
name: property-full-report
description: Run a complete King County property analysis for a given address. Invokes all four property skills with parallelism — parcel-radar first, then slope_tool + kingcounty-imap in parallel, then parcel-validator — and presents a unified full report. Use when the user wants a comprehensive property deep-dive, full due diligence, or complete property report for any address in King County, WA.
---

# Property Full Report — King County Complete Analysis

## Overview

This master skill orchestrates a full property analysis using **parallel execution** to minimize total run time.

**Pipeline:**
```
        Step 1: parcel-radar          (serial — provides coords/PIN for all others)
                     |
        ┌────────────┴────────────┐
        ↓                         ↓
Step 2a: slope_tool     Step 2b: kingcounty-imap   (PARALLEL — independent of each other)
        └────────────┬────────────┘
                     ↓
        Step 3: parcel-validator      (serial — synthesizes all data, generates PDF)
```

**Expected time savings:** ~40–50% vs. sequential execution. Steps 2a and 2b run simultaneously.

---

## Execution Instructions

When this skill is invoked, follow these steps exactly.

### Step 0 — Confirm Address

Echo back the address and confirm the parallel pipeline:

> "Running full property analysis for: **[ADDRESS]**
> Pipeline: parcel-radar → [slope_tool ‖ kingcounty-imap] → parcel-validator"

---

### Step 1 — parcel-radar (serial)

Invoke the `parcel-radar` skill for the given address.

**Goal:** Establish the property baseline. This step MUST complete before Step 2 because all other skills depend on the coordinates, PIN, and city it returns.

Collect and retain:
- Parcel PIN
- Latitude / Longitude (WGS84) — **critical for Steps 2a and 2b**
- City name (normalized, e.g. "BELLEVUE", "KENMORE")
- Lot size (sq ft and acres) — use `Shape.STArea()` from KC parcel API, NOT bbox estimate
- Building sq ft, year built, bedrooms, bathrooms
- Assessed value (land + improvement + total)
- Zoning code and jurisdiction

Print when done:
```
## 1. Parcel Data (parcel-radar)
[results here]
```

---

### Step 2 — slope_tool + kingcounty-imap (PARALLEL)

Launch **both** skills simultaneously using the `Agent` tool. Send a single message with two Agent tool calls at the same time — do NOT wait for one before starting the other.

**Agent A — slope_tool:**
- Run the `slope_tool` skill for the address
- Pass the city and parcel bbox from Step 1 as context
- Goal: elevation range, contour count, max slope estimate, terrain classification

**Agent B — kingcounty-imap:**
- Run the `kingcounty-imap` skill for the address
- Pass `--lat [lat] --lon [lng]` from Step 1 to the imap_scrape.py script
- Goal: flood zone, landslide hazard, wetlands, sensitive area overlays, iMap screenshots

Wait for BOTH agents to return before proceeding to Step 3.

Print when both are done:
```
## 2. Slope & Terrain (slope_tool)
[Agent A results]

## 3. Environmental & Hazard Layers (kingcounty-imap)
[Agent B results]
```

---

### Step 3 — parcel-validator (serial)

Invoke the `parcel-validator` skill for the same address.

**Goal:** Cross-validate KC Assessor data vs. Zillow. Generate PDF report with screenshots.

Pass all data collected in Steps 1 and 2 as context — the validator should NOT re-fetch KC Assessor data it already has.

For PDF generation use **reportlab** (not WeasyPrint — WeasyPrint requires libgobject which is not available on Windows). Example:
```bash
pip install reportlab --break-system-packages -q
python3 gen_report.py
```

Print when done:
```
## 4. Data Validation vs. Zillow (parcel-validator)
[results here]
```

---

### Step 4 — Final Summary

Print a unified summary table:

```
## Full Report Summary — [ADDRESS]

| Category              | Key Finding                          |
|-----------------------|--------------------------------------|
| Parcel ID             | [PIN]                                |
| Lot Size              | [X] sq ft / [Y] acres                |
| Building              | [sqft], [beds]/[baths], built [year] |
| Assessed Value        | $[total]                             |
| Zoning                | [zone code] ([city/KC])              |
| Terrain               | [type] — [elevation range] ft relief |
| Max Slope (est.)      | ~[X]% ([Y]°)                         |
| Flood Zone            | [FEMA zone]                          |
| Landslide Hazard      | [Yes/No/Moderate]                    |
| Wetlands / Sensitive  | [Yes/No]                             |
| Zillow Data Match     | [Match / Discrepancies found]        |
| PDF Report            | [path]                               |
```

Call out any **red flags** explicitly if: slope > 40%, flood zone AE/VE, landslide hazard present, sensitive area notice on title, non-residential zoning, or >30% discrepancy in assessed value.

---

## Error Handling

- If any individual skill fails, log the error under that section header and continue. Do not abort the pipeline.
- If Step 1 (parcel-radar) fails to geocode, stop immediately and ask the user to verify the address — all other steps depend on it.
- If one of the parallel agents (Step 2) fails, still wait for the other before proceeding to Step 3.

---

## Notes

- All data sources are public King County GIS and Assessor APIs — no API key required.
- This skill covers **King County, WA only**.
- Lot size: always use `Shape.STArea()` from the KC parcel API. Never use bbox approximation — it overestimates.
- PDF generation: use **reportlab** on Windows. WeasyPrint requires libgobject and will fail.
- Total pipeline time with parallelism: ~2–3 min (vs. ~4–5 min sequential).
