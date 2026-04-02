---
name: windermere-transaction-worksheet
description: Given a real estate purchase contract PDF, extract all relevant fields and auto-fill the Windermere Transaction Worksheet Tier 1 form at https://www.windermerets.com/transaction-worksheet-tier-1/ using Chrome. Use when user says "fill the transaction worksheet", "submit the Windermere form", "fill out the tier 1 worksheet", or provides a contract and mentions Windermere.
---

# Windermere Transaction Worksheet — Auto-Fill Skill

## Overview

This skill:
1. Reads a purchase contract PDF
2. Extracts all fields mappable to the Windermere Tier 1 Transaction Worksheet
3. Opens the form in Chrome via Claude in Chrome MCP
4. Fills in every field it can find in the contract
5. Pauses before submitting so the agent can review and complete any missing fields

**Browser:** Uses Claude in Chrome MCP (real Chrome browser — NOT headless). This avoids bot detection and lets the user see the form being filled in real time.

**URL:** https://www.windermerets.com/transaction-worksheet-tier-1/

---

## Step 1 — Get Inputs from User

Before reading any PDF, confirm two things:

**A. Contract PDF path:**
Ask the user: "Please provide the full path to the contract PDF (e.g. C:\Users\...\contract.pdf)"

**B. Agent's own information** (not in the contract — must ask user):
Ask for the following if not already provided:
- WRE Office (Bellevue / Bellevue South / Bellevue West / Issaquah / Redmond / Yarrow Bay)
- Agent Full Name
- Agent LAG #
- Agent E-mail
- Transaction Side (Listing / Selling / Both)
- Assistant E-mail (optional)

You can ask for A and B together in one message to save time.

---

## Step 2 — Extract Contract Data

Use Python + pdfplumber to extract text from the contract PDF:

```python
import pdfplumber

with pdfplumber.open(pdf_path) as pdf:
    full_text = ""
    for page in pdf.pages:
        full_text += page.extract_text() + "\n"
```

Then use your language understanding to extract these fields from the text. Washington state real estate contracts follow the NWMLS Purchase and Sale Agreement format. Common field locations:

### Field Extraction Map

| Form Field | What to look for in contract |
|---|---|
| **Street Address** | Property address at top of contract, "Property Address:" label |
| **City / State / Zip** | Part of property address |
| **NWMLS #** | "NWMLS#", "MLS#", or "Listing Number" |
| **Seller Name** | "Seller:" label, often on page 1 |
| **Buyer Name** | "Buyer:" label, often on page 1 |
| **Seller Email** | Email near Seller section or signature block |
| **Buyer Email** | Email near Buyer section or signature block |
| **Seller Phone** | Phone near Seller name |
| **Buyer Phone** | Phone near Buyer name |
| **Purchase Price** | "Purchase Price:", "Sales Price:", dollar amount on page 1 |
| **Earnest Money Amount** | "Earnest Money:", "EM:" followed by dollar amount |
| **Earnest Money Held At** | "held by", "Escrow" or "Selling Office" near earnest money |
| **Contract Date** | Date at top of agreement, "Date:" or "Agreement Date:" |
| **Mutual Acceptance Date** | "Mutual Acceptance Date:", "MA Date:" |
| **Closing Date** | "Closing Date:", "Close of Escrow:", "COE:" |
| **Financing Type** | "Cash", "Conventional", "FHA", "VA" — look for financing addendum or page 1 checkbox |
| **Title Company** | "Title Company:", "Title Insurance:" |
| **Escrow Company** | "Escrow Company:", "Escrow Agent:" |
| **Escrow Closer Name** | Name near escrow company |
| **Escrow Closer Email** | Email near escrow section |
| **Escrow Closer Phone** | Phone near escrow section |
| **Compensation % (total)** | "Commission:", "Compensation:", "%" on page 1 or commission addendum |
| **Compensation % to Selling Office** | "Selling Office:", "Co-op:" percentage |
| **Compensation % to Listing Office** | "Listing Office:" percentage |
| **Other Broker Name** | Broker on the opposite side from agent's transaction side |
| **Other Broker Company** | Company of other broker |
| **Other Broker Email** | Email of other broker |
| **Pending Status** | Look for inspection contingency → "Pending Inspection"; feasibility → "Contingent Feasibility" |
| **FSBO** | "For Sale By Owner" or no listing agent |

### Output Format

Build a Python dict with all extracted values:
```python
contract_data = {
    "street_address": "...",
    "city": "...",
    "state": "WA",
    "zip": "...",
    "nwmls": "...",
    "seller_name": "...",
    "buyer_name": "...",
    "seller_email": "...",
    "buyer_email": "...",
    "seller_phone": "...",
    "buyer_phone": "...",
    "purchase_price": "...",
    "earnest_money": "...",
    "earnest_held_at": "Escrow" or "Selling Office",
    "contract_date": "MM/DD/YYYY",
    "mutual_acceptance_date": "MM/DD/YYYY",
    "closing_date": "MM/DD/YYYY",
    "financing_type": "Cash" or "Conventional" or "FHA" or "VA" or "Other",
    "title_company": "...",
    "escrow_company": "...",
    "escrow_closer_name": "...",
    "escrow_closer_email": "...",
    "escrow_closer_phone": "...",
    "total_compensation_pct": "...",
    "compensation_pct_selling": "...",
    "compensation_pct_listing": "...",
    "other_broker_name": "...",
    "other_broker_company": "...",
    "other_broker_email": "...",
    "pending_status": "Pending Inspection" or "Contingent Feasibility",
    "fsbo": "Yes" or "No",
}
```

Set any field to `None` if not found — do NOT guess.

