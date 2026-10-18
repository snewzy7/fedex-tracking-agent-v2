# Shipment Tracker

Reads shipment rows from the team's Google Sheet, checks each FedEx tracking
number, writes a status next to it (green when delivered), and flags
delays, exceptions, and failed lookups. Claude summarizes the problems and
suggests next steps.

> **Current stage:** Milestone 1. Synthetic data only. No real shipments,
> no Google Sheets, no AI calls yet.

## How it fits together

```
Sheet rows ──▶ look_up() ──▶ classify() ──▶ status_cell() ──▶ Sheet "Status" column
                  │              │
           tracking provider   plain rules            Claude summarizes flagged rows
           (mock now, FedEx    (no AI)                (later, read-only: it never
            later)                                     sets a status)
```

| File | Job |
|---|---|
| `models.py` | Shared data shapes: `TrackingResult`, `TrackingStatus`, `Flag` |
| `tracking_numbers.py` | Cleans up the Tracking cell (spaces, dashes, Sheets' scientific notation) |
| `tracking/base.py` | The contract every tracking provider follows |
| `tracking/mock_provider.py` | Fake provider serving `data/mock_shipments.json` |
| `tracking/lookup.py` | Safe lookup: always returns a real status or a recorded failure |
| `rules.py` | Decides the flag: delivered / on track / delayed / exception / lookup failed |
| `display.py` | Status cell text and color |

**Delayed** means not delivered and today is past the ETA.

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```bash
pytest                           # run the tests
python -m shipment_tracker.demo  # see sample Status cells from the mock data
```

## Sheet layout

Two tabs, *Form Responses 1* and *Manual Entries*, with the columns:
Date, Name, Address, Address 2, City, State, ZIP code, Kit quantity, Tracking.
The tool will add a **Status** column after Tracking and will only ever write to
that column.

## Roadmap

- [x] **1. Core:** data shapes, mock provider, status rules, display, tests
- [ ] **2. Sheet layer:** in-memory sheet, safe updater that only writes the Status column
- [ ] **3. Runner:** command-line run, dry-run mode, run log, `.env` loading
- [ ] **4. Claude summary:** structured output, tested with a fake client
- [ ] **5. Real Google Sheet:** a test copy first
- [ ] **6. Daily schedule**
- [ ] **7. Real FedEx Track API:** needs a FedEx Developer account

## Secrets

Credentials go in `.env` (git-ignored). See `.env.example` for the names.
Never put keys in source code.
