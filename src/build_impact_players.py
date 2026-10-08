"""
build_impact_players.py - one-off: data/impact_players_2020_2026.csv, every Impact Player substitution.

From 2023 a team may bring in one substitute (the Impact Player) who can bat or bowl.
The ball-by-ball file has no column for this, but the Cricsheet JSON files record each
substitution with the reason "impact_player" (concussion substitutes are left out).
Columns: match_id, season, team, player_in, player_out, inning, over, ball.

Run (needs data/cricsheet/ipl_json.zip, see data/README.md):  python src/build_impact_players.py
"""

import json
import os
import zipfile
import pandas as pd


SCRIPT_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(SCRIPT_FOLDER)
CRICSHEET_ZIP = os.path.join(PROJECT_FOLDER, "data", "cricsheet", "ipl_json.zip")
OUTPUT_FILE = os.path.join(PROJECT_FOLDER, "data", "impact_players_2020_2026.csv")
FIRST_SEASON = 2020


def impact_rows(match_id, match):
    """All Impact Player substitutions in one Cricsheet match, as a list of rows."""
    season = int(match["info"]["dates"][0][:4])
    rows = []
    for inning_number, innings in enumerate(match["innings"], start=1):
        for over in innings["overs"]:
            # enumerate(..., start=1): the first delivery of the over is ball 1.
            for ball_number, delivery in enumerate(over["deliveries"], start=1):
                replacements = delivery.get("replacements", {}).get("match", [])
                for change in replacements:
                    if change["reason"] != "impact_player":
                        continue
                    rows.append([match_id, season, change["team"], change["in"], change["out"],
                                 inning_number, over["over"] + 1, ball_number])
    return rows


def main():
    rows = []
    with zipfile.ZipFile(CRICSHEET_ZIP) as archive:
        for file_name in sorted(archive.namelist()):
            if not file_name.endswith(".json"):
                continue
            match = json.loads(archive.read(file_name))
            if int(match["info"]["dates"][0][:4]) < FIRST_SEASON:
                continue
            # The Cricsheet file name is the match id used in the merged dataset (e.g. 1359475.json).
            match_id = int(file_name.replace(".json", ""))
            rows.extend(impact_rows(match_id, match))

    table = pd.DataFrame(rows, columns=["match_id", "season", "team", "player_in", "player_out",
                                        "inning", "over", "ball"])
    table = table.sort_values(["season", "match_id", "inning", "over", "ball", "team"]).reset_index(drop=True)
    table.to_csv(OUTPUT_FILE, index=False)
    print("Impact Player substitutions:", len(table))
    print(table.groupby("season").size().to_string())
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
