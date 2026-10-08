"""
build_report.py - Step 7: build the website, outputs/index.html (plus match_centre.html).

One offline page with several views, chosen by the address after "#" (the router is src/site.js):
Home, Players, Grounds, Teams, 2027 predictions, Ask (the chatbot) and More analysis.
Python works out every number and puts it in the page as JSON; the JavaScript files only show it.

Run:  python src/build_report.py      (with Docker: http://localhost:8080)
"""

import os
import json
import pandas as pd
import metrics
import dashboard_data   # the numbers for the analyst views and the player / ground / team pages
import match_centre     # the ball-by-ball match centre page
import chat_facts       # the facts the chatbot may use
import predict

OUTPUT_FOLDER = os.path.join(metrics.PROJECT_FOLDER, "outputs")
EXPLORER_SCRIPT = os.path.join(metrics.SCRIPT_FOLDER, "dashboard_explorer.js")
ANALYTICS_SCRIPT = os.path.join(metrics.SCRIPT_FOLDER, "dashboard_analytics.js")
CHATBOT_SCRIPT = os.path.join(metrics.SCRIPT_FOLDER, "chatbot.js")
SITE_SCRIPT = os.path.join(metrics.SCRIPT_FOLDER, "site.js")
CHASE_MODEL_FILE = os.path.join(OUTPUT_FOLDER, "chase_win_probability_model.csv")   # saved by analysis.py
DEFAULT_PLAYER = "V Kohli"   # shown first in the player search

# The charts made by analysis.py, with their captions.
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
        ("ground_map.png", "How each ground plays: runs index vs wickets index"),
        ("player_ground_fit_v_kohli.png", "Kohli: strike rate at each ground vs elsewhere in the same seasons"),
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

with open(os.path.join(metrics.SCRIPT_FOLDER, "site.css"), encoding="utf-8") as css_file:
    PAGE_STYLE = css_file.read()        # the look of the page: src/site.css


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def json_script(element_id, data):
    """Data inside the page as JSON. numpy numbers become normal numbers, and "</" is
    escaped so a name can never end the <script> tag early."""
    text = json.dumps(data, separators=(",", ":"), default=lambda value: value.item())
    return "<script type='application/json' id='" + element_id + "'>" + text.replace("</", "<\\/") + "</script>"


def js_script(path):
    """A JavaScript file from src/ copied into the page, so it works offline."""
    with open(path, encoding="utf-8") as file:
        return "<script>\n" + file.read() + "\n</script>"


def table_html(table, columns, titles):
    """Chosen columns of a table as HTML, with friendly titles."""
    part = table[columns].copy()
    part.columns = titles
    return "<div class='table-box'>" + part.to_html(index=False, na_rep="-") + "</div>"


def figure_html(file_name, title):
    """A chart with its caption (only if it was made)."""
    if not os.path.exists(os.path.join(OUTPUT_FOLDER, file_name)):
        return ""
    return ("<figure><img src='" + file_name + "' alt='" + title + "'><figcaption>" + title
            + "</figcaption></figure>")


def control(label, html):
    """A labelled drop-down or text box."""
    return "<label>" + label + html + "</label>"


# ---------------------------------------------------------------------------
# Home numbers and key insights
# ---------------------------------------------------------------------------
def headline_numbers(matches, deliveries):
    return [
        (format(len(matches), ","), "matches"),
        (format(len(deliveries), ","), "balls analysed"),
        (str(matches["season"].nunique()), "seasons (" + metrics.season_range_text(matches) + ")"),
        (str(len(set(matches["team1_franchise"]))), "franchises"),
    ]


def key_insights(matches, deliveries):
    """The key insights as sentences, every number calculated from the data."""
    chase = metrics.bat_first_vs_chase(deliveries, matches)
    chase_pct = round(100 - chase["bat_first_wins"].sum() / chase["matches"].sum() * 100, 1)

    toss_table, toss_pct = metrics.toss_impact(matches)

    phases = metrics.phase_run_rate(deliveries)
    death = phases[phases["phase"] == "Death"]
    death_rate = round(metrics.per_over(death["runs"].sum(), death["legal_balls"].sum()), 1)

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


