# Protocol regression test

`test_stream_protocol.py` tests delayed-feedback handling at the actual `simulate` call site. The tiny toy classifier and recording detector are **test fixtures**, not the datasets or models used for the thesis performance results. The fixture forces a refit while older predictions await labels, so the test fails if their errors enter the reset detector.

Current implementation:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Archived defective implementation, expected failure:

```sh
PHISHING_MODULE_DIR="$PWD/experiments/legacy_20261001/src" .venv/bin/python -m unittest discover -s tests -v
```

The legacy test admits four old-model fixture errors into the new detector. The corrected implementation admits none. Actual experiment labels still remain usable for training after arrival, and every original prediction remains in performance scoring.
