"""
build_report.py
---------------
Step 4 of the Sports Arena pipeline.

Builds a simple web dashboard, outputs/index.html, that shows:
  - headline numbers (matches, balls, seasons)
  - key insights
  - the Orange Cap / Purple Cap table
  - predictions for the next season (made by predict.py)
  - an INTERACTIVE "Explore the data" section: filter by season and team,
    click the bars, and search any player (the code is in dashboard_explorer.js)
  - every chart made by analysis.py

Open outputs/index.html in any web browser. With Docker, the "dashboard"
service serves it at http://localhost:8080.

Run it with:
    python src/build_report.py
"""

import os
import json
import pandas as pd
import metrics   # our own file: src/metrics.py
import predict   # our own file: src/predict.py (for the list of champions)

OUTPUT_FOLDER = os.path.join(metrics.PROJECT_FOLDER, "outputs")
EXPLORER_SCRIPT = os.path.join(metrics.SCRIPT_FOLDER, "dashboard_explorer.js")
DEFAULT_PLAYER = "V Kohli"   # player shown first in the player search

# Each chart file, with the title shown above it on the dashboard.
# The file names are the ones saved by analysis.py.
CHART_SECTIONS = {
    "Player form": [
        ("form_v_kohli_2016.png", "Kohli, IPL 2016: runs per innings and 5-innings rolling average"),
        ("career_v_kohli.png", "Kohli: runs and strike rate by season"),
        ("bowler_sl_malinga.png", "Malinga: wickets and economy by season"),
        ("compare_v_kohli_vs_rg_sharma.png", "Kohli vs Rohit Sharma: runs per season"),
    ],
    "Team comparisons": [
        ("team_win_pct_alltime.png", "All-time win % by team"),
        ("team_win_pct_2016.png", "Team win % in IPL 2016"),
        ("phase_run_rate.png", "Run rate in Powerplay, Middle and Death overs"),
        ("bat_first_vs_chase.png", "Batting first vs chasing: win % by season"),
        ("first_innings_trend.png", "Average first-innings score by season"),
        ("home_vs_away.png", "Home vs away win %"),
        ("head_to_head.png", "Head to head: Mumbai Indians vs Chennai Super Kings"),
        ("heatmap_team_season.png", "Win % by team and season"),
    ],
    "Top performers": [
        ("cap_winners.png", "Orange Cap and Purple Cap winners"),
        ("top_strike_rate_2016.png", "Top 10 strike rates, IPL 2016"),
        ("top_economy_2016.png", "Best economy, IPL 2016"),
        ("top_sixes_2016.png", "Most sixes, IPL 2016"),
        ("batting_quadrant.png", "Batting average vs strike rate"),
        ("death_over_specialists.png", "Death-over specialists (overs 16-20)"),
        ("player_of_match.png", "Most Player of the Match awards"),
    ],
}

