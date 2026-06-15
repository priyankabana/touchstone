# Minimal Verification Demo

This folder exists so judges can verify one end-to-end Touchstone flow without opening the browser.

## Run One Row

```bash
python demo/verify_one.py r3
```

Expected result: `r3` is detected as the retired Square ticker and auto-fixed to Block / XYZ.

Try the novel row before approval:

```bash
python demo/verify_one.py r8
```

Expected result: `r8` is `UNKNOWN` because it is 1,302x the independent estimate and no approved currency rule exists yet.

## Run The Agent Gate

```bash
OFFLINE=1 python -m agent.run_agent
```

Expected result: the cached KRW/USD proposal passes validation, passes sandbox replay, catches the novel row with zero false alarms, and is approved into the library.

## Finalize The Dataset

```bash
python -m engine.finalize
```

This writes:

- `data/corrected_dataset.json`
- `data/correction_report.json`

