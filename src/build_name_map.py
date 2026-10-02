"""
build_name_map.py
-----------------
Builds data/player_name_map.csv: how to rewrite the player names of the
2008-2019 (Kaggle) part of the dataset so they match the names used for
2020-2026 (Cricsheet).

THE PROBLEM
    The two sources write some players differently. Kaggle wrote the 2018-19
    debutants in its own short way, Cricsheet uses its own register:
        "S Gill"  (Kaggle)  vs  "Shubman Gill" (Cricsheet)
        "J Archer"          vs  "JC Archer"
        "P Shaw"            vs  "PP Shaw"
    Without a fix, Shubman Gill's career would be split into two players.

WHY NOT JUST GUESS FROM THE NAMES?
    Because different people can share a name:
      - "Ankit Sharma" at Delhi 2018 / Hyderabad 2019 is really Abhishek Sharma,
        but "Ankit Sharma" at Rajasthan 2018 is a different, real player.
      - "AS Yadav" at Mumbai 2018 is Suryakumar Yadav, but "AS Yadav" at
        Deccan Chargers 2008 is someone else.
    So we use EVIDENCE instead of guessing.

HOW IT WORKS (step by step)
    1. Cricsheet also publishes every 2008-2019 match (data/cricsheet/ipl_json.zip).
       Each Cricsheet file has a REGISTER: every player's unique ID, so two
       people with the same name always have different IDs.
    2. Pair each Kaggle match with its Cricsheet match (same date, same two teams).
    3. Line up the balls of each over. If an over has the same number of balls
       in both files, ball 1 matches ball 1, ball 2 matches ball 2, and so on.
       So the Kaggle batter on that ball and the Cricsheet batter on that ball
       are the same person. Same for the non-striker and the bowler.
    4. Each lined-up ball is one VOTE: "Kaggle name X, playing for team T in
       season S, is Cricsheet player ID Y". A batter facing 300 balls gets
       about 300 votes, so one odd ball cannot change the answer.
    5. The majority vote decides. The key is (season, team, Kaggle name), so
       the two different "Ankit Sharma"s are never merged.
    6. We keep only the rows where the name actually changes.
    7. Safety rule: never rename to a name that two different people share
       in the register (two players are called "Harmeet Singh"; Kaggle's
       "Harmeet Singh (2)" keeps them apart, so we leave it).
    8. Bonus check: a few players are spelt two ways INSIDE the Cricsheet
       files (same ID: "NA Saini" / "Navdeep Saini"); those are joined too.

Run it with (needs data/cricsheet/ipl_json.zip, see data/README.md):
    python src/build_name_map.py
"""

import json
import os
import zipfile
import pandas as pd


SCRIPT_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(SCRIPT_FOLDER)
MERGED_FOLDER = os.path.join(PROJECT_FOLDER, "data", "merged")
CRICSHEET_ZIP = os.path.join(PROJECT_FOLDER, "data", "cricsheet", "ipl_json.zip")
NAME_MAP_FILE = os.path.join(PROJECT_FOLDER, "data", "player_name_map.csv")

LAST_KAGGLE_SEASON = 2019

# Cricsheet writes the 2016 Pune team with an "s" and the 2017 one without;
# we compare team names in one spelling so the matches pair up.
SAME_TEAM = {"Rising Pune Supergiants": "Rising Pune Supergiant"}


def one_spelling(team):
    """Return the team name in the single spelling used for pairing matches."""
    return SAME_TEAM.get(team, team)


def load_cricsheet_matches(zip_path):
    """
    Read every Cricsheet match of 2008-2019 from the zip file.
    Returns a dictionary:  (date, team A, team B) -> the match JSON
    (the two teams are sorted, so the order of the teams does not matter).
    """
    found = {}
    with zipfile.ZipFile(zip_path) as archive:
        for file_name in sorted(archive.namelist()):
            if not file_name.endswith(".json"):
                continue
            match = json.loads(archive.read(file_name))
            date = match["info"]["dates"][0]
            if int(date[:4]) > LAST_KAGGLE_SEASON:
                continue
            teams = sorted(one_spelling(team) for team in match["info"]["teams"])
            found[(date, teams[0], teams[1])] = match
    return found


