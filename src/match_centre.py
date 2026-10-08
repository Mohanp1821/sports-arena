"""
match_centre.py - outputs/match_centre.html: every match, ball by ball.

For any match the page shows the scorecard, an over-by-over strip and the raw ball
rows (the drawing code is in src/match_centre.js). Names link back to the main site.

To keep the page small each name is stored once in a list, and each ball is 14 numbers:
    [over, ball, batter, non_striker, bowler, batsman_runs, wide_runs, noball_runs,
     bye_runs, legbye_runs, penalty_runs, player_dismissed, dismissal_kind, fielder]
(a name = its position in the list, -1 = nobody)
"""

import json
import os
import metrics   # our own file: src/metrics.py

SCRIPT_FILE = os.path.join(metrics.SCRIPT_FOLDER, "match_centre.js")

with open(os.path.join(metrics.SCRIPT_FOLDER, "match_centre.css"), encoding="utf-8") as css_file:
    PAGE_STYLE = css_file.read()        # the look of the page: src/match_centre.css


def build_data(matches, deliveries):
    """The compact JSON data for every match (see the format at the top of this file)."""
    names = sorted(set(deliveries["batter"]) | set(deliveries["non_striker"]) | set(deliveries["bowler"])
                   | set(deliveries["player_dismissed"].dropna()) | set(deliveries["fielder"].dropna()))
    position = {name: i for i, name in enumerate(names)}
    kinds = [""] + sorted(deliveries["dismissal_kind"].dropna().unique())
    kind_position = {kind: i for i, kind in enumerate(kinds)}

    def name_number(value):
        """A name's position in the list, or -1 for an empty cell."""
        if isinstance(value, str) and value != "":
            return position[value]
        return -1

    def ball_row(b):
        kind = b["dismissal_kind"] if isinstance(b["dismissal_kind"], str) else ""
        return [int(b["over"]), int(b["ball"]), name_number(b["batter"]), name_number(b["non_striker"]),
                name_number(b["bowler"]), int(b["batsman_runs"]), int(b["wide_runs"]), int(b["noball_runs"]),
                int(b["bye_runs"]), int(b["legbye_runs"]), int(b["penalty_runs"]),
                name_number(b["player_dismissed"]), kind_position[kind], name_number(b["fielder"])]

    # Split the balls by match once (much faster than filtering 1,243 times).
    balls_by_match = {match_id: group for match_id, group in deliveries.groupby("match_id", sort=False)}

    match_list = []
    for match in matches.to_dict("records"):
        if match["no_result"]:
            result = "No result"
        elif match["result"] == "tie":
            result = "Tied, " + match["winner"] + " won the super over"
        else:
            result = match["winner"] + " " + metrics.margin_text(match)
        stage = match["playoff_name"] if match["stage"] == "Playoff" else "League"
        innings_list = []
        group = balls_by_match.get(match["match_id"])
        if group is not None:
            for inning in sorted(group["inning"].unique()):
                balls = group[group["inning"] == inning]
                innings_list.append({"t": balls["batting_team"].iloc[0], "so": int(balls["is_super_over"].iloc[0]),
                                     "b": [ball_row(b) for b in balls.to_dict("records")]})
        match_list.append({
            "id": int(match["match_id"]), "s": int(match["season"]), "d": match["date"].strftime("%Y-%m-%d"),
            "t1": match["team1"], "t2": match["team2"], "f1": match["team1_franchise"], "f2": match["team2_franchise"],
            "tw": match["toss_winner"], "td": match["toss_decision"], "res": result, "st": stage,
            "v": match["venue"], "c": match["city"], "pom": match["player_of_match"],
            "u": [u for u in [match["umpire1"], match["umpire2"]] if isinstance(u, str) and u != ""],
            "i": innings_list,
        })
    # Names with a player page on the main site (anyone who batted or bowled outside super overs);
    # a substitute who only fielded has none, so his name is shown without a link.
    normal = metrics.remove_super_overs(deliveries)
    page_players = set(normal["batter"]) | set(normal["non_striker"]) | set(normal["bowler"])
    has_page = [1 if name in page_players else 0 for name in names]
    return {"p": names, "hp": has_page, "k": kinds, "m": match_list}


def build_page(matches, deliveries, output_path):
    """Write the match centre page (data + script inside, so it works offline)."""
    data = json.dumps(build_data(matches, deliveries), separators=(",", ":"))
    with open(SCRIPT_FILE, encoding="utf-8") as file:
        script = file.read()
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Sports Arena Match Centre</title><style>" + PAGE_STYLE + "</style></head><body><main>"
            "<p><a href='index.html'>&larr; Back to the dashboard</a></p>"
            "<h1>Match centre: IPL " + metrics.season_range_text(matches) + ", ball by ball</h1>"
            "<p class='note'>" + format(len(matches), ",") + " matches and " + format(len(deliveries), ",")
            + " balls. Pick a season or team, then a match: scorecard, every over, and the raw ball rows. "
            "Team names are as they were that season; player and ground names are the cleaned ones "
            "(see data/README.md).</p>"
            "<div class='filters'><select id='season'></select><select id='team'></select>"
            "<input id='search' type='search' placeholder='Search a ground, team or player of the match'></div>"
            "<div class='layout'><div class='list' id='list'></div><div class='detail' id='detail'></div></div>"
            "<script type='application/json' id='match-data'>" + data.replace("</", "<\\/") + "</script>"
            "<script>\n" + script + "\n</script></main></body></html>")
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(page)
    print("Match centre saved:", output_path)
