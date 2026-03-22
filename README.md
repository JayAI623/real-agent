# Real Agent — King County Property Intelligence

A collection of Claude Code skills for automated property research, data cross-validation, and PDF report generation in **King County, WA** (Seattle, Bellevue, Kirkland, Redmond, etc.).

## Skills Included

| Skill | Description |
|-------|-------------|
| **parcel-radar** | Look up property data from King County Assessor (PIN, assessed values, building details, tax info) via public GIS & eRealProperty APIs |
| **kingcounty-imap** | Automate King County iMap to enable environmental/hazard layers and capture GIS screenshots (landslide zones, flood plains, wetlands, etc.) |
| **parcel-validator** | Orchestrator skill — calls parcel-radar, zillow-scraper, and kingcounty-imap in parallel, then generates a comparison report (MD + PDF) highlighting data discrepancies |

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed
- Python 3.10+
- The following Python packages:

```bash
pip3 install --break-system-packages patchright weasyprint markdown
```

- Chromium browser (installed automatically by Patchright on first run):

```bash
python3 -c "from patchright.sync_api import sync_playwright; print('Patchright OK')"
```

> **Note:** `parcel-validator` also depends on the [zillow-scraper](https://github.com/JayAI623/zillow-scraper) skill (not included in this repo). Install it separately if needed.

## Installation

### Option 1: One-line install script

```bash
git clone https://github.com/JayAI623/real-agent.git ~/.claude/skills/real-agent && \
  ln -sf ~/.claude/skills/real-agent/parcel-radar ~/.claude/skills/parcel-radar && \
  ln -sf ~/.claude/skills/real-agent/kingcounty-imap ~/.claude/skills/kingcounty-imap && \
  ln -sf ~/.claude/skills/real-agent/parcel-validator ~/.claude/skills/parcel-validator
```

### Option 2: Manual install

```bash
# 1. Clone the repo
git clone https://github.com/JayAI623/real-agent.git

# 2. Copy each skill to Claude Code's skills directory
cp -r real-agent/parcel-radar ~/.claude/skills/parcel-radar
cp -r real-agent/kingcounty-imap ~/.claude/skills/kingcounty-imap
cp -r real-agent/parcel-validator ~/.claude/skills/parcel-validator
```

### Option 3: Install script

```bash
git clone https://github.com/JayAI623/real-agent.git
cd real-agent
./install.sh
```

After installation, **restart Claude Code** to load the new skills.

## Usage

### Property Lookup (Assessor Data)

```
/parcel-radar 218 163rd Place SE, Bellevue, WA 98008
```

Returns: parcel number, owner, assessed values, building details (sqft, beds, baths, year built), tax info.

### iMap Environmental Layers Screenshot

```
/kingcounty-imap 218 163rd Place SE, Bellevue, WA 98008
```

Returns: two screenshots — clean map with hazard layers enabled, and map with the layer list panel visible.

### Full Property Validation Report (PDF)

```
/parcel-validator 218 163rd Place SE, Bellevue, WA 98008
```

This is the main workflow. It:

1. Dispatches 3 parallel agents (parcel-radar, zillow-scraper, kingcounty-imap)
2. Compares data from County Assessor vs Zillow:
   - Square footage, lot size, year built
   - Bedrooms, bathrooms, stories
   - Assessed value vs Zestimate
   - HOA, parking, heating/cooling
   - Last sold date/price, days on market
3. Highlights discrepancies with possible causes and impact analysis
4. Embeds screenshots (Zillow listing + iMap hazard layers)
5. Generates a styled PDF report

### Output Example

```
218-163rd-Pl-SE-property-validation.md    # Markdown source
218-163rd-Pl-SE-property-validation.pdf   # Styled PDF with embedded images
zillow_property.png                        # Zillow listing screenshot
imap_218_163rd.png                         # iMap environmental layers
imap_218_163rd_with_layers.png             # iMap with layer panel
```

## Customizing iMap Layers

Edit `kingcounty-imap/layers.md` to add or remove layers. Each `- Layer Name` line maps to a layer in the iMap Layer List panel. Available layers (~230) can be discovered via the script — see the kingcounty-imap SKILL.md for details.

## Limitations

- **King County, WA only** — parcel-radar and kingcounty-imap use King County's public GIS systems
- **Zillow anti-bot** — zillow-scraper uses Patchright to bypass detection, but occasional blocks may occur
- **iMap tile rendering** — environmental layers only render at zoom levels ≤ 3000m buffer
- **Assessment lag** — County data may not reflect recent renovations; Zillow may show seller-reported updates

## License

MIT