def cricsheet_overs(match, batting_team):
    """
    The deliveries of one innings, grouped by over:  {over number 1-20: [ball, ball, ...]}
    Cricsheet numbers overs from 0, Kaggle from 1, so we add 1.
    Super-over innings are skipped (the Kaggle side skips them too).
    """
    overs = {}
    for innings in match["innings"]:
        if innings.get("super_over"):
            continue
        if one_spelling(innings["team"]) != one_spelling(batting_team):
            continue
        for over in innings["overs"]:
            overs[over["over"] + 1] = over["deliveries"]
    return overs


def collect_votes(matches, deliveries, cricsheet):
    """
    Line up the balls and count votes.
    Returns a list of rows: season, team, kaggle_name, cricsheet_id (one per vote),
    plus how many matches could and could not be paired.
    """
    votes = []
    paired = 0
    not_paired = []
    for i in range(len(matches)):
        match = matches.iloc[i]
        teams = sorted([one_spelling(match["team1"]), one_spelling(match["team2"])])
        key = (match["date"], teams[0], teams[1])
        if key not in cricsheet:
            not_paired.append(match["id"])
            continue
        paired += 1
        cs_match = cricsheet[key]
        register = cs_match["info"]["registry"]["people"]   # name -> unique ID

        balls = deliveries[(deliveries["match_id"] == match["id"]) & (deliveries["is_super_over"] == 0)]
        for batting_team in balls["batting_team"].unique():
            innings_balls = balls[balls["batting_team"] == batting_team]
            bowling_team = innings_balls["bowling_team"].iloc[0]
            cs_overs = cricsheet_overs(cs_match, batting_team)
            for over_number in innings_balls["over"].unique():
                kaggle_over = innings_balls[innings_balls["over"] == over_number]
                cs_over = cs_overs.get(over_number, [])
                # Only line up overs with the same number of balls in both files.
                if len(kaggle_over) != len(cs_over):
                    continue
                for position in range(len(cs_over)):
                    k_ball = kaggle_over.iloc[position]
                    c_ball = cs_over[position]
                    votes.append([match["season"], batting_team, k_ball["batsman"], register[c_ball["batter"]]])
                    votes.append([match["season"], batting_team, k_ball["non_striker"], register[c_ball["non_striker"]]])
                    votes.append([match["season"], bowling_team, k_ball["bowler"], register[c_ball["bowler"]]])
    table = pd.DataFrame(votes, columns=["season", "team", "kaggle_name", "cricsheet_id"])
    return table, paired, not_paired


def read_register(zip_path):
    """
    Look through EVERY Cricsheet file (2008-2026) and count, for each player ID,
    which names it was written with, and in which season and team.
    Returns:
      names_of_id : {ID: {name: number of matches}}
      ids_of_name : {name: set of IDs}   (a name with 2+ IDs = 2 different people)
      places      : {(ID, name): set of (season, team)}
    """
    names_of_id = {}
    ids_of_name = {}
    places = {}
    with zipfile.ZipFile(zip_path) as archive:
        for file_name in sorted(archive.namelist()):
            if not file_name.endswith(".json"):
                continue
            info = json.loads(archive.read(file_name))["info"]
            season = int(info["dates"][0][:4])
            register = info["registry"]["people"]
            for team in info["players"]:
                for name in info["players"][team]:
                    player_id = register[name]
                    names_of_id.setdefault(player_id, {})
                    names_of_id[player_id][name] = names_of_id[player_id].get(name, 0) + 1
                    ids_of_name.setdefault(name, set()).add(player_id)
                    places.setdefault((player_id, name), set()).add((season, team))
    return names_of_id, ids_of_name, places


def usual_name(names_of_id, player_id):
    """The name Cricsheet uses most often for this ID (ties: alphabetical, so it never changes)."""
    counts = names_of_id[player_id]
    return sorted(counts, key=lambda name: (-counts[name], name))[0]


