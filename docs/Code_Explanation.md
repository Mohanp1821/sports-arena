# Code Explanation

A plain-language walkthrough of every part of Sports Arena: what each file does, every
cleaning step, every cricket formula and every chart.

---

## 1. The big picture

```
data/raw/ ──► verify_data.py ──► prepare_data.py ──► analysis.py ──► test_facts.py ──► build_report.py
 original      "is the data       clean data          stats, tables     check against     dashboard
 CSV files      unchanged?"       data/processed/     charts outputs/   official records  outputs/index.html
                                                           ▲
                                                 all formulas live in metrics.py
```

**Why split it into steps?** Each script does one job. If something looks wrong, we know where to
look: data (verify), cleaning (prepare), formula (metrics), drawing (analysis) or the web page (build_report).

## 2. Three ways to run the same code

| Way | Command | Used for |
|---|---|---|
| Terminal | `./run_all.sh` | Everyday runs on a laptop |
| Docker | `docker compose up --build` | A reproducible, containerised run, plus the dashboard at http://localhost:8080 |
| Google Colab | Open `notebooks/ipl_analysis.ipynb` | Explaining the code cell by cell in a browser |

---

## 3. The dataset

Two CSV files from Kaggle, covering the IPL from 2008 to 2019:

- `matches.csv`: **one row per match** (756 rows): season, date, teams, toss, winner, venue, Player of the Match.
- `deliveries.csv`: **one row per ball** (179,078 rows): batter, bowler, runs, extras, wicket.

They are linked by the match number (`id` in matches = `match_id` in deliveries).
Because we have every single ball, we can calculate any statistic ourselves.

---

## 4. `verify_data.py`: is the data the original?

It calculates a **SHA-256 checksum** of each raw file. A checksum is a "fingerprint": change
one character in the file and the fingerprint changes completely. The script compares the result with the
fingerprints saved in `data/README.md` and prints `OK` or `CHANGED`.
**Why?** Reproducibility: anyone running the project can prove they have the same data we used.

---

## 5. `prepare_data.py`: cleaning, step by step

| Step | Problem | Fix | Why it matters |
|---|---|---|---|
| Team renames | "Delhi Daredevils" became "Delhi Capitals", "Kings XI Punjab" became "Punjab Kings", and so on | Dictionary `TEAM_RENAMES` maps old names to new ones | Otherwise one team is split into two rows in every chart. Defunct teams (Deccan Chargers, Kochi, Gujarat Lions, Pune Warriors) keep their names because they are different franchises |
| Venue names | "M. Chinnaswamy Stadium" and "M Chinnaswamy Stadium" are the same ground | Dictionary `VENUE_RENAMES` | Home-ground analysis would be wrong |
| Dates | Two formats: `2017-04-05` and `07/04/18` | Read each format separately, then combine | The match numbers are **not** in time order (2017 has ids 1–59), so the form chart must sort by date |
| Seasons | Some datasets write "2007/08" | Season = year of the match date | IPL 2008 was played in 2008, IPL 2020 in 2020, so the date's year is always correct |
| No result | 4 matches were washed out | Added a `no_result` True/False column | Nobody won, so they are left out of win %. The balls bowled still count for players |
| Rain (D/L) | 19 matches were shortened | Added a `rain_affected` column | A 12-over score would pull the "average score" down unfairly |
| **Extras counted twice** | In 2018–19, 1,245 wides, byes and leg-byes were also written as batter runs | Set batter runs to 0 on those balls | Cricket rule: a batter never scores off a wide, bye or leg-bye. Warner 2019 went from 727 (wrong) to 692 (official) |
| Super overs | 81 tie-breaker balls | Kept in the file, removed in `metrics.py` | Official player records exclude super overs |

**Deterministic** means the same input always gives the same output: no random numbers, and a fixed sort
order. We tested it by running the script twice and comparing checksums of the outputs.

---

## 6. `metrics.py`: the cricket formulas

