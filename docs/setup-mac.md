# Setting up on a Mac

One-time setup takes about 15 minutes. Commands go in **Terminal**: press
Cmd+Space, type `Terminal`, press Return. Type or paste each command, then
press Return.

## 1. Install Python

Check what you have:

```bash
python3 --version
```

You need **3.10 or newer**. If it prints an older version, says
"command not found", or pops up an offer to install developer tools, install
Python from the official site instead:

1. Go to https://www.python.org/downloads/ and click the big yellow
   "Download Python 3.x" button.
2. Open the downloaded `.pkg` file and click through the installer.
3. **Quit and reopen Terminal**, then run `python3 --version` again. It should
   show the version you installed.

## 2. Get the code

1. Go to https://github.com/snewzy7/fedex-tracking-agent-v2 (signed in).
2. Click the green **Code** button, then **Download ZIP**.
3. Open the ZIP in Finder. You get a folder named `fedex-tracking-agent-v2-main`.
4. Rename it to `fedex-tracking-agent-v2` and move it into your home folder's
   `Documents` folder.

Then in Terminal, move into that folder:

```bash
cd ~/Documents/fedex-tracking-agent-v2
```

`cd` means "change directory". Every command below runs from this folder.

## 3. Create a virtual environment and install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

- The first line creates `.venv`, a private Python setup just for this project,
  so its packages never clash with anything else on your Mac.
- The second line turns it on. Your prompt now starts with `(.venv)`.
- The third installs the project and its packages (anthropic, openpyxl, and so
  on). The quotes around `".[dev]"` matter on a Mac.

## 4. Check that everything works

```bash
python -m shipment_tracker test
```

You should see all tests pass, for example `150 passed`.

## 5. Run on the sample file

```bash
python -m shipment_tracker run --xlsx data/sample_tracking.xlsx --today 2026-10-18 --no-summary
```

- `--today 2026-10-18` makes the synthetic dates line up, so you get the same
  results as in the README no matter what day you run it.
- `--no-summary` skips the Claude step (no API key yet).

Then look at the result:

```bash
open output
```

That opens the `output` folder in Finder. Open the newest
`sample_tracking-with-status-....xlsx` in Numbers, Excel, or by uploading it to
Google Drive. Column J ("Status") should be filled in, with Delivered rows
green, the delayed row yellow, and problems red.

## Every time after this

```bash
cd ~/Documents/fedex-tracking-agent-v2
source .venv/bin/activate
```

Then run any command from the README. When you're done, `deactivate` turns
the virtual environment off (or just close Terminal).

## If something goes wrong

| Message | Fix |
|---|---|
| `zsh: no matches found: .[dev]` | Add the quotes: `pip install -e ".[dev]"` |
| `externally-managed-environment` | The virtual environment isn't on. Run `source .venv/bin/activate` |
| `No module named shipment_tracker` | Same: activate first, and make sure you're in the project folder (`pwd` shows where you are) |
| `requires a different Python: ... not in '>=3.10'` | Install a newer Python (step 1), then delete `.venv` and redo step 3 |
| `cd: no such file or directory` | The folder name or location differs. In Finder, drag the folder onto the Terminal window after typing `cd ` |
