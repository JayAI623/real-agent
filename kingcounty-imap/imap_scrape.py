"""
King County iMap Layer Automation using Patchright.

Usage:
    python3 imap_scrape.py "218 163rd Pl SE, Bellevue, WA 98008"
    python3 imap_scrape.py "218 163rd Pl SE, Bellevue, WA 98008" /path/to/output.png
    python3 imap_scrape.py "218 163rd Pl SE, Bellevue, WA 98008" output.png --lat 47.607 --lon -122.122
"""

from patchright.sync_api import sync_playwright
import math
import time
import sys
import json
import argparse
import os

# ── Layer config file path ───────────────────────────────────────────────────
LAYERS_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layers.md")

# ── Reliability: default buffer 1500m ────────────────────────────────────────
# Lesson learned: buffer > 3000m causes layer tiles to not render at all.
# 1500m gives good balance between context and layer visibility.
DEFAULT_BUFFER = 1500


def load_layers_from_md(path):
    """Parse layers.md — each '- Layer Name' line becomes a layer to enable."""
    layers = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- "):
                layers.append(line[2:].strip())
    return layers


LAYERS_TO_ENABLE = load_layers_from_md(LAYERS_CONFIG)


def latlon_to_webmercator(lat, lon):
    """Convert lat/lon (WGS84) to Web Mercator (EPSG:3857)."""
    x = lon * 20037508.34 / 180
    sin_lat = math.sin(lat * math.pi / 180)
    y = 20037508.34 / 2 * math.log((1 + sin_lat) / (1 - sin_lat)) / math.pi
    return x, y


def geocode_via_imap(page, address):
    """Use iMap's built-in geocoder to place a pin at the address."""
    page.click("#esri_dijit_Search_0_input")
    page.fill("#esri_dijit_Search_0_input", address)
    time.sleep(1)
    page.keyboard.press("Enter")
    time.sleep(2)
    # Click first suggestion if dropdown appears
    page.evaluate('''() => {
        const items = document.querySelectorAll(
            '.suggestionsMenu .searchMenuItem, .searchMenu .searchMenuItem'
        );
        if (items.length > 0) items[0].click();
    }''')
    time.sleep(2)


def build_imap_url(lat, lon, buffer_m=DEFAULT_BUFFER):
    """Build iMap URL with extent centered on lat/lon."""
    x, y = latlon_to_webmercator(lat, lon)
    return (
        f"https://gismaps.kingcounty.gov/iMap/"
        f"?extent={x-buffer_m},{y-buffer_m},{x+buffer_m},{y+buffer_m},102100"
    )


# ── Layer checkbox helpers ───────────────────────────────────────────────────
# CRITICAL LESSON: WAB uses Dojo dijit widgets for checkboxes.
#   - DOM `element.click()` via JS evaluate does NOT trigger Dojo event handlers.
#   - `page.mouse.click()` at the element's screen coordinates DOES work
#     because it dispatches real browser-level mouse events.
#   - The "checked" state is NOT indicated by a `checked` class on the outer
#     `.jimu-checkbox` div. Instead, the INNER `.checkbox` div toggles between
#     `jimu-icon-checkbox` (unchecked) and `jimu-icon-checked` (checked).


def is_layer_checked(page, node_id):
    """Check if a layer checkbox is on. Reads the inner icon class, not outer div."""
    return page.evaluate('''(nodeId) => {
        const cb = document.querySelector('.visible-checkbox-' + nodeId);
        if (!cb) return false;
        const inner = cb.querySelector('.checkbox');
        if (inner) return inner.classList.contains('jimu-icon-checked');
        return cb.classList.contains('checked');
    }''', node_id)


def click_layer_checkbox(page, node_id):
    """Click a layer checkbox using real mouse coordinates (bypasses Dojo)."""
    rect = page.evaluate('''(nodeId) => {
        const cb = document.querySelector('.visible-checkbox-' + nodeId);
        if (!cb) return null;
        cb.scrollIntoView({block: 'center'});
        const r = cb.getBoundingClientRect();
        return {x: r.x + r.width / 2, y: r.y + r.height / 2};
    }''', node_id)
    if rect:
        page.mouse.click(rect['x'], rect['y'])
        return True
    return False


