#!/bin/bash
# =============================================================================
# run_all.sh: run the whole Sports Arena analysis with one command (no Docker)
#
#     cd ~/"Downloads/Final sports arena project"
#     ./run_all.sh
# =============================================================================

set -e                      # stop at the first error, so nothing is hidden
cd "$(dirname "$0")"        # go to the project folder

# Create the Python environment the first time (exact versions from requirements.txt).
if [ ! -d ".venv" ]; then
    echo "Creating Python environment (first run only) ..."
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi
source .venv/bin/activate

echo; echo "===== Step 1: check the raw data (SHA-256 checksums) ====="
python src/verify_data.py

echo; echo "===== Step 2: clean the data -> data/processed/ ====="
python src/prepare_data.py

echo; echo "===== Step 3: statistics, tables and charts -> outputs/ ====="
python src/analysis.py

echo; echo "===== Step 4: fact-check against official IPL records ====="
python tests/test_facts.py

echo; echo "===== Step 5: predict the next season's champion and awards ====="
python src/predict.py

echo; echo "===== Step 6: build the dashboard -> outputs/index.html ====="
python src/build_report.py

echo; echo "Finished. Open outputs/index.html in your browser to see the dashboard."
