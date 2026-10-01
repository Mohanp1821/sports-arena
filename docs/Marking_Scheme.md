# Marking Scheme: Where to Find the Evidence

**Course:** Open Source Tools for Data Science (OST), CA3 & CA4 mini project
**Project:** Sports Arena: IPL Performance Analyzer
**Matching topic:** No. 13, *Open-Source Data Visualisation Dashboard* (sports dataset, GitHub,
open-source libraries, documentation, containerisation)

| # | Criterion | Marks | Where the evidence is |
|---|---|:---:|---|
| 1 | Problem statement & scope | 3 | `README.md` sections 1–2, `data/README.md` |
| 2 | Repository & commit discipline | 3 | GitHub history, 4 feature branches, tags `v1.0`, `v1.1`, `v1.2`, `git_commands.sh` |
| 3 | Architecture design (containerisation) | 4 | `Dockerfile`, `docker-compose.yml`, `docs/Code_Explanation.md` §11 |
| 4 | Progress demonstrated (live demo) | 3 | `./run_all.sh`, `docker compose up`, `outputs/index.html` |
| 5 | Q&A | 2 | `docs/Viva_QA.md` (24 questions with answers) |
| | **Total** | **15** | |

---

## 1. Problem statement & scope (3 marks)

**Problem.** IPL match results are easy to find, but *why* teams win is not. How much does the toss matter?
Is chasing better? Which players are in form, and who performs in the Death overs? Answering these needs
analysis of every ball, not just final scores.

**Objective.** Build an open-source, reproducible tool that turns 179,078 raw ball-by-ball records
into clear insights on three themes:
1. **Player form:** within a season (rolling average) and across a career.
2. **Team comparisons:** win %, phase-wise run rate, toss impact, home advantage, head-to-head.
3. **Top performers:** Orange/Purple Cap winners and top-10 lists for each metric.
4. **Predictions:** the likely 2020 champion (10,000 simulated seasons) and award winners, with a backtest.

**Scope.**

| In scope | Out of scope |
|---|---|
| IPL seasons 2008–2019 (756 matches, real Kaggle data) | Real data from 2020 onward (not in the dataset) |
| Data cleaning, cricket metrics, 21 charts, interactive web dashboard (season/team filters, player search) | Predicting single matches, or player auctions and injuries |
| 2020 champion and award predictions from past form (explainable, backtested) | Complex machine-learning models |
| Terminal, Docker and Colab ways to run | A live-updating website |

**What to show:** `README.md` (top), then `data/README.md` (source, licence, checksums).

---

## 2. Repository & commit discipline (3 marks)

| Good practice | Evidence |
|---|---|
| Clear, small commits with meaningful messages | `git log --oneline --graph --all` |
| Feature branches merged with `--no-ff` | `feature/visualizations`, `feature/docker`, `feature/predictions` and `feature/interactive-dashboard`, all visible in the graph |
| Release tags | `v1.0` (first release), `v1.1` (adds 2020 predictions), `v1.2` (interactive dashboard) |
| Standard open-source files | `README.md`, `LICENSE` (MIT), `CONTRIBUTING.md`, `.gitignore`, `requirements.txt` |
| Clean repository structure | `data/`, `src/`, `tests/`, `notebooks/`, `outputs/`, `docs/` |
| Hosted publicly | https://github.com/Mohanp1821/sports-arena |
| Every Git command explained | `git_commands.sh` |

**What to show:** run `git log --oneline --graph --all` in the terminal, then open the GitHub page.

---

## 3. Architecture design (4 marks)

```
┌──────────────────────────────┐   writes    ┌───────────┐   serves    ┌──────────────────────────────┐
│ pipeline (runs once)         │ ──────────► │ ./outputs │ ──────────► │ dashboard (web server)       │
│ verify → prepare → analysis  │  charts +   │  (shared  │  read-only  │ python -m http.server 8080   │
│ → tests → predict → report   │  index.html │  folder)  │             │ → http://localhost:8080      │
└──────────────────────────────┘             └───────────┘             └──────────────────────────────┘
```

| Design choice | Why |
|---|---|
| One `Dockerfile`, one image (`sports-arena:1.0`) shared by both services | Built once, so both services run the identical environment |
| `python:3.12-slim` base image + pinned `requirements.txt` | Small image, same library versions everywhere |
| Dependencies installed **before** copying code | Docker layer caching makes rebuilds fast |
| Two services: `pipeline` and `dashboard` | Separation of concerns: compute results vs. show results |
| `depends_on: condition: service_completed_successfully` | The dashboard starts only if every fact check passed |
| Bind mount `./outputs`, **read-only** for the dashboard | Results appear on the host; the web server cannot change them |
| Modular code: 6 scripts, each with one job | Easy to test, explain and change |

**What to show:** open `docker-compose.yml` and explain the two services, then the diagram above.

---

## 4. Progress demonstrated: live demo script (3 marks)

About 5 minutes. Run each step in the terminal:

```bash
cd ~/"Downloads/Final sports arena project"

# 1. The whole analysis in one command (about 30 seconds)
./run_all.sh

# 2. Open the dashboard
open outputs/index.html

# 3. The Git history
git log --oneline --graph --all

# 4. The containerised version (tested and working)
colima start                 # Mac: start the Docker engine first (once after every restart)
docker compose up --build
#    then open http://localhost:8080 ; stop with Ctrl+C and: docker compose down
```

Points to say during the demo:
- "Step 1 proves the data is the original (SHA-256 checksums)."
- "Step 2 found a real error in the dataset: 1,245 extras counted twice in 2018–19. We fixed it."
- "Step 4 checks our Orange/Purple Cap winners and all 12 champions against the official records: all match."
- "Step 5 predicts 2020: Chennai are favourites at 23.7%. We backtested it on 2011–2019: the real champion
  was in our top 5 in 7 of 9 seasons. And against the real 2020 season: Mumbai won, our #2 pick, and the
  Purple Cap pick was exactly right."
- "The dashboard numbers are calculated by code; none are typed by hand."
- **Interactive demo:** click *Explore (interactive)*, choose Team = Chennai Super Kings (the 🏆 marks
  their titles), click the 2010 bar to drill into that season, then type `MS Dhoni` in the player search.

Backup if something fails: the notebook runs in Google Colab from the **Open in Colab** badge in `README.md`.

---

## 5. Q&A (2 marks)

Read `docs/Viva_QA.md`: 24 questions covering reproducibility, data cleaning, cricket formulas,
predictions, Git branching, Docker and licences. `docs/Code_Explanation.md` explains every file in plain language.
