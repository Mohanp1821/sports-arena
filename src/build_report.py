"""
build_report.py
---------------
Step 4 of the Sports Arena pipeline.

Builds a simple web dashboard, outputs/index.html, that shows:
  - headline numbers (matches, balls, seasons)
  - key insights
  - the Orange Cap / Purple Cap table
  - predictions for the next season (made by predict.py)
  - every chart made by analysis.py

Open outputs/index.html in any web browser. With Docker, the "dashboard"
service serves it at http://localhost:8080.

Run it with:
    python src/build_report.py
"""

import os
import pandas as pd
import metrics   # our own file: src/metrics.py

OUTPUT_FOLDER = os.path.join(metrics.PROJECT_FOLDER, "outputs")

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
    parts = ["<h2>Predictions for IPL " + season + "</h2>"]
    favourite = chances.iloc[0]
    parts.append("<p>Predicted champion: <b>" + favourite["team"] + "</b> ("
                 + str(favourite["title_pct"]) + "% chance). Each team's strength is its win % "
                 "over the last 3 seasons (weights 3, 2, 1), and the whole season was simulated "
                 "10,000 times.</p>")

    # Title chances table
    chances = chances[["team", "strength", "playoff_pct", "title_pct"]]
    chances.columns = ["Team", "Strength (form win %)", "Reach playoffs %", "Win title %"]
    parts.append("<div class='table-box'>" + chances.to_html(index=False) + "</div>")

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

    # Prediction charts
    parts.append("<div class='charts'>")
    for file_name, title in [("prediction_title_" + season + ".png", "Title and playoff chances, IPL " + season),
                             ("prediction_awards_" + season + ".png", "Award candidates, IPL " + season)]:
        if os.path.exists(os.path.join(OUTPUT_FOLDER, file_name)):
            parts.append("<figure><img src='" + file_name + "' alt='" + title + "'>"
                         "<figcaption>" + title + "</figcaption></figure>")
    parts.append("</div>")
    return "\n".join(parts)


def make_page(matches, deliveries):
    """Build the full HTML page as one text string."""
    parts = []
    parts.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append("<title>Sports Arena Dashboard</title><style>" + PAGE_STYLE + "</style></head><body><main>")

    # Title
    parts.append("<h1>Sports Arena: IPL Performance Dashboard</h1>")
    parts.append("<p class='subtitle'>Indian Premier League 2008-2019, built from ball-by-ball data "
                 "with Python, pandas, matplotlib and seaborn.</p>")

    # Headline number boxes
    parts.append("<div class='numbers'>")
    for value, label in headline_numbers(matches, deliveries):
        parts.append("<div class='number'><b>" + value + "</b><span>" + label + "</span></div>")
    parts.append("</div>")

    # Insights
    parts.append("<h2>Key insights</h2><ul class='insights'>")
    for sentence in key_insights(matches, deliveries):
        parts.append("<li>" + sentence + "</li>")
    parts.append("</ul>")

    # Orange / Purple Cap table (pandas can turn a DataFrame into an HTML table)
    caps = metrics.cap_winners(deliveries)
    caps.columns = ["Season", "Orange Cap", "Runs", "Purple Cap", "Wickets", "Economy"]
    parts.append("<h2>Orange Cap and Purple Cap winners</h2><div class='table-box'>")
    parts.append(caps.to_html(index=False))
    parts.append("</div>")

    # Predictions for the next season (made by predict.py)
    parts.append(prediction_section(int(matches["season"].max()) + 1))

    # Charts, section by section
    for section_name in CHART_SECTIONS:
        parts.append("<h2>" + section_name + "</h2><div class='charts'>")
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