### Ball-level rules (function `add_ball_columns`)
- **Ball faced** = every ball except a **wide**. A wide is out of the batter's reach; a no-ball can be hit, so it counts.
- **Legal ball** = not a wide and not a no-ball. Only legal balls count towards the 6 balls of an over.
- **Runs conceded** = bat runs + wides + no-balls. Byes and leg-byes did not come off the bat, so they are not the bowler's fault.
- **Bowler wicket** = bowled, caught, caught and bowled, lbw, stumped, hit wicket. A **run out** is a fielding dismissal, and **retired hurt** is not out.
- **Phases:** Powerplay = overs 1–6 (fielding restrictions), Middle = 7–15, Death = 16–20.

### Batting (`batting_stats`)
| Metric | Formula | Meaning |
|---|---|---|
| Runs | sum of bat runs | Total scored |
| Balls faced | count of non-wide balls | How many balls they used |
| Innings | number of (match, innings) they batted in | |
| Dismissals | times they appear in `player_dismissed` (not retired hurt) | We use `player_dismissed` because in a run out the **non-striker** can be out |
| Average | runs ÷ dismissals | Runs per wicket lost: **consistency**. Left empty if never out (no division by zero) |
| Strike rate | runs ÷ balls × 100 | Runs per 100 balls: **speed** |
| Boundary % | (4s×4 + 6s×6) ÷ runs × 100 | How much of their scoring comes from boundaries |
| Fifties / hundreds | innings with 50–99 / 100+ | Match-winning innings |

### Bowling (`bowling_stats`)
| Metric | Formula | Meaning |
|---|---|---|
| Economy | runs conceded ÷ (legal balls ÷ 6) | Runs given per over: **control** (the key T20 bowling stat) |
| Bowling average | runs conceded ÷ wickets | Runs "paid" per wicket |
| Bowling strike rate | legal balls ÷ wickets | Balls needed per wicket |
| Dot ball % | legal balls with 0 runs conceded ÷ legal balls × 100 | Pressure created |

### Team
- **Win %** = wins ÷ matches played × 100. Each match is turned into two rows (one per team) by `team_results`; no-results are removed. Tied matches count for the super-over winner.
- **Run rate** = all runs (including extras) ÷ overs faced.
- **Average first-innings score:** total of innings 1, rain matches removed.
- **Bat first vs chase:** the team batting first is read from the ball data (innings 1), which is more reliable than the toss decision.
- **Toss impact:** % of matches the toss winner also won.
- **Head to head** (`head_to_head`): keep only matches between two chosen teams, then count each team's wins per season.
- **Home vs away:** each major team's home ground is in the `HOME_VENUES` dictionary; we compare win % there with win % elsewhere.

### Helpers
- `find_player("kohli")` lists matching names, because the data uses short forms like `V Kohli`.
- `top_performers(deliveries, season, metric, n, min_balls)` gives a top-n list. `min_balls` stops someone with 3 lucky balls from topping the strike-rate list.
- `cap_winners` gives the Orange Cap (most runs) and Purple Cap (most wickets; ties broken by economy, like the real award).

---

## 7. `analysis.py` and the notebook: the charts

| Chart | Type | What it shows | Why this type |
|---|---|---|---|
| Player form (Kohli 2016) | Bars + line | Runs each innings + 5-innings rolling average | Bars show single innings; the rolling line smooths out luck to show **form** |
| Career (Kohli) | Two panels | Runs per season, strike rate per season | Two panels, not two y-axes, because the scales differ and dual axes mislead |
| Bowler career (Malinga) | Two panels | Wickets and economy per season | Same reason |
| Compare two players | Two lines | Runs per season | Same unit, so one axis works |
| Season win % | Bar | Each team's win % in one season | Comparing categories |
| All-time win % | Horizontal bar | Ranking of teams | Long team names fit on the left |
| Phase run rate | Grouped bar | Powerplay/Middle/Death run rate per team | Compares three phases side by side |
| Bat first vs chase | Grouped bar + 50% line | Which choice wins more each season | 50% line = "no advantage" |
| First-innings trend | Line | Average score by season | A line suits change over time |
| Home vs away | Grouped bar | Home advantage for each team | |
| Head to head (MI vs CSK) | Grouped bar | Wins per season in matches between two rivals (17-11 to Mumbai) | Two teams compared season by season |
| Orange/Purple Caps | Two panels of bars | Winners and totals by season | |
| Top 10 strike rate / economy / sixes | Horizontal bar | Best players in a season | Rankings |
| Quadrant | Scatter + median lines | Average vs strike rate: Elite / Anchors / Finishers / Struggling | Shows two skills at once |
| Death-over specialists | Horizontal bar | Best economy in overs 16–20 | |
| Player of the Match | Horizontal bar | Most awards | |
| Heatmap | Colour grid | Win % for every team in every season | 13 teams × 12 seasons would be unreadable as bars |

