# Shipment Tracker

Reads shipment rows from the team's Google Sheet, checks each FedEx tracking
number, writes a status next to it (green when delivered), and flags
delays, exceptions, and failed lookups. Claude summarizes the problems and
suggests next steps.

> **Current stage:** Milestone 4. Synthetic data only. No real shipments or
> Google Sheets yet. The Claude summary runs only if you set an API key.

## How it fits together

```
Sheet rows ──▶ look_up() ──▶ classify() ──▶ status_cell() ──▶ Sheet "Status" column
                  │              │                                     │
           tracking provider   plain rules                       run report + logs
           (mock now, FedEx    (no AI)                                 │
            later)                                     Claude summarizes flagged rows
                                                       (later, read-only: it never
                                                        sets a status)
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
| `sheets/base.py` | The contract every spreadsheet backend follows (read a tab, write cells) |
| `sheets/memory_sheet.py` | Fake in-memory spreadsheet, for tests |
| `sheets/json_file_sheet.py` | Practice sheet saved to `work/mock_sheet.json`, so runs persist |
| `sheets/layout.py` | Finds Tracking and Status columns by header name, never by position |
| `sheets/shipments.py` | Turns rows into `Shipment` objects; skips rows with a blank Tracking cell |
| `updater.py` | Writes only the Status column, matched by tracking number, only when changed |
| `pipeline.py` | One full check of every tab, producing a `RunReport` |
| `run_log.py` | Text log, one JSON report per run |
| `config.py` | Settings from environment variables / `.env` |
| `summarizer.py` | The only AI: Claude explains flagged rows and suggests next steps; answer is checked |
| `cli.py` | The `python -m shipment_tracker ...` commands |

**Delayed** means not delivered and today is past the ETA.

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env             # optional: the defaults work as-is
```

## Commands

```bash
python -m shipment_tracker run --dry-run    # show what would change, write nothing
python -m shipment_tracker run              # check every tab and update Status
python -m shipment_tracker run --today 2026-10-25   # pretend it's another day
python -m shipment_tracker run --recheck-delivered  # also re-check Delivered rows
python -m shipment_tracker run --no-summary         # skip the Claude summary
python -m shipment_tracker test             # run the tests and save the results
python -m shipment_tracker reset-mock-sheet # start the practice sheet over
```

`run` exits with code 0 when there were no errors and 1 when something needs
attention. Failed lookups are *not* errors: they show in the sheet as
"Lookup failed" so someone can fix the tracking number. Errors are problems
with a tab (missing, bad layout) or unexpected crashes on a row.

## AI summary

After the sheet is updated, Claude reads the flagged rows (delays, exceptions,
failed lookups) and suggests a next step for each. It needs `ANTHROPIC_API_KEY`
in `.env`; without one the summary is skipped and everything else still works.

Claude never sets a status. It only receives city, state, tab, row, tracking
number, and our status text (no names or addresses), and its answer is
discarded if it doesn't match the expected format or mentions a shipment we
didn't send. The printed summary shows *our* status next to Claude's advice.
A failed summary is a warning in the log, not a failed run.

Rows already marked **Delivered** are skipped on later runs, so finished
packages don't use up tracking lookups.

## Logs

Everything goes in `logs/` (git-ignored):

- `logs/runs.log`: timestamped text log; errors include full technical details
- `logs/runs/<timestamp>.json`: every row's outcome, counts, and errors for one run
- `logs/tests/history.log` and `logs/tests/<timestamp>.xml`: test results

## Sheet layout

Two tabs, *Form Responses 1* and *Manual Entries*, with the columns:
Date, Name, Address, Address 2, City, State, ZIP code, Kit quantity, Tracking.
The tool adds a **Status** header in the empty column after Tracking (or uses an
existing Status column anywhere) and only ever writes to that column. If the
column after Tracking is already used for something else, it stops without
writing anything and asks you to add a Status header yourself.

## Roadmap

- [x] **1. Core:** data shapes, mock provider, status rules, display, tests
- [x] **2. Sheet layer:** in-memory sheet, safe updater that only writes the Status column
- [x] **3. Runner:** command-line run, dry-run mode, run log, `.env` loading
- [x] **4. Claude summary:** structured output, tested with a fake client
- [ ] **5. Real Google Sheet:** a test copy first
- [ ] **6. Daily schedule**
- [ ] **7. Real FedEx Track API:** needs a FedEx Developer account

## Secrets

Credentials go in `.env` (git-ignored). See `.env.example` for the names.
Never put keys in source code.