Print the extracted dict and ask the user to confirm or correct before proceeding:
> "Here's what I extracted from the contract. Please review and correct anything before I fill the form:"

---

## Step 3 — Open Form in Chrome

Use Claude in Chrome MCP:

```
mcp__Claude_in_Chrome__tabs_context_mcp  (createIfEmpty: true)
mcp__Claude_in_Chrome__navigate  (url: "https://www.windermerets.com/transaction-worksheet-tier-1/")
```

Wait for page to load fully before filling.

---

## Step 4 — Fill the Form

Use `mcp__Claude_in_Chrome__find` to locate each field, then `mcp__Claude_in_Chrome__form_input` to fill it.

Work through the form top to bottom in this order:

### Section: WRE Office & Setup
```
find: "WRE Office dropdown"         → select agent's office
find: "Transaction Side"            → select Listing / Selling / Both
find: "Moreland Insurance"          → select "No – do not receive insurance support" (default; ask user if they want Yes)
find: "Testimonial/Review"          → select "No" (default; ask user if they want Yes)
```

### Section: My Information
```
find: "LAG # field"                 → agent LAG #
find: "My Full Name"                → agent full name
find: "My E-mail"                   → agent email
find: "Assistant E-mail"            → assistant email (if provided)
```

### Section: Other Broker Information
```
find: "Other Broker Full Name"      → other_broker_name
find: "Other Broker Company"        → other_broker_company
find: "Other Broker E-mail"         → other_broker_email
```

### Section: Property & Client Information
```
find: "NWMLS # field"               → nwmls
find: "FSBO"                        → fsbo
find: "Street Address"              → street_address
find: "City field"                  → city
find: "State field"                 → state
find: "Zip Code"                    → zip
find: "Seller Name"                 → seller_name
find: "Buyer Name"                  → buyer_name
find: "Seller 1 E-mail"             → seller_email
find: "Buyer 1 E-mail"              → buyer_email
find: "Seller 1 Phone"              → seller_phone
find: "Buyer 1 Phone"               → buyer_phone
```

### Section: Earnest Money
```
find: "Earnest Money Amount"        → earnest_money
find: "Earnest Money Held at"       → earnest_held_at (radio button)
```

### Section: Transaction Information
```
find: "Contract Date"               → contract_date (MM/DD/YYYY)
find: "Mutual Acceptance Date"      → mutual_acceptance_date
find: "Projected Closing Date"      → closing_date
find: "Pending Status"              → pending_status (radio button)
find: "Financing Type"              → financing_type (radio button)
find: "Title Company"               → title_company
```

### Section: Escrow Information
```
find: "Escrow Company"              → escrow_company
find: "Escrow Closer Name"          → escrow_closer_name
find: "Escrow Closer E-mail"        → escrow_closer_email
find: "Escrow Closer Phone"         → escrow_closer_phone
```

### Section: Compensation Information
```
find: "Purchase Price"              → purchase_price (numbers only, no $)
find: "Total Compensation %"        → total_compensation_pct
find: "Compensation % to Selling"   → compensation_pct_selling
find: "Compensation % to Listing"   → compensation_pct_listing
```

### Tip: Radio buttons and dropdowns
For radio buttons (Financing Type, Transaction Side, Pending Status, Earnest Money Held at):
- Use `mcp__Claude_in_Chrome__find` to locate the specific radio option text
- Then use `mcp__Claude_in_Chrome__form_input` or click it

For dropdowns (WRE Office, State):
- Use `mcp__Claude_in_Chrome__find` to locate the dropdown
- Use `mcp__Claude_in_Chrome__form_input` with the option value

---

## Step 5 — Review Before Submitting

After filling all fields, take a screenshot:
```
mcp__Claude_in_Chrome__computer (action: screenshot)
```

Present the screenshot to the user and list:
- Fields successfully filled
- Fields left blank (not found in contract)
- Any fields needing user input (e.g. Accounting section, Broker compensation splits)

Say:
> "I've filled all fields I could find in the contract. Please review the form above.
> Missing fields: [list]
> When you're ready, tell me to scroll down and click Submit, or make changes first."

**DO NOT click Submit without explicit user confirmation.**

---

## Step 6 — Submit (only after user says yes)

When user confirms:
```
find: "Next button" or "Submit button"
→ click to proceed to review page
→ find: "Submit button" on review page
→ click Submit
```

Confirm submission success by checking for confirmation message on page.

---

## Error Handling

- If a field is not found by `find`, skip it and log it as "not filled"
- If the PDF has scanned images (not text), use pytesseract OCR as fallback:
  ```python
  from pdf2image import convert_from_path
  import pytesseract
  images = convert_from_path(pdf_path)
  text = "\n".join(pytesseract.image_to_string(img) for img in images)
  ```
- If Chrome MCP is not available, tell user: "This skill requires Claude in Chrome MCP. Please ensure it is enabled."

---

## Dependencies

```bash
pip install pdfplumber pypdf --break-system-packages
# For scanned PDFs (optional):
pip install pdf2image pytesseract --break-system-packages
```

---

## Notes

- This skill uses **Claude in Chrome MCP** (real Chrome browser), NOT a headless browser. The user will see the form being filled live.
- The Accounting section (Broker compensation splits, WRE Foundation, Retirement Plan) is NOT filled automatically — these require internal broker knowledge not present in the contract. The skill will leave these blank for the user.
- The PDF upload field ("Mutual Acceptance Bundle") cannot be filled programmatically — remind user to upload manually.
- Dates must be in MM/DD/YYYY format for Gravity Forms date pickers.
- Purchase Price and dollar amounts: strip all `$` and `,` characters before filling (e.g. "$750,000" → "750000").
