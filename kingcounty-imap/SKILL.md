---
name: kingcounty-imap
description: Use when the user wants to look up environmental, flooding, landslide, or parcel data for an address in King County WA using the iMap GIS tool at gismaps.kingcounty.gov/iMap. Also use when checking FEMA flood zones, sensitive areas, steep slopes, wetlands, or property parcels in King County.
---

# King County iMap GIS Layer Automation

## Overview

Automates the King County iMap web application (ArcGIS Web AppBuilder) to search for an address, enable environmental/hazard layers, and capture screenshots. Uses **Patchright** for browser automation.

iMap does NOT persist layer state between sessions — layers must be enabled programmatically each time. The script handles this automatically.

## Quick Start

```bash
# With known coordinates (recommended — most reliable)
python3 ~/.claude/skills/kingcounty-imap/imap_scrape.py \
    "218 163rd Pl SE, Bellevue, WA 98008" output.png \
    --lat 47.5872 --lon -122.1298

# Address only (uses iMap geocoder, less reliable)
python3 ~/.claude/skills/kingcounty-imap/imap_scrape.py \
    "218 163rd Pl SE, Bellevue, WA 98008"
```

Outputs two files:
- `imap_result.png` — clean map with layers enabled
- `imap_result_with_layers.png` — map with Layer List panel visible

## Customizing Layers

Edit `~/.claude/skills/kingcounty-imap/layers.md`. Each `- Layer Name` line is a layer to enable. Names must match what appears in the iMap Layer List panel (case-insensitive).

## How It Works

1. **URL extent params** zoom the map to coordinates (Web Mercator, WKID 102100)
2. **Layer List widget** opened via `[data-widget-name="LayerList"]`
3. **Checkboxes clicked** with `page.mouse.click()` at screen coordinates (NOT JS `.click()` — see pitfalls)
4. **State verified** by checking inner `.checkbox` div for `jimu-icon-checked` class
5. **Address pin** placed via search input `#esri_dijit_Search_0_input`
6. **Wait for tile rendering** before taking screenshots

## Known Pitfalls & Lessons Learned

### 1. JS `element.click()` does NOT work on WAB checkboxes

**Problem:** `document.querySelector('.visible-checkbox-X').click()` fires DOM click but does NOT trigger the Dojo dijit event handler. The checkbox appears unchanged.

**Root cause:** ArcGIS WAB uses Dojo dijit widgets. Event listeners are registered via Dojo's `on()` system, which ignores programmatic DOM `.click()` calls from `page.evaluate()`.

**Solution:** Use `page.mouse.click(x, y)` with the element's screen coordinates. This dispatches real browser-level mouse events that Dojo's event system does process.

```python
# WRONG — silently fails
page.evaluate('document.querySelector(".visible-checkbox-X").click()')

# RIGHT — works reliably
rect = page.evaluate('''(nodeId) => {
    const cb = document.querySelector('.visible-checkbox-' + nodeId);
    cb.scrollIntoView({block: 'center'});
    const r = cb.getBoundingClientRect();
    return {x: r.x + r.width/2, y: r.y + r.height/2};
}''', node_id)
page.mouse.click(rect['x'], rect['y'])
```

### 2. Checked state is on the INNER div, not the outer

**Problem:** Checking `cb.classList.contains('checked')` on `.jimu-checkbox` always returns false, making the script think every layer is unchecked.

**Root cause:** The outer `.jimu-checkbox` div never gets a `checked` class. The actual state indicator is on the INNER `div.checkbox`:
- Unchecked: `jimu-icon-checkbox`
- Checked: `jimu-icon-checked`

**Solution:**
```python
def is_layer_checked(page, node_id):
    return page.evaluate('''(nodeId) => {
        const cb = document.querySelector('.visible-checkbox-' + nodeId);
        if (!cb) return false;
        const inner = cb.querySelector('.checkbox');
        return inner ? inner.classList.contains('jimu-icon-checked') : false;
    }''', node_id)
```

### 3. False success reporting

