"""
prepare_data.py
---------------
Step 2 of the Sports Arena pipeline: the ANALYSIS LAYER.

Reads the merged 2008-2026 dataset and writes analysis-ready copies to
data/processed/. The merged files are NEVER changed: every fix happens here.

Input files:
    data/merged/matches_2008_2026.csv      one row per match  (1,243 rows)
    data/merged/deliveries_2008_2026.csv   one row per ball   (295,729 rows)
    data/player_name_map.csv               71 player-name fixes (made by build_name_map.py)
    data/impact_players_2020_2026.csv      557 Impact Player substitutions (build_impact_players.py)

Output files:
    data/processed/matches_clean.csv
    data/processed/deliveries_clean.csv.gz   (gzip-compressed: the plain file is over 50 MB)
    data/processed/impact_players_clean.csv

What this step adds (each one is explained in its own function below):
    1. a FRANCHISE column next to every team name (team names stay as they
       were that season, for display)
    2. one standard name and one city for every ground
    3. one name per player across both data sources (the name map)
    4. real dates, no-result and rain flags, and the match STAGE (league or playoff)
    5. the match PHASE of every ball (Powerplay / Middle / Death)

The script is DETERMINISTIC: no random numbers and a fixed sort order,
so the same input always gives byte-for-byte the same output.

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
DATA_FOLDER = os.path.join(PROJECT_FOLDER, "data")
MERGED_FOLDER = os.path.join(DATA_FOLDER, "merged")
PROCESSED_FOLDER = os.path.join(DATA_FOLDER, "processed")


# ---------------------------------------------------------------------------
# Rule 1: FRANCHISES
# ---------------------------------------------------------------------------
# Some teams changed their name but are the SAME franchise (same owners, same
# players' contracts, same fans). The data keeps the name used THAT season
# (so a 2015 scorecard still says "Delhi Daredevils"), and we add a
# "franchise" column with today's name, so a team's stats run across eras.
# Defunct teams (Deccan Chargers, Kochi Tuskers Kerala, Pune Warriors,
# Gujarat Lions, Rising Pune Supergiant) are separate franchises: Sunrisers
# Hyderabad is NOT Deccan Chargers (different owners), so they are not merged.
TEAM_TO_FRANCHISE = {
    "Delhi Daredevils": "Delhi Capitals",                          # renamed for 2019
    "Kings XI Punjab": "Punjab Kings",                             # renamed for 2021
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",   # renamed for 2024
    "Rising Pune Supergiants": "Rising Pune Supergiant",           # 2016 spelling had an extra "s"
}

# The 10 teams playing today, with a short code for charts and the chatbot.
CURRENT_TEAMS = {
    "Chennai Super Kings": "CSK", "Delhi Capitals": "DC", "Gujarat Titans": "GT",
    "Kolkata Knight Riders": "KKR", "Lucknow Super Giants": "LSG", "Mumbai Indians": "MI",
    "Punjab Kings": "PBKS", "Rajasthan Royals": "RR", "Royal Challengers Bengaluru": "RCB",
    "Sunrisers Hyderabad": "SRH",
}


# ---------------------------------------------------------------------------
# Rule 2: VENUES and CITIES
# ---------------------------------------------------------------------------
# Kaggle writes "Wankhede Stadium", Cricsheet writes "Wankhede Stadium, Mumbai".
# Step a: remove a ", City" ending when it is the match's city.
# Step b: grounds that were RENAMED get today's name.
VENUE_RENAMES = {
    "Feroz Shah Kotla": "Arun Jaitley Stadium",                    # renamed in 2019
    "Sardar Patel Stadium, Motera": "Narendra Modi Stadium",        # rebuilt and renamed in 2021
    "Sheikh Zayed Stadium": "Zayed Cricket Stadium",                # renamed in 2023
    "Subrata Roy Sahara Stadium": "Maharashtra Cricket Association Stadium",   # same Pune ground, old name
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur":
        "Maharaja Yadavindra Singh International Cricket Stadium",
    "Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh":
        "Maharaja Yadavindra Singh International Cricket Stadium",
    "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium": "Ekana Cricket Stadium",
}

# One city per ground. Most grounds already have one; these needed a rule.
CITY_RENAMES = {"Bangalore": "Bengaluru"}
VENUE_CITY = {
    "Punjab Cricket Association IS Bindra Stadium": "Mohali",                 # data says Chandigarh or Mohali
    "Maharaja Yadavindra Singh International Cricket Stadium": "Mullanpur",   # data says Mohali or New Chandigarh
    "Dr DY Patil Sports Academy": "Navi Mumbai",                              # data says Mumbai or Navi Mumbai
}

# Playoff matches are the LAST matches of each season:
#   2008-2009: 2 semi-finals + final = 3
#   2010: 2 semi-finals + 3rd place play-off + final = 4
#   2011 onwards: Qualifier 1, Eliminator, Qualifier 2, Final = 4
# (Checked against the "stage" written in the Cricsheet files for all 19 seasons.)
PLAYOFF_MATCH_COUNT = {2008: 3, 2009: 3}
DEFAULT_PLAYOFF_MATCH_COUNT = 4


def load_merged_data():
    """Read the two merged CSV files (never edited) and return them as DataFrames."""
    matches = pd.read_csv(os.path.join(MERGED_FOLDER, "matches_2008_2026.csv"), keep_default_na=False)
    deliveries = pd.read_csv(os.path.join(MERGED_FOLDER, "deliveries_2008_2026.csv"),
                             keep_default_na=False, low_memory=False)
    print("Loaded matches   :", matches.shape)
    print("Loaded deliveries:", deliveries.shape)
    return matches, deliveries


def franchise_of(team):
    """Today's franchise name for a team name from any season."""
    return TEAM_TO_FRANCHISE.get(team, team)


