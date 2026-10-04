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

    return ("<h3>Model A: why each team got its strength</h3>"
            "<p>A team's strength is its win % over the last 3 seasons, with the latest season counting 3 times. "
            + example + ". A season a team did not play is skipped, so only the seasons it played count.</p>"
            "<div class='table-box'>" + table.to_html(index=False) + "</div>")


def table_html(table, columns, titles):
    """A pandas table as HTML, with chosen columns and friendly column titles."""
    part = table[columns].copy()
    part.columns = titles
    return "<div class='table-box'>" + part.to_html(index=False, na_rep="-") + "</div>"


def figure_html(file_name, title):
    """A chart from outputs/ with its caption (only if analysis/predict made it)."""
    if not os.path.exists(os.path.join(OUTPUT_FOLDER, file_name)):
        return ""
    return ("<figure><img src='" + file_name + "' alt='" + title + "'><figcaption>" + title
            + "</figcaption></figure>")


def award_pick_rows(awards_a, awards_b):
    """One row per award: Model A's pick and next two, Model B's pick and next two."""
    rows = []
    for award in awards_a["award"].unique():
        a = awards_a[awards_a["award"] == award]
        b = awards_b[awards_b["award"] == award]
        rows.append({
            "Award": award,
            "Model A pick": a.iloc[0]["player"] + " (" + a.iloc[0]["team"] + ")",
            "Model A form score": str(a.iloc[0]["form"]) + " " + a.iloc[0]["measure"] + " a season",
            "Model A next": ", ".join(a.iloc[1:3]["player"]),
            "Model B pick": b.iloc[0]["player"] + " (" + b.iloc[0]["team"] + ")",
            "Model B predicts": str(b.iloc[0]["predicted"]) + " " + b.iloc[0]["measure"],
            "Model B next": ", ".join(b.iloc[1:3]["player"]),
        })
    return pd.DataFrame(rows)


def limits_note(matches, deliveries, award_backtest, scores, last_season):
    """
    What the models cannot know, with the numbers worked out from the data:
    the breakout season of the latest Orange Cap winner, and how close to a
    coin flip pre-season predictions are.
    """
    caps = metrics.cap_winners(deliveries)
    latest = caps[caps["season"] == last_season].iloc[0]
    batting = metrics.batting_stats(deliveries, ["batter", "season"])
    player = latest["orange_cap"]
    before = batting[(batting["batter"] == player) & (batting["season"] == last_season - 1)]
    runs_before = int(before["runs"].iloc[0]) if len(before) else 0
    ranks = award_backtest[(award_backtest["season"] == last_season) & (award_backtest["award"] == "Orange Cap (most runs)")]
    rank_text = []
    for model in ["Model A", "Model B"]:
        rank = ranks[ranks["model"] == model]["actual_rank"].iloc[0]
        rank_text.append(model + " had him " + ("#" + str(int(rank)) if pd.notna(rank) else "outside its list"))
    overall = scores[scores["season"] == "2021-2026"].set_index("model")
    return ("<div class='panel'><h3>What the models cannot know</h3><ul>"
            "<li><b>Auctions, trades and releases.</b> Both models read <code>data/squads_2027.csv</code>, which starts as "
            "each franchise's " + str(last_season) + " players. Edit it after the auction and run the pipeline again.</li>"
            "<li><b>Injuries and availability</b> during the season.</li>"
            "<li><b>Breakout players.</b> " + player + " scored " + str(runs_before) + " runs in " + str(last_season - 1)
            + " and " + str(latest["runs"]) + " in " + str(last_season) + " to win the Orange Cap; before that season, "
            + " and ".join(rank_text) + " in the Orange Cap list. Past numbers cannot see a jump like that coming.</li>"
            "<li><b>T20 is close to a coin flip before a ball is bowled.</b> In the 2021-2026 backtest Model A picked "
            + str(overall.loc["Model A", "accuracy_pct"]) + "% of winners and Model B " + str(overall.loc["Model B", "accuracy_pct"])
            + "%, against 50% for a coin flip, and neither beat the coin flip's log loss ("
            + str(overall.loc["Random guess (50%)", "log_loss"]) + "). Treat the title chances as rough guides, not certainties.</li>"
            "</ul></div>")


