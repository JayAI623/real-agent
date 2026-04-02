---
name: slope_contour
description: "Use this skill when the user provides a property address in King County, WA and asks about lot topography, slope, grade, steepness, contour lines, elevation, or terrain. Triggers: 'what's the slope', 'check the grade', 'look up contours', 'is this lot flat or hilly', 'terrain analysis', or any mention of GIS contour lookup for a specific address. This skill geocodes the address, fetches the parcel boundary, queries city-level 2ft contour data (preferred) or King County 5ft contour data (fallback), then produces a slope assessment with visualized contour output."
---

# Slope & Contour Analysis for King County Properties

## Overview

Given a property address in King County WA, this skill:
1. Geocodes the address → gets lat/lng + parcel polygon
2. Detects which city the parcel is in
3. Queries that city's 2ft contour FeatureLayer (preferred) or falls back to King County 5ft
4. Extracts all contour lines that intersect the parcel
5. Computes elevation range, estimated max slope, and terrain characterization
6. Reports findings in a structured format with a contour map image link

---

## Step 1 — Geocode Address + Get Parcel

Use King County's parcel API (no API key required):

```python
import requests, json

def geocode_and_get_parcel(address: str) -> dict:
    """
    Returns: {
        "lat": float, "lng": float,
        "city": str,        # e.g. "KIRKLAND", "BELLEVUE", "SAMMAMISH"
        "parcel_id": str,
        "parcel_wkt": str,  # WKT polygon in WGS84
        "bbox": [xmin, ymin, xmax, ymax]  # WGS84
    }
    """
    # Step 1a: Geocode via King County Assessor address search
    geocode_url = "https://gismaps.kingcounty.gov/arcgis/rest/services/Address/KingCo_Address/GeocodeServer/findAddressCandidates"
    params = {
        "SingleLine": address,
        "outFields": "Ref_ID,City",
        "outSR": 4326,
        "f": "json",
        "maxLocations": 1
    }
    r = requests.get(geocode_url, params=params, timeout=15)
    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError(f"Address not found: {address}")
    
    best = candidates[0]
    lat = best["location"]["y"]
    lng = best["location"]["x"]
    city = best["attributes"].get("City", "").upper().strip()
    parcel_id = best["attributes"].get("Ref_ID", "")
    
    # Step 1b: Get parcel polygon from King County Parcel FeatureLayer
    parcel_url = "https://gismaps.kingcounty.gov/arcgis/rest/services/Districts/KingCo_Districts/MapServer/40/query"
    parcel_params = {
        "geometry": json.dumps({"x": lng, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "PIN,MAJOR,MINOR,SITUSADDR,SITUSCITY",
        "returnGeometry": True,
        "outSR": 4326,
        "f": "json"
    }
    r2 = requests.get(parcel_url, params=parcel_params, timeout=15)
    parcel_data = r2.json()
    features = parcel_data.get("features", [])
    if features:
        feat = features[0]
        attrs = feat["attributes"]
        city = attrs.get("SITUSCITY", city).upper().strip()
        parcel_id = attrs.get("PIN", parcel_id)
        rings = feat["geometry"]["rings"]
        # Compute bbox
        all_x = [pt[0] for ring in rings for pt in ring]
        all_y = [pt[1] for ring in rings for pt in ring]
        bbox = [min(all_x), min(all_y), max(all_x), max(all_y)]
        # Build simple WKT for reference
        ring0 = rings[0]
        coords_str = ", ".join(f"{pt[0]} {pt[1]}" for pt in ring0)
        parcel_wkt = f"POLYGON(({coords_str}))"
    else:
        # Fallback: use 500ft buffer bbox around point
        delta = 0.001  # ~100m
        bbox = [lng - delta, lat - delta, lng + delta, lat + delta]
        parcel_wkt = None
    
    return {
        "lat": lat, "lng": lng,
        "city": city,
        "parcel_id": parcel_id,
        "parcel_wkt": parcel_wkt,
        "bbox": bbox
    }
```

**IMPORTANT**: If the King County geocoder fails (returns no candidates), fall back to the Nominatim geocoder:
```python
nom_url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(address)}&format=json&limit=1&countrycodes=us"
```

---

## Step 2 — Select Contour Data Source

Based on `city` from Step 1, pick the appropriate GIS endpoint.

### Priority 1 — City-level 2ft contours (preferred)