# ---------------------------------------------------------------------------
# 2027 predictions: Model A vs Model B
# ---------------------------------------------------------------------------
def strength_explanation(strengths, next_season):
    """Each team's win % in the last 3 seasons and the strength made from them, with a worked example."""
    season_columns = [column for column in strengths.columns if column.startswith("win_pct_")]
    years = [column.replace("win_pct_", "") for column in season_columns]
    oldest, middle, newest = years[0], years[1], years[2]

    # The worked example is the strongest team that played all 3 seasons.
    full = strengths.dropna(subset=season_columns)
    top = full.iloc[0]
    example = (top["team"] + ": (3 &times; " + str(top["win_pct_" + newest]) + " + 2 &times; "
               + str(top["win_pct_" + middle]) + " + 1 &times; " + str(top["win_pct_" + oldest])
               + ") &divide; 6 = <b>" + str(top["strength"]) + "</b>")

    table = strengths.copy()
    for column in season_columns:
        table[column] = table[column].apply(lambda value: "did not play" if pd.isna(value) else str(value) + "%")
    table.columns = ["Team"] + ["Win % " + year + " (weight " + str(weight) + ")"
                                for year, weight in zip(years, [1, 2, 3])] + ["Strength"]

    return ("<h3>Model A: why each team got its strength</h3>"
            "<p>A team's strength is its win % over the last 3 seasons, with the latest season counting 3 times. "
            + example + ". A season a team did not play is skipped, so only the seasons it played count.</p>"
            "<div class='table-box'>" + table.to_html(index=False) + "</div>")


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
    """What the models cannot know: auctions, injuries, breakout seasons, and how close T20 is to a coin flip."""
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
    """The predictions section, from the files predict.py and predict_ml.py saved."""
    comparison = dashboard_data.read_output("prediction_" + str(next_season) + "_comparison.csv")
    chances_a = dashboard_data.read_output("prediction_title_chances.csv")
    chances_b = dashboard_data.read_output("prediction_model_b_title_chances.csv")
    awards_a = dashboard_data.read_output("prediction_awards.csv")
    awards_b = dashboard_data.read_output("prediction_model_b_awards.csv")
    scores = dashboard_data.read_output("model_comparison_matches.csv")
    titles = dashboard_data.read_output("model_comparison_titles.csv")
    award_backtest = dashboard_data.read_output("model_comparison_awards.csv")
    if comparison is None or awards_b is None or scores is None:
        return ""   # the prediction scripts have not been run yet
    season = str(next_season)
    last_season = next_season - 1
    parts = ["<h2 id='predictions'>IPL " + season + " predictions: Model A vs Model B</h2>"]
    parts.append("<p><b>Model A (explainable):</b> each team's strength is its form win % over the last 3 seasons "
                 "(weights 3, 2, 1); team A beats team B with chance A / (A + B). <b>Model B (machine learning):</b> "
                 "logistic regression and gradient boosting, averaged, using only pre-season information: Elo rating, "
                 "last-10 form, head-to-head, ground record, home ground, squad strength and the Impact Player era. "
                 "Both play the " + season + " season " + format(predict.SIMULATIONS, ",") + " times in the real "
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

    groups = dashboard_data.read_output("prediction_groups.csv")
    if groups is not None and len(groups) > 0:
        parts.append("<p class='note'>Simulated groups (seeded by titles, then finals reached, in a snake). "
                     "Teams on the same row play each other twice.</p>"
                     + table_html(groups, ["seed_row", "group_a", "group_b"], ["Row", "Group A", "Group B"]))

    strengths = dashboard_data.read_output("prediction_strengths.csv")
    if strengths is not None:
        parts.append(strength_explanation(strengths, next_season))

    parts.append("<h3>Award picks</h3><p class='note'>Model A: the 2027-squad player with the best form score. "
                 "Model B: a linear regression on each player's previous two seasons.</p>"
                 + "<div class='table-box'>" + award_pick_rows(awards_a, awards_b).to_html(index=False) + "</div>")

    features = dashboard_data.read_output("model_b_features.csv")
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


# ---------------------------------------------------------------------------
# Explore (season and team filters)
# ---------------------------------------------------------------------------
def result_text(match):
    """e.g. 'by 140 runs' or 'by 7 wickets (D/L)'."""
    if match["no_result"]:
        return "No result"
    if match["result"] == "tie":
        return "Tie, won the super over"
    if match["win_by_runs"] > 0:
        text = "by " + str(match["win_by_runs"]) + " runs"
    else:
        text = "by " + str(match["win_by_wickets"]) + " wickets"
    if match["dl_applied"] == 1:
        text += " (D/L)"
    return text


def explorer_data(matches, deliveries):
    """Small tables the Explore filters add up: every match, and batting and bowling per player, season and team."""
    # [season, date, team1, team2, winner, margin, player of the match]
    match_rows = []
    for match in matches.to_dict("records"):
        winner = "" if match["no_result"] else match["winner_franchise"]
        potm = "" if match["no_result"] else match["player_of_match"]
        match_rows.append([match["season"], match["date"].strftime("%Y-%m-%d"), match["team1_franchise"],
                           match["team2_franchise"], winner, result_text(match), potm])
    match_rows.sort(key=lambda row: row[1])   # oldest first

    balls = metrics.add_ball_columns(deliveries)
    batting = balls.groupby(["batter", "season", "batting_team_franchise"]).agg(
        runs=("batsman_runs", "sum"),
        balls_faced=("is_ball_faced", "sum"),
        sixes=("is_six", "sum"),
        innings=("match_id", "nunique"),
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
    """The filters, empty boxes the JavaScript draws into, the data and the script."""
    parts = ["<h2 id='explore'>Explore the data (interactive)</h2>"]
    parts.append("<p>Choose a season and a team: the numbers, chart and tables below update straight away. "
                 "Click a bar in the chart to select that team or season.</p>")

    parts.append("<div class='filters'>"
                 "<label>Season<select id='filter-season'><option value='all'>All seasons</option></select></label>"
                 "<label>Team<select id='filter-team'><option value='all'>All teams</option></select></label>"
                 "<button id='filter-reset' type='button'>Reset filters</button></div>")

    parts.append("<div class='numbers' id='explore-cards'></div>")
    parts.append("<div class='panel'><h3 id='explore-chart-title'></h3><div id='explore-chart'></div></div>")
    parts.append("<div class='two-columns'>"
                 "<div class='panel'><h3>Top run scorers</h3><div class='table-box' id='explore-batting'></div></div>"
                 "<div class='panel'><h3>Top wicket takers</h3><div class='table-box' id='explore-bowling'></div></div>"
                 "</div>")
    parts.append("<div class='panel'><h3>Match results</h3>"
                 "<div class='table-box scroll' id='explore-results'></div></div>")

    parts.append("<div class='panel'><h3>Player career</h3>"
                 "<div class='filters'><label>Type a player's name"
                 "<input id='filter-player' list='player-list' placeholder='e.g. V Kohli'></label></div>"
                 "<datalist id='player-list'></datalist>"
                 "<div id='player-chart'></div><div class='table-box' id='player-table'></div></div>")

    parts.append(json_script("explorer-data", explorer_data(matches, deliveries)))
    parts.append(js_script(EXPLORER_SCRIPT))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Analyst views and the chatbot
# ---------------------------------------------------------------------------
def analyst_sections(matches, deliveries, impact):
    """Each analyst view: its drop-downs and an empty box that src/dashboard_analytics.js fills."""
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
    parts.append("<h2 id='pitch'>Pitch and player fit</h2>"
                 "<p>How each ground plays, and how it suits a particular batter, bowler or fielder. "
                 "<b>Note:</b> the data has no pitch reports (grass, cracks, soil) or ball-tracking, so \"how the pitch "
                 "plays\" is measured from what happened there: runs, wickets, fours and sixes, and dot balls, compared "
                 "with the whole league in the <b>same seasons</b> (100 = average), so the 2026 scoring boom does not make "
                 "newer grounds look flatter. This mixes the pitch with boundary size, outfield and weather.</p>"
                 "<div class='filters'>" + control("Ground", "<select id='pf-venue'></select>")
                 + control("Period", "<select id='pf-period'></select>") + "</div><div id='pf-profile'></div>"
                 "<div class='panel'><h3>How this ground suits a player</h3><p class='note'>The player at this ground "
                 "against the same player at other grounds in the same seasons (all seasons he played here).</p>"
                 "<div class='filters'>" + control("Player", player_box.format(id="pf-player")) + "</div>"
                 "<div id='pf-fit'></div><div id='pf-grounds'></div></div>")
    parts.append("<h2 id='specialists'>Phase and role specialists</h2><div class='filters'>"
                 + control("Season", "<select id='sp-season'></select>")
                 + control("Phase", "<select id='sp-phase'></select>") + "</div><div id='sp-out'></div>"
                 "<div class='panel'><h3>Finishers</h3><p class='note'>Best strike rate in overs 16-20 (min 150 balls "
                 "there), and how often they were not out when chasing.</p><div class='table-box' id='sp-finishers'></div></div>"
                 "<div class='panel'><h3>Biggest partnerships</h3><div class='filters'>"
                 + control("Team", "<select id='sp-team'></select>") + "</div>"
                 "<div class='table-box' id='sp-partners'></div></div>")
    parts.append("<h2 id='records'>Records</h2><p>The fastest fifties and hundreds, the best bowling in one match, "
                 "and the most catches, stumpings and run-outs, for all seasons or one season. Click a date "
                 "to open that match.</p><div class='filters'>"
                 + control("Season", "<select id='rec-season'></select>") + "</div><div class='two-columns'>"
                 "<div class='panel'><h3>Fastest fifties</h3><div class='table-box' id='rec-fifties'></div></div>"
                 "<div class='panel'><h3>Fastest hundreds</h3><div class='table-box' id='rec-hundreds'></div></div>"
                 "<div class='panel'><h3>Best bowling figures</h3><div class='table-box' id='rec-bowling'></div></div>"
                 "<div class='panel'><h3>Fielding</h3><p class='note'>Caught and bowled counts as a catch for the bowler; "
                 "every fielder named on a run-out gets one; substitute fielders are left out.</p>"
                 "<div class='table-box' id='rec-fielding'></div></div></div>")
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

    parts.append(json_script("analyst-data", dashboard_data.analyst_data(matches, deliveries, impact, CHASE_MODEL_FILE)))
    parts.append(js_script(ANALYTICS_SCRIPT))
    return "\n".join(parts)


def chat_section(matches, deliveries, impact):
    """The chat panel; the facts and the answer engine (src/chatbot.js) are inside the page."""
    facts = chat_facts.build_facts(matches, deliveries, impact)
    return ("<h2 id='ask'>Ask Sports Arena</h2>"
            "<p>Ask about players, teams, grounds, caps, champions, matchups, the Impact Player era, a match on a date, "
            "or the " + str(int(matches["season"].max()) + 1) + " predictions. Answers use only numbers calculated "
            "from the data, and say where they come from.</p>"
            "<div class='chat'><div id='chat-mode' class='note'>Offline mode (no internet or API key needed).</div>"
            "<div id='chat-log'></div><form id='chat-form'><input id='chat-input' autocomplete='off' "
            "placeholder='e.g. Kohli vs Bumrah, or Who won the Orange Cap in 2016?'><button type='submit'>Ask</button>"
            "</form><div id='chat-examples'></div></div>"
            + json_script("chat-facts", facts) + js_script(CHATBOT_SCRIPT))


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------
def section_id(name):
    """'Player form' -> 'player-form'."""
    return name.lower().replace(" ", "-")


# The view each section belongs to; any other section goes to "More analysis".
SECTION_VIEWS = {"predictions": "predictions", "ask": "ask", "explore": "teams", "rivalry": "teams"}


def site_header(next_season):
    """The brand, the menu, the search box and the light/dark switch."""
    links = [("home", "#/home", "Home"), ("players", "#/players", "Players"), ("grounds", "#/grounds", "Grounds"),
             ("teams", "#/teams", "Teams"), ("predictions", "#/predictions", str(next_season) + " predictions"),
             ("ask", "#/ask", "Ask"), ("analysis", "#/analysis", "More analysis")]
    nav = "".join("<a data-nav='" + key + "' href='" + href + "'>" + label + "</a>" for key, href, label in links)
    nav += "<a href='match_centre.html'>Match centre</a>"
    return ("<header class='site-header'><div class='bar'>"
            "<a class='brand' href='#/home'>Sports Arena<span>IPL analytics</span></a>"
            "<nav class='site-nav' aria-label='Main'>" + nav + "</nav>"
            "<form id='site-search' role='search'><input id='site-search-input' list='site-search-list' "
            "placeholder='Search a player, ground or team' aria-label='Search a player, ground or team'>"
            "<button type='submit'>Go</button></form>"
            "<button id='theme-toggle' type='button' aria-label='Switch between light and dark'>&#9680;</button>"
            "</div><div id='site-search-hint' aria-live='polite'></div>"
            "<datalist id='site-search-list'></datalist></header>")


def wrap_sections(html):
    """Wrap each section (it starts with <h2 id='...'>) in its view: <div data-view='teams'>...</div>."""
    pieces = html.split("<h2 id='")
    parts = [pieces[0]] if pieces[0].strip() else []
    for piece in pieces[1:]:
        section = piece.split("'")[0]
        view = SECTION_VIEWS.get(section, "analysis")
        parts.append("<div data-view='" + view + "'><h2 id='" + piece + "</div>")
    return "\n".join(parts)


def analysis_menu():
    """Links to every section of the "More analysis" view."""
    links = [("matchups", "Matchups"), ("grounds", "Ground explorer"), ("pitch", "Pitch & player fit tool"),
             ("specialists", "Specialists"), ("records", "Records"), ("impact-era", "Impact Player era"), ("trends", "Trends"),
             ("insights", "Key insights"), ("caps", "Cap winners")]
    for section_name in CHART_SECTIONS:
        links.append((section_id(section_name), "Charts: " + section_name))
    return ("<div data-view='analysis'><h1>More analysis</h1><p class='note view-intro'>Every tool and chart in one place. "
            "For one player or one ground, use the Players and Grounds pages.</p><div class='subnav chips'>"
            + "".join("<a class='chip' href='#" + target + "'>" + label + "</a>" for target, label in links) + "</div></div>")


def make_page(matches, deliveries):
    """The whole page, all views, as one text string."""
    next_season = int(matches["season"].max()) + 1
    impact = metrics.load_impact_players()
    parts = []
    parts.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append("<title>Sports Arena</title><style>" + PAGE_STYLE + "</style></head><body>")
    parts.append(site_header(next_season))
    parts.append("<main>")

    # Views drawn by site.js
    parts.append("<div data-view='home'><div id='home-page'></div><p class='subtitle'>Built from ball-by-ball data with "
                 "Python, pandas, matplotlib, seaborn, scikit-learn and plain JavaScript.</p><div class='numbers'>")
    for value, label in headline_numbers(matches, deliveries):
        parts.append("<div class='number'><b>" + value + "</b><span>" + label + "</span></div>")
    parts.append("</div></div>")
    parts.append("<div data-view='players' hidden><div id='players-page'></div></div>")
    parts.append("<div data-view='grounds' hidden><div id='grounds-page'></div></div>")
    parts.append("<div data-view='teams' hidden><div id='teams-page'></div></div>")
    parts.append("<div data-view='team' hidden><div id='team-page'></div></div>")
    parts.append("<div data-view='compare' hidden><div id='compare-page'></div></div>")
    parts.append(analysis_menu())

    # Sections built here, each put into its view
    parts.append(wrap_sections(prediction_section(matches, deliveries, next_season)))
    parts.append(wrap_sections(chat_section(matches, deliveries, impact)))
    parts.append(wrap_sections(explorer_section(matches, deliveries)))
    parts.append(wrap_sections(analyst_sections(matches, deliveries, impact)))

    insights = ["<h2 id='insights'>Key insights</h2><ul class='insights'>"]
    for sentence in key_insights(matches, deliveries):
        insights.append("<li>" + sentence + "</li>")
    insights.append("</ul>")
    caps = metrics.cap_winners(deliveries)
    caps.columns = ["Season", "Orange Cap", "Runs", "Purple Cap", "Wickets", "Economy"]
    insights.append("<h2 id='caps'>Orange Cap and Purple Cap winners</h2><div class='table-box'>" + caps.to_html(index=False) + "</div>")
    for section_name in CHART_SECTIONS:
        insights.append("<h2 id='" + section_id(section_name) + "'>Charts: " + section_name + "</h2><div class='charts'>")
        for file_name, title in CHART_SECTIONS[section_name]:
            if os.path.exists(os.path.join(OUTPUT_FOLDER, file_name)):
                insights.append("<figure><img src='" + file_name + "' alt='" + title + "' loading='lazy'>"
                                "<figcaption>" + title + "</figcaption></figure>")
        insights.append("</div>")
    parts.append(wrap_sections("".join(insights)))

    # The site's own data, then the router and the player / ground / team pages (src/site.js)
    players = sorted(set(deliveries["batter"]) | set(deliveries["bowler"]) | set(deliveries["non_striker"]))
    squads = pd.read_csv(os.path.join(metrics.PROJECT_FOLDER, "data", "squads_" + str(next_season) + ".csv"))
    site = dashboard_data.site_data(matches, deliveries, players, sorted(matches["venue"].unique()), squads)
    parts.append(json_script("site-data", site))
    parts.append(js_script(SITE_SCRIPT))
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
