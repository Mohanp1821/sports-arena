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
import metrics          # our own file: src/metrics.py
import dashboard_data   # our own file: src/dashboard_data.py (tables for the analyst views)
import match_centre     # our own file: src/match_centre.py (the ball-by-ball match centre page)

OUTPUT_FOLDER = os.path.join(metrics.PROJECT_FOLDER, "outputs")
EXPLORER_SCRIPT = os.path.join(metrics.SCRIPT_FOLDER, "dashboard_explorer.js")
ANALYTICS_SCRIPT = os.path.join(metrics.SCRIPT_FOLDER, "dashboard_analytics.js")
CHASE_MODEL_FILE = os.path.join(OUTPUT_FOLDER, "chase_win_probability_model.csv")   # saved by analysis.py
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
        ("rivalry_chennai_super_kings_vs_mumbai_indians.png", "Rivalry centre: CSK vs MI by season and ground"),
        ("home_fortress.png", "Home fortress index"),
        ("ground_ma_chidambaram_stadium.png", "Chepauk: average first-innings score by season"),
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
        ("matchups_v_kohli.png", "Kohli against the bowlers he faced most"),
        ("finishers.png", "Finishers: death-over strike rate and not-out % in chases"),
        ("top_partnerships.png", "Biggest partnerships"),
    ],
    "Trends and the Impact Player era": [
        ("scoring_inflation.png", "Scoring inflation: first-innings average and sixes per match"),
        ("impact_player_era.png", "Before and after the Impact Player rule"),
        ("impact_player_choices.png", "Impact Player choices and win %"),
        ("chase_win_probability.png", "Chase win probability (logistic regression)"),
        ("impact_scores_2026.png", "Season impact scores, IPL 2026"),
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
        (str(matches["season"].nunique()), "seasons (" + metrics.season_range_text(matches) + ")"),
        (str(len(set(matches["team1_franchise"]))), "franchises"),
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

    eras = metrics.impact_era_summary(deliveries, matches)
    before = eras.iloc[0]
    after = eras.iloc[1]

    return [
        "Chasing wins more: teams batting second won " + str(chase_pct) + "% of matches.",
        "The toss hardly matters: the toss winner won " + str(toss_pct) + "% of matches.",
        "Death overs (16-20) are the fastest scoring phase: " + str(death_rate) + " runs per over.",
        best_team["team"] + " have the best all-time win rate: " + str(best_team["win_pct"]) + "%.",
        "Best single season: " + best_season["orange_cap"] + " scored " + str(best_season["runs"])
        + " runs in " + str(best_season["season"]) + ".",
        "Since the Impact Player rule, the average first-innings score rose from " + str(before["avg_first_innings"])
        + " (" + before["era"].split(" ")[0] + ") to " + str(after["avg_first_innings"]) + " ("
        + after["era"].split(" ")[0] + "), and 200+ totals from " + str(before["totals_200_plus_per_match"])
        + " to " + str(after["totals_200_plus_per_match"]) + " per match.",
    ]


def read_output_csv(file_name):
    """Read a CSV saved by predict.py, or return None if it has not been made yet."""
    path = os.path.join(OUTPUT_FOLDER, file_name)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def strength_explanation(strengths, next_season):
    """HTML: each team's win % in the last 3 seasons, and the strength worked out from them."""
    season_columns = [column for column in strengths.columns if column.startswith("win_pct_")]
    years = [column.replace("win_pct_", "") for column in season_columns]
    oldest, middle, newest = years[0], years[1], years[2]

    # The strongest team as a worked example, with the numbers taken from the table
    # (only if it played all 3 seasons, so the example uses all three weights).
    full = strengths.dropna(subset=season_columns)
    top = full.iloc[0]
    example = (top["team"] + ": (3 &times; " + str(top["win_pct_" + newest]) + " + 2 &times; "
               + str(top["win_pct_" + middle]) + " + 1 &times; " + str(top["win_pct_" + oldest])
               + ") &divide; 6 = <b>" + str(top["strength"]) + "</b>")

    table = strengths.copy()
    for column in season_columns:
        # A missing season (e.g. Chennai's 2017 suspension) is shown as "did not play".
        table[column] = table[column].apply(lambda value: "did not play" if pd.isna(value) else str(value) + "%")
    table.columns = ["Team"] + ["Win % " + year + " (weight " + str(weight) + ")"
                                for year, weight in zip(years, [1, 2, 3])] + ["Strength"]

    return ("<h3>Why these teams are the favourites</h3>"
            "<p>A team's strength is its win % over the last 3 seasons, with the latest season counting 3 times. "
            + example + ". A season a team did not play is skipped, so only the seasons it played count.</p>"
            "<div class='table-box'>" + table.to_html(index=False) + "</div>")


def actual_check_section(actual, next_season):
    """HTML: our predictions next to the official results of that season."""
    season = str(next_season)
    table = actual[["prediction", "our_pick", "actual", "verdict"]].copy()
    table.columns = ["Prediction", "Our pick", "What really happened", "Result"]
    champion = actual[actual["prediction"] == "IPL champion"].iloc[0]
    return ("<h3>How did the " + season + " prediction do?</h3>"
            "<p>The dataset ends in 2019, so the model never saw the " + season + " season. Here are its "
            "predictions next to the official results (source: iplt20.com, typed in by hand only for this check). "
            "<b>" + champion["actual"].split(" (")[0] + "</b> won the title: the model's #"
            + str(int(champion["actual_rank"])) + " pick, with a " + champion_chance_text(champion["actual"])
            + " chance. The Purple Cap pick was exactly right.</p>"
            "<div class='table-box'>" + table.to_html(index=False) + "</div>")


def champion_chance_text(actual_text):
    """The predicted title chance of the real champion, e.g. '21.2%'."""
    chances = read_output_csv("prediction_title_chances.csv")
    team = actual_text.split(" (")[0]
    row = chances[chances["team"] == team]
    if len(row) == 0:
        return "unknown"
    return str(row.iloc[0]["title_pct"]) + "%"


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

    # Why each team got its strength (win % in each of the last 3 seasons)
    strengths = read_output_csv("prediction_strengths.csv")
    if strengths is not None:
        parts.append(strength_explanation(strengths, next_season))

    # How the prediction compares with what really happened (if the real results are known)
    actual = read_output_csv("prediction_vs_actual_" + season + ".csv")
    if actual is not None:
        parts.append(actual_check_section(actual, next_season))

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
    parts.append("<h3>How reliable is this? (backtest " + str(int(read_output_csv("prediction_backtest.csv")["season"].min()))
                 + "-" + str(int(read_output_csv("prediction_backtest.csv")["season"].max())) + ")</h3>"
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
        winner = "" if match["no_result"] else match["winner_franchise"]
        potm = "" if match["no_result"] else match["player_of_match"]
        match_rows.append([match["season"], match["date"].strftime("%Y-%m-%d"), match["team1_franchise"],
                           match["team2_franchise"], winner, result_text(match), potm])
    match_rows.sort(key=lambda row: row[1])   # oldest match first

    # Per player, per season, per team: batting and bowling totals.
    # add_ball_columns (metrics.py) applies the cricket rules and removes super overs.
    balls = metrics.add_ball_columns(deliveries)
    batting = balls.groupby(["batter", "season", "batting_team_franchise"]).agg(
        runs=("batsman_runs", "sum"),
        balls_faced=("is_ball_faced", "sum"),
        sixes=("is_six", "sum"),
        innings=("match_id", "nunique"),     # one innings per match in T20
    ).reset_index()
    bowling = balls.groupby(["bowler", "season", "bowling_team_franchise"]).agg(
        wickets=("is_bowler_wicket", "sum"),
        legal_balls=("is_legal_ball", "sum"),
        runs_conceded=("runs_conceded", "sum"),
    ).reset_index()

    champions = metrics.season_champions(matches)
    players = sorted(set(batting["batter"]) | set(bowling["bowler"]))
    return {
        "season_range": metrics.season_range_text(matches),
        "seasons": sorted(matches["season"].unique()),
        "teams": sorted(set(matches["team1_franchise"]) | set(matches["team2_franchise"])),
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


def control(label, html):
    """A labelled drop-down or text box for the filter bars."""
    return "<label>" + label + html + "</label>"


def analyst_sections(matches, deliveries, impact):
    """
    HTML for the six analyst views. Each view has its own drop-downs and an
    empty box; src/dashboard_analytics.js fills the boxes.
    """
    player_box = "<input list='analyst-players' id='{id}' placeholder='e.g. V Kohli'>"
    parts = []
    parts.append("<h2 id='rivalry'>Rivalry centre</h2><p>Pick any two teams: overall and season-by-season "
                 "record, league vs playoffs, every ground, the last 5 meetings, highest and lowest totals, and the "
                 "top players in the fixture. Teams are franchises (Delhi Daredevils = Delhi Capitals).</p>"
                 "<div class='filters'>" + control("Team A", "<select id='riv-a'></select>")
                 + control("Team B", "<select id='riv-b'></select>") + "</div><div id='riv-out'></div>")
    parts.append("<h2 id='matchups'>Matchups</h2><p>Batter against bowler, a player against every team, and "
                 "how a batter usually gets out.</p>"
                 "<div class='panel'><h3>Batter vs bowler</h3><div class='filters'>"
                 + control("Batter", player_box.format(id="mu-batter"))
                 + control("Bowler", player_box.format(id="mu-bowler")) + "</div><div id='mu-out'></div></div>"
                 "<div class='panel'><h3>A player against each team</h3><div class='filters'>"
                 + control("Player", player_box.format(id="pt-player")) + "</div><div id='pt-out'></div></div>")
    parts.append("<h2 id='grounds'>Ground profiles</h2><div class='filters'>"
                 + control("Ground", "<select id='gr-venue'></select>") + "</div><div id='gr-out'></div>"
                 "<div class='panel'><h3>A team at this ground, season by season</h3><div class='filters'>"
                 + control("Team", "<select id='gr-team'></select>") + "</div><div id='gr-team-out'></div></div>"
                 "<div class='panel'><h3>Home fortress index</h3><p class='note'>Home win % minus away win %, "
                 "for the 10 current teams at their home ground(s).</p><div class='table-box' id='gr-fortress'></div></div>")
    parts.append("<h2 id='specialists'>Phase and role specialists</h2><div class='filters'>"
                 + control("Season", "<select id='sp-season'></select>")
                 + control("Phase", "<select id='sp-phase'></select>") + "</div><div id='sp-out'></div>"
                 "<div class='panel'><h3>Finishers</h3><p class='note'>Best strike rate in overs 16-20 (min 150 balls "
                 "there), and how often they were not out when chasing.</p><div class='table-box' id='sp-finishers'></div></div>"
                 "<div class='panel'><h3>Biggest partnerships</h3><div class='filters'>"
                 + control("Team", "<select id='sp-team'></select>") + "</div>"
                 "<div class='table-box' id='sp-partners'></div></div>")
    parts.append("<h2 id='impact-era'>Impact Player era</h2><p>From 2023 each team may bring in one substitute "
                 "(the Impact Player). Here 2020-22 is compared with 2023-26 (rain-shortened and no-result matches "
                 "left out), using " + str(len(impact)) + " substitutions from the Cricsheet files.</p>"
                 "<div class='table-box' id='ip-summary'></div><h3>Run rate by phase</h3><div class='table-box' id='ip-phases'></div>"
                 "<div class='two-columns'><div class='panel'><h3>What the Impact Player did (all teams)</h3>"
                 "<div id='ip-all'></div></div><div class='panel'><h3>One team's choices</h3><div class='filters'>"
                 + control("Team", "<select id='ip-team'></select>") + "</div><div id='ip-team-out'></div></div></div>")
    parts.append("<h2 id='trends'>Trends</h2><div class='two-columns'>"
                 "<div class='panel'><h3>Scoring inflation</h3><div class='table-box scroll' id='tr-inflation'></div></div>"
                 "<div class='panel'><h3>Points table (rebuilt from the results)</h3><div class='filters'>"
                 + control("Season", "<select id='tr-season'></select>") + "</div><div class='table-box' id='tr-points'></div>"
                 "<p class='note'>2 points for a win, 1 for a no-result; NRR from the ball data (a team bowled out "
                 "counts 20 overs). Rain-shortened matches use the overs actually bowled.</p></div></div>"
                 "<div class='panel'><h3>Chase win-probability calculator</h3><p class='note'>A logistic regression "
                 "trained on every ball of every normal chase in the data (see the chase chart below).</p>"
                 "<div class='filters'>" + control("Runs needed", "<input id='tr-runs' type='number' value='60' min='1'>")
                 + control("Balls left", "<input id='tr-balls' type='number' value='60' min='1' max='120'>")
                 + control("Wickets left", "<input id='tr-wickets' type='number' value='7' min='1' max='10'>")
                 + "</div><div id='tr-chance'></div></div>"
                 "<div class='two-columns'><div class='panel'><h3>Season impact scores</h3><p class='note'>Runs "
                 "weighted by how hard scoring was in that phase, plus wickets worth the average runs per wicket "
                 "in that phase (see docs/Code_Explanation.md).</p><div class='filters'>"
                 + control("Season", "<select id='tr-impact-season'></select>") + "</div><div class='table-box' id='tr-impact'></div></div>"
                 "<div class='panel'><h3>One player's impact score by season</h3><div class='filters'>"
                 + control("Player", player_box.format(id="tr-impact-player")) + "</div>"
                 "<div class='table-box' id='tr-impact-player-out'></div></div></div>")
    parts.append("<h2 id='match-centre'>Match centre</h2><p>Every match ball by ball: scorecard with dismissals "
                 "and bowling card, an over-by-over strip, and the raw ball rows. "
                 "<a href='match_centre.html'><b>Open the match centre &rarr;</b></a></p>")

    data = dashboard_data.analyst_data(matches, deliveries, impact, CHASE_MODEL_FILE)
    text = json.dumps(data, separators=(",", ":"), default=lambda value: value.item())
    parts.append("<script type='application/json' id='analyst-data'>" + text.replace("</", "<\\/") + "</script>")
    with open(ANALYTICS_SCRIPT, encoding="utf-8") as file:
        parts.append("<script>\n" + file.read() + "\n</script>")
    return "\n".join(parts)


def section_id(name):
    """Turn a section name like 'Player form' into a link target like 'player-form'."""
    return name.lower().replace(" ", "-")


def navigation_bar(next_season):
    """A menu fixed at the top of the page with a link to every section."""
    links = [("predictions", "Predictions " + str(next_season)), ("explore", "Explore (interactive)"),
             ("rivalry", "Rivalries"), ("matchups", "Matchups"), ("grounds", "Grounds"),
             ("specialists", "Specialists"), ("impact-era", "Impact Player era"), ("trends", "Trends"),
             ("match-centre", "Match centre"), ("insights", "Key insights"), ("caps", "Cap winners")]
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
    parts.append("<p class='subtitle'>Indian Premier League " + metrics.season_range_text(matches) + ", built from ball-by-ball data "
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

    # Analyst views: rivalries, matchups, grounds, specialists, Impact Player era, trends
    parts.append(analyst_sections(matches, deliveries, metrics.load_impact_players()))

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
    match_centre.build_page(matches, deliveries, os.path.join(OUTPUT_FOLDER, "match_centre.html"))


if __name__ == "__main__":
    main()
