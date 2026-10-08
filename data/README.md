# Dataset record

## 1. The single source of truth: `data/merged/`

| File | Rows | Size (bytes) | SHA-256 checksum |
|---|---|---|---|
| `merged/matches_2008_2026.csv` | 1,243 matches | 242,337 | `a2ed25f1be44d4986aa98875e85096e44b3bf4defdc3ce5a5044c8dc037307a6` |
| `merged/deliveries_2008_2026.csv` | 295,729 balls | 30,709,099 | `81c69222b95fcb3755b4de6e92df6aef5fc5a3480d0ff98b71186ff563406736` |

* 19 seasons (2008-2026), Kaggle column names (`batsman`, `wide_runs`, ...), team names **as they were that season**.
* These two files are **never edited**. Every fix happens in `src/prepare_data.py`, which writes `data/processed/`.
* `python src/verify_data.py` checks their checksums (and the other files below) before every run.

### Where they come from

The merged set was built from two sources:

| Seasons | Source | Licence |
|---|---|---|
| 2008-2019 | [Indian Premier League 2008-2019](https://www.kaggle.com/datasets/nowke9/ipldata), Kaggle, by Navaneesh Kumar (`nowke9`) | **CC BY-NC-SA 4.0**: non-commercial use, with credit, under the same licence |
| 2020-2026 | [Cricsheet](https://cricsheet.org) IPL ball-by-ball JSON (data version 1.2.0) | See below |

**Cricsheet licence (checked on cricsheet.org on 2026-10-05):** the Cricsheet **register** (player names and IDs)
is published under the **Open Data Commons Attribution License, ODC-By 1.0**
(https://opendatacommons.org/licenses/by/1.0/), which asks users to attribute public use and keep the licence notice.
The downloads page, the about page and the README inside `ipl_json.zip` do **not** state a separate licence for the
match files themselves. This project credits Cricsheet for all 2020-2026 data and for the player register.
Please check cricsheet.org before any public or commercial reuse.

The Kaggle rows of 2018-19 that counted wides/byes/leg-byes twice and repeated a few balls were already fixed in
the merged set (`tests/test_facts.py` checks that no batter runs are scored off wides, byes or leg-byes).

### How the merged files were recovered (`src/recover_merged_data.py`)

The merged set was published as an interactive page, *"IPL 2008-2026, ball by ball"*, which carries every ball as
compact JSON and rebuilds the CSV rows in its "Raw CSV rows" tab. The original CSV files were not on this computer
(and the three build scripts named on that page, `build_classic_data.py`, `build_recent_data.py` and
`merge_datasets.py`, are not in this repository), so `src/recover_merged_data.py` does what that tab does for all
1,243 matches. A gzipped copy of the page is kept in `data/source/` so the recovery can be repeated.

Checks made on the recovered files: 1,243 matches and 295,729 balls; seasons 2008-2017 identical (balls, runs, batter
runs) to the original Kaggle files in `data/raw/`; 2018-19 a few balls fewer (the repeated balls removed); all 38
official Orange and Purple Caps 2008-2026 within 2 runs and exact on wickets.

## 2. Files built from Cricsheet (`data/cricsheet/ipl_json.zip`, not in Git)

`ipl_json.zip` (5,180,977 bytes, 1,243 matches, downloaded 2026-10-02 from https://cricsheet.org/downloads/ipl_json.zip,
SHA-256 `841b98290a08bdf2a063a9f4d6342fb2363ff246491ed3db4c571bddb6ea2a79`) is only needed to rebuild the two files
below. It is git-ignored; download it again from that address if you want to re-run the scripts.

### `player_name_map.csv`: one name per player (`src/build_name_map.py`)

Kaggle wrote some 2018-19 debutants differently from Cricsheet ("S Gill" vs "Shubman Gill", "J Archer" vs "JC Archer").
The merged set did not fix this, so:

1. Each Kaggle 2008-2019 match is paired with its Cricsheet match (same date, same two teams): 756 of 756 paired.
2. The balls of each over are lined up (only overs with the same number of balls in both files). Each lined-up ball
   is a vote: "this Kaggle name, for this team in this season, is this Cricsheet player ID".
3. The majority vote decides, keyed by **(season, team, name)**, so two people with the same name are never merged:
   "Ankit Sharma" at Delhi 2018 / Hyderabad 2019 is Abhishek Sharma, but "Ankit Sharma" at Rajasthan 2018 keeps his name;
   "AS Yadav" at Mumbai 2018-19 is SA Yadav (Suryakumar), but AS Yadav at Deccan 2008 is not changed.
4. Safety rule: never rename to a name two different people share in the register. Two players are called
   "Harmeet Singh" (IDs `2a72fd4f` and `0bf15e52`), so Kaggle's "Harmeet Singh (2)" is kept.
5. Three players are spelt two ways inside the Cricsheet files themselves (same ID): NA Saini / Navdeep Saini,
   Arshad Khan (2) / Arshad Khan, Salil Arora / S Arora. These are joined too.

Result: **71 fixes** (68 from the alignment, 3 same-ID spellings), the 68 alignment fixes each won 99.7-100% of their votes. Columns:
`season, team, old_name, new_name, cricsheet_id, method, votes, total_votes, vote_share`.

### `impact_players_2020_2026.csv`: Impact Player substitutions (`src/build_impact_players.py`)

From the Cricsheet `replacements` records with reason `impact_player` (concussion substitutes are left out):
**557 rows**, 2023-2026. Columns: `match_id, season, team, player_in, player_out, inning, over, ball`.

## 3. The analysis layer (`src/prepare_data.py` → `data/processed/`)

| File | What it is |
|---|---|
| `matches_clean.csv` | Matches with franchise columns, standard grounds and cities, `no_result`, `rain_affected`, `stage`, `playoff_name` |
| `deliveries_clean.csv.gz` | Balls with fixed names, franchise columns, `season`, `date`, `stage`, `phase` (gzip: the plain file is over 50 MB) |
| `impact_players_clean.csv` | The Impact Player list with fixed names and franchise |

The script is deterministic (no random numbers, fixed sort order, gzip written without a timestamp), so running it
again gives byte-for-byte identical files.

### Rules

**Franchises.** Team names stay as they were that season (for display) and a `..._franchise` column holds today's name:
Delhi Daredevils (to 2018) → Delhi Capitals; Kings XI Punjab (to 2020) → Punjab Kings; Royal Challengers Bangalore
(to 2023) → Royal Challengers Bengaluru; Rising Pune Supergiants → Rising Pune Supergiant (spelling). Deccan Chargers,
Kochi Tuskers Kerala, Pune Warriors, Gujarat Lions and Rising Pune Supergiant are separate franchises
(Sunrisers Hyderabad is not Deccan Chargers).

**Grounds: one name per ground (36 grounds).**
1. A ", City" ending is removed when it is a city in the data (Cricsheet's "Wankhede Stadium, Mumbai" → "Wankhede Stadium";
   "..., Mohali, Chandigarh" loses both). Area names such as ", Chepauk" or ", Uppal" stay.
2. Renamed grounds get today's name: Feroz Shah Kotla → Arun Jaitley Stadium; Sardar Patel Stadium, Motera →
   Narendra Modi Stadium; Sheikh Zayed Stadium → Zayed Cricket Stadium; Subrata Roy Sahara Stadium →
   Maharashtra Cricket Association Stadium (the same Pune ground); both Mullanpur / New Chandigarh spellings →
   Maharaja Yadavindra Singh International Cricket Stadium; Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium →
   Ekana Cricket Stadium.

**Cities: one per ground.** Bangalore → Bengaluru; the Punjab Cricket Association ground → Mohali; the Maharaja
Yadavindra Singh ground → Mullanpur; Dr DY Patil Sports Academy → Navi Mumbai; any other ground uses its most common city
(this also fills blank cities).

**Home grounds** (in `src/metrics.py`): CSK Chepauk; DC Arun Jaitley; GT Narendra Modi; KKR Eden Gardens; LSG Ekana;
MI Wankhede; PBKS Mohali **and** Mullanpur (moved in 2024); RR Sawai Mansingh; RCB Chinnaswamy; SRH Uppal.

**Stage.** The last 3 matches of 2008-2009 and the last 4 of every later season are playoffs (checked against the
stage written in the Cricsheet files: 74 of 74). The last match of a season is the Final.

**Phase.** Powerplay = overs 1-6, Middle = 7-15, Death = 16-20.

**Super overs** are kept in the files and removed before any player or team statistic.

## 4. Other files

| File | What it is |
|---|---|
| `raw/matches.csv`, `raw/deliveries.csv` | The original Kaggle 2008-2019 download (reference only; checksums `57241c84…` and `412dca48…`) |
| `source/ipl_2008_2026_explorer.html.gz` | The explorer page the merged files were recovered from |
| `squads_2027.csv` | 2027 squads (team, player). Created from each franchise's 2026 players; **edit it after trades and the auction** |
| `analyst_notes.csv` | **Your own comments** shown on the site, one row each: `page,name,note`. `page` is `player`, `ground` or `team`; `name` is exactly as the site writes it (e.g. `player,V Kohli,"Slows down against left-arm spin..."`, `ground,Wankhede Stadium,...`, `team,Mumbai Indians,...`). Empty = no notes shown. Rebuild with `python src/build_report.py` |

## 5. Checksums checked by `src/verify_data.py`

| File | SHA-256 |
|---|---|
| `merged/matches_2008_2026.csv` | `a2ed25f1be44d4986aa98875e85096e44b3bf4defdc3ce5a5044c8dc037307a6` |
| `merged/deliveries_2008_2026.csv` | `81c69222b95fcb3755b4de6e92df6aef5fc5a3480d0ff98b71186ff563406736` |
| `player_name_map.csv` | `21505be19e2d0fbfc240b434d4664230323071d32f6ef176473c69b576e756f8` |
| `impact_players_2020_2026.csv` | `ef45b304787c7736f75cfffa001e76c730a8b0058cfea5a7aac1a785e3774f34` |
| `source/ipl_2008_2026_explorer.html.gz` | `e18f126c1e5034deb8d7846679de3c62f2af1cf5840e59b1c639c6cad8248d6d` |
| `raw/matches.csv` | `57241c8438ce93f1824e8a07f779dc1c588687cc8afa344b2974518ad35195cb` |
| `raw/deliveries.csv` | `412dca480d2bfd89138828331d45d687c29d7fb402f6b002803dd16952107314` |

## 6. Column guide (processed files)

| Column | File | Meaning |
|---|---|---|
| `match_id` | both | Unique match number (**not** in time order: sort by `date`) |
| `season`, `date` | both | IPL year (2008-2026) and match date |
| `team1`, `team2`, `toss_winner`, `winner` | matches | Team names as used that season |
| `team1_franchise` … `winner_franchise` | matches | Today's franchise name (use these for team statistics) |
| `toss_decision` | matches | `bat` or `field` |
| `result`, `dl_applied` | matches | `normal`, `tie` (decided by super over) or `no result`; 1 if the rain rule decided it |
| `win_by_runs`, `win_by_wickets` | matches | The margin |
| `player_of_match`, `venue`, `city`, `umpire1`, `umpire2` | matches | As named |
| `no_result`, `rain_affected`, `stage`, `playoff_name` | matches | Added flags (see Rules) |
| `inning` | deliveries | 1, 2 (3+ are super overs) |
| `batting_team`, `bowling_team` (+ `_franchise`) | deliveries | Teams on this ball |
| `over`, `ball`, `phase` | deliveries | Over 1-20, ball in the over (above 6 with extras), Powerplay/Middle/Death |
| `batter`, `non_striker`, `bowler` | deliveries | Players (names fixed with the name map) |
| `wide_runs`, `noball_runs`, `bye_runs`, `legbye_runs`, `penalty_runs` | deliveries | Extras, each in its own column |
| `batsman_runs`, `extra_runs`, `total_runs` | deliveries | Runs off the bat; all extras; both together |
| `player_dismissed`, `dismissal_kind`, `fielder` | deliveries | Wicket details (`fielder` may list two names for a run out; "(sub)" = substitute) |
| `is_super_over` | deliveries | 1 for super-over balls |