# The look of the page (CSS). Kept in one place so the Python code stays simple.
PAGE_STYLE = """
body { margin: 0; background: #f6f6f4; color: #1a1a1a;
       font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.5; }
main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { margin: 0; font-size: 30px; }
h2 { margin-top: 44px; border-top: 1px solid #ddd; padding-top: 16px; }
.subtitle { color: #555; margin-top: 4px; }
.numbers { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-top: 24px; }
.number { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 12px 16px; }
.number b { display: block; font-size: 26px; }
.number span { color: #555; font-size: 14px; }
ul.insights li { margin-bottom: 6px; }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 480px), 1fr)); gap: 16px; }
figure { margin: 0; background: white; border: 1px solid #ddd; border-radius: 10px; overflow: hidden; }
figure img { width: 100%; display: block; }
figcaption { padding: 8px 12px; font-size: 14px; color: #333; border-top: 1px solid #eee; }
table { border-collapse: collapse; background: white; font-size: 14px; width: 100%; }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
th { background: #eef3fb; }
.table-box { overflow-x: auto; margin-bottom: 16px; }
.note { color: #555; font-size: 14px; }
nav { position: sticky; top: 0; z-index: 10; background: #1a1a1a; }
nav div { max-width: 1100px; margin: 0 auto; padding: 0 16px; display: flex; overflow-x: auto; }
nav a { color: white; text-decoration: none; padding: 10px 12px; font-size: 14px; white-space: nowrap; }
nav a:hover { background: #333; }
nav a.star { background: #eb6834; font-weight: bold; }
h2 { scroll-margin-top: 50px; }
.charts.wide { grid-template-columns: 1fr; }
.picks { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 20px; }
.pick { background: white; border: 1px solid #ddd; border-left: 5px solid #eb6834; border-radius: 10px; padding: 10px 14px; }
.pick span { display: block; color: #555; font-size: 13px; }
.pick b { font-size: 20px; }
.filters { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; background: white;
           border: 1px solid #ddd; border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; }
.filters label { display: flex; flex-direction: column; font-size: 13px; color: #555; gap: 4px; }
select, input, button { font: inherit; font-size: 15px; padding: 6px 10px; border: 1px solid #bbb;
                        border-radius: 6px; background: white; color: #1a1a1a; }
button { cursor: pointer; background: #eef3fb; }
.panel { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 12px 16px; margin-top: 16px; }
.panel h3, .panel h4 { margin: 0 0 10px; }
.two-columns { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: 16px; }
.scroll { max-height: 360px; overflow-y: auto; }
.bar-row { display: grid; grid-template-columns: minmax(90px, 230px) 1fr minmax(70px, auto);
           gap: 10px; align-items: center; padding: 3px 4px; border-radius: 4px; font-size: 14px; }
.bar-row.clickable { cursor: pointer; }
.bar-row.clickable:hover { background: #f1f1ee; }
.bar-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { background: #eeeeea; border-radius: 4px; height: 16px; overflow: hidden; }
.bar-fill { display: block; height: 100%; background: #2a78d6; }
.bar-row.highlight .bar-fill { background: #eb6834; }
.bar-row.highlight { font-weight: bold; }
.bar-value { white-space: nowrap; color: #333; }
"""


def headline_numbers(matches, deliveries):
    """Return the numbers shown in the boxes at the top of the page."""
    return [
        (str(len(matches)), "matches"),
        (format(len(deliveries), ","), "balls analysed"),
        (str(matches["season"].nunique()), "seasons (2008-2019)"),
        (str(len(set(matches["team1"]))), "teams"),
    ]


def key_insights(matches, deliveries):
    """Calculate the key insight sentences from the data (no numbers typed by hand)."""
    chase = metrics.bat_first_vs_chase(deliveries, matches)
    chase_pct = round(100 - chase["bat_first_wins"].sum() / chase["matches"].sum() * 100, 1)

    toss_table, toss_pct = metrics.toss_impact(matches)

    phases = metrics.phase_run_rate(deliveries)
    death = phases[phases["phase"] == "Death"]
    death_rate = round(death["runs"].sum() / (death["legal_balls"].sum() / 6), 1)

    teams = metrics.team_win_percent(matches, by_season=False)
    teams = teams.sort_values("win_pct", ascending=False)
    best_team = teams.iloc[0]

    caps = metrics.cap_winners(deliveries)
    best_season = caps.sort_values("runs", ascending=False).iloc[0]

    return [
        "Chasing wins more: teams batting second won " + str(chase_pct) + "% of matches.",
        "The toss hardly matters: the toss winner won " + str(toss_pct) + "% of matches.",
        "Death overs (16-20) are the fastest scoring phase: " + str(death_rate) + " runs per over.",
        best_team["team"] + " have the best all-time win rate: " + str(best_team["win_pct"]) + "%.",
        "Best single season: " + best_season["orange_cap"] + " scored " + str(best_season["runs"])
        + " runs in " + str(best_season["season"]) + ".",
    ]


