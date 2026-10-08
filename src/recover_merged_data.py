"""
recover_merged_data.py - one-off: rebuild data/merged/*.csv from the published explorer page.

The merged 2008-2026 dataset was published as a web page (a copy is in data/source/)
that holds every ball as compact JSON. This script does what the page's "Raw CSV rows"
tab does, for all 1,243 matches. After that the two CSV files are never edited:
verify_data.py checks their fingerprints and every fix happens in prepare_data.py.

Run (only needed once):  python src/recover_merged_data.py
"""

import gzip
import json
import os
import re
import pandas as pd


SCRIPT_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(SCRIPT_FOLDER)
SOURCE_PAGE = os.path.join(PROJECT_FOLDER, "data", "source", "ipl_2008_2026_explorer.html.gz")
MERGED_FOLDER = os.path.join(PROJECT_FOLDER, "data", "merged")

# The same column order as the Kaggle deliveries.csv (and the page's raw-rows tab).
DELIVERY_COLUMNS = ["match_id", "inning", "batting_team", "bowling_team", "over", "ball",
                    "batsman", "non_striker", "bowler", "is_super_over",
                    "wide_runs", "bye_runs", "legbye_runs", "noball_runs", "penalty_runs",
                    "batsman_runs", "extra_runs", "total_runs",
                    "player_dismissed", "dismissal_kind", "fielder"]

# The Kaggle matches.csv columns (umpire3 was almost always empty, so it is left out).
MATCH_COLUMNS = ["id", "season", "city", "date", "team1", "team2", "toss_winner", "toss_decision",
                 "result", "dl_applied", "winner", "win_by_runs", "win_by_wickets",
                 "player_of_match", "venue", "umpire1", "umpire2"]


def read_page_data(page_path):
    """Open the gzipped page and return the JSON data stored inside it."""
    with gzip.open(page_path, "rt", encoding="utf-8") as file:
        html = file.read()
    # The data sits between these two tags: <script type="application/json" id="data"> ... </script>
    found = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    if found is None:
        raise ValueError("No data block found in " + page_path)
    return json.loads(found.group(1))


def name_at(names, position):
    """Turn a stored position back into a player name (-1 means empty)."""
    if position < 0:
        return ""
    return names[position]


def delivery_rows(data):
    """
    Rebuild every ball, exactly like the page's "Raw CSV rows" tab:
      - inning     = 1, 2, ... in the order the innings are stored
      - bowling_team = the other team of the match
      - extra_runs = wides + no-balls + byes + leg-byes + penalties
      - total_runs = batsman_runs + extra_runs
    """
    names = data["p"]
    kinds = data["k"]
    rows = []
    for match in data["m"]:
        for innings_number, innings in enumerate(match["i"], start=1):
            batting_team = innings["t"]
            if batting_team == match["t1"]:
                bowling_team = match["t2"]
            else:
                bowling_team = match["t1"]
            for b in innings["b"]:
                wide, noball, bye, legbye, penalty = b[6], b[7], b[8], b[9], b[10]
                extras = wide + noball + bye + legbye + penalty
                rows.append([
                    match["id"], innings_number, batting_team, bowling_team, b[0], b[1],
                    name_at(names, b[2]), name_at(names, b[3]), name_at(names, b[4]), innings["so"],
                    wide, bye, legbye, noball, penalty,
                    b[5], extras, b[5] + extras,
                    name_at(names, b[11]), kinds[b[12]], name_at(names, b[13]),
                ])
    return pd.DataFrame(rows, columns=DELIVERY_COLUMNS)


def result_columns(result_text):
    """
    The page keeps the result as one sentence, e.g.
        "Kolkata Knight Riders won by 140 runs"
        "Mumbai Indians won by 5 wickets (DLS)"
        "Tied, Delhi Capitals won the super over"
        "No result"
    Turn it back into the Kaggle columns: result, dl_applied, win_by_runs, win_by_wickets.
    """
    result = "normal"
    dl_applied = 0
    win_by_runs = 0
    win_by_wickets = 0
    if result_text == "No result":
        result = "no result"
    elif result_text.startswith("Tied"):
        result = "tie"
    else:
        margin = re.search(r"won by (\d+) (run|wicket)", result_text)
        if margin is None:
            raise ValueError("Cannot read the result: " + result_text)
        if margin.group(2) == "run":
            win_by_runs = int(margin.group(1))
        else:
            win_by_wickets = int(margin.group(1))
    # Rain rule: older files write (D/L), newer ones (DLS). Both mean the same thing.
    if "(D/L)" in result_text or "(DLS)" in result_text:
        dl_applied = 1
    return result, dl_applied, win_by_runs, win_by_wickets


def match_rows(data):
    """One row per match in the Kaggle matches.csv layout."""
    rows = []
    for match in data["m"]:
        result, dl_applied, win_by_runs, win_by_wickets = result_columns(match["res"])
        umpires = match["u"] + ["", ""]          # pad so there are always two
        rows.append([match["id"], match["s"], match["c"], match["d"], match["t1"], match["t2"],
                     match["tw"], match["td"], result, dl_applied, match["w"] or "",
                     win_by_runs, win_by_wickets, match["pom"] or "", match["v"],
                     umpires[0], umpires[1]])
    return pd.DataFrame(rows, columns=MATCH_COLUMNS)


def main():
    data = read_page_data(SOURCE_PAGE)
    deliveries = delivery_rows(data)
    matches = match_rows(data)
    print("Matches   :", len(matches))
    print("Deliveries:", len(deliveries))

    os.makedirs(MERGED_FOLDER, exist_ok=True)
    matches.to_csv(os.path.join(MERGED_FOLDER, "matches_2008_2026.csv"), index=False)
    deliveries.to_csv(os.path.join(MERGED_FOLDER, "deliveries_2008_2026.csv"), index=False)
    print("Saved to:", MERGED_FOLDER)


if __name__ == "__main__":
    main()
