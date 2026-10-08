"""
prepare_data.py - Step 2: clean the data.

Reads the merged 2008-2026 files (never edited) and writes analysis-ready
copies to data/processed/. It adds:
  1. a franchise column (Delhi Daredevils and Delhi Capitals = one team)
  2. one name and one city for every ground
  3. one name per player across both data sources
  4. no-result and rain flags, and the stage (League / Playoff)
  5. the phase of every ball (Powerplay / Middle / Death)

Run:  python src/prepare_data.py
"""

import os
import pandas as pd

DATA_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MERGED_FOLDER = os.path.join(DATA_FOLDER, "merged")
PROCESSED_FOLDER = os.path.join(DATA_FOLDER, "processed")

# Renamed teams that are the SAME franchise. The season's name is kept for display.
# Deccan Chargers is NOT Sunrisers Hyderabad (different owners), so defunct teams stay separate.
TEAM_TO_FRANCHISE = {
    "Delhi Daredevils": "Delhi Capitals",                          # renamed 2019
    "Kings XI Punjab": "Punjab Kings",                             # renamed 2021
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",   # renamed 2024
    "Rising Pune Supergiants": "Rising Pune Supergiant",           # 2016 spelling
}

# Grounds that changed their name get today's name.
VENUE_RENAMES = {
    "Feroz Shah Kotla": "Arun Jaitley Stadium",
    "Sardar Patel Stadium, Motera": "Narendra Modi Stadium",
    "Sheikh Zayed Stadium": "Zayed Cricket Stadium",
    "Subrata Roy Sahara Stadium": "Maharashtra Cricket Association Stadium",
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur":
        "Maharaja Yadavindra Singh International Cricket Stadium",
    "Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh":
        "Maharaja Yadavindra Singh International Cricket Stadium",
    "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium": "Ekana Cricket Stadium",
}
CITY_RENAMES = {"Bangalore": "Bengaluru"}
# Grounds the data gives two cities for.
VENUE_CITY = {
    "Punjab Cricket Association IS Bindra Stadium": "Mohali",
    "Maharaja Yadavindra Singh International Cricket Stadium": "Mullanpur",
    "Dr DY Patil Sports Academy": "Navi Mumbai",
}

# Playoffs = the last matches of a season: 3 in 2008-09, 4 from 2010.
PLAYOFF_MATCH_COUNT = {2008: 3, 2009: 3}
DEFAULT_PLAYOFF_MATCH_COUNT = 4


def load_merged_data():
    matches = pd.read_csv(os.path.join(MERGED_FOLDER, "matches_2008_2026.csv"), keep_default_na=False)
    deliveries = pd.read_csv(os.path.join(MERGED_FOLDER, "deliveries_2008_2026.csv"),
                             keep_default_na=False, low_memory=False)
    print("Loaded matches   :", matches.shape)
    print("Loaded deliveries:", deliveries.shape)
    return matches, deliveries


# ---------------------------------------------------------------------------
# Teams and grounds
# ---------------------------------------------------------------------------
def franchise_of(team):
    return TEAM_TO_FRANCHISE.get(team, team)


def add_franchise_columns(df, team_columns):
    """team1 -> team1_franchise, and so on."""
    for column in team_columns:
        df[column + "_franchise"] = df[column].apply(franchise_of)
    return df


def standard_city(city):
    return CITY_RENAMES.get(city, city)


def standard_venue(venue, all_cities):
    """Remove ", City" endings ("Wankhede Stadium, Mumbai" -> "Wankhede Stadium"), then apply renames."""
    removed_one = True
    while removed_one:          # repeated, so "..., Mohali, Chandigarh" loses both endings
        removed_one = False
        for city in all_cities:
            ending = ", " + city
            if city and venue.endswith(ending):
                venue = venue[: -len(ending)]
                removed_one = True
    return VENUE_RENAMES.get(venue, venue)


def clean_venues(matches):
    """One name per ground, then exactly one city per ground."""
    all_cities = sorted(set(matches["city"]) | set(standard_city(city) for city in matches["city"]))
    matches["venue"] = matches["venue"].apply(lambda venue: standard_venue(venue, all_cities))
    matches["city"] = matches["city"].apply(standard_city)

    for venue, city in VENUE_CITY.items():
        matches.loc[matches["venue"] == venue, "city"] = city

    # Any other ground: its most common city (this also fills a blank city).
    for venue in sorted(matches["venue"].unique()):
        rows = matches["venue"] == venue
        known = matches.loc[rows & (matches["city"] != ""), "city"]
        if len(known) > 0:
            matches.loc[rows, "city"] = known.value_counts().sort_index().idxmax()
    return matches