def build_layer_map(page):
    """Build name → nodeId mapping from the Layer List DOM."""
    return page.evaluate('''() => {
        const rows = document.querySelectorAll('.layer-row');
        let mapping = {};
        rows.forEach(row => {
            const nodeId = row.getAttribute('layertrnodeid');
            const titleEl = row.querySelector('.layer-title-node');
            const title = titleEl ? titleEl.innerText.trim() : row.innerText.trim();
            if (nodeId && title) mapping[title] = nodeId;
        });
        return mapping;
    }''')


def find_layer_id(target, layer_map):
    """Find nodeId for a target layer name. Exact match first, then partial."""
    target_lower = target.lower()
    for name, nid in layer_map.items():
        if target_lower == name.lower():
            return nid
    for name, nid in layer_map.items():
        if target_lower in name.lower():
            return nid
    return None


def enable_layers(page, layer_names):
    """Open Layer List and enable specified layers. Returns count enabled."""
    # Open Layer List widget
    page.click('[data-widget-name="LayerList"]')
    time.sleep(2)

    layer_map = build_layer_map(page)
    print(f"   Found {len(layer_map)} layers in panel", file=sys.stderr)

    enabled = 0
    not_found = []

    # IMPORTANT: Process parent groups FIRST, then sub-layers.
    # Enabling a parent group auto-enables all children. If we then click
    # a child that's already on (via parent), we'd toggle it OFF.
    # The layers.md list is ordered parent-first by convention.

    for target in layer_names:
        matched_id = find_layer_id(target, layer_map)

        if matched_id:
            if is_layer_checked(page, matched_id):
                print(f"   ● {target} (already on)", file=sys.stderr)
            else:
                if click_layer_checkbox(page, matched_id):
                    time.sleep(0.5)
                    # Verify — but do NOT retry-click on failure.
                    # Sub-layer checkboxes may not update their jimu-icon-checked
                    # class reliably, and a 2nd click would toggle them OFF.
                    if is_layer_checked(page, matched_id):
                        enabled += 1
                        print(f"   ✓ {target}", file=sys.stderr)
                    else:
                        enabled += 1  # Trust the click worked
                        print(f"   ✓ {target} (click sent, state unverifiable)", file=sys.stderr)
                else:
                    print(f"   ✗ {target} (element not found)", file=sys.stderr)
        else:
            not_found.append(target)

    # Retry not-found layers — they may load lazily
    if not_found:
        print(f"   Retrying {len(not_found)} missing layers...", file=sys.stderr)
        time.sleep(2)
        layer_map2 = build_layer_map(page)
        for target in not_found:
            matched_id = find_layer_id(target, layer_map2)
            if matched_id:
                if not is_layer_checked(page, matched_id):
                    click_layer_checkbox(page, matched_id)
                    time.sleep(0.3)
                    if is_layer_checked(page, matched_id):
                        enabled += 1
                        print(f"   ✓ {target} (found on retry)", file=sys.stderr)
                    else:
                        print(f"   ⚠ {target} (found but toggle failed)", file=sys.stderr)
                else:
                    print(f"   ● {target} (already on, retry)", file=sys.stderr)
            else:
                print(f"   ✗ {target} (still not found)", file=sys.stderr)

    return enabled