Colours come from a colour-blind-safe palette, and every chart has a title, axis labels and a legend when there are two or more series.

---

## 8. `tests/test_facts.py`: are the numbers right?

1. Dataset size: 756 matches, 12 seasons, 4 no-results.
2. Old team names are gone.
3. No batter runs on wides, byes or leg-byes.
4. A **hand-made 4-ball example** where we worked out the answer on paper (strike rate, economy, legal balls).
5. **All 12 Orange Cap and Purple Cap winners** match the official list. Runs may differ by at most 2.

**Result:** all names match; all wickets match exactly; runs match exactly except 2018
(Williamson 736 here vs 735 official). This 1-run gap comes from how the ball-by-ball source recorded
one delivery, not from our formula.

---

## 9. `build_report.py`: the dashboard

It builds one web page, `outputs/index.html`, containing:
- headline numbers (matches, balls, seasons, teams);
- 5 key insights, **calculated from the data** (no numbers are typed by hand);
- the Orange Cap / Purple Cap table (`DataFrame.to_html()`);
- all 19 charts, grouped into Player form, Team comparisons and Top performers.

It is plain HTML with a small CSS style block, so it opens in any browser with no internet connection.

---

## 10. Docker architecture

```
┌──────────────────────────────┐   writes    ┌───────────┐   serves    ┌──────────────────────────────┐
│ pipeline (runs once)         │ ──────────► │ ./outputs │ ──────────► │ dashboard (web server)       │
│ verify → prepare → analysis  │  charts +   │  (shared  │  read-only  │ python -m http.server 8080   │
│ → tests → build_report       │  index.html │  folder)  │             │ → http://localhost:8080      │
└──────────────────────────────┘             └───────────┘             └──────────────────────────────┘
        dashboard starts ONLY if pipeline finished successfully (depends_on: service_completed_successfully)
```

- **`Dockerfile`**: the recipe for one image. It starts from `python:3.12-slim`, installs the pinned
  libraries (a cached layer, so rebuilds are fast), copies the code and data, and by default runs the pipeline.
- **`docker-compose.yml`**: two services built from that one image.
  - `pipeline` runs the analysis once and writes results into `./outputs` (a **bind mount**, so the
    charts appear on your own computer).
  - `dashboard` serves `./outputs` as a website on port **8080**. It mounts the folder **read-only**
    (`:ro`), so the web server cannot change results.
  - `depends_on … service_completed_successfully` means that if a fact check fails, the dashboard
    never starts, so wrong results are never shown.
- **Why containers?** The analysis runs the same way on any computer that has Docker or Podman,
  whatever Python version is installed there.

---

## 11. Git workflow

- `main` always holds working code.
- New work is done on **feature branches**, then merged with `--no-ff`, so the history graph shows each branch:
  - `feature/visualizations`: charts, the Colab notebook and the dashboard.
  - `feature/docker`: the Dockerfile and the two-service Compose architecture.
- Small commits with clear messages ("Add data cleaning script") tell the story of the project.
- The **`v1.0` tag** marks the finished release.
- Every command, with explanations, is in `git_commands.sh`.