def add_stage(matches):
    """Mark the last 3-4 matches of each season as Playoff, with their names."""
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
    matches = matches.rename(columns={"id": "match_id"})
    matches["date"] = pd.to_datetime(matches["date"], format="%Y-%m-%d")

    # Safety check: the season must be the year the match was played.
    wrong_season = (matches["season"] != matches["date"].dt.year).sum()
    if wrong_season > 0:
        raise ValueError(str(wrong_season) + " matches have a season that is not the match year")

    matches = add_franchise_columns(matches, ["team1", "team2", "toss_winner", "winner"])
    matches = clean_venues(matches)
    matches["no_result"] = matches["result"] == "no result"     # left out of win %
    matches["rain_affected"] = matches["dl_applied"] == 1       # shortened, so not a normal 20-over score
    print("No-result matches:", matches["no_result"].sum(), "  Rain-rule matches:", matches["rain_affected"].sum())

    matches = matches.sort_values(["date", "match_id"]).reset_index(drop=True)
    return add_stage(matches)


# ---------------------------------------------------------------------------
# Player names: one name per person across both sources
# ---------------------------------------------------------------------------
def load_name_map():
    """{(season, team, old name): new name}. The team is in the key so two people with one name never mix."""
    table = pd.read_csv(os.path.join(DATA_FOLDER, "player_name_map.csv"))
    name_map = {}
    for row in table.to_dict("records"):
        name_map[(int(row["season"]), row["team"], row["old_name"])] = row["new_name"]
    return name_map


def fixed_name(name_map, season, team, name):
    return name_map.get((season, team, name), name)


def fixed_fielders(name_map, season, team, text):
    """Fix each name in "MS Dhoni, DJ Bravo", keeping any "(sub)" mark."""
    if text == "":
        return text
    fixed = []
    for part in text.split(", "):
        is_sub = part.endswith(" (sub)")
        name = fixed_name(name_map, season, team, part.replace(" (sub)", ""))
        fixed.append(name + " (sub)" if is_sub else name)
    return ", ".join(fixed)


def apply_name_map(deliveries, matches, name_map):
    """Rewrite names: batters belong to the batting team, bowlers and fielders to the bowling team."""
    changed = 0
    columns = [("batter", "batting_team"), ("non_striker", "batting_team"),
               ("player_dismissed", "batting_team"), ("bowler", "bowling_team")]
    for (season, team, old_name), new_name in sorted(name_map.items()):
        for name_column, team_column in columns:
            rows = ((deliveries["season"] == season) & (deliveries[team_column] == team)
                    & (deliveries[name_column] == old_name))
            deliveries.loc[rows, name_column] = new_name
            changed += rows.sum()

    # Fielders: only rows in the seasons that have fixes and that name a fielder.
    seasons_in_map = set(key[0] for key in name_map)
    rows = deliveries["season"].isin(seasons_in_map) & (deliveries["fielder"] != "")
    deliveries.loc[rows, "fielder"] = [
        fixed_fielders(name_map, deliveries.at[i, "season"], deliveries.at[i, "bowling_team"], deliveries.at[i, "fielder"])
        for i in deliveries.index[rows]]

    # Player of the match could be from either team, so try both.
    for i in matches.index:
        for team in [matches.at[i, "team1"], matches.at[i, "team2"]]:
            new_name = fixed_name(name_map, matches.at[i, "season"], team, matches.at[i, "player_of_match"])
            if new_name != matches.at[i, "player_of_match"]:
                matches.at[i, "player_of_match"] = new_name
                changed += 1
                break
    print("Player names fixed with the name map:", changed, "cells")
    return deliveries, matches


# ---------------------------------------------------------------------------
# Ball by ball
# ---------------------------------------------------------------------------
def add_phase(deliveries):
    """Powerplay = overs 1-6 (fielding limits), Middle = 7-15, Death = 16-20."""
    deliveries["phase"] = "Middle"
    deliveries.loc[deliveries["over"] <= 6, "phase"] = "Powerplay"
    deliveries.loc[deliveries["over"] >= 16, "phase"] = "Death"
    return deliveries


def clean_deliveries(deliveries, matches):
    """Super overs are kept here; metrics.remove_super_overs() drops them before any player statistic."""
    deliveries = deliveries.rename(columns={"batsman": "batter"})
    deliveries = add_franchise_columns(deliveries, ["batting_team", "bowling_team"])
    deliveries = deliveries.merge(matches[["match_id", "season", "date", "stage"]], on="match_id", how="left")
    deliveries = add_phase(deliveries)

    # A "stable" sort (mergesort) keeps the balls of an over in the order they were bowled.
    deliveries["row_order"] = range(len(deliveries))
    deliveries = deliveries.sort_values(["date", "match_id", "inning", "over", "row_order"], kind="mergesort")
    return deliveries.drop(columns=["row_order"]).reset_index(drop=True)


def clean_impact_players(name_map):
    table = pd.read_csv(os.path.join(DATA_FOLDER, "impact_players_2020_2026.csv"))
    for column in ["player_in", "player_out"]:
        table[column] = [fixed_name(name_map, int(row["season"]), row["team"], row[column])
                         for row in table.to_dict("records")]
    table["franchise"] = table["team"].apply(franchise_of)
    return table


def save_processed(matches, deliveries, impact):
    """The ball file is gzip-compressed (the plain CSV is over 50 MB); mtime 0 keeps it byte-identical each run."""
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
