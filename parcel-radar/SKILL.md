---
name: parcel-radar
description: Look up property/parcel information for addresses in King County, WA using public GIS and Assessor APIs. Use when the user asks about property details, assessed values, tax info, parcel numbers, lot size, or building details for any address in King County (Seattle, Bellevue, Kirkland, Redmond, etc.).
---

# Parcel Radar - King County Property Lookup

## Workflow

### Step 1: Geocode Address to Parcel PIN

Use WebFetch to call the King County GIS Geocode service:

```
https://gismaps.kingcounty.gov/arcgis/rest/services/Address/KingCo_ParcelAddress_locator/GeocodeServer/findAddressCandidates?SingleLine={URL_ENCODED_ADDRESS}&outFields=*&f=json
```

- URL-encode the full address (e.g., `1201+NE+124th+St+Seattle+WA`)
- Extract the `PIN` field from the response attributes
- Verify `Score` is 100 or near 100 for confidence

### Step 2: Fetch Property Details from eRealProperty

Use the PIN from Step 1 to query the King County Assessor's eRealProperty system:

```
https://blue.kingcounty.com/Assessor/eRealProperty/Dashboard.aspx?ParcelNbr={PIN}
```

Extract:
- Building details: year built, sq ft, bedrooms, bathrooms, grade, condition
- Lot size
- Sales history

### Step 3: Zoning Lookup via GIS

Use the `location.x` and `location.y` coordinates from the Step 1 geocoder response (State Plane, WKID 2926) to query two zoning layers **in parallel**:

**Layer 0 — Incorporated Areas** (returns which city the parcel is in):
```
https://gismaps.kingcounty.gov/arcgis/rest/services/Planning/KingCo_Zoning/MapServer/0/query?geometry={X},{Y}&geometryType=esriGeometryPoint&inSR=2926&spatialRel=esriSpatialRelIntersects&outFields=*&f=json
```
- If features returned → parcel is in an **incorporated city** (e.g., Kenmore, Bellevue)
- Extract `CITYNAME` and `JURIS` code

**Layer 1 — King County Zoning** (unincorporated areas only):
```
https://gismaps.kingcounty.gov/arcgis/rest/services/Planning/KingCo_Zoning/MapServer/1/query?geometry={X},{Y}&geometryType=esriGeometryPoint&inSR=2926&spatialRel=esriSpatialRelIntersects&outFields=*&f=json
```
- If features returned → parcel is in **unincorporated King County**
- Extract `CURRZONE` (current zone code) and `POTENTIAL`

**Interpretation logic:**
- Layer 0 hit + Layer 1 empty → incorporated city, zoning managed by city
- Layer 0 empty + Layer 1 hit → unincorporated KC, show `CURRZONE`
- Both empty → zoning data not available

### Step 4: Present Results

Format as a structured table with sections:
1. Building details (year built, sq ft, beds/baths, etc.)
2. Zoning (zone code or city jurisdiction + link)
3. Sales history

## Additional API Endpoints

For advanced queries, see [references/api_endpoints.md](references/api_endpoints.md).

## Notes

- All data comes from King County's public GIS and Assessor systems
- This skill covers **King County, WA only** (Seattle, Bellevue, Kirkland, Redmond, Renton, etc.)
- The parcel viewer UI at `gismaps.kingcounty.gov/parcelviewer2/` is a dynamic app and cannot be scraped via WebFetch - always use the API endpoints instead
- If the geocode returns no results, try variations of the address (abbreviations, spelling)
