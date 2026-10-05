# Code Explanation

A plain-language walkthrough of every part of Sports Arena: the data, every cleaning rule, every cricket
formula, the analyst views, both prediction models, the backtest, the dashboard and the chatbot.

---

## 1. The big picture

```
data/merged/ ─► verify_data ─► prepare_data ─► analysis ─► test_facts ─► predict ─► predict_ml ─► build_report ─► test_chatbot
 never edited   "unchanged?"   clean layer     charts       official      Model A     Model B +      dashboard,       chatbot
                               data/processed/              records       2027        backtest       match centre,    questions
                                                                                                     chat facts
                                     all cricket formulas live in metrics.py
```

**Why split it into steps?** Each script does one job. If a number looks wrong we know where to look: data
(verify), cleaning (prepare), formula (metrics), drawing (analysis), predictions (predict, predict_ml) or the web
page (build_report, the JavaScript files).

## 2. Three ways to run the same code

| Way | Command | Used for |
|---|---|---|
| Terminal | `./run_all.sh` | Everyday runs (8 steps) |
| Docker | `colima start` (Mac), then `docker compose up --build` | A reproducible run plus the dashboard at http://localhost:8080 |
| Google Colab | Open `notebooks/ipl_analysis.ipynb` | Explaining the code cell by cell in a browser |

---

## 3. The dataset (one source of truth)

Two files in `data/merged/`, covering **IPL 2008-2026**:
- `matches_2008_2026.csv`: **one row per match** (1,243 rows).
- `deliveries_2008_2026.csv`: **one row per ball** (295,729 rows).

They were built from Kaggle (2008-2019) and Cricsheet (2020-2026) with the Kaggle column names, and recovered from
the published explorer page by `src/recover_merged_data.py` (see `data/README.md`). They are **never edited**: every
fix is done in `prepare_data.py`, so anyone can see exactly what was changed and why.

## 4. `verify_data.py`: is the data the original?

It calculates a **SHA-256 checksum** (a "fingerprint") of each data file and compares it with the value saved in
`data/README.md`. Change one character and the fingerprint changes completely. It checks the merged files, the name
map, the Impact Player list, the source page and the original Kaggle files.

## 5. The one-off data scripts (already run; outputs committed)

| Script | What it makes | How |
|---|---|---|
| `recover_merged_data.py` | `data/merged/*.csv` | The explorer page stores every ball as a list of 14 numbers and names in one list; the script rebuilds the CSV rows exactly as the page's "Raw CSV rows" tab does |
| `build_name_map.py` | `data/player_name_map.csv` (71 fixes) | Lines up Kaggle and Cricsheet balls over by over and takes a majority vote of Cricsheet player IDs (below) |
| `build_impact_players.py` | `data/impact_players_2020_2026.csv` (557 rows) | Reads Cricsheet's `replacements` records with reason `impact_player` |

