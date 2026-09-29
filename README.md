# Sports Arena: IPL Performance Analyzer

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Mohanp1821/sports-arena/blob/main/notebooks/ipl_analysis.ipynb)
![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)

An open-source data visualisation project that analyses **every ball of the Indian Premier League
from 2008 to 2019** (756 matches, 179,078 deliveries) and turns it into clear charts and a web dashboard.

**Course:** Open Source Tools for Data Science (OST), mini project · **Author:** Mohan Pawar

---

## 1. Problem statement

Match results are easy to find, but *why* teams win is not. Does winning the toss help? Is chasing
better than batting first? Which players are in form, and who is best in the Death overs?
These questions need analysis of **every ball**, not just final scores.

## 2. Objectives and scope

1. **Player form:** runs per innings with a 5-innings rolling average, and career trends by season.
2. **Team comparisons:** win %, run rate in each phase (Powerplay / Middle / Death), toss impact, home advantage, head-to-head.
3. **Top performers:** Orange Cap and Purple Cap winners for every season, and top-10 lists.

Scope: IPL 2008–2019 (real Kaggle data). Built only with open-source tools: **Python, pandas,
matplotlib, seaborn, Git, Docker**.

## 3. Key results

| Finding | Result |
|---|---|
| Chasing vs batting first | Teams batting second won **55.5%** of matches |
| Does the toss matter? | Barely: the toss winner won **52.3%** |
| Fastest scoring phase | Death overs (16–20): **9.8 runs per over**, compared with about 7.6 earlier in the innings |
| Most successful team | Chennai Super Kings: **61.0%** win rate |
| Best season by a batter | Virat Kohli, 2016: **973 runs** |
| Accuracy check | All **24 Orange/Purple Cap winners match the official records** |

<p align="center">
  <img src="outputs/form_v_kohli_2016.png" width="49%" alt="Kohli 2016 form">
  <img src="outputs/phase_run_rate.png" width="49%" alt="Run rate by phase">
  <img src="outputs/heatmap_team_season.png" width="49%" alt="Win % heatmap">
  <img src="outputs/batting_quadrant.png" width="49%" alt="Average vs strike rate">
</p>

All 19 charts are in `outputs/`. The full dashboard is `outputs/index.html`.

## 4. How to run

**Option A: Terminal (one command)**
```bash
./run_all.sh
```
Runs the 5 steps and creates the Python environment automatically the first time.
Then open `outputs/index.html` in a browser.

**Option B: Docker**
```bash
docker compose up --build
```
Then open **http://localhost:8080**. Stop with `Ctrl+C`, then run `docker compose down`.

**Option C: Google Colab** (no installation)
Click the **Open in Colab** badge above, then choose **Runtime → Run all**.

## 5. How it works

```
data/raw/ ──► verify_data.py ──► prepare_data.py ──► analysis.py ──► test_facts.py ──► build_report.py
 original      checks SHA-256     cleans the data     stats + 19        checks results    dashboard
 CSV files     checksums          data/processed/     charts            vs official       outputs/index.html
```

| Step | File | What it does |
|---|---|---|
| 1 | `src/verify_data.py` | Proves the raw data is unchanged (SHA-256 checksums) |
| 2 | `src/prepare_data.py` | Fixes team renames, venue spellings, 2 date formats, no-result matches, and **1,245 extras counted twice in 2018–19** |
| 3 | `src/analysis.py` | Draws all charts, using the cricket formulas in `src/metrics.py` |
| 4 | `tests/test_facts.py` | Checks the results against official IPL records |
| 5 | `src/build_report.py` | Builds the web dashboard |

**Docker architecture:** two services from one image. `pipeline` runs steps 1–5; `dashboard` serves the
results on port 8080, and starts only if the pipeline succeeded.

## 6. Project structure

```
sports-arena/
├── README.md               ← you are here
├── run_all.sh              run everything with one command
├── git_commands.sh         every Git command used to build this repository, explained
├── Dockerfile              container recipe
├── docker-compose.yml      two-service architecture (pipeline + dashboard)
├── requirements.txt        pinned library versions
├── data/
│   ├── raw/                original dataset (never edited)
│   ├── processed/          cleaned data
│   └── README.md           source, licence, checksums, column guide
├── src/
│   ├── verify_data.py      step 1
│   ├── prepare_data.py     step 2
│   ├── metrics.py          all cricket formulas
│   ├── analysis.py         step 3
│   └── build_report.py     step 5
├── tests/test_facts.py     step 4
├── notebooks/ipl_analysis.ipynb   the same analysis, cell by cell (Colab)
├── outputs/                19 charts + index.html dashboard
├── docs/
│   ├── Marking_Scheme.md   each marking criterion → where the evidence is + demo script
│   ├── Code_Explanation.md every file, formula and chart explained simply
│   └── Viva_QA.md          16 likely viva questions with answers
├── CONTRIBUTING.md
└── LICENSE                 MIT (code)
```

## 7. Dataset and licence

**Data:** [Indian Premier League 2008-2019](https://www.kaggle.com/datasets/nowke9/ipldata) by Navaneesh Kumar (Kaggle),
licensed **CC BY-NC-SA 4.0**. Details and checksums are in [`data/README.md`](data/README.md).
**Code:** MIT licence ([`LICENSE`](LICENSE)). The dataset keeps its own licence.

**Limitations:** the data ends in 2019; player names are short forms (e.g. `V Kohli`); ball-by-ball totals
can differ from official scorecards by a run (Williamson 2018: 736 here vs 735 official).