| City | ArcGIS REST FeatureLayer URL | Layer ID | Coord System | Notes |
|------|------------------------------|----------|--------------|-------|
| KIRKLAND | `https://maps.kirklandwa.gov/host/rest/services/TPO_cont2ft_cart/MapServer/0` | 0 | 2285 (WA State Plane N, ft) | Confirmed public |
| SAMMAMISH | `https://maps.sammamishwa.gov/arcgis/rest/services/mapServices/Contours/MapServer/0` | 0 | 2926 (WA State Plane S, ft) | Confirmed public |
| BELLEVUE | See dynamic discovery below | — | 4326 | ArcGIS Online hosted |
| REDMOND | Use King County fallback | — | — | No confirmed public REST |
| BOTHELL | Use King County fallback | — | — | No confirmed public REST |

#### Bellevue 2ft Contour — Dynamic Discovery

Bellevue's 2ft contour layer is hosted on ArcGIS Online (`cobgis.maps.arcgis.com`) via their Open Data portal, not on their internal GIS server. The FeatureServer URL follows the pattern for ArcGIS Online hosted feature layers. At runtime, discover it as follows:

```python
def get_bellevue_contour_url() -> str | None:
    """
    Attempts to find Bellevue's 2ft contour FeatureServer URL.
    Returns the query URL if found, None if not accessible.
    """
    # Method 1: Try ArcGIS Online search API for cobgis org
    search_url = "https://www.arcgis.com/sharing/rest/search"
    params = {
        "q": 'title:"Contour" owner:cobgis orgid:G6Aa3DqJB0OHaKhA type:"Feature Service"',
        "num": 10,
        "f": "json"
    }
    try:
        r = requests.get(search_url, params=params, timeout=10)
        results = r.json().get("results", [])
        for item in results:
            title = item.get("title", "").lower()
            if "2" in title and "contour" in title:
                item_id = item["id"]
                # FeatureServer URL pattern for ArcGIS Online
                return f"https://services.arcgis.com/G6Aa3DqJB0OHaKhA/arcgis/rest/services/{item.get('name','')}/FeatureServer/0/query"
    except Exception:
        pass

    # Method 2: Try known Bellevue Open Data FeatureServer patterns
    # Bellevue Open Data uses the cobgis ArcGIS Online org
    # Their contour datasets are published as hosted feature layers
    candidate_urls = [
        # These item IDs are based on Bellevue Open Data portal patterns
        "https://services.arcgis.com/G6Aa3DqJB0OHaKhA/arcgis/rest/services/Contour_2_ft/FeatureServer/0/query",
        "https://services.arcgis.com/G6Aa3DqJB0OHaKhA/arcgis/rest/services/Topographic_Contours_2ft/FeatureServer/0/query",
        # Try gis-web.bellevuewa.gov internal server (may be blocked externally)
        "https://gis-web.bellevuewa.gov/gisext/rest/services/Topo/Contours/MapServer/0/query",
        "https://gis-web.bellevuewa.gov/gisext/rest/services/Enterprise/Topo/MapServer/0/query",
    ]
    for url in candidate_urls:
        try:
            test_params = {"where": "1=1", "resultRecordCount": 1, "f": "json"}
            r = requests.get(url, params=test_params, timeout=8)
            data = r.json()
            if "features" in data or "error" not in data:
                return url
        except Exception:
            continue

    return None  # Fall through to King County 5ft fallback
```

**If `get_bellevue_contour_url()` returns None**, use King County 5ft fallback and note in the report:
> "Bellevue 2ft contour REST endpoint not publicly accessible at this time. Used King County 5ft data instead. For higher precision, view manually at: https://cobgis.maps.arcgis.com/apps/webappviewer/index.html?id=e1748172d4f34f1eb3710032a351cd57 — enable the '2' Contour Lines' layer."

The Bellevue Map Viewer direct link with address pre-loaded:
```python
def bellevue_map_viewer_link(address: str) -> str:
    encoded = requests.utils.quote(address)
    return (
        f"https://cobgis.maps.arcgis.com/apps/webappviewer/index.html"
        f"?id=e1748172d4f34f1eb3710032a351cd57"
        f"&find={encoded}"
    )
```
Always include this link in the output for Bellevue properties so the user can verify visually.

### Priority 2 — King County 5ft contours (fallback)

URL: `https://gismaps.kingcounty.gov/arcgis/rest/services/Topo/KingCo_Contours/MapServer/5/query`
- Layer 5 = "contours - 5 foot (below 1000 feet)"
- ELEVATION field: `ELEVATION` (feet)
- Spatial reference input: 4326 (WGS84)

---

## Step 3 — Query Contour Lines Within Parcel

