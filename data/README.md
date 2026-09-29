# Dataset record

| Field | Value |
|---|---|
| **Dataset name** | Indian Premier League 2008-2019 (`matches.csv` + `deliveries.csv`) |
| **Publisher** | Navaneesh Kumar (Kaggle user `nowke9`), last updated 2019-05-14 |
| **Source URL** | https://www.kaggle.com/datasets/nowke9/ipldata. Kaggle lists it as 18,375,440 bytes, exactly the size of our two CSV files together. A re-upload with the same total size is at https://www.kaggle.com/datasets/roopacalistus/ipl-dataset-2008-2019 |
| **Original ball-by-ball source** | Not stated by the publisher |
| **Download date** | 2026-09-25 (date `ipl.zip` was saved on the project computer) |
| **License** | **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-ShareAlike), https://creativecommons.org/licenses/by-nc-sa/4.0/. You may share and adapt the data for **non-commercial** use, with **credit**, under the **same license**. This applies to `data/raw/` and `data/processed/`. The MIT license in this repo covers only the code |
| **Seasons covered** | 2008–2019 (12 seasons, 756 matches, 179,078 balls) |
| **Downloaded as** | `ipl.zip` (1,260,993 bytes) |

## Raw files (`data/raw/`)

Both files are under GitHub's 50 MB limit, so they are committed to the repo.

| File | Size (bytes) | Rows | SHA-256 checksum |
|---|---|---|---|
| `matches.csv` | 140,113 | 756 | `57241c8438ce93f1824e8a07f779dc1c588687cc8afa344b2974518ad35195cb` |
| `deliveries.csv` | 18,235,327 | 179,078 | `412dca480d2bfd89138828331d45d687c29d7fb402f6b002803dd16952107314` |

Check that your copy is identical with:

```bash
python src/verify_data.py
```

## Processed files (`data/processed/`)

Made by `python src/prepare_data.py`. They are committed, so the Colab notebook can load
them straight from GitHub. The script is deterministic, so running it again gives
byte-for-byte identical files.

| File | What it is |
|---|---|
| `matches_clean.csv` | Matches with current team names, standard venue names, real dates, plus `no_result` and `rain_affected` flags |
| `deliveries_clean.csv` | Balls with current team names, `batter` column, `season` and `date` added, and 2018–19 double-counted extras fixed |

## Column guide (columns used by the analysis)

| Column | File | Meaning |
|---|---|---|
| `match_id` (`id` in raw) | both | Unique match number (**not** in time order) |
| `season` | matches | IPL year, 2008–2019 |
| `date` | matches | Match date (raw file mixes `2017-04-05` and `07/04/18`) |
| `team1`, `team2` | matches | The two teams |
| `toss_winner`, `toss_decision` | matches | Who won the toss and chose `bat` or `field` |
| `result` | matches | `normal`, `tie` (decided by super over) or `no result` |
| `dl_applied` | matches | 1 if the result used the Duckworth-Lewis rain rule |
| `winner` | matches | Winning team (includes super-over winner for ties) |
| `player_of_match` | matches | Player of the Match |
| `venue`, `city` | matches | Ground and city |
| `inning` | deliveries | 1 or 2 (3–5 are super overs) |
| `batting_team`, `bowling_team` | deliveries | Teams on this ball |
| `over` | deliveries | Over number **1–20** |
| `ball` | deliveries | Ball number in the over (goes above 6 when there are wides/no-balls) |
| `batsman` → `batter` | deliveries | Striker (facing the ball) |
| `non_striker`, `bowler` | deliveries | Other batter, bowler |
| `is_super_over` | deliveries | 1 for super-over balls (81 balls) |
| `wide_runs`, `noball_runs`, `bye_runs`, `legbye_runs`, `penalty_runs` | deliveries | Extras, each in its own column |
| `batsman_runs` | deliveries | Runs off the bat |
| `extra_runs`, `total_runs` | deliveries | All extras; batter runs + extras |
| `player_dismissed`, `dismissal_kind`, `fielder` | deliveries | Wicket details (empty on non-wicket balls) |