def read_output_csv(file_name):
    """Read a CSV saved by predict.py, or return None if it has not been made yet."""
    path = os.path.join(OUTPUT_FOLDER, file_name)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def prediction_section(next_season):
    """HTML for the predictions: title chances, award picks and the backtest."""
    chances = read_output_csv("prediction_title_chances.csv")
    awards = read_output_csv("prediction_awards.csv")
    summary = read_output_csv("prediction_backtest_summary.csv")
    if chances is None or awards is None or summary is None:
        return ""   # predict.py has not been run, so there is nothing to show

    season = str(next_season)
    parts = ["<h2 id='predictions'>Predictions for IPL " + season + "</h2>"]
    parts.append("<p>Each team's strength is its win % over the last 3 seasons (weights 3, 2, 1), "
                 "and the whole season was simulated 10,000 times. Award picks are the players "
                 "with the best form over the same 3 seasons.</p>")

    # Headline cards: the predicted champion and the pick for each award
    favourite = chances.iloc[0]
    parts.append("<div class='picks'>")
    parts.append("<div class='pick'><span>Champion (" + str(favourite["title_pct"]) + "% chance)</span><b>"
                 + favourite["team"] + "</b></div>")
    for award in awards["award"].unique():
        pick = awards[awards["award"] == award].iloc[0]
        parts.append("<div class='pick'><span>" + award + "</span><b>" + pick["player"] + "</b></div>")
    parts.append("</div>")

    # Prediction charts, full width so they are easy to read
    parts.append("<div class='charts wide'>")
    for file_name, title in [("prediction_title_" + season + ".png", "Title and playoff chances, IPL " + season),
                             ("prediction_awards_" + season + ".png", "Award candidates, IPL " + season
                              + " (orange = our pick)")]:
        if os.path.exists(os.path.join(OUTPUT_FOLDER, file_name)):
            parts.append("<figure><img src='" + file_name + "' alt='" + title + "'>"
                         "<figcaption>" + title + "</figcaption></figure>")
    parts.append("</div>")

    # Title chances table
    chances = chances[["team", "strength", "playoff_pct", "title_pct"]]
    chances.columns = ["Team", "Strength (form win %)", "Reach playoffs %", "Win title %"]
    parts.append("<h3>Title chances</h3><div class='table-box'>" + chances.to_html(index=False) + "</div>")

    # Award picks: one row per award, with our pick and the next two candidates
    rows = []
    for award in awards["award"].unique():
        candidates = awards[awards["award"] == award]
        pick = candidates.iloc[0]
        others = ", ".join(candidates.iloc[1:3]["player"])
        rows.append({"Award": award, "Our pick": pick["player"],
                     "Form score": str(pick["form"]) + " " + pick["measure"] + " per season",
                     "Next best": others})
    parts.append("<h3>Award predictions</h3><div class='table-box'>"
                 + pd.DataFrame(rows).to_html(index=False) + "</div>")

    # Backtest: how often this method was right in the past
    summary = summary[["award", "seasons", "correct", "in_top_5"]]
    summary.columns = ["Prediction", "Seasons tested", "Exactly right", "Winner in our top 5"]
    parts.append("<h3>How reliable is this? (backtest 2011-2019)</h3>"
                 "<p class='note'>For each past season we predicted using only earlier seasons, "
                 "then compared with the real result. A random pick of the champion is right "
                 "1 time in 8. Treat the predictions as informed guesses, not certainties: "
                 "player auctions, injuries and new talent are not in the data.</p>"
                 "<div class='table-box'>" + summary.to_html(index=False) + "</div>")
    return "\n".join(parts)


def result_text(match):
    """How a match was won, in words, e.g. 'by 140 runs' or 'by 7 wickets (D/L)'."""
    if match["no_result"]:
        return "No result"
    if match["result"] == "tie":
        return "Tie, won the super over"
    if match["win_by_runs"] > 0:
        text = "by " + str(match["win_by_runs"]) + " runs"
    else:
        text = "by " + str(match["win_by_wickets"]) + " wickets"
    if match["dl_applied"] == 1:
        text += " (D/L)"   # rain-shortened match, Duckworth-Lewis method
    return text