def prediction_section(matches, deliveries, next_season):
    """HTML for "IPL 2027 predictions: Model A vs Model B" (made by predict.py and predict_ml.py)."""
    comparison = read_output_csv("prediction_" + str(next_season) + "_comparison.csv")
    chances_a = read_output_csv("prediction_title_chances.csv")
    chances_b = read_output_csv("prediction_model_b_title_chances.csv")
    awards_a = read_output_csv("prediction_awards.csv")
    awards_b = read_output_csv("prediction_model_b_awards.csv")
    scores = read_output_csv("model_comparison_matches.csv")
    titles = read_output_csv("model_comparison_titles.csv")
    award_backtest = read_output_csv("model_comparison_awards.csv")
    if comparison is None or awards_b is None or scores is None:
        return ""   # the prediction scripts have not been run, so there is nothing to show
    season = str(next_season)
    last_season = next_season - 1
    parts = ["<h2 id='predictions'>IPL " + season + " predictions: Model A vs Model B</h2>"]
    parts.append("<p><b>Model A (explainable):</b> each team's strength is its form win % over the last 3 seasons "
                 "(weights 3, 2, 1); team A beats team B with chance A / (A + B). <b>Model B (machine learning):</b> "
                 "logistic regression and gradient boosting, averaged, using only pre-season information: Elo rating, "
                 "last-10 form, head-to-head, ground record, home ground, squad strength and the Impact Player era. "
                 "Both play the " + season + " season " + format(predict_simulations(), ",") + " times in the real "
                 "10-team format (two groups of 5, 14 league games each, then Qualifier 1, Eliminator, Qualifier 2 and the Final).</p>")

    favourite_a = chances_a.iloc[0]
    favourite_b = chances_b.iloc[0]
    parts.append("<div class='picks'>"
                 "<div class='pick'><span>Model A favourite (" + str(favourite_a["title_pct"]) + "% title chance)</span><b>"
                 + favourite_a["team"] + "</b></div>"
                 "<div class='pick'><span>Model B favourite (" + str(favourite_b["title_pct"]) + "% title chance)</span><b>"
                 + favourite_b["team"] + "</b></div>")
    for award in ["Orange Cap (most runs)", "Purple Cap (most wickets)"]:
        pick_a = awards_a[awards_a["award"] == award].iloc[0]["player"]
        pick_b = awards_b[awards_b["award"] == award].iloc[0]["player"]
        parts.append("<div class='pick'><span>" + award + ": A / B</span><b>" + pick_a
                     + (" (both)" if pick_a == pick_b else " / " + pick_b) + "</b></div>")
    parts.append("</div>")

    parts.append("<div class='charts wide'>" + figure_html("prediction_" + season + "_models.png",
                 "Title chances, IPL " + season + ": Model A vs Model B") + "</div>")
    table = comparison.merge(chances_a[["team", "strength"]], on="team").merge(
        chances_b[["team", "squad_strength", "elo"]], on="team")
    parts.append("<h3>Title and playoff chances</h3>" + table_html(
        table, ["team", "title_pct_a", "playoff_pct_a", "title_pct_b", "playoff_pct_b", "strength", "squad_strength", "elo"],
        ["Team", "Model A title %", "Model A playoffs %", "Model B title %", "Model B playoffs %",
         "Model A strength (form win %)", "Model B squad strength", "Model B Elo"]))

    groups = read_output_csv("prediction_groups.csv")
    if groups is not None and len(groups) > 0:
        parts.append("<p class='note'>Simulated groups (seeded by titles, then finals reached, in a snake). "
                     "Teams on the same row play each other twice.</p>"
                     + table_html(groups, ["seed_row", "group_a", "group_b"], ["Row", "Group A", "Group B"]))

    strengths = read_output_csv("prediction_strengths.csv")
    if strengths is not None:
        parts.append(strength_explanation(strengths, next_season))

    parts.append("<h3>Award picks</h3><p class='note'>Model A: the 2027-squad player with the best form score. "
                 "Model B: a linear regression on each player's previous two seasons.</p>"
                 + "<div class='table-box'>" + award_pick_rows(awards_a, awards_b).to_html(index=False) + "</div>")

    features = read_output_csv("model_b_features.csv")
    if features is not None:
        parts.append("<h3>What Model B looks at</h3><p class='note'>Logistic regression weight (features scaled to the "
                     "same size: + helps team A, - hurts) and how much the gradient-boosting trees used each feature.</p>"
                     + table_html(features, ["feature", "logistic_weight", "boosting_importance"],
                                  ["Feature", "Logistic weight", "Boosting importance"]))

    overall = scores[scores["season"] == "2021-2026"]
    parts.append("<h3>Which model was better? Walk-forward backtest 2021-2026</h3>"
                 "<p>For each season both models learned only from earlier seasons, then predicted all "
                 + str(int(overall["matches"].iloc[0])) + " matches and the title.</p>"
                 + table_html(overall, ["model", "matches", "accuracy_pct", "log_loss", "brier"],
                              ["Model", "Matches", "Accuracy %", "Log loss (lower is better)", "Brier (lower is better)"])
                 + "<div class='charts'>" + figure_html("model_comparison_backtest.png", "Backtest scores 2021-2026")
                 + figure_html("model_calibration.png", "Calibration: does 60% mean 60%?") + "</div>"
                 + "<h3>Where the real champion ranked</h3>"
                 + table_html(titles, ["season", "teams", "champion", "favourite_a", "champion_rank_a", "champion_title_pct_a",
                                       "favourite_b", "champion_rank_b", "champion_title_pct_b", "random_title_pct"],
                              ["Season", "Teams", "Champion", "Model A favourite", "A: champion's rank", "A: champion's title %",
                               "Model B favourite", "B: champion's rank", "B: champion's title %", "Random pick %"]))
    summary = award_backtest.groupby(["model", "award"], sort=False).agg(
        exact=("actual_rank", lambda ranks: int((ranks == 1).sum())),
        top5=("actual_rank", lambda ranks: int((ranks <= 5).sum())),
        seasons=("season", "count")).reset_index()
    parts.append("<h3>Award picks in the backtest</h3>" + table_html(
        summary, ["model", "award", "seasons", "exact", "top5"],
        ["Model", "Award", "Seasons", "Exactly right", "Winner in top 5"]))
    parts.append(limits_note(matches, deliveries, award_backtest, scores, last_season))
    return "\n".join(parts)


def predict_simulations():
    """The number of simulated seasons (from predict.py, so it is never typed in twice)."""
    import predict
    return predict.SIMULATIONS


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
    links = [("predictions", "Predictions " + str(next_season) + ": A vs B"), ("explore", "Explore (interactive)"),
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
                 "with Python, pandas, matplotlib, seaborn, scikit-learn and plain JavaScript.</p>")

    # Headline number boxes
    parts.append("<div class='numbers'>")
    for value, label in headline_numbers(matches, deliveries):
        parts.append("<div class='number'><b>" + value + "</b><span>" + label + "</span></div>")
    parts.append("</div>")

    # Predictions for the next season (made by predict.py), near the top so they are easy to find
    parts.append(prediction_section(matches, deliveries, next_season))

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