def majority_vote(votes, names_of_id, ids_of_name):
    """
    For each (season, team, Kaggle name), pick the Cricsheet ID with the most votes.
    Keep only rows where the name changes.

    SAFETY RULE: if the new name is shared by two different people in the
    Cricsheet register (e.g. two players called "Harmeet Singh"), we do NOT
    rename, because that would merge two people. The Kaggle name (here
    "Harmeet Singh (2)") already keeps them apart.
    """
    counts = votes.groupby(["season", "team", "kaggle_name", "cricsheet_id"]).size().reset_index(name="votes")
    totals = counts.groupby(["season", "team", "kaggle_name"])["votes"].sum().reset_index(name="total_votes")
    # Sort so the biggest vote comes first, then keep the first row of each group.
    counts = counts.sort_values(["season", "team", "kaggle_name", "votes", "cricsheet_id"],
                                ascending=[True, True, True, False, True])
    winners = counts.groupby(["season", "team", "kaggle_name"]).head(1)
    winners = winners.merge(totals, on=["season", "team", "kaggle_name"])
    winners["new_name"] = [usual_name(names_of_id, player_id) for player_id in winners["cricsheet_id"]]
    winners["vote_share"] = (winners["votes"] / winners["total_votes"] * 100).round(1)

    changed = winners[winners["kaggle_name"] != winners["new_name"]].copy()
    shared = [len(ids_of_name[name]) > 1 for name in changed["new_name"]]
    for i in range(len(changed)):
        if shared[i]:
            row = changed.iloc[i]
            print("Kept apart (name shared by 2+ people):", row["kaggle_name"], row["season"], row["team"],
                  "-> would have become", row["new_name"])
    changed = changed[[not flag for flag in shared]]

    changed = changed.rename(columns={"kaggle_name": "old_name"})
    changed["method"] = "Kaggle vs Cricsheet ball alignment"
    return changed


def same_id_spellings(names_of_id, ids_of_name, places):
    """
    A few players are written two ways inside the Cricsheet files themselves
    (same ID, e.g. "NA Saini" once and "Navdeep Saini" 33 times).
    Map the rare spelling to the usual one, for the season and team where it appears.
    """
    rows = []
    for player_id in sorted(names_of_id):
        if len(names_of_id[player_id]) < 2:
            continue
        target = usual_name(names_of_id, player_id)
        if len(ids_of_name[target]) > 1:
            continue          # same safety rule as above
        for name in sorted(names_of_id[player_id]):
            if name == target:
                continue
            for season, team in sorted(places[(player_id, name)]):
                rows.append({"season": season, "team": team, "old_name": name, "new_name": target,
                             "cricsheet_id": player_id, "votes": names_of_id[player_id][name],
                             "total_votes": sum(names_of_id[player_id].values()),
                             "method": "same Cricsheet ID, different spelling"})
    return pd.DataFrame(rows)


def main():
    matches = pd.read_csv(os.path.join(MERGED_FOLDER, "matches_2008_2026.csv"))
    deliveries = pd.read_csv(os.path.join(MERGED_FOLDER, "deliveries_2008_2026.csv"), low_memory=False)
    matches = matches[matches["season"] <= LAST_KAGGLE_SEASON]
    deliveries = deliveries[deliveries["match_id"].isin(matches["id"])]

    print("Reading Cricsheet matches ...")
    cricsheet = load_cricsheet_matches(CRICSHEET_ZIP)
    votes, paired, not_paired = collect_votes(matches, deliveries, cricsheet)
    print("Kaggle matches paired with Cricsheet:", paired, "of", len(matches))
    if not_paired:
        print("Not paired (no same-date match found):", not_paired)

    names_of_id, ids_of_name, places = read_register(CRICSHEET_ZIP)
    from_alignment = majority_vote(votes, names_of_id, ids_of_name)
    from_spellings = same_id_spellings(names_of_id, ids_of_name, places)
    name_map = pd.concat([from_alignment, from_spellings], ignore_index=True)
    name_map = name_map[["season", "team", "old_name", "new_name", "cricsheet_id", "method",
                         "votes", "total_votes", "vote_share"]]
    name_map = name_map.sort_values(["season", "team", "old_name"]).reset_index(drop=True)
    name_map.to_csv(NAME_MAP_FILE, index=False)
    print("Name fixes found:", len(name_map))
    print(name_map.to_string())
    print("Saved:", NAME_MAP_FILE)


if __name__ == "__main__":
    main()