def add_franchise_columns(df, team_columns):
    """For every team column, add a column with the franchise, e.g. team1 -> team1_franchise."""
    for column in team_columns:
        df[column + "_franchise"] = df[column].apply(franchise_of)
    return df


def standard_city(city):
    """Use one spelling for each city (Bangalore -> Bengaluru)."""
    return CITY_RENAMES.get(city, city)


def standard_venue(venue, all_cities):
    """
    One name per ground:
      a) remove a ", City" ending when it is the name of a city in the data
         (repeated, so "..., Mohali, Chandigarh" loses both endings).
         Endings like ", Chepauk" or ", Uppal" are areas, not cities, so they stay.
      b) apply the rename list for grounds that changed their name
    """
    removed_one = True
    while removed_one:
        removed_one = False
        for city in all_cities:
            ending = ", " + city
            if city and venue.endswith(ending):
                venue = venue[: -len(ending)]
                removed_one = True
    return VENUE_RENAMES.get(venue, venue)


def clean_venues(matches):
    """Standard ground names, then exactly one city for each ground."""
    # Every city name in the data, in both spellings (e.g. Bangalore and Bengaluru).
    all_cities = set(matches["city"]) | set(standard_city(city) for city in matches["city"])
    all_cities = sorted(all_cities)
    matches["venue"] = matches["venue"].apply(lambda venue: standard_venue(venue, all_cities))
    matches["city"] = matches["city"].apply(standard_city)

    # Grounds with a fixed city from the rule list above.
    for venue in VENUE_CITY:
        matches.loc[matches["venue"] == venue, "city"] = VENUE_CITY[venue]

    # Any other ground: use its most common city (this also fills any blank city).
    for venue in sorted(matches["venue"].unique()):
        rows = matches["venue"] == venue
        known = matches.loc[rows & (matches["city"] != ""), "city"]
        if len(known) > 0:
            matches.loc[rows, "city"] = known.value_counts().sort_index().idxmax()
    return matches


def add_stage(matches):
    """
    Label every match "League" or "Playoff" (the last 3 or 4 matches of a season),
    and give the playoffs their names. The last match of a season is the Final.
    """
    matches["stage"] = "League"
    matches["playoff_name"] = ""
    for season in sorted(matches["season"].unique()):
        count = PLAYOFF_MATCH_COUNT.get(season, DEFAULT_PLAYOFF_MATCH_COUNT)
        if season <= 2009:
            names = ["Semi-final 1", "Semi-final 2", "Final"]
        elif season == 2010:
            names = ["Semi-final 1", "Semi-final 2", "3rd place play-off", "Final"]
        else:
            names = ["Qualifier 1", "Eliminator", "Qualifier 2", "Final"]
        season_rows = matches[matches["season"] == season].sort_values(["date", "match_id"])
        last_rows = season_rows.index[-count:]
        matches.loc[last_rows, "stage"] = "Playoff"
        matches.loc[last_rows, "playoff_name"] = names
    return matches