def explorer_data(matches, deliveries):
    """
    The small tables the interactive section needs, as plain lists.
    The page's JavaScript filters and adds these up when a filter changes.
    Each row is a list (not a dictionary) to keep the page small.
    """
    # One row per match: [season, date, team1, team2, winner, margin, player of the match]
    match_rows = []
    for i in range(len(matches)):
        match = matches.iloc[i]
        winner = "" if match["no_result"] else match["winner"]
        potm = "" if match["no_result"] else match["player_of_match"]
        match_rows.append([match["season"], match["date"].strftime("%Y-%m-%d"), match["team1"],
                           match["team2"], winner, result_text(match), potm])
    match_rows.sort(key=lambda row: row[1])   # oldest match first

    # Per player, per season, per team: batting and bowling totals.
    # add_ball_columns (metrics.py) applies the cricket rules and removes super overs.
    balls = metrics.add_ball_columns(deliveries)
    batting = balls.groupby(["batter", "season", "batting_team"]).agg(
        runs=("batsman_runs", "sum"),
        balls_faced=("is_ball_faced", "sum"),
        sixes=("is_six", "sum"),
        innings=("match_id", "nunique"),     # one innings per match in T20
    ).reset_index()
    bowling = balls.groupby(["bowler", "season", "bowling_team"]).agg(
        wickets=("is_bowler_wicket", "sum"),
        legal_balls=("is_legal_ball", "sum"),
        runs_conceded=("runs_conceded", "sum"),
    ).reset_index()

    champions = predict.season_champions(matches)
    players = sorted(set(batting["batter"]) | set(bowling["bowler"]))
    return {
        "seasons": sorted(matches["season"].unique()),
        "teams": sorted(set(matches["team1"]) | set(matches["team2"])),
        "players": players,
        "default_player": DEFAULT_PLAYER,
        "champions": dict(zip(champions["season"].astype(str), champions["champion"])),
        "matches": match_rows,
        "batting": batting.values.tolist(),
        "bowling": bowling.values.tolist(),
    }


def explorer_section(matches, deliveries):
    """HTML for the interactive section: the filters, empty boxes, the data and the script."""
    parts = ["<h2 id='explore'>Explore the data (interactive)</h2>"]
    parts.append("<p>Choose a season and a team: the numbers, chart and tables below update straight away. "
                 "Click a bar in the chart to select that team or season.</p>")

    # The filters. The JavaScript fills the drop-downs with every season and team.
    parts.append("<div class='filters'>"
                 "<label>Season<select id='filter-season'><option value='all'>All seasons</option></select></label>"
                 "<label>Team<select id='filter-team'><option value='all'>All teams</option></select></label>"
                 "<button id='filter-reset' type='button'>Reset filters</button></div>")

    # Empty boxes: the JavaScript draws into these (each one has an id).
    parts.append("<div class='numbers' id='explore-cards'></div>")
    parts.append("<div class='panel'><h3 id='explore-chart-title'></h3><div id='explore-chart'></div></div>")
    parts.append("<div class='two-columns'>"
                 "<div class='panel'><h3>Top run scorers</h3><div class='table-box' id='explore-batting'></div></div>"
                 "<div class='panel'><h3>Top wicket takers</h3><div class='table-box' id='explore-bowling'></div></div>"
                 "</div>")
    parts.append("<div class='panel'><h3>Match results</h3>"
                 "<div class='table-box scroll' id='explore-results'></div></div>")

    # Player search: typing shows a list of matching names (an HTML "datalist").
    parts.append("<div class='panel'><h3>Player career</h3>"
                 "<div class='filters'><label>Type a player's name"
                 "<input id='filter-player' list='player-list' placeholder='e.g. V Kohli'></label></div>"
                 "<datalist id='player-list'></datalist>"
                 "<div id='player-chart'></div><div class='table-box' id='player-table'></div></div>")

    # The data, as JSON text. numpy numbers are turned into normal Python numbers
    # with .item(), and "</" is escaped so a name can never end the <script> tag early.
    data = json.dumps(explorer_data(matches, deliveries), separators=(",", ":"),
                      default=lambda value: value.item())
    parts.append("<script type='application/json' id='explorer-data'>"
                 + data.replace("</", "<\\/") + "</script>")

    # The JavaScript itself is kept in its own file, src/dashboard_explorer.js,
    # and copied into the page so it works offline.
    with open(EXPLORER_SCRIPT, encoding="utf-8") as file:
        parts.append("<script>\n" + file.read() + "\n</script>")
    return "\n".join(parts)


