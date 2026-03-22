---
name: parcel-radar
description: Look up property/parcel information for addresses in King County, WA using public GIS and Assessor APIs. Use when the user asks about property details, assessed values, tax info, parcel numbers, lot size, owner info, or building details for any address in King County (Seattle, Bellevue, Kirkland, Redmond, etc.).
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
- Owner name
- Assessed values: land, improvement, total
- Building details: year built, sq ft, bedrooms, bathrooms, grade, condition
- Lot size
- Tax info: levy rate, levy code, tax year
- Other: waterfront, views, zoning

### Step 3: Present Results

Format as a structured table with sections:
1. Basic info (parcel number, owner, address)
2. Assessed values (land, improvement, total)
3. Building details (year built, sq ft, beds/baths, etc.)
4. Tax information
5. Value trend if historical data is available

## Additional API Endpoints

For advanced queries, see [references/api_endpoints.md](references/api_endpoints.md).

## Notes

- All data comes from King County's public GIS and Assessor systems
- This skill covers **King County, WA only** (Seattle, Bellevue, Kirkland, Redmond, Renton, etc.)
- The parcel viewer UI at `gismaps.kingcounty.gov/parcelviewer2/` is a dynamic app and cannot be scraped via WebFetch - always use the API endpoints instead
- If the geocode returns no results, try variations of the address (abbreviations, spelling)
