"""
prepare_data.py
---------------
Step 2 of the Sports Arena pipeline.

Reads the ORIGINAL files from data/raw/ and writes CLEANED files to
data/processed/. The raw files are never changed.

Input files (Kaggle IPL dataset, seasons 2008-2019):
    data/raw/matches.csv      -> one row per match   (756 rows)
    data/raw/deliveries.csv   -> one row per ball    (179,078 rows)

Output files:
    data/processed/matches_clean.csv
    data/processed/deliveries_clean.csv

The script is DETERMINISTIC: it uses no random numbers and always sorts
the data the same way, so the same input always gives the same output.

Run it with:
    python src/prepare_data.py
"""

import os
import pandas as pd


# ---------------------------------------------------------------------------
# Folder paths
# ---------------------------------------------------------------------------
SCRIPT_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(SCRIPT_FOLDER)
RAW_FOLDER = os.path.join(PROJECT_FOLDER, "data", "raw")
PROCESSED_FOLDER = os.path.join(PROJECT_FOLDER, "data", "processed")


# ---------------------------------------------------------------------------
# Cleaning rule 1: TEAM RENAMES
# ---------------------------------------------------------------------------
# Some franchises changed their name but are the SAME team (same owners,
# same fans). If we do not merge the names, one team would be split into two
# rows in every chart.
# Left side = old name in the data, right side = current name.
# Defunct teams (Deccan Chargers, Kochi Tuskers Kerala, Gujarat Lions,
# Pune Warriors) are NOT in this dictionary, so they keep their own names.
TEAM_RENAMES = {
    "Delhi Daredevils": "Delhi Capitals",                        # renamed in 2019
    "Kings XI Punjab": "Punjab Kings",                           # renamed in 2021
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",  # renamed in 2024
    "Rising Pune Supergiants": "Rising Pune Supergiant",          # 2016 spelling had an extra "s"
}


# ---------------------------------------------------------------------------
# Cleaning rule 2: VENUE SPELLINGS
# ---------------------------------------------------------------------------
# The same stadium is written in different ways in different seasons.
# We choose one standard name for each stadium.
VENUE_RENAMES = {
    "M. Chinnaswamy Stadium": "M Chinnaswamy Stadium",
    "M. A. Chidambaram Stadium": "MA Chidambaram Stadium, Chepauk",
    "MA Chidambaram Stadium": "MA Chidambaram Stadium, Chepauk",
    "Feroz Shah Kotla Ground": "Feroz Shah Kotla",
    "Rajiv Gandhi Intl. Cricket Stadium": "Rajiv Gandhi International Stadium, Uppal",
    "Punjab Cricket Association Stadium, Mohali": "Punjab Cricket Association IS Bindra Stadium, Mohali",
    "IS Bindra Stadium": "Punjab Cricket Association IS Bindra Stadium, Mohali",
    "Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium": "ACA-VDCA Stadium",
}


def load_raw_data():
    """Read the two raw CSV files and return them as two DataFrames."""
    matches = pd.read_csv(os.path.join(RAW_FOLDER, "matches.csv"))
    deliveries = pd.read_csv(os.path.join(RAW_FOLDER, "deliveries.csv"))
    print("Loaded matches   :", matches.shape)
    print("Loaded deliveries:", deliveries.shape)
    return matches, deliveries


def rename_teams(df, team_columns):
    """Replace old team names with current names in the given columns."""
    for column in team_columns:
        df[column] = df[column].replace(TEAM_RENAMES)
    return df


def fix_dates(matches):
    """
    Cleaning rule 3: DATE FORMATS.

    Seasons 2008-2017 write dates like "2017-04-05" (year-month-day), but
    seasons 2018-2019 write them like "07/04/18" (day/month/2-digit year).
    We read each format separately and combine them into one real date column.
    This matters because the match "id" numbers are NOT in time order
    (2017 matches have ids 1-59), so we must sort by date instead.
    """
    # Try the first format. Rows that do not fit become NaT ("not a time").
    dates_format_1 = pd.to_datetime(matches["date"], format="%Y-%m-%d", errors="coerce")
    # Try the second format for all rows.
    dates_format_2 = pd.to_datetime(matches["date"], format="%d/%m/%y", errors="coerce")
    # Use format 1 where it worked, otherwise use format 2.
    matches["date"] = dates_format_1.fillna(dates_format_2)

    # Safety check: every row must now have a date.
    missing = matches["date"].isna().sum()
    if missing > 0:
        raise ValueError(str(missing) + " dates could not be read")
    return matches


def fix_seasons(matches):
    """
    Cleaning rule 4: SEASON FORMAT.

    Some IPL datasets write seasons like "2007/08" or "2020/21". In those
    cases the IPL year is the SECOND year for "2007/08" (IPL 2008 was played
    in April 2008) but the FIRST year for "2020/21" (IPL 2020 was played in
    Sept-Nov 2020). The simplest correct rule is: use the year of the match date.

    In THIS dataset seasons are already plain numbers (2008, 2009 ...), so
    we simply check that the season equals the year of the match date.
    """
    matches["season"] = matches["date"].dt.year
    return matches


def fix_missing_cities(matches):
    """
    Seven 2014 matches played in the UAE have no city. Their venue is
    "Dubai International Cricket Stadium", so the city is Dubai.
    """
    dubai_rows = matches["venue"] == "Dubai International Cricket Stadium"
    matches.loc[dubai_rows, "city"] = "Dubai"
    return matches


