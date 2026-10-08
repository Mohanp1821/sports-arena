# Marking Scheme: Where to Find the Evidence

**Course:** Open Source Tools for Data Science (OST), CA3 & CA4 mini project
**Project:** Sports Arena: IPL Performance Analyzer
**Matching topic:** No. 13, *Open-Source Data Visualisation Dashboard* (sports dataset, GitHub,
open-source libraries, documentation, containerisation)

| # | Criterion | Marks | Where the evidence is |
|---|---|:---:|---|
| 1 | Problem statement & scope | 3 | `README.md` sections 1-3, `data/README.md` |
| 2 | Repository & commit discipline | 3 | GitHub history, feature branches (incl. `feature/ipl-2008-2026`), tags `v1.0`-`v1.2`, `git_commands.sh` |
| 3 | Architecture design (containerisation) | 4 | `Dockerfile`, `docker-compose.yml` (2 services + optional `llm` profile), `docs/Code_Explanation.md` §14 |
| 4 | Progress demonstrated (live demo) | 3 | `./run_all.sh`, `docker compose up`, `outputs/index.html`, `outputs/match_centre.html` |
| 5 | Q&A | 2 | `docs/Viva_QA.md` (44 questions with answers) |
| | **Total** | **15** | |

---

## 1. Problem statement & scope (3 marks)

**Problem.** Match results are easy to find, but *why* teams win is not: does the toss matter, is chasing better, who
wins a rivalry and where, did the Impact Player rule change scoring, and how far can a 2027 prediction be trusted?
Answering these needs every ball, cleaned so names and teams agree across 19 seasons and two sources.

**Objectives.**
1. **One clean dataset 2008-2026** (1,243 matches, 295,729 balls): franchise names, one name per ground, one name per
   player (a name map built from Cricsheet registry IDs), Impact Player substitutions.
2. **Analyst views** for any team, player or ground: rivalries, matchups, grounds, specialists, Impact Player era, trends.
3. **Two 2027 prediction models** (explainable vs machine learning), each simulating 10,000 seasons in the real format,
   compared in a walk-forward backtest against a random baseline.
4. **"Ask Sports Arena" chatbot** that answers only from computed facts.

**Scope.**

| In scope | Out of scope |
|---|---|
| IPL 2008-2026, every ball | Seasons after 2026; live data |
| Cleaning layer, cricket metrics, 37 charts, offline dashboard with drop-downs, match centre | Pace vs spin splits (no bowling styles in the data) |
| 2027 champion and award predictions, backtest, honest limits | Auctions, injuries (users can edit `data/squads_2027.csv`) |
| Offline chatbot + optional local open-weights LLM | Paid / cloud AI APIs |
| Terminal, Docker and Colab ways to run | A hosted website |

**What to show:** `README.md` (key results table), then `data/README.md` (sources, licences, name map, checksums).

---

## 2. Repository & commit discipline (3 marks)

| Good practice | Evidence |
|---|---|
| Clear, small commits with meaningful messages | `git log --oneline --graph --all` |
| Feature branches merged with `--no-ff` | `feature/visualizations`, `feature/docker`, `feature/predictions`, `feature/interactive-dashboard`, `feature/ipl-2008-2026` |
| One commit per phase on the new branch | merged data → analyst views → two models → chatbot → docs |
| Release tags | `v1.0`, `v1.1`, `v1.2` (a `v2.0` tag can mark this version after merging) |
| Standard open-source files | `README.md`, `LICENSE` (MIT), `CONTRIBUTING.md`, `.gitignore`, `requirements.txt` |
| Data never edited, all fixes in code | `data/merged/` + checksums; `src/prepare_data.py` |
| Every Git command explained | `git_commands.sh` |

---

## 3. Architecture design (4 marks)

```
┌───────────────────────────────┐  writes   ┌───────────┐  serves   ┌─────────────────────────────┐
│ pipeline (runs once)          │ ────────► │ ./outputs │ ────────► │ dashboard (web server)      │
│ verify → prepare → analysis → │           │ (shared)  │ read-only │ http://localhost:8080       │
│ tests → Model A → Model B →   │           └───────────┘           └─────────────────────────────┘
│ report → chatbot checks       │                 │ read-only     (optional profile "llm")
└───────────────────────────────┘                 ▼
                                         chat (8765) ───► ollama (11434)
```

| Design choice | Why |
|---|---|
| One `Dockerfile`, one image shared by the services | Built once, identical environment |
| `python:3.12-slim` + pinned `requirements.txt` + Node.js | Small image; same versions everywhere; Node runs the chatbot checks |
| `depends_on: service_completed_successfully` | The dashboard starts only if every check passed |
| Read-only bind mount for the dashboard | Results appear on the host; the web server cannot change them |
| Optional `llm` profile (Ollama + chat server) | Extra AI features without changing the default `docker compose up` |
| Modular code: one job per script; formulas only in `metrics.py` | Easy to test, explain and change |

---

## 4. Progress demonstrated: live demo script (3 marks)

About 6 minutes:

```bash
./run_all.sh                       # 8 steps, about 1 minute, ends with "All 24 chatbot checks passed"
open outputs/index.html            # the dashboard (works offline)
git log --oneline --graph --all    # the history
colima start && docker compose up --build    # the containerised version, then http://localhost:8080
```

Points to say:
- "Step 1 checks the merged 2008-2026 data has not changed (SHA-256)."
- "Step 2 joins team renames into franchises, gives every ground one name, and fixes 71 player names with a name map
  built from Cricsheet registry IDs, without merging two different people with the same name."
- "Step 4 checks all 38 Orange/Purple Caps and all 19 champions against the official records: all match."
- "Steps 5-6: both models favour RCB for 2027 (22.5% and 20.7%). The backtest shows neither beats a coin flip's log loss
  before a season starts; we report that honestly."
- **Demo clicks:** Home → click "V Kohli" (player page; hover the season chart; click a "last 10 innings" bar to open the
  scorecard; scroll to "Grounds" and click M Chinnaswamy Stadium) → on the ground page change the Period → search "SKY"
  in the header → switch light/dark with ◐ → Teams → Mumbai Indians (season chart, how they play) → "compare here" on
  Wankhede (MI v CSK at Wankhede side by side). Then Teams → Rivalries → CSK v MI → click a date in "Last 5 meetings" to open the match centre;
  Matchups → V Kohli v JJ Bumrah; Grounds → Chepauk; Pitch & player fit → Chepauk, then type "V Kohli" and click
  M Chinnaswamy Stadium in his "best grounds" chart; Trends → points table 2026 and the chase calculator;
  Ask Sports Arena → "Who won the Orange Cap in 2016?", "Kohli vs Bumrah", "Who will win IPL 2027?".

Backup: the Colab notebook (badge in `README.md`).

---

## 5. Q&A (2 marks)

`docs/Viva_QA.md`: 44 questions on reproducibility, the merge and name map, cricket formulas, both models, the backtest,
the dashboard, the chatbot, Git, Docker and licences. `docs/Code_Explanation.md` explains every file in plain language.
