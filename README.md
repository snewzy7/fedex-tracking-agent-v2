# Shipment Tracker

Reads shipment rows from the team's Google Sheet, checks each FedEx tracking
number, writes a status next to it (green when delivered), and flags
delays, exceptions, and failed lookups. Claude summarizes the problems and
suggests next steps.

> **Current stage:** Milestone 6. Real FedEx statuses, copied from fedex.com's
> multi-tracking page (no API needed), applied to an Excel download of the
> Google Sheet. The Claude summary runs only if you set an API key.

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
| `tracking/fedex_paste_provider.py` | Reads FedEx's pasted *Summary Tracking Results* page |
| `batches.py` | Splits the numbers still to check into groups of 30 for fedex.com |
| `tracking/mock_provider.py` | Fake provider serving `data/mock_shipments.json` |
| `tracking/lookup.py` | Safe lookup: always returns a real status or a recorded failure |
| `rules.py` | Decides the flag: delivered / on track / delayed / exception / lookup failed |
| `display.py` | Status cell text and color |
| `sheets/base.py` | The contract every spreadsheet backend follows (read a tab, write cells) |
| `sheets/memory_sheet.py` | Fake in-memory spreadsheet, for tests |
| `sheets/excel_file_sheet.py` | Reads an `.xlsx` downloaded from Google Sheets; saves an updated copy |
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

Requires Python 3.10+. **New to this? Follow [docs/setup-mac.md](docs/setup-mac.md)** for step-by-step Mac instructions.

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
python -m shipment_tracker run --xlsx FILE.xlsx     # use a sheet downloaded as Excel
python -m shipment_tracker test             # run the tests and save the results
python -m shipment_tracker reset-mock-sheet # start the practice sheet over
```

`run` exits with code 0 when there were no errors and 1 when something needs
attention. Failed lookups are *not* errors: they show in the sheet as
"Lookup failed" so someone can fix the tracking number. Errors are problems
with a tab (missing, bad layout) or unexpected crashes on a row.

## Weekly workflow: real FedEx statuses, no API

1. **Download your tracker.** In Google Sheets: *File > Download > Microsoft Excel (.xlsx)*.
2. **Get the numbers to check:**
   ```bash
   python -m shipment_tracker batches --xlsx ~/Downloads/your-file.xlsx
   ```
   This prints the tracking numbers that still need checking (rows already
   marked Delivered are skipped) in batches of up to 30, and saves each batch
   as `output/fedex-batch-1.txt`, `-2.txt`, and so on.
3. **Look them up on fedex.com.** For each batch: paste its numbers into the
   tracking box, then on the *Summary Tracking Results* page press **Cmd+A**,
   **Cmd+C**, and paste into a new TextEdit file. Save it as plain text
   (*Format > Make Plain Text*), e.g. `~/Downloads/fedex-1.txt`.
4. **Run:**
   ```bash
   python -m shipment_tracker run --xlsx ~/Downloads/your-file.xlsx --fedex-paste ~/Downloads/fedex-1.txt ~/Downloads/fedex-2.txt
   ```
5. **Paste the Status column back** (see below).

Every status comes from FedEx's own page. A number that wasn't in any paste,
or a row the tool can't read clearly, shows *Lookup failed* with the reason.
If FedEx shows a status word the tool hasn't seen before, it reports it
instead of guessing; tell Claude the wording and it can be added.

## Excel file workflow (until Google Sheets access is set up)

1. **Download.** In Google Sheets: *File > Download > Microsoft Excel (.xlsx)*.
   One file holds both tabs.
2. **Run.**
   ```bash
   python -m shipment_tracker run --xlsx ~/Downloads/your-file.xlsx --dry-run   # preview
   python -m shipment_tracker run --xlsx ~/Downloads/your-file.xlsx
   ```
   The tool saves an updated copy in `output/` and never changes your download.
   Try it first with the synthetic sample: `--xlsx data/sample_tracking.xlsx`.
3. **Paste back.** Open the updated copy, and for each tab copy the **Status**
   column (header included) and paste it into the same column of the real
   sheet with *Paste values only* (Ctrl+Shift+V, or Cmd+Shift+V on a Mac).
   - Paste soon after downloading, and **don't sort or delete rows in
     between**: the pasted column lines up with rows by position. New form
     responses added at the bottom are fine; they just won't have a status yet.
   - Spot-check a few rows: each status should sit next to its own tracking number.

**Colors, set up once:** instead of pasting formatting, let Google Sheets
color the Status column itself. Select the Status column, then
*Format > Conditional formatting > Format cells if... > Text starts with*:

| Text starts with | Fill color |
|---|---|
| `Delivered` | light green |
| `Delayed` | light yellow |
| `Exception` | light red |
| `Lookup failed` | light red |

Downloads and updated copies contain real names and addresses, so `*.xlsx`
and `output/` are git-ignored (only the synthetic sample is committed).

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

Two tabs, *Form Responses 1* (Google Form answers: Timestamp, Account Name,
Shipping Address, City & State, ..., Tracking) and *Manual Entry* (Date, Name,
Address, Address 2, City, State, Zip Code, Kit Quantity, Tracking). Columns are
found by header name, so their order doesn't matter. Only **Tracking** is required.

The tool writes to a column headed **Status**. If there isn't one, it uses the
column right after Tracking, but only if that column is completely empty
(header *and* every cell). Otherwise it stops without writing anything and asks
you to insert an empty column after Tracking and type `Status` as its header.

## Roadmap

- [x] **1. Core:** data shapes, mock provider, status rules, display, tests
- [x] **2. Sheet layer:** in-memory sheet, safe updater that only writes the Status column
- [x] **3. Runner:** command-line run, dry-run mode, run log, `.env` loading
- [x] **4. Claude summary:** structured output, tested with a fake client
- [x] **5. Excel file workflow:** download, run, paste the Status column back
- [x] **6. Real FedEx statuses (no API):** paste fedex.com's multi-tracking results
- [ ] **7. FedEx Track API (optional):** removes the copy/paste step
- [ ] **8. Direct Google Sheets access:** needs a Google Cloud service account (IT)
- [ ] **9. Daily schedule:** needs 7 and 8, so nobody has to download and paste

## Secrets

Credentials go in `.env` (git-ignored). See `.env.example` for the names.
Never put keys in source code.
