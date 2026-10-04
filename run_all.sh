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
fi
# Install (or update) the exact library versions. When they are already
# installed this takes a second and needs no internet.
.venv/bin/pip install -q -r requirements.txt
source .venv/bin/activate

echo; echo "===== Step 1: check the raw data (SHA-256 checksums) ====="
python src/verify_data.py

echo; echo "===== Step 2: clean the data -> data/processed/ ====="
python src/prepare_data.py

echo; echo "===== Step 3: statistics, tables and charts -> outputs/ ====="
python src/analysis.py

echo; echo "===== Step 4: fact-check against official IPL records ====="
python tests/test_facts.py

echo; echo "===== Step 5: Model A (explainable) predicts the next season ====="
python src/predict.py

echo; echo "===== Step 6: Model B (machine learning) and the A vs B backtest ====="
python src/predict_ml.py

echo; echo "===== Step 7: build the dashboard -> outputs/index.html and match_centre.html ====="
python src/build_report.py

echo; echo "===== Step 8: chatbot question checks (Node.js) ====="
if command -v node > /dev/null; then
    node tests/test_chatbot.js
else
    echo "SKIPPED: Node.js is not installed, so the chatbot checks could not run (Docker runs them)."
fi

echo; echo "Finished. Open outputs/index.html in your browser to see the dashboard."