**Problem:** Script logs `✓ Layer enabled` but the layer is actually not checked.

**Root cause:** Combination of pitfalls #1 and #2 — wrong state detection (always thinks unchecked) + click that doesn't work (silently fails) = always reports "success."

**Solution:** Always verify state AFTER clicking. Retry if verification fails.

### 4. Buffer/zoom level matters for tile rendering

**Problem:** At buffer > 3000m, environmental layers appear completely blank. No error — the tiles just don't render.

**Root cause:** iMap's tile server only returns layer data at certain zoom levels. Wide zooms (high buffer values) are below the minimum zoom for most overlay layers.

**Solution:** Default buffer is 1500m. Never exceed 3000m for environmental layers. For large area views, layers won't be visible.

### 5. `window.require`, `dijit`, `dojo`, `esri` are all undefined

**Problem:** Attempting to use ArcGIS/Dojo APIs via `page.evaluate()` fails — none of the expected globals exist.

**Root cause:** WAB does not expose the AMD loader or Dojo/Esri modules to the global `window` scope. They're encapsulated in the WAB framework.

**Solution:** Don't try to use the ArcGIS JS API. Use DOM manipulation + real mouse clicks instead.

### 6. Geocoding coordinate extraction is fragile

**Problem:** The coordinate widget text format varies or doesn't always appear after a search.

**Solution:** Always prefer passing `--lat` and `--lon` explicitly. Get coordinates from Zillow JSON-LD, Google Maps, or another geocoding source. The iMap geocoder is a fallback, not the primary path.

### 7. Retry-click toggles sub-layers OFF

**Problem:** After enabling parent group "Environmentally Sensitive Areas", its children show as "clicked but not verified." Retry logic clicks them again, which toggles them OFF.

**Root cause:** Enabling a parent group auto-enables all children. The children's inner `.checkbox` div may not immediately update to `jimu-icon-checked`, so verification fails. A retry-click then toggles the already-on child OFF.

**Solution:** Never double-click. If a click was sent but verification fails, trust the click and move on. The `layers.md` file lists parents before children by convention, so children are typically already on when reached.

## Key Technical Details

| Item | Detail |
|------|--------|
| **App type** | ArcGIS Web AppBuilder (WAB) with Dojo dijit widgets |
| **Layer tree** | `.layer-row[layertrnodeid="..."]` elements |
| **Checkbox outer** | `.jimu-checkbox.visible-checkbox-<nodeId>` — do NOT use `.click()` |
| **Checkbox inner** | `.checkbox.jimu-icon-checked` = on, `.jimu-icon-checkbox` = off |
| **Click method** | `page.mouse.click(x, y)` — the ONLY reliable way |
| **Widget buttons** | `[data-widget-name="LayerList"]` at top-right toolbar |
| **Coordinate system** | Web Mercator (WKID 3857/102100) |
| **Extent URL param** | `?extent=xmin,ymin,xmax,ymax,102100` |
| **Max useful buffer** | ~3000m (beyond this, layers don't render) |
| **Default buffer** | 1500m |
| **Layer state** | Not persisted — must enable every session |
| **Layer config** | `layers.md` in skill directory |

## Coordinate Conversion

```python
import math
x = lon * 20037508.34 / 180
sin_lat = math.sin(lat * math.pi / 180)
y = 20037508.34 / 2 * math.log((1 + sin_lat) / (1 - sin_lat)) / math.pi
# Use: ?extent={x-buf},{y-buf},{x+buf},{y+buf},102100
```

## Discovering Available Layers

After opening the Layer List, run:
```python
layer_map = page.evaluate('''() => {
    const rows = document.querySelectorAll('.layer-row');
    let mapping = {};
    rows.forEach(row => {
        const nodeId = row.getAttribute('layertrnodeid');
        const titleEl = row.querySelector('.layer-title-node');
        const title = titleEl ? titleEl.innerText.trim() : '';
        if (nodeId && title) mapping[title] = nodeId;
    });
    return mapping;
}''')
# Returns ~230 layers. Add desired names to layers.md.
```