def clean_matches(matches):
    """Apply all match-level steps in order."""
    matches = matches.rename(columns={"id": "match_id"})
    matches["date"] = pd.to_datetime(matches["date"], format="%Y-%m-%d")

    # Safety check: the IPL season is the year the match was played
    # (IPL 2020 was played in Sept-Nov 2020, IPL 2010 in March-April 2010).
    wrong_season = (matches["season"] != matches["date"].dt.year).sum()
    if wrong_season > 0:
        raise ValueError(str(wrong_season) + " matches have a season that is not the match year")

    matches = add_franchise_columns(matches, ["team1", "team2", "toss_winner", "winner"])
    matches = clean_venues(matches)

    # No result: nobody won, so these are left out of win %; the balls still count for players.
    matches["no_result"] = matches["result"] == "no result"
    # Rain rule (D/L or DLS): a shortened match, so its score is not a normal 20-over score.
    matches["rain_affected"] = matches["dl_applied"] == 1
    print("No-result matches:", matches["no_result"].sum(), "  Rain-rule matches:", matches["rain_affected"].sum())

    matches = matches.sort_values(["date", "match_id"]).reset_index(drop=True)
    matches = add_stage(matches)
    return matches


# ---------------------------------------------------------------------------
# Rule 3: PLAYER NAMES (one name per person across both sources)
# ---------------------------------------------------------------------------
def load_name_map():
    """
    Read data/player_name_map.csv into a dictionary:
        (season, season team name, old name) -> new name
    The team is part of the key so two different people with the same name
    (e.g. "Ankit Sharma" at Rajasthan 2018 vs Delhi 2018) are never mixed up.
    """
    table = pd.read_csv(os.path.join(DATA_FOLDER, "player_name_map.csv"))
    name_map = {}
    for i in range(len(table)):
        row = table.iloc[i]
        name_map[(int(row["season"]), row["team"], row["old_name"])] = row["new_name"]
    return name_map


def fixed_name(name_map, season, team, name):
    """The corrected name for one player, or the same name if no fix is needed."""
    return name_map.get((season, team, name), name)


def fixed_fielders(name_map, season, team, text):
    """
    The fielder column can hold several names ("MS Dhoni, DJ Bravo" for a run out)
    and substitutes are marked "(sub)". Fix each name and keep the "(sub)" mark.
    """
    if text == "":
        return text
    fixed = []
    for part in text.split(", "):
        is_sub = part.endswith(" (sub)")
        name = part.replace(" (sub)", "")
        name = fixed_name(name_map, season, team, name)
        fixed.append(name + " (sub)" if is_sub else name)
    return ", ".join(fixed)


def apply_name_map(deliveries, matches, name_map):
    """
    Rewrite the player names. A batter belongs to the batting team, a bowler
    and a fielder to the bowling team. Only 71 (season, team, name) keys change,
    so we only touch the rows of those seasons and teams.
    """
    changed = 0
    # Ball-by-ball columns and which team the player belongs to.
    columns = [("batter", "batting_team"), ("non_striker", "batting_team"),
               ("player_dismissed", "batting_team"), ("bowler", "bowling_team")]
    for (season, team, old_name), new_name in sorted(name_map.items()):
        for name_column, team_column in columns:
            rows = ((deliveries["season"] == season) & (deliveries[team_column] == team)
                    & (deliveries[name_column] == old_name))
            deliveries.loc[rows, name_column] = new_name
            changed += rows.sum()

    # Fielders (bowling team), one ball at a time but only where a fielder is named.
    seasons_in_map = set(key[0] for key in name_map)
    rows = deliveries["season"].isin(seasons_in_map) & (deliveries["fielder"] != "")
    new_values = []
    for index in deliveries.index[rows]:
        new_values.append(fixed_fielders(name_map, deliveries.at[index, "season"],
                                         deliveries.at[index, "bowling_team"], deliveries.at[index, "fielder"]))
    deliveries.loc[rows, "fielder"] = new_values

    # Player of the match: the player could be from either team, so try both.
    for i in matches.index:
        season = matches.at[i, "season"]
        for team in [matches.at[i, "team1"], matches.at[i, "team2"]]:
            new_name = fixed_name(name_map, season, team, matches.at[i, "player_of_match"])
            if new_name != matches.at[i, "player_of_match"]:
                matches.at[i, "player_of_match"] = new_name
                changed += 1
                break
    print("Player names fixed with the name map:", changed, "cells")
    return deliveries, matches