def wait_for_tiles(page, seconds=8):
    """Wait for map tiles to finish rendering after layer changes."""
    time.sleep(seconds // 2)
    page.wait_for_load_state("networkidle")
    time.sleep(seconds // 2)


def main():
    parser = argparse.ArgumentParser(description="King County iMap layer automation")
    parser.add_argument("address", help="Property address")
    parser.add_argument("output", nargs="?", default=None, help="Output screenshot path")
    parser.add_argument("--lat", type=float, help="Latitude (WGS84)")
    parser.add_argument("--lon", type=float, help="Longitude (WGS84)")
    parser.add_argument("--buffer", type=int, default=DEFAULT_BUFFER,
                        help=f"Map buffer in meters (default: {DEFAULT_BUFFER})")
    parser.add_argument("--headless", action="store_true",
                        help="Run headless (less reliable)")
    args = parser.parse_args()

    output_path = args.output or os.path.join(os.getcwd(), "imap_result.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # ── Step 1: Open iMap ─────────────────────────────────────────────────
        if args.lat and args.lon:
            url = build_imap_url(args.lat, args.lon, args.buffer)
            print(f"1/4 Opening iMap at ({args.lat}, {args.lon})...", file=sys.stderr)
        else:
            print("1/4 Geocoding address...", file=sys.stderr)
            page.goto("https://gismaps.kingcounty.gov/iMap/", timeout=60000)
            page.wait_for_load_state("networkidle")
            time.sleep(5)

            geocode_via_imap(page, args.address)

            # Try to extract coordinates from URL hash or coordinate widget
            coords = page.evaluate('''() => {
                try {
                    const coordWidget = document.querySelector('.jimu-widget-coordinate');
                    if (coordWidget) {
                        const text = coordWidget.innerText;
                        const match = text.match(/([-\\d.]+)\\s+([-\\d.]+)/);
                        if (match) return { lat: parseFloat(match[1]), lon: parseFloat(match[2]) };
                    }
                } catch(e) {}
                return null;
            }''')

            if coords and coords.get('lat'):
                print(f"   Geocoded: {coords['lat']}, {coords['lon']}", file=sys.stderr)
                url = build_imap_url(coords['lat'], coords['lon'], args.buffer)
            else:
                # Fallback: enable layers on current view without re-navigating
                print("   Coord extraction failed, using current view...", file=sys.stderr)
                print("2/4 Enabling layers...", file=sys.stderr)
                count = enable_layers(page, LAYERS_TO_ENABLE)
                print(f"   Enabled {count} layers.", file=sys.stderr)

                wait_for_tiles(page)

                print("3/4 Taking screenshots...", file=sys.stderr)
                page.click('[data-widget-name="LayerList"]')
                time.sleep(1)
                page.screenshot(path=output_path)
                print(f"   Map: {output_path}", file=sys.stderr)

                page.click('[data-widget-name="LayerList"]')
                time.sleep(1)
                layers_path = output_path.replace('.png', '_with_layers.png')
                page.screenshot(path=layers_path)
                print(f"   With layers: {layers_path}", file=sys.stderr)

                browser.close()
                print("Done!", file=sys.stderr)
                return

        # Load iMap with extent
        page.goto(url, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(5)

        # ── Step 2: Enable layers ─────────────────────────────────────────────
        print("2/4 Enabling layers...", file=sys.stderr)
        count = enable_layers(page, LAYERS_TO_ENABLE)
        print(f"   Enabled {count} layers.", file=sys.stderr)

        # Wait for layer tiles to render
        wait_for_tiles(page)

        # ── Step 3: Place address pin via search ──────────────────────────────
        print("3/4 Placing address pin...", file=sys.stderr)
        geocode_via_imap(page, args.address)
        page.keyboard.press("Escape")
        time.sleep(1)

        # ── Step 4: Screenshots ───────────────────────────────────────────────
        print("4/4 Taking screenshots...", file=sys.stderr)

        # Close Layer List for clean map
        page.click('[data-widget-name="LayerList"]')
        time.sleep(1)
        page.screenshot(path=output_path)
        print(f"   Map: {output_path}", file=sys.stderr)

        # With layer panel
        page.click('[data-widget-name="LayerList"]')
        time.sleep(1)
        layers_path = output_path.replace('.png', '_with_layers.png')
        page.screenshot(path=layers_path)
        print(f"   With layers: {layers_path}", file=sys.stderr)

        browser.close()
        print("Done!", file=sys.stderr)


if __name__ == "__main__":
    main()