### The name map, step by step
1. **Problem:** Kaggle writes some 2018-19 debutants differently ("S Gill" vs Cricsheet's "Shubman Gill"), which would
   split one career into two players.
2. **Pair matches:** each Kaggle match is matched with the Cricsheet match on the same date between the same teams (756/756).
3. **Line up balls:** in an over with the same number of balls in both files, ball 1 = ball 1, ball 2 = ball 2…
   So the Kaggle batter and the Cricsheet batter on that ball are the same person. Each ball is a **vote**.
4. **Majority vote keyed by (season, team, name):** the key includes the team, so "Ankit Sharma" at Delhi 2018 (really
   Abhishek Sharma) and "Ankit Sharma" at Rajasthan 2018 (a different player) are kept apart.
5. **Registry IDs, not names:** Cricsheet gives every person a unique ID. Two people called "Harmeet Singh" have
   different IDs, so we never rename Kaggle's "Harmeet Singh (2)" into "Harmeet Singh".

---

## 6. `prepare_data.py`: the analysis layer

| Step | Problem | Fix | Why it matters |
|---|---|---|---|
| Franchises | Delhi Daredevils became Delhi Capitals, Kings XI Punjab became Punjab Kings, RCB Bangalore became Bengaluru | Keep the season's name for display, add a `..._franchise` column with today's name | Team records run across eras; Deccan Chargers stay separate (a different franchise from Sunrisers) |
| Grounds | "Wankhede Stadium" (Kaggle) vs "Wankhede Stadium, Mumbai" (Cricsheet); renamed grounds | Remove a ", City" ending; rename list (Kotla → Arun Jaitley, Motera → Narendra Modi …) | 36 grounds, each with one name across 19 seasons |
| Cities | Bangalore/Bengaluru; Mohali/Chandigarh; blank cities | One city per ground | Ground and home analysis |
| Player names | Kaggle and Cricsheet spellings | Apply the name map to batter, non-striker, bowler, dismissed, fielders, Player of the Match and Impact Players | Shubman Gill has one career 2018-2026 |
| Dates and seasons | Season must equal the match year | Checked; the script stops if not | Match ids are not in time order, so we sort by date |
| No result / rain | 9 washed-out matches; 23 decided by the rain rule | `no_result` and `rain_affected` flags | Left out of win % and of average scores |
| Stage | Playoffs are not marked | Last 3 (2008-09) or 4 (2010+) matches of a season = playoffs; last = Final | Rivalry "league vs playoffs", points tables, champions (checked: 74/74 against Cricsheet) |
| Phase | Needed by many views | Powerplay 1-6, Middle 7-15, Death 16-20 | Phase specialists, era comparison, impact scores |

**Deterministic:** no random numbers and a fixed sort order. The ball file is saved gzipped **without a time stamp**
(`mtime: 0`), so running twice gives identical bytes (we checked the checksums).

---

## 7. `metrics.py`: the cricket formulas

### Ball-level rules (`add_ball_columns`)
- **Ball faced** = every ball except a **wide** (out of the batter's reach). A no-ball can be hit, so it counts.
- **Legal ball** = not a wide and not a no-ball (only legal balls make up the 6 balls of an over).
- **Runs conceded** = bat runs + wides + no-balls. Byes and leg-byes are not the bowler's fault.
- **Bowler wicket** = bowled, caught, caught and bowled, lbw, stumped, hit wicket (a run out is a fielding dismissal; retired hurt is not out).
- **Super overs** are removed before every statistic (official records exclude them).

### Batting and bowling
| Metric | Formula | Meaning |
|---|---|---|
| Average | runs ÷ dismissals | Consistency (empty if never out) |
| Strike rate | runs ÷ balls faced × 100 | Speed |
| Economy | runs conceded ÷ (legal balls ÷ 6) | Runs per over: control |
| Bowling average / strike rate | runs ÷ wickets; legal balls ÷ wickets | Cost and speed of taking wickets |
| Dot ball % | legal balls with 0 conceded ÷ legal balls × 100 | Pressure |

### Teams (always by franchise)
- **Win %** = wins ÷ matches played × 100 (`team_results` turns each match into two rows; no-results removed; a super-over win counts as a win).
- **Innings totals** (`innings_totals`): runs, wickets and legal balls of every innings; reused by many views.
- **Home grounds** (`HOME_GROUNDS`): a **list** per team, because Punjab Kings moved from Mohali to Mullanpur in 2024.
- **Champion** = winner of the last match of the season (the Final).

## 8. The analyst views (Phase 2)

| View | Function(s) | How it is calculated |
|---|---|---|
| Rivalry centre | `rivalry_record`, `rivalry_last_meetings`, `rivalry_totals`, `rivalry_top_players` | Keep only matches between the two franchises, then count wins by season, stage and ground; highest/lowest totals from `innings_totals` (lowest leaves out rain matches and won chases, which stop early on purpose) |
| Batter vs bowler | `matchup_table`, `batter_vs_bowler` | Balls faced (no wides), runs, dismissals credited to that bowler, dot %, boundary %, runs per dismissal |
| Player vs teams / how out | `batting_vs_teams`, `bowling_vs_teams`, `dismissal_types` | `batting_stats` grouped by opponent; dismissal kinds counted and turned into % |
| Ground profiles | `ground_summary`, `ground_first_innings_by_season`, `ground_phase_run_rate`, `ground_highest_totals`, `team_at_ground` | Average first innings, chase win %, how often the toss winner won after choosing bat or field, run rate by phase |
| Home fortress index | `home_fortress_index` | Home win % minus away win % (percentage points) |
| Phase specialists | `phase_batting_leaders`, `phase_bowling_leaders` | The same batting/bowling formulas on one phase's balls, with a minimum number of balls |
| Finishers | `finishers` | Death-over strike rate (min 150 balls) and % of chase innings not out |
| Partnerships | `partnerships` | Group balls by the pair at the crease (written alphabetically); the wicket number = wickets fallen before + 1. **Check:** in every innings the partnership runs add up to the team total |
| Impact Player era | `impact_era_summary`, `impact_era_phase_run_rate`, `impact_player_choices` | 2020-22 vs 2023-26; the substitute's role = what he did in that match (batted, bowled, both, neither) |
| Scoring inflation | `scoring_inflation` | First-innings average, sixes per match and run rate per season |
| Points tables | `points_table` | 2 points a win, 1 a no-result; **NRR** = runs per over scored − runs per over conceded, a team bowled out counts 20 overs. Check: the top 4 = the playoff teams in 2009-2026 (2008 differs because a match abandoned without a ball is not in the data) |
| Chase win probability | `chase_states`, `win_probability_model` | Before every chase ball: runs needed, balls left, wickets left (and required rate) → **logistic regression** learns the chance the chasing team wins (about 140,000 situations) |
| Season impact score | `season_impact_scores` | Runs × (season run rate ÷ phase run rate) + wickets × (runs per wicket in that phase); the weights come from each season's own data |

### Pitch and player fit (how a ground plays, and how it suits a player)
The data has **no pitch reports** (grass, cracks, soil) and no ball-tracking, so a ground's "pitch behaviour" is measured
from what happened there, always **compared with the league in the same seasons** (so the 2026 scoring boom does not make
grounds used recently look flatter):

| Function | How it is calculated |
|---|---|
| `pitch_components` | Per ground and season: runs, wickets, boundaries, dot balls, and what the league average would expect from the same number of balls that season (e.g. expected runs = legal balls × league runs per ball) |
| `pitch_profile` / `profile_from_components` | Add the seasons you choose, then **index = actual ÷ expected × 100** (100 = average, 110 = 10% more). Label: 105+ = high-scoring, 95 or less = low-scoring (`PITCH_HIGH`, `PITCH_LOW`) |
| `phase_index_from_components` | The same runs index for the Powerplay, Middle and Death overs (Chepauk's Middle overs: 93.3) |
| `pitch_dismissal_mix` | % of each way of getting out at the ground vs the league (a clue, e.g. bowled/lbw, not a verdict) |
| `player_ground_batting` / `_bowling` | A player at a ground vs **the same player at other grounds in the same seasons** (`same_season_split`): elsewhere = his season total − here, added over the seasons he played at the ground. This compares him with himself, in the same years, so his age and the era cancel out |
| `fielding_events`, `player_ground_fielding` | Catches (caught and bowled → the bowler), run outs (every named fielder), stumpings; substitutes left out; per match here vs elsewhere. No drops or runs saved are recorded |
| `best_ground_fits` | Players with the biggest strike-rate gain / economy drop at a ground (min 120 balls here and elsewhere) |

Checks: the whole league's index is exactly 100 every season; here + elsewhere balls = all the player's balls in those seasons.

**Pace vs spin** splits were left out: the data has no bowling styles, and guessing them would break the rule
"every number comes from the data".

## 9. `analysis.py`: the charts (37 PNG files)

Earlier charts: form, careers, team win %, phase run rate, bat first vs chase, first-innings trend, home vs away,
head to head, caps, top 10s, quadrant, death-over specialists, Player of the Match, heatmap.
Phase 2 adds: the ground map (runs index vs wickets index) and Kohli's strike rate at each ground vs elsewhere, rivalry (CSK v MI), Kohli vs the bowlers he faced most, Chepauk profile, home fortress, finishers,
partnerships, Impact Player era, Impact Player choices, scoring inflation, chase win probability, impact scores.
Rules: a title, axis labels, a legend when there are 2+ series, **no dual y-axes** (two panels instead), and the
colour-blind-safe colours BLUE, ORANGE and AQUA.

---

## 10. `predict.py`: Model A and the season simulator

### Strength (`weighted_form`, `team_strengths`)
    form = (3 × last season + 2 × season before + 1 × season before that) ÷ 6
A season a team did not play is skipped. Example (RCB): (3 × 68.8 + 2 × 73.3 + 1 × 46.7) ÷ 6 = 66.6.

### The real season format (`league_fixtures`, `make_groups`)
- 8 or 9 teams: everyone plays everyone twice.
- 10 teams: two groups of 5, **seeded by titles won, then finals reached**, in a snake (1, 4, 5, 8, 9 vs 2, 3, 6, 7, 10).
  A team plays its group twice (8), the other group once (5), and its **row-mate** in the other group a second time (1) = 14 games.
  `tests/test_facts.py` checks 70 league games and 14 per team.

### One season (`simulate_season`) and 10,000 seasons (`title_chances`)
- League: in each match the home team wins with `chance[(home, away)]` (a random number below the chance = a win).
- Table by points (a tiny random number breaks ties, standing in for net run rate).
- Playoffs at neutral grounds: Qualifier 1 (1v2), Eliminator (3v4), Qualifier 2, Final.
- Title % = seasons won ÷ 10,000. The random seed is fixed (42), so the result is the same on every run.
Model A's match chance: **A ÷ (A + B)** whoever is at home (`model_a_chances`).

### Awards (`award_candidates`)
The top 5 by form score for runs, wickets, sixes and Player of the Match awards, **only players in `data/squads_2027.csv`**.

### Squads (`load_squads`, `players_used`)
The first run writes `data/squads_2027.csv` from the players each franchise used in 2026 (batted, bowled, fielded or
came on as Impact Player). After that it is never overwritten, so you can edit it after trades and the auction.

## 11. `predict_ml.py`: Model B and the comparison

### Features (all known before the season starts)
| Feature | Meaning |
|---|---|
| `elo_diff` | Elo: like chess ratings. After each match: new = old + 20 × (result − expected), expected = 1 ÷ (1 + 10^((other − own) ÷ 400)). Before each season ratings move 1/3 back to 1500 |
| `form_diff` | Win % in the last 10 matches |
| `h2h` | Win % against this opponent in the last 3 seasons (− 50) |
| `venue_diff` | Win % at the ground, smoothed with 5 imaginary 50% games so 1 match does not count as 100% |
| `home` | +1 home, −1 away, 0 neutral |
| `squad_diff` | Sum of the best 11 previous-season impact scores in each squad |
| `impact_era` | 1 from 2023 |

**Why freeze features at the start of the season?** That is exactly the information we have before 2027, and it
keeps training and testing the same kind of data. The toss is left out because nobody knows it before the season.

### Models
- **Logistic regression** (with `StandardScaler`, so features of different sizes are comparable): a weighted sum of the
  features turned into a chance by the S-shaped logistic curve.
- **Gradient boosting** (`random_state=42`): many small decision trees, each correcting the mistakes of the ones before.
- Each match is used **twice** (A v B and B v A) and each chance is asked both ways round and averaged
  (`fair_chance`), so P(A beats B) + P(B beats A) = 1 (tested).
- **Model B** = the average of the two models' chances, fed into the same simulator.
- **Awards:** `LinearRegression` predicts next season's runs, wickets, sixes and awards from the previous two seasons.

### Walk-forward backtest 2021-2026
For each season S: train only on seasons before S (tested: training for 2021 stops at 2020), predict every real match
of S and simulate S's title in its real format; do the same for Model A.

| Score | Meaning | Coin flip |
|---|---|---|
| Accuracy | % of matches where the team given more than 50% won | 50% |
| Log loss | Average of −log(chance given to what happened); punishes confident mistakes | 0.693 |
| Brier | Average of (chance − result)²  | 0.25 |
| Calibration | When the model says 60%, does that side win about 60%? | — |
| Champion's rank | Where the real champion was in the title-chance list | 1 in 8 or 1 in 10 |

**Result:** Model A 51.2% accuracy (log loss 0.700), Model B 50.7% (0.704): **neither beats a coin flip's log loss**,
and both are over-confident (favourites at 55-65% won about half the time). This is an honest, important finding:
before a ball is bowled, IPL matches are close to a coin flip. We did **not** tune the models on the backtest seasons,
because that would make the backtest look better than the models really are (overfitting).

---

## 12. The dashboard (`build_report.py` + JavaScript)

One page, `outputs/index.html`, with all data inside it (so it works offline):

| Part | Python | JavaScript |
|---|---|---|
| Predictions: Model A vs Model B | `prediction_section` reads the prediction CSVs | — |
| Ask Sports Arena | `chat_section` embeds `chat_facts` | `chatbot.js` |
| Explore | `explorer_data` | `dashboard_explorer.js` |
| Rivalries, Matchups, Grounds, Specialists, Impact Player era, Trends | `dashboard_data.analyst_data` calculates every table | `dashboard_analytics.js` only looks rows up and divides a few counts |
| Match centre | `match_centre.build_page` → `outputs/match_centre.html` | `match_centre.js`: scorecard with dismissals and bowling card, over-by-over strip (• dot, 1-6, W, wd, nb, b, lb), raw rows |

**Why plain JavaScript (no Plotly/Streamlit)?** Nothing to install, no internet needed, and Docker serves the page as a
normal file. `tests/test_facts.py` checks that the page's tables give the same numbers as `metrics.py`.

### The site design (`src/site.js`)
- **One page, several views.** Every section sits in a `<div data-view='...'>`; `build_report.wrap_sections` puts each
  existing section into its view (Teams, Predictions, Ask, More analysis).
- **Hash router** (`parseRoute`, `route`): the part of the address after `#` says what to show (`#/player/V Kohli`,
  `#/ground/Eden Gardens`, `#/teams`). The page shows that view and hides the others, so every page has a link and the
  browser's Back button works, while it stays one offline file. Old links like `#rivalry` still work: the router finds
  the view that holds that section.
- **Search** (`resolveSearch`): exact names first, then the chatbot's alias lists ("sky", "chepauk", "kings xi punjab"),
  then names that contain the text; several matches → "Did you mean…".
- **Player and ground pages** are drawn from three data blocks already in the page (analyst data, chatbot facts and the
  small `site_data` block: phase splits, last 10 innings and spells, awards, fielding, squads, home grounds). A role's
  sections appear only if it is a real part of the player's game (120+ balls batted, 300+ balls bowled).
- **Charts** (`svgBars`, `svgLine`) are SVG written as text: bars and dots carry a `<title>`, which shows as a tooltip on
  hover; form bars link to the match centre. Axes use round steps (`niceMax`).
- **Team pages** (`renderTeam`): `metrics.team_season_summary` (win %, league position from the rebuilt points table, and
  how far they got: Champion / Runner-up / Playoffs / League stage), `team_phase_components` (runs scored and conceded per
  phase against the league in the same seasons: batting index above 100 = faster, bowling index below 100 = cheaper),
  `team_style` (batting first vs chasing, toss choices), `team_top_players`, `team_extremes` (biggest wins and defeats).
- **Two teams at one ground** (`renderCompare`): the head to head at that ground (rivalry centre data), then each team's
  record there against ANY opponent from `metrics.team_ground_stats` (played, won, batting first and chasing, runs and balls
  scored and conceded, wickets) and `team_ground_phases`, next to the ground's own average; `edgeText` writes "X lead on …"
  from two numbers; `team_ground_top_players` gives each team's best players there. Fewer than 5 matches → "small sample".
- **Links in the older tables** (`linkForText`, `linkNamesIn`): after an older section draws a table (and every time it
  redraws, noticed by a `MutationObserver`), each cell or bar label whose WHOLE text is a known player, ground or team
  (including old team names like "Kings XI Punjab") becomes a link; partnership cells ("AB de Villiers & V Kohli") get two
  links. Only exact names are linked, so ordinary text is never changed, and bars that already select a filter are skipped.
- **Match centre links:** `outputs/match_centre.html` links every player (batters, bowlers, each name in the dismissal text,
  the over strip and the raw rows), both teams, the toss winner, the ground and the player of the match back to the site
  (`index.html#/player/...`). Names that only ever appear as a substitute fielder have no player page, so they stay plain
  text (`match_centre.build_data` marks which names have a page).
- **Design tokens:** every colour is a CSS variable; dark mode (from the computer's setting or the ◐ button, remembered in
  the browser) only changes the variables. On phones the columns stack and the header scrolls away.
- **Tests:** `tests/test_site.js` (router, search, roles, career numbers, charts) and `test_site_data` in `test_facts.py`.

## 13. The chatbot

### Offline engine (`chat_facts.py` + `chatbot.js`)
1. `chat_facts.py` writes **every fact the chatbot may use** (caps, champions, careers, seasons, matchups, rivalries,
   team-at-ground, matches by date, Impact Player era, both models' predictions and backtest) plus **aliases**
   ("SKY" → SA Yadav, "CSK" → Chennai Super Kings, "Kings XI Punjab" → Punjab Kings, "Chepauk" → the ground).
2. `chatbot.js` finds the names in the question (longest alias first, whole words only; grounds, then teams, then
   players). A surname shared by several players ("Sharma") makes it ask which one, unless one player's career is
   5 times bigger (it then says which one it chose).
3. It decides the question type from keywords (a date → match on a date; "orange cap" + season → cap; two players →
   matchup; two teams → rivalry; team + ground → team at ground; "2027"/"will win" → predictions…).
4. It writes the answer **only** from the facts and adds a **source** line. Outside the data → it says so and suggests
   questions it can answer.

### Optional local LLM (`chat_server.py`)
**Retrieval-augmented generation (RAG):** the server scores every fact line by the words it shares with the question
(divided by the square root of the line length, plus hint words like "won" → "champion"), sends the best 25 lines
to a local open-weights model through **Ollama** with the rule "answer only from these facts", and returns the answer
with the model name and the number of facts used. The page uses it when `GET /health` answers within 1.5 seconds;
otherwise it stays offline. Nothing is sent to the internet.

### Tests (`tests/test_chatbot.js`)
24 question → expected-answer checks run with Node.js, e.g. "Who won the Orange Cap in 2016?" must contain "V Kohli" and
"973", and every numeric answer must name its source.

---

## 14. Docker architecture

```
┌───────────────────────────────┐  writes   ┌───────────┐  serves   ┌─────────────────────────────┐
│ pipeline (runs once)          │ ────────► │ ./outputs │ ────────► │ dashboard (web server)      │
│ verify → prepare → analysis → │           │ (shared)  │ read-only │ http://localhost:8080       │
│ tests → Model A → Model B →   │           └───────────┘           └─────────────────────────────┘
│ report → chatbot checks       │                 │ read-only
└───────────────────────────────┘                 ▼   (optional profile "llm")
                                         ┌──────────────────┐      ┌──────────────────┐
                                         │ chat (port 8765) │ ───► │ ollama (11434)   │
                                         └──────────────────┘      └──────────────────┘
```
- One image (`python:3.12-slim` + pinned libraries + Node.js for the chatbot checks).
- `dashboard` starts only if `pipeline` finished successfully, so wrong results are never shown.
- `chat` and `ollama` are in the **`llm` profile**, so the default `docker compose up` is unchanged.

## 15. Git workflow

Feature branches merged into `main` with `--no-ff` (history graph shows each branch), small commits with clear
messages, release tags, and every command explained in `git_commands.sh`. This version was built on
`feature/ipl-2008-2026` in five phases: the merged-data layer, the analyst views, the two models, the chatbot, the docs.