# ---------------------------------------------------------------------------
# Ball-by-ball cleaning
# ---------------------------------------------------------------------------
def add_phase(deliveries):
    """
    Phase of the innings for every ball (overs are numbered 1-20):
        Powerplay = overs 1-6 (only 2 fielders allowed outside the circle)
        Middle    = overs 7-15
        Death     = overs 16-20 (the last 5 overs, when batters attack)
    """
    deliveries["phase"] = "Middle"
    deliveries.loc[deliveries["over"] <= 6, "phase"] = "Powerplay"
    deliveries.loc[deliveries["over"] >= 16, "phase"] = "Death"
    return deliveries


def clean_deliveries(deliveries, matches):
    """
    Notes about the ball-by-ball file (checked while building the project):
      - Overs are numbered 1 to 20, and balls start at 1.
      - Extras are in separate columns, so balls faced and economy can be correct.
      - SUPER OVERS are kept here (is_super_over = 1) and removed in
        metrics.remove_super_overs() before any player statistic.
      - The 2018-19 Kaggle rows that counted extras twice were already fixed
        when the dataset was merged; tests/test_facts.py checks this.
    """
    deliveries = deliveries.rename(columns={"batsman": "batter"})
    deliveries = add_franchise_columns(deliveries, ["batting_team", "bowling_team"])

    # Add season, date and stage to every ball (merge on match_id).
    match_info = matches[["match_id", "season", "date", "stage"]]
    deliveries = deliveries.merge(match_info, on="match_id", how="left")
    deliveries = add_phase(deliveries)

    # Keep the original order of balls inside an over with a "stable" sort.
    deliveries["row_order"] = range(len(deliveries))
    deliveries = deliveries.sort_values(["date", "match_id", "inning", "over", "row_order"], kind="mergesort")
    deliveries = deliveries.drop(columns=["row_order"]).reset_index(drop=True)
    return deliveries


def clean_impact_players(name_map):
    """Impact Player substitutions with fixed names and a franchise column."""
    table = pd.read_csv(os.path.join(DATA_FOLDER, "impact_players_2020_2026.csv"))
    for column in ["player_in", "player_out"]:
        new_names = []
        for i in range(len(table)):
            row = table.iloc[i]
            new_names.append(fixed_name(name_map, int(row["season"]), row["team"], row[column]))
        table[column] = new_names
    table["franchise"] = table["team"].apply(franchise_of)
    return table


def save_processed(matches, deliveries, impact):
    """
    Write the cleaned tables to data/processed/ (dates as plain 2017-04-05 text).
    The ball-by-ball file is compressed with gzip, because the plain CSV is over
    GitHub's 50 MB warning size. pandas reads .csv.gz files directly.
    "mtime": 0 stops gzip from writing today's time into the file, so the
    output stays byte-for-byte identical every time (deterministic).
    """
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)
    matches.to_csv(os.path.join(PROCESSED_FOLDER, "matches_clean.csv"), index=False, date_format="%Y-%m-%d")
    deliveries.to_csv(os.path.join(PROCESSED_FOLDER, "deliveries_clean.csv.gz"), index=False,
                      date_format="%Y-%m-%d", compression={"method": "gzip", "mtime": 0})
    impact.to_csv(os.path.join(PROCESSED_FOLDER, "impact_players_clean.csv"), index=False)
    print("Saved cleaned files to:", PROCESSED_FOLDER)


def main():
    matches, deliveries = load_merged_data()
    matches = clean_matches(matches)
    deliveries = clean_deliveries(deliveries, matches)

    name_map = load_name_map()
    deliveries, matches = apply_name_map(deliveries, matches, name_map)
    impact = clean_impact_players(name_map)

    print("Seasons:", matches["season"].min(), "to", matches["season"].max(),
          "(" + str(matches["season"].nunique()) + " seasons)")
    print("Franchises:", matches["team1_franchise"].nunique(), "  Grounds:", matches["venue"].nunique())
    save_processed(matches, deliveries, impact)


if __name__ == "__main__":
    main()