def flag_results(matches):
    """
    Cleaning rule 5: NO RESULT MATCHES.

    4 matches were abandoned because of rain ("no result"). They have no winner.
    We do NOT delete them (the balls that were bowled still count in player
    records), but we add a True/False column "no_result" so team win %
    calculations can leave them out.

    Also note:
      - result == "tie": 9 matches were tied and decided by a SUPER OVER.
        The "winner" column already holds the super over winner, so we
        count them as normal wins.
      - dl_applied == 1: 19 matches were shortened by rain and decided by the
        Duckworth-Lewis method. Their scores are not comparable to full
        20-over scores, so we flag them for the "average score" chart.
    """
    matches["no_result"] = matches["result"] == "no result"
    matches["rain_affected"] = matches["dl_applied"] == 1
    print("No-result matches flagged:", matches["no_result"].sum())
    print("Rain (D/L) matches flagged:", matches["rain_affected"].sum())
    return matches


def clean_matches(matches):
    """Apply all match-level cleaning steps in order."""
    matches = rename_teams(matches, ["team1", "team2", "toss_winner", "winner"])
    matches["venue"] = matches["venue"].replace(VENUE_RENAMES)
    matches = fix_dates(matches)
    matches = fix_seasons(matches)
    matches = fix_missing_cities(matches)
    matches = flag_results(matches)

    # The third umpire column is mostly empty and not needed for analysis.
    matches = matches.drop(columns=["umpire3"])

    # Rename "id" to "match_id" so it has the same name as in deliveries.
    matches = matches.rename(columns={"id": "match_id"})

    # Sort by date, then by match_id, so the order is always the same.
    matches = matches.sort_values(["date", "match_id"]).reset_index(drop=True)
    return matches


def fix_double_counted_extras(deliveries):
    """
    Cleaning rule 6: EXTRAS COUNTED TWICE (found while checking this dataset).

    Cricket rule: a batter can NEVER score runs off a wide, a bye or a
    leg-bye. Those runs are extras only.

    In the 2018 and 2019 rows of this dataset, about 1,245 balls break
    this rule: a wide of 1 run is stored as wide_runs = 1 AND
    batsman_runs = 1, so the run is counted twice. This made David
    Warner's 2019 total 727 instead of the real 692.

    Fix: on any ball with wide, bye or leg-bye runs, set batsman_runs to 0
    and recalculate total_runs. Seasons 2008-2017 already follow the rule,
    so they are not changed.
    """
    extra_only = (deliveries["wide_runs"] > 0) | (deliveries["bye_runs"] > 0) | (deliveries["legbye_runs"] > 0)
    wrong_rows = extra_only & (deliveries["batsman_runs"] > 0)
    print("Balls with extras counted twice (fixed):", wrong_rows.sum())

    deliveries.loc[wrong_rows, "batsman_runs"] = 0
    deliveries["total_runs"] = deliveries["batsman_runs"] + deliveries["extra_runs"]
    return deliveries


def clean_deliveries(deliveries, matches):
    """
    Apply all ball-by-ball cleaning steps.

    Notes about this file (checked while building the project):
      - Overs are numbered 1 to 20 (not 0 to 19), and balls start at 1.
      - Extras are stored in separate columns: wide_runs, noball_runs,
        bye_runs, legbye_runs, penalty_runs. This lets us calculate
        balls faced and economy rate correctly.
      - SUPER OVERS: 81 balls have is_super_over == 1 (innings 3, 4, 5).
        We KEEP them in this file (so the data is complete), but the metric
        functions in src/metrics.py REMOVE them before calculating player
        stats, because official IPL records do not count super overs.
      - 32 balls share the same (match, innings, over, ball) number. They are
        real, different deliveries in very long overs with many extras, so
        we keep them.
    """
    deliveries = rename_teams(deliveries, ["batting_team", "bowling_team"])
    deliveries = fix_double_counted_extras(deliveries)

    # Rename "batsman" to "batter" (the modern cricket word).
    deliveries = deliveries.rename(columns={"batsman": "batter"})

    # Add season and date to every ball, using a merge on match_id.
    match_info = matches[["match_id", "season", "date"]]
    deliveries = deliveries.merge(match_info, on="match_id", how="left")

    # Remember the original row order, so balls with the same number
    # stay in the order they were bowled.
    deliveries["row_order"] = range(len(deliveries))

    # Sort by date, then match, innings, over and original order.
    # kind="mergesort" is a "stable" sort: equal rows keep their order.
    deliveries = deliveries.sort_values(
        ["date", "match_id", "inning", "over", "row_order"], kind="mergesort"
    )
    deliveries = deliveries.drop(columns=["row_order"]).reset_index(drop=True)
    return deliveries


def save_processed(matches, deliveries):
    """Write the cleaned DataFrames to data/processed/."""
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)
    # Write dates as plain text like 2017-04-05 so the output never changes.
    matches.to_csv(os.path.join(PROCESSED_FOLDER, "matches_clean.csv"),
                   index=False, date_format="%Y-%m-%d")
    deliveries.to_csv(os.path.join(PROCESSED_FOLDER, "deliveries_clean.csv"),
                      index=False, date_format="%Y-%m-%d")
    print("Saved cleaned files to:", PROCESSED_FOLDER)


def main():
    matches, deliveries = load_raw_data()
    matches = clean_matches(matches)
    deliveries = clean_deliveries(deliveries, matches)

    # Quick summary so the user can see what was produced.
    print("Seasons:", matches["season"].min(), "to", matches["season"].max())
    print("Teams after renaming:", matches["team1"].nunique())
    print("Venues after cleaning:", matches["venue"].nunique())
    save_processed(matches, deliveries)


if __name__ == "__main__":
    main()