def section_id(name):
    """Turn a section name like 'Player form' into a link target like 'player-form'."""
    return name.lower().replace(" ", "-")


def navigation_bar(next_season):
    """A menu fixed at the top of the page with a link to every section."""
    links = [("predictions", "Predictions " + str(next_season)), ("explore", "Explore (interactive)"),
             ("insights", "Key insights"), ("caps", "Cap winners")]
    for section_name in CHART_SECTIONS:
        links.append((section_id(section_name), section_name))

    parts = ["<nav><div>"]
    for target, label in links:
        css_class = " class='star'" if target in ["predictions", "explore"] else ""
        parts.append("<a href='#" + target + "'" + css_class + ">" + label + "</a>")
    parts.append("</div></nav>")
    return "".join(parts)


def make_page(matches, deliveries):
    """Build the full HTML page as one text string."""
    parts = []
    parts.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append("<title>Sports Arena Dashboard</title><style>" + PAGE_STYLE + "</style></head><body>")
    next_season = int(matches["season"].max()) + 1
    parts.append(navigation_bar(next_season))
    parts.append("<main>")

    # Title
    parts.append("<h1>Sports Arena: IPL Performance Dashboard</h1>")
    parts.append("<p class='subtitle'>Indian Premier League 2008-2019, built from ball-by-ball data "
                 "with Python, pandas, matplotlib and seaborn.</p>")

    # Headline number boxes
    parts.append("<div class='numbers'>")
    for value, label in headline_numbers(matches, deliveries):
        parts.append("<div class='number'><b>" + value + "</b><span>" + label + "</span></div>")
    parts.append("</div>")

    # Predictions for the next season (made by predict.py), near the top so they are easy to find
    parts.append(prediction_section(next_season))

    # Interactive section: filters, clickable chart and player search
    parts.append(explorer_section(matches, deliveries))

    # Insights
    parts.append("<h2 id='insights'>Key insights</h2><ul class='insights'>")
    for sentence in key_insights(matches, deliveries):
        parts.append("<li>" + sentence + "</li>")
    parts.append("</ul>")

    # Orange / Purple Cap table (pandas can turn a DataFrame into an HTML table)
    caps = metrics.cap_winners(deliveries)
    caps.columns = ["Season", "Orange Cap", "Runs", "Purple Cap", "Wickets", "Economy"]
    parts.append("<h2 id='caps'>Orange Cap and Purple Cap winners</h2><div class='table-box'>")
    parts.append(caps.to_html(index=False))
    parts.append("</div>")

    # Charts, section by section
    for section_name in CHART_SECTIONS:
        parts.append("<h2 id='" + section_id(section_name) + "'>" + section_name + "</h2><div class='charts'>")
        for file_name, title in CHART_SECTIONS[section_name]:
            # Only show charts that exist (analysis.py must be run first).
            if os.path.exists(os.path.join(OUTPUT_FOLDER, file_name)):
                parts.append("<figure><img src='" + file_name + "' alt='" + title + "'>"
                             "<figcaption>" + title + "</figcaption></figure>")
        parts.append("</div>")

    parts.append("</main></body></html>")
    return "\n".join(parts)


def main():
    matches, deliveries = metrics.load_processed_data()
    page = make_page(matches, deliveries)
    path = os.path.join(OUTPUT_FOLDER, "index.html")
    with open(path, "w", encoding="utf-8") as file:
        file.write(page)
    print("Dashboard saved:", path)


if __name__ == "__main__":
    main()