```python
import requests, json
from pyproj import Transformer

def query_contours(bbox_wgs84: list, layer_url: str, sr_in: int = 4326) -> list:
    """
    bbox_wgs84: [xmin, ymin, xmax, ymax] in WGS84
    layer_url: full FeatureLayer URL ending in /query
    sr_in: input spatial reference of the layer (2285, 2926, or 4326)
    
    Returns list of dicts: [{"elevation": float, "geometry": {...}}, ...]
    """
    # If layer uses State Plane ft, reproject bbox
    if sr_in in (2285, 2926):
        t = Transformer.from_crs("EPSG:4326", f"EPSG:{sr_in}", always_xy=True)
        xmin, ymin = t.transform(bbox_wgs84[0], bbox_wgs84[1])
        xmax, ymax = t.transform(bbox_wgs84[2], bbox_wgs84[3])
        query_sr = sr_in
    else:
        xmin, ymin, xmax, ymax = bbox_wgs84
        query_sr = 4326
    
    params = {
        "geometry": json.dumps({
            "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
            "spatialReference": {"wkid": query_sr}
        }),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ELEVATION,CONTOUR_FT,ELEV,ContourElev",  # try common field names
        "returnGeometry": True,
        "outSR": 4326,
        "f": "json"
    }
    
    r = requests.get(layer_url, params=params, timeout=20)
    data = r.json()
    features = data.get("features", [])
    
    results = []
    for feat in features:
        attrs = feat["attributes"]
        # Find elevation field (different services use different names)
        elev = (attrs.get("ELEVATION") or attrs.get("CONTOUR_FT") or
                attrs.get("ELEV") or attrs.get("ContourElev"))
        if elev is not None:
            results.append({"elevation": float(elev), "geometry": feat["geometry"]})
    
    return results
```

**Query endpoint construction:**
- For MapServer layers, append `/query` to the layer URL
- Example: `https://maps.kirklandwa.gov/host/rest/services/TPO_cont2ft_cart/MapServer/0/query`

---

## Step 4 — Compute Slope Statistics

```python
import math

def compute_slope_stats(contours: list, parcel_info: dict) -> dict:
    """
    contours: list of {"elevation": float, ...}
    parcel_info: dict with bbox
    
    Returns slope assessment dict.
    """
    if not contours:
        return {"error": "No contour data found for this parcel"}
    
    elevations = sorted(set(c["elevation"] for c in contours))
    elev_min = min(elevations)
    elev_max = max(elevations)
    elev_range = elev_max - elev_min
    num_contours = len(elevations)
    
    # Estimate parcel diagonal in feet (rough approximation)
    bbox = parcel_info["bbox"]
    # 1 degree lat ≈ 364,000 ft; 1 degree lng ≈ 290,000 ft at Seattle latitude
    delta_x_ft = (bbox[2] - bbox[0]) * 290000
    delta_y_ft = (bbox[3] - bbox[1]) * 364000
    parcel_diagonal_ft = math.sqrt(delta_x_ft**2 + delta_y_ft**2)
    parcel_area_sqft = delta_x_ft * delta_y_ft  # rough
    
    # Contour spacing (ft) is parcel_diagonal / (num_contours - 1) roughly
    # Max slope estimate: steepest possible if contours are tightest
    if num_contours > 1:
        contour_interval = elevations[1] - elevations[0] if len(elevations) > 1 else 5
        # Minimum horizontal run between adjacent contours
        # (rough: assume contours spread across parcel evenly)
        avg_horiz_per_contour = parcel_diagonal_ft / max(num_contours - 1, 1)
        max_slope_pct = (contour_interval / avg_horiz_per_contour) * 100
        max_slope_deg = math.degrees(math.atan(max_slope_pct / 100))
    else:
        max_slope_pct = 0
        max_slope_deg = 0
    
    # Terrain classification
    if elev_range <= 5:
        terrain = "Flat/Nearly Flat"
        concern = "Low slope concern. Standard construction applies."
    elif elev_range <= 15:
        terrain = "Gently Sloping"
        concern = "Moderate grading may be needed. Check drainage direction."
    elif elev_range <= 30:
        terrain = "Moderately Sloped"
        concern = "Significant grading cost. Verify retaining wall needs. Check for erosion hazard designation."
    elif elev_range <= 50:
        terrain = "Steeply Sloped"
        concern = "High grading cost. Likely requires geo-technical report. Check city steep slope / landslide hazard overlay."
    else:
        terrain = "Very Steep"
        concern = "Critical slope likely (>40%). Check for critical area restrictions, may limit buildable area significantly."
    
    return {
        "elevation_min_ft": elev_min,
        "elevation_max_ft": elev_max,
        "elevation_range_ft": round(elev_range, 1),
        "num_contour_lines": num_contours,
        "contour_interval_ft": contour_interval if num_contours > 1 else "N/A",
        "estimated_max_slope_pct": round(max_slope_pct, 1),
        "estimated_max_slope_deg": round(max_slope_deg, 1),
        "terrain_type": terrain,
        "advisory": concern,
        "elevations_found": elevations
    }
```

