"""
match_centre.py
---------------
Builds outputs/match_centre.html: a ball-by-ball MATCH CENTRE for all
1,243 matches, using the PROCESSED data (fixed player names, standard
ground names, franchise names for filtering).

Every player, team and ground name links back to its page on the main site
(index.html#/player/..., #/team/..., #/ground/...).

For any match it shows (the drawing code is in src/match_centre.js):
  - the scorecard: every batter with how they got out, and the bowling card
  - an over-by-over strip: one symbol per ball
        .  dot    1-6 runs    W wicket    wd wide    nb no-ball    lb/b byes
  - the raw ball rows, in the same columns as the ball-by-ball CSV file

To keep the page small, each player's name is stored ONCE in a list, and each
ball stores the position of the names in that list. One ball is a list of 14 numbers:
    [over, ball, batter, non_striker, bowler, batsman_runs,
     wide_runs, noball_runs, bye_runs, legbye_runs, penalty_runs,
     player_dismissed, dismissal_kind, fielder]        (-1 = nobody)

Used by build_report.py:   match_centre.build_page(matches, deliveries, output_path)
"""

import json
import os
import metrics   # our own file: src/metrics.py

SCRIPT_FILE = os.path.join(metrics.SCRIPT_FOLDER, "match_centre.js")

PAGE_STYLE = """
body { margin: 0; background: #f6f6f4; color: #1a1a1a;
       font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.5; }
main { max-width: 1200px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { margin: 0 0 4px; font-size: 28px; }
a { color: #1d5fb3; }
.note { color: #555; font-size: 14px; }
.filters { display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }
select, input, button { font: inherit; font-size: 15px; padding: 6px 10px; border: 1px solid #bbb;
                        border-radius: 6px; background: white; color: #1a1a1a; }
input { flex: 1; min-width: 200px; }
.layout { display: grid; grid-template-columns: minmax(0, 340px) minmax(0, 1fr); gap: 16px; align-items: start; }
.list { background: white; border: 1px solid #ddd; border-radius: 10px; max-height: 80vh; overflow-y: auto; }
.row { display: block; width: 100%; text-align: left; border: 0; border-bottom: 1px solid #eee;
       border-radius: 0; background: white; padding: 8px 12px; cursor: pointer; }
.row:hover, .row.current { background: #eef3fb; }
.row small { color: #555; display: block; }
.detail { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 16px; min-width: 0; }
.meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 6px 16px;
        font-size: 14px; color: #555; }
.meta b { display: block; color: #1a1a1a; font-weight: normal; }
.tabs { display: flex; gap: 6px; margin: 16px 0 8px; }
.tabs button.on { background: #1a1a1a; color: white; }
table { border-collapse: collapse; width: 100%; font-size: 14px; margin-bottom: 12px; }
th, td { border-bottom: 1px solid #eee; padding: 5px 8px; text-align: right; white-space: nowrap; }
th:first-child, td:first-child, td.how { text-align: left; }
td.how { color: #555; white-space: normal; }
.table-box { overflow-x: auto; }
.over { display: grid; grid-template-columns: 34px minmax(0, 170px) 1fr 40px; gap: 8px; align-items: center;
        border-bottom: 1px dashed #ddd; padding: 3px 0; font-size: 13px; }
.over .who { color: #555; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ball { display: inline-flex; min-width: 24px; height: 24px; padding: 0 4px; margin: 1px; border-radius: 12px;
        align-items: center; justify-content: center; font-size: 12px; font-weight: bold; background: #eeeeea; }
.ball.dot { color: #777; }  .ball.four { background: #dcefe0; color: #24693a; }
.ball.six { background: #f6e7c2; color: #8a5f07; }  .ball.out { background: #f8dcd8; color: #a8241c; }
.ball.extra { background: #e6e8ec; color: #4b5563; font-size: 11px; }
@media (max-width: 800px) { .layout { grid-template-columns: 1fr; } .list { max-height: 320px; }
                            .over { grid-template-columns: 30px 1fr 36px; } .over .who { grid-column: 2 / 4; } }
"""


def build_data(matches, deliveries):
    """The compact JSON data for every match (see the format at the top of this file)."""
    names = sorted(set(deliveries["batter"]) | set(deliveries["non_striker"]) | set(deliveries["bowler"])
                   | set(deliveries["player_dismissed"].dropna()) | set(deliveries["fielder"].dropna()))
    position = {}
    for i in range(len(names)):
        position[names[i]] = i
    kinds = [""] + sorted(deliveries["dismissal_kind"].dropna().unique())
    kind_position = {}
    for i in range(len(kinds)):
        kind_position[kinds[i]] = i

    def name_number(value):
        """Position of a name in the list, or -1 for an empty cell."""
        if isinstance(value, str) and value != "":
            return position[value]
        return -1

    # Group the balls by match once (much faster than filtering 1,243 times).
    balls_by_match = {}
    for match_id, group in deliveries.groupby("match_id", sort=False):
        balls_by_match[match_id] = group

    match_list = []
    for i in range(len(matches)):
        match = matches.iloc[i]
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
                rows = []
                for j in range(len(balls)):
                    b = balls.iloc[j]
                    kind = b["dismissal_kind"] if isinstance(b["dismissal_kind"], str) else ""
                    rows.append([int(b["over"]), int(b["ball"]), name_number(b["batter"]), name_number(b["non_striker"]),
                                 name_number(b["bowler"]), int(b["batsman_runs"]), int(b["wide_runs"]),
                                 int(b["noball_runs"]), int(b["bye_runs"]), int(b["legbye_runs"]),
                                 int(b["penalty_runs"]), name_number(b["player_dismissed"]), kind_position[kind],
                                 name_number(b["fielder"])])
                innings_list.append({"t": balls["batting_team"].iloc[0], "so": int(balls["is_super_over"].iloc[0]),
                                     "b": rows})
        match_list.append({
            "id": int(match["match_id"]), "s": int(match["season"]), "d": match["date"].strftime("%Y-%m-%d"),
            "t1": match["team1"], "t2": match["team2"], "f1": match["team1_franchise"], "f2": match["team2_franchise"],
            "tw": match["toss_winner"], "td": match["toss_decision"], "res": result, "st": stage,
            "v": match["venue"], "c": match["city"], "pom": match["player_of_match"],
            "u": [u for u in [match["umpire1"], match["umpire2"]] if isinstance(u, str) and u != ""],
            "i": innings_list,
        })
    # Which names have a player page on the main site: anyone who batted or bowled outside super overs
    # (the same players as the site's player pages). Fielders who only came on as substitutes have none,
    # so their names are shown without a link.
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
