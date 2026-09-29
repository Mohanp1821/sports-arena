# Marking Scheme: Where to Find the Evidence

**Course:** Open Source Tools for Data Science (OST), CA3 & CA4 mini project
**Project:** Sports Arena: IPL Performance Analyzer
**Matching topic:** No. 13, *Open-Source Data Visualisation Dashboard* (sports dataset, GitHub,
open-source libraries, documentation, containerisation)

| # | Criterion | Marks | Where the evidence is |
|---|---|:---:|---|
| 1 | Problem statement & scope | 3 | `README.md` sections 1–2, `data/README.md` |
| 2 | Repository & commit discipline | 3 | GitHub history, 2 feature branches, tag `v1.0`, `git_commands.sh` |
| 3 | Architecture design (containerisation) | 4 | `Dockerfile`, `docker-compose.yml`, `docs/Code_Explanation.md` §10 |
| 4 | Progress demonstrated (live demo) | 3 | `./run_all.sh`, `docker compose up`, `outputs/index.html` |
| 5 | Q&A | 2 | `docs/Viva_QA.md` (16 questions with answers) |
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

**Scope.**

| In scope | Out of scope |
|---|---|
| IPL seasons 2008–2019 (756 matches, real Kaggle data) | Seasons from 2020 onward (not in the dataset) |
| Data cleaning, cricket metrics, 19 charts, web dashboard | Predicting future match results (machine learning) |
| Terminal, Docker and Colab ways to run | A live-updating website |

**What to show:** `README.md` (top), then `data/README.md` (source, licence, checksums).

---

## 2. Repository & commit discipline (3 marks)

| Good practice | Evidence |
|---|---|
| Clear, small commits with meaningful messages | `git log --oneline --graph --all` |
| Feature branches merged with `--no-ff` | `feature/visualizations` and `feature/docker`, both visible in the graph |
| Release tag | `v1.0` |
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
│ → tests → build_report       │  index.html │  folder)  │             │ → http://localhost:8080      │
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
| Modular code: 5 scripts, each with one job | Easy to test, explain and change |

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

# 4. (If Docker is installed) the containerised version
docker compose up --build
#    then open http://localhost:8080 ; stop with Ctrl+C and: docker compose down
```

Points to say during the demo:
- "Step 1 proves the data is the original (SHA-256 checksums)."
- "Step 2 found a real error in the dataset: 1,245 extras counted twice in 2018–19. We fixed it."
- "Step 4 checks our Orange/Purple Cap winners against the official records: all 24 match."
- "The dashboard numbers are calculated by code; none are typed by hand."

Backup if something fails: the notebook runs in Google Colab from the **Open in Colab** badge in `README.md`.

---

## 5. Q&A (2 marks)

Read `docs/Viva_QA.md`: 16 questions covering reproducibility, data cleaning, cricket formulas,
Git branching, Docker and licences. `docs/Code_Explanation.md` explains every file in plain language.