---

## Step 5 — Generate Map Image URL

For quick visual reference, generate a King County iMap deep-link or an ArcGIS ExportMap image:

```python
def generate_map_urls(parcel_info: dict) -> dict:
    bbox = parcel_info["bbox"]
    lat = parcel_info["lat"]
    lng = parcel_info["lng"]
    
    # King County iMap deep link with contour layer
    imap_url = (
        f"https://kingcounty.gov/en/dept/kcit/data-information-services/gis-center/maps-apps/imap"
        f"#lat={lat}&lng={lng}&zoom=17"
    )
    
    # Export static map image from King County contour MapServer
    # bbox needs to be in Web Mercator (3857) for ExportMap
    # Quick approximation: use the bbox directly in geographic for the envelope
    # More accurate: use pyproj to convert
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    xmin_m, ymin_m = t.transform(bbox[0], bbox[1])
    xmax_m, ymax_m = t.transform(bbox[2], bbox[3])
    
    # Add 20% buffer around parcel
    buf_x = (xmax_m - xmin_m) * 0.3
    buf_y = (ymax_m - ymin_m) * 0.3
    
    export_bbox = f"{xmin_m-buf_x},{ymin_m-buf_y},{xmax_m+buf_x},{ymax_m+buf_y}"
    
    kc_contour_image = (
        "https://gismaps.kingcounty.gov/arcgis/rest/services/Topo/KingCo_Contours/MapServer/export"
        f"?bbox={export_bbox}&bboxSR=3857&imageSR=3857"
        "&size=800,600&format=png&transparent=true&f=image"
        "&layers=show:5"  # layer 5 = 5ft contours
    )
    
    return {
        "imap_link": imap_url,
        "contour_image_url": kc_contour_image
    }
```

---

## Step 6 — Full Pipeline

```python
def analyze_property_slope(address: str) -> dict:
    """Main entry point. Returns full slope analysis report."""
    
    print(f"Analyzing: {address}")
    
    # 1. Geocode + parcel
    parcel = geocode_and_get_parcel(address)
    city = parcel["city"]
    print(f"  City: {city} | Parcel: {parcel['parcel_id']}")
    
    # 2. Select contour source
    city_sources = {
        "KIRKLAND": {
            "url": "https://maps.kirklandwa.gov/host/rest/services/TPO_cont2ft_cart/MapServer/0/query",
            "sr": 2285,
            "interval": 2
        },
        "SAMMAMISH": {
            "url": "https://maps.sammamishwa.gov/arcgis/rest/services/mapServices/Contours/MapServer/0/query",
            "sr": 2926,
            "interval": 2
        },
    }
    kc_fallback = {
        "url": "https://gismaps.kingcounty.gov/arcgis/rest/services/Topo/KingCo_Contours/MapServer/5/query",
        "sr": 4326,
        "interval": 5
    }
    
    # Bellevue: attempt dynamic discovery of 2ft REST endpoint
    bellevue_map_link = None
    if city == "BELLEVUE":
        bellevue_map_link = bellevue_map_viewer_link(address)
        bvue_url = get_bellevue_contour_url()
        if bvue_url:
            source = {"url": bvue_url, "sr": 4326, "interval": 2}
            data_source_name = "Bellevue 2ft GIS (ArcGIS Online)"
        else:
            source = kc_fallback
            data_source_name = "King County 5ft GIS (Bellevue 2ft not publicly accessible via REST)"
        print(f"  Using: {data_source_name}")
    else:
        source = city_sources.get(city, kc_fallback)
        data_source_name = f"{city} 2ft GIS" if city in city_sources else "King County 5ft GIS (fallback)"
        print(f"  Using: {data_source_name}")
    
    # 3. Query contours
    contours = query_contours(parcel["bbox"], source["url"], source["sr"])
    
    # If city source returned 0 results, fall back to KC
    if not contours and city in city_sources:
        print("  City source returned 0 results, falling back to King County")
        contours = query_contours(parcel["bbox"], kc_fallback["url"], kc_fallback["sr"])
        data_source_name = "King County 5ft GIS (fallback)"
    
    # 4. Compute stats
    stats = compute_slope_stats(contours, parcel)
    
    # 5. Map URLs
    map_urls = generate_map_urls(parcel)
    
    # 6. Assemble report
    report = {
        "address": address,
        "parcel_id": parcel["parcel_id"],
        "city": city,
        "data_source": data_source_name,
        "slope_analysis": stats,
        "map_urls": map_urls
    }
    if bellevue_map_link:
        report["bellevue_map_viewer"] = bellevue_map_link
        report["bellevue_note"] = (
            "For 2ft precision, enable '2\\' Contour Lines' layer in the Bellevue Map Viewer link above."
        )
    
    return report
```

---

## Output Format for Claude

When presenting results, format the report like this:

```
## Slope Analysis — [ADDRESS]

**Parcel ID:** [PIN]
**Data Source:** [city 2ft / KC 5ft]

### Elevation Summary
- Range: [min] ft – [max] ft  (total relief: [range] ft)
- Contour lines crossing parcel: [N] lines at [interval]ft interval
- Elevations found: [list]

### Slope Assessment
- Estimated max slope: ~[X]% ([Y]°)
- Terrain type: [Flat / Gently Sloping / Moderately Sloped / Steeply Sloped / Very Steep]

### Advisory
[advisory text]

### Verify in GIS
- King County iMap: [link]
- Contour overlay image: [link]
[If Bellevue:]
- Bellevue Map Viewer (2ft contours): [bellevue_map_viewer link]
  → Enable the "2' Contour Lines" layer in the left panel for 2ft precision
```

**Always tell the user:**
> This is a programmatic estimate based on contour line counts within the parcel bounding box. For precise slope calculations (e.g., for permit applications, retaining wall design, or geotechnical reports), verify directly in the city's GIS portal or order a survey.

**For Bellevue properties where REST fallback was used**, additionally tell the user:
> Bellevue's 2ft contour data is available in their Map Viewer but is not publicly accessible via REST API at this time. The King County 5ft data above gives a reasonable approximation. For precise 2ft contour review, use the Bellevue Map Viewer link and enable the "2' Contour Lines" layer — this matches exactly what you see manually in cobgis.

---

## Dependencies

```bash
pip install requests pyproj --break-system-packages
```

---

## Known Limitations & Edge Cases

**Parcels on city borders:** bbox may extend into adjacent city. The contour query will still work since it uses geographic coordinates; just note the data source may be the KC fallback.

**Bellevue:** The 2ft contour layer you use manually is at `cobgis.maps.arcgis.com` — a Bellevue ArcGIS Online org. The underlying FeatureServer URL is not indexed publicly, so the skill attempts dynamic discovery at runtime via the ArcGIS Online search API. If that fails (likely due to the layer requiring org-level auth or being unlisted), the skill falls back to King County 5ft and always provides a direct Bellevue Map Viewer deep link so you can verify manually. The Bellevue Map Viewer link format is:
```
https://cobgis.maps.arcgis.com/apps/webappviewer/index.html?id=e1748172d4f34f1eb3710032a351cd57&find=[encoded_address]
```

**Redmond/Bothell:** No confirmed public 2ft REST endpoint. Use King County 5ft fallback.

**Very large parcels:** The bounding box query may return many contour lines from adjacent lots. The elevation range stat is still valid; the slope estimate becomes less meaningful for large lots. For large parcels (bbox > 0.01° on any side), note this in output.

**Parcel query failure:** If the King County parcel FeatureLayer query fails, use a 150m bbox centered on the geocoded point as fallback. Note in output that parcel boundary was not confirmed.

**No contours found:** If even KC fallback returns 0 results, the parcel may be at very high elevation (>1000ft, outside 5ft contour coverage) or there may be a spatial reference mismatch. Try layer IDs 0–10 on the KC MapServer to find the right scale layer.

**City name normalization:** King County data may return city as "CITY OF KIRKLAND", "KIR", or similar. Normalize before lookup:
```python
city_map = {
    "CITY OF KIRKLAND": "KIRKLAND", "KIR": "KIRKLAND",
    "CITY OF SAMMAMISH": "SAMMAMISH", "SAM": "SAMMAMISH",
    "CITY OF BELLEVUE": "BELLEVUE", "BEL": "BELLEVUE",
    "CITY OF REDMOND": "REDMOND", "RED": "REDMOND",
}
city = city_map.get(city, city)
```
