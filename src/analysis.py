"""
analysis.py
-----------
Step 3 of the Sports Arena pipeline.

Uses the calculations in metrics.py to:
  1. print summary tables in the terminal
  2. draw every chart and save it as a PNG in outputs/

Run it from the project folder with:
    python src/analysis.py
"""

import os
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

import metrics   # our own file: src/metrics.py


# ---------------------------------------------------------------------------
# Settings you can change
# ---------------------------------------------------------------------------
CHOSEN_SEASON = 2016            # season used for "one season" charts
FORM_BATTER = "V Kohli"         # batter for the form chart
COMPARE_PLAYERS = ["V Kohli", "RG Sharma"]
CAREER_BOWLER = "SL Malinga"
HEAD_TO_HEAD_TEAMS = ["Mumbai Indians", "Chennai Super Kings"]
RIVALRY_TEAMS = ["Chennai Super Kings", "Mumbai Indians"]   # rivalry centre chart
MATCHUP_BATTER = "V Kohli"                                  # batter vs bowlers chart
PROFILE_GROUND = "MA Chidambaram Stadium, Chepauk"          # ground profile chart

# SHOW_CHARTS = False -> only save PNG files (used when running this script).
# The notebook sets it to True so charts also appear on screen.
SHOW_CHARTS = False

OUTPUT_FOLDER = os.path.join(metrics.PROJECT_FOLDER, "outputs")

# Colours: the same palette as the web page (src/build_report.py).
# Slate is the main colour; red (a cricket ball) is the one highlight. Slate, red and
# green stay distinguishable for colour-blind readers because they also differ in lightness.
SLATE = "#3b5b6e"
RED = "#b1262c"
GREEN = "#4c7a5a"
GREY = "#8a8984"
PHASE_COLOURS = {"Powerplay": SLATE, "Middle": RED, "Death": GREEN}

# The 10 franchises playing today (used to keep charts readable).
MAJOR_TEAMS = metrics.CURRENT_FRANCHISES


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------
def setup_style():
    """Use one clean, readable style for every chart, like a newspaper graphic."""
    sns.set_theme(style="whitegrid", font_scale=1.1)
    plt.rcParams["figure.dpi"] = 100
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.titlelocation"] = "left"      # titles read from the left, like a headline
    plt.rcParams["axes.spines.top"] = False          # no box around the chart: only the axes that matter
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["font.sans-serif"] = ["Helvetica Neue", "Arial", "DejaVu Sans"]


def save_chart(fig, file_name):
    """Save a chart into outputs/, then show it (notebook) or close it (script)."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    path = os.path.join(OUTPUT_FOLDER, file_name)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print("  saved", path)
    if SHOW_CHARTS:
        plt.show()
    else:
        plt.close(fig)


def safe_file_name(text):
    """Turn a player name like 'V Kohli' into 'v_kohli' for a file name."""
    return text.lower().replace(" ", "_").replace(".", "")


# ---------------------------------------------------------------------------
# Section 6: Player form trends
# ---------------------------------------------------------------------------
def plot_player_form(deliveries, player, season):
    """Runs in each innings of one season, plus a 5-innings rolling average."""
    innings = metrics.batting_innings(deliveries)
    innings = innings[(innings["batter"] == player) & (innings["season"] == season)].copy()
    if len(innings) == 0:
        print("No innings found for", player, "in", season)
        return

    # Number the innings 1, 2, 3 ... in the order they were played.
    innings["innings_number"] = range(1, len(innings) + 1)
    # Rolling average: the mean of the last 5 innings (fewer at the start).
    innings["rolling_avg"] = innings["runs"].rolling(window=5, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(innings["innings_number"], innings["runs"], color=SLATE, alpha=0.6,
           label="Runs in the innings")
    ax.plot(innings["innings_number"], innings["rolling_avg"], color=RED,
            linewidth=2.5, marker="o", label="5-innings rolling average")
    ax.axhline(50, color=GREY, linestyle="--", linewidth=1, label="50 runs")
    ax.set_title(player + ": runs per innings in IPL " + str(season))
    ax.set_xlabel("Innings number in the season")
    ax.set_ylabel("Runs")
    ax.set_xticks(innings["innings_number"])
    ax.legend()
    save_chart(fig, "form_" + safe_file_name(player) + "_" + str(season) + ".png")


def plot_player_career(deliveries, player):
    """Season-by-season runs and strike rate (two panels, one measure each)."""
    table = metrics.batting_stats(deliveries, ["batter", "season"])
    table = table[table["batter"] == player]

    # Two separate panels, because runs and strike rate have different scales.
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    ax1.bar(table["season"], table["runs"], color=SLATE)
    ax1.set_title(player + ": IPL career by season")
    ax1.set_ylabel("Runs in season")

    ax2.plot(table["season"], table["strike_rate"], color=RED, marker="o", linewidth=2)
    ax2.set_ylabel("Strike rate")
    ax2.set_xlabel("Season")
    ax2.set_xticks(table["season"])
    save_chart(fig, "career_" + safe_file_name(player) + ".png")


def plot_bowler_career(deliveries, bowler):
    """A bowler's economy rate and wickets per season (two panels)."""
    table = metrics.bowling_stats(deliveries, ["bowler", "season"])
    table = table[table["bowler"] == bowler]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    ax1.bar(table["season"], table["wickets"], color=SLATE)
    ax1.set_title(bowler + ": wickets and economy by season")
    ax1.set_ylabel("Wickets")

    ax2.plot(table["season"], table["economy"], color=RED, marker="o", linewidth=2)
    ax2.set_ylabel("Economy (runs per over)")
    ax2.set_xlabel("Season")
    ax2.set_xticks(table["season"])
    save_chart(fig, "bowler_" + safe_file_name(bowler) + ".png")


def compare_players(deliveries, player_a, player_b):
    """Compare two batters' runs per season on one chart."""
    table = metrics.batting_stats(deliveries, ["batter", "season"])

    fig, ax = plt.subplots(figsize=(11, 5))
    colours = [SLATE, RED]
    for i, player in enumerate([player_a, player_b]):
        rows = table[table["batter"] == player]
        ax.plot(rows["season"], rows["runs"], marker="o", linewidth=2,
                color=colours[i], label=player)

    ax.set_title("Runs per season: " + player_a + " vs " + player_b)
    ax.set_xlabel("Season")
    ax.set_ylabel("Runs")
    ax.set_xticks(sorted(table["season"].unique()))
    ax.legend()
    save_chart(fig, "compare_" + safe_file_name(player_a) + "_vs_" + safe_file_name(player_b) + ".png")


# ---------------------------------------------------------------------------
# Section 7: Team comparisons
# ---------------------------------------------------------------------------
def plot_season_win_pct(matches, season):
    """Bar chart of each team's win % in one season."""
    table = metrics.team_win_percent(matches, by_season=True)
    table = table[table["season"] == season].sort_values("win_pct", ascending=False)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(table["team"], table["win_pct"], color=SLATE)
    ax.set_title("Team win % in IPL " + str(season))
    ax.set_xlabel("Team")
    ax.set_ylabel("Win %")
    ax.tick_params(axis="x", rotation=40)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    save_chart(fig, "team_win_pct_" + str(season) + ".png")


def plot_alltime_win_pct(matches):
    """Horizontal bar chart ranking every team by all-time win %."""
    table = metrics.team_win_percent(matches, by_season=False)
    table = table.sort_values("win_pct")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(table["team"], table["win_pct"], color=SLATE)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["win_pct"] + 0.5, i, str(row["win_pct"]) + "% (" + str(row["played"]) + " matches)",
                va="center", fontsize=9)
    ax.set_title("All-time win % by franchise (" + metrics.season_range_text(matches) + ")")
    ax.set_xlabel("Win %")
    ax.set_ylabel("Team")
    ax.set_xlim(0, 75)
    save_chart(fig, "team_win_pct_alltime.png")


def plot_phase_run_rate(deliveries):
    """Grouped bar chart: run rate in Powerplay, Middle and Death overs per team."""
    table = metrics.phase_run_rate(deliveries)
    table = table[table["batting_team"].isin(MAJOR_TEAMS)]

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(data=table, x="batting_team", y="run_rate", hue="phase",
                hue_order=["Powerplay", "Middle", "Death"], palette=PHASE_COLOURS, ax=ax)
    ax.set_title("Run rate by match phase (current teams, " + metrics.season_range_text(deliveries) + ")")
    ax.set_xlabel("Team")
    ax.set_ylabel("Run rate (runs per over)")
    ax.tick_params(axis="x", rotation=40)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    # Put the legend outside the plot so it does not cover any bars.
    ax.legend(title="Phase", loc="upper left", bbox_to_anchor=(1.01, 1))
    save_chart(fig, "phase_run_rate.png")


def plot_bat_first_vs_chase(deliveries, matches):
    """Grouped bars: % of matches won batting first vs chasing, per season."""
    table = metrics.bat_first_vs_chase(deliveries, matches)

    # Change the table from "wide" to "long" format so seaborn can group it.
    long_table = pd.melt(table, id_vars="season",
                         value_vars=["bat_first_win_pct", "chase_win_pct"],
                         var_name="result", value_name="win_pct")
    long_table["result"] = long_table["result"].replace(
        {"bat_first_win_pct": "Batting first", "chase_win_pct": "Chasing"})

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.barplot(data=long_table, x="season", y="win_pct", hue="result",
                palette={"Batting first": SLATE, "Chasing": RED}, ax=ax)
    ax.axhline(50, color=GREY, linestyle="--", linewidth=1)
    ax.set_title("Batting first vs chasing: win % by season")
    ax.set_xlabel("Season")
    ax.set_ylabel("Win %")
    ax.legend(title="")
    save_chart(fig, "bat_first_vs_chase.png")


def plot_first_innings_trend(deliveries, matches):
    """Line chart of the average first-innings score in each season."""
    table = metrics.first_innings_scores(deliveries, matches)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(table["season"], table["avg_first_innings"], color=SLATE, marker="o", linewidth=2)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["season"], row["avg_first_innings"] + 1.5, str(row["avg_first_innings"]),
                ha="center", fontsize=9)
    ax.set_title("Average first-innings score by season")
    ax.set_xlabel("Season")
    ax.set_ylabel("Average runs")
    ax.set_xticks(table["season"])
    save_chart(fig, "first_innings_trend.png")


def plot_home_away(matches):
    """Grouped bars: home vs away win % for the 10 current franchises."""
    table = metrics.home_away_performance(matches)

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.barplot(data=table, x="team", y="win_pct", hue="location",
                hue_order=["Home", "Away"], palette={"Home": SLATE, "Away": RED}, ax=ax)
    ax.set_title("Home ground vs away win % (" + metrics.season_range_text(matches) + ")")
    ax.set_xlabel("Team")
    ax.set_ylabel("Win %")
    ax.tick_params(axis="x", rotation=40)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    ax.legend(title="")
    save_chart(fig, "home_vs_away.png")


def plot_head_to_head(matches, team_a, team_b):
    """Grouped bars: wins for each team, per season, in matches between the two."""
    table = metrics.head_to_head(matches, team_a, team_b)
    total_a = table[team_a].sum()
    total_b = table[team_b].sum()

    # Long format: one row per season per team, so seaborn can group the bars.
    long_table = pd.melt(table, id_vars="season", value_vars=[team_a, team_b],
                         var_name="team", value_name="wins")

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.barplot(data=long_table, x="season", y="wins", hue="team",
                palette={team_a: SLATE, team_b: RED}, ax=ax)
    ax.set_title("Head to head: " + team_a + " " + str(total_a) + " - "
                 + str(total_b) + " " + team_b)
    ax.set_xlabel("Season")
    ax.set_ylabel("Wins against the other team")
    ax.set_yticks(range(0, int(long_table["wins"].max()) + 2))
    ax.legend(title="")
    save_chart(fig, "head_to_head.png")


# ---------------------------------------------------------------------------
# Section 8: Top performers
# ---------------------------------------------------------------------------
def plot_cap_winners(caps):
    """Two panels: Orange Cap runs and Purple Cap wickets, labelled with names."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    ax1.bar(caps["season"], caps["runs"], color=RED)
    for i in range(len(caps)):
        row = caps.iloc[i]
        ax1.text(row["season"], row["runs"] + 10, row["orange_cap"], ha="center",
                 rotation=90, va="bottom", fontsize=9)
    ax1.set_title("Orange Cap (most runs) and Purple Cap (most wickets) by season")
    ax1.set_ylabel("Runs")
    ax1.set_ylim(0, 1250)

    ax2.bar(caps["season"], caps["wickets"], color="#7a5c8a")
    for i in range(len(caps)):
        row = caps.iloc[i]
        ax2.text(row["season"], row["wickets"] + 0.5, row["purple_cap"], ha="center",
                 rotation=90, va="bottom", fontsize=9)
    ax2.set_ylabel("Wickets")
    ax2.set_xlabel("Season")
    ax2.set_ylim(0, 45)
    ax2.set_xticks(caps["season"])
    save_chart(fig, "cap_winners.png")


def plot_top_bar(table, name_column, metric, title, x_label, file_name):
    """Generic horizontal bar chart for a top-10 table (best player at the top)."""
    # Reverse the order so the best player is drawn at the top.
    table = table.iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(table[name_column], table[metric], color=SLATE)
    for i in range(len(table)):
        value = table.iloc[i][metric]
        ax.text(value, i, " " + str(value), va="center", fontsize=9)
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel("Player")
    save_chart(fig, file_name)


def plot_batting_quadrant(deliveries, min_balls=1000):
    """
    Scatter: batting average (x) vs strike rate (y), with median lines.
    The two median lines split the chart into four groups:
      Elite      = high average AND high strike rate
      Anchors    = high average, lower strike rate (steady, build innings)
      Finishers  = lower average, high strike rate (fast hitters late on)
      Struggling = below the median on both
    """
    table = metrics.batting_stats(deliveries)
    table = table[table["balls_faced"] >= min_balls].dropna(subset=["average"])
    median_avg = table["average"].median()
    median_sr = table["strike_rate"].median()

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.scatter(table["average"], table["strike_rate"], s=60, color=SLATE,
               edgecolor="white", linewidth=1)
    ax.axvline(median_avg, color=GREY, linestyle="--")
    ax.axhline(median_sr, color=GREY, linestyle="--")

    # Label only the top 15 run scorers, so names do not overlap too much.
    top = table.sort_values("runs", ascending=False).head(15)
    for i in range(len(top)):
        row = top.iloc[i]
        ax.annotate(row["batter"], (row["average"], row["strike_rate"]),
                    xytext=(5, 4), textcoords="offset points", fontsize=9)

    # Quadrant names in the four corners.
    ax.text(0.98, 0.98, "Elite", transform=ax.transAxes, ha="right", va="top", fontsize=13, weight="bold")
    ax.text(0.98, 0.02, "Anchors", transform=ax.transAxes, ha="right", va="bottom", fontsize=13, weight="bold")
    ax.text(0.02, 0.98, "Finishers", transform=ax.transAxes, ha="left", va="top", fontsize=13, weight="bold")
    ax.text(0.02, 0.02, "Struggling", transform=ax.transAxes, ha="left", va="bottom", fontsize=13, weight="bold")

    ax.set_title("Batting average vs strike rate (min " + str(min_balls) + " balls faced)")
    ax.set_xlabel("Batting average (runs per dismissal)")
    ax.set_ylabel("Strike rate (runs per 100 balls)")
    save_chart(fig, "batting_quadrant.png")


def plot_team_season_heatmap(matches):
    """Heatmap: rows = teams, columns = seasons, colour = win %."""
    table = metrics.team_win_percent(matches, by_season=True)
    # pivot: turn the long table into a grid of team x season.
    grid = table.pivot(index="team", columns="season", values="win_pct")

    fig, ax = plt.subplots(figsize=(14, 7))
    sns.heatmap(grid, annot=True, fmt=".0f", cmap=sns.light_palette(SLATE, as_cmap=True), linewidths=1,
                linecolor="white", cbar_kws={"label": "Win %"}, ax=ax)
    ax.grid(False)   # turn off background gridlines so empty cells stay blank
    ax.set_title("Win % by team and season (blank = did not play)")
    ax.set_xlabel("Season")
    ax.set_ylabel("Team")
    save_chart(fig, "heatmap_team_season.png")


# ---------------------------------------------------------------------------
# Section 10: Analyst views (rivalries, matchups, grounds, specialists, eras, trends)
# ---------------------------------------------------------------------------
def plot_rivalry(matches, team_a, team_b):
    """Two panels: wins per season, and wins at the grounds they met most."""
    overall, by_season, by_stage, by_ground = metrics.rivalry_record(matches, team_a, team_b)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9))

    long_table = pd.melt(by_season, id_vars="season", value_vars=[team_a, team_b], var_name="team", value_name="wins")
    sns.barplot(data=long_table, x="season", y="wins", hue="team", palette={team_a: SLATE, team_b: RED}, ax=ax1)
    ax1.set_title("Rivalry: " + team_a + " " + str(overall[team_a]) + " - " + str(overall[team_b]) + " " + team_b
                  + " (" + str(overall["played"]) + " matches)")
    ax1.set_xlabel("Season")
    ax1.set_ylabel("Wins")
    ax1.set_yticks(range(0, int(long_table["wins"].max()) + 2))   # whole numbers only
    ax1.legend(title="")

    grounds = by_ground.head(6)
    long_ground = pd.melt(grounds, id_vars="venue", value_vars=[team_a, team_b], var_name="team", value_name="wins")
    sns.barplot(data=long_ground, y="venue", x="wins", hue="team", palette={team_a: SLATE, team_b: RED}, ax=ax2)
    ax2.set_title("Wins at the grounds where they met most")
    ax2.set_xlabel("Wins")
    ax2.set_ylabel("Ground")
    ax2.legend(title="")
    save_chart(fig, "rivalry_" + safe_file_name(team_a) + "_vs_" + safe_file_name(team_b) + ".png")


def plot_batter_vs_bowlers(deliveries, batter, n=10):
    """Strike rate against the n bowlers the batter faced most (label = balls and dismissals)."""
    table = metrics.matchup_table(deliveries[deliveries["batter"] == batter])
    table = table.sort_values(["balls", "bowler"], ascending=[False, True]).head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(table["bowler"], table["strike_rate"], color=SLATE)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["strike_rate"], i, " SR " + str(row["strike_rate"]) + " | " + str(row["balls"]) + " balls, out "
                + str(row["dismissals"]) + "x", va="center", fontsize=9)
    ax.set_title(batter + " against the " + str(n) + " bowlers he faced most")
    ax.set_xlabel("Strike rate (runs per 100 balls)")
    ax.set_ylabel("Bowler")
    ax.set_xlim(0, table["strike_rate"].max() * 1.45)
    save_chart(fig, "matchups_" + safe_file_name(batter) + ".png")


def plot_ground_profile(deliveries, matches, venue):
    """Average first-innings score at one ground per season, next to the average of all grounds."""
    ground = metrics.ground_first_innings_by_season(deliveries, matches, venue)
    everywhere = metrics.first_innings_scores(deliveries, matches)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(everywhere["season"], everywhere["avg_first_innings"], color=GREY, marker="o", linewidth=2,
            label="All grounds")
    ax.plot(ground["season"], ground["avg_first_innings"], color=SLATE, marker="o", linewidth=2.5, label=venue)
    ax.set_title("Average first-innings score: " + venue + " vs all grounds")
    ax.set_xlabel("Season")
    ax.set_ylabel("Average first-innings runs")
    ax.set_xticks(everywhere["season"])
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    save_chart(fig, "ground_" + safe_file_name(venue.split(",")[0]) + ".png")


def plot_fortress(matches):
    """Home fortress index: home win % minus away win % for each current franchise."""
    table = metrics.home_fortress_index(matches).iloc[::-1]
    colours = [SLATE if value >= 0 else RED for value in table["fortress_index"]]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(table["team"], table["fortress_index"], color=colours)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["fortress_index"], i, " home " + str(row["home_win_pct"]) + "% / away " + str(row["away_win_pct"]) + "% ",
                va="center", ha="left" if row["fortress_index"] >= 0 else "right", fontsize=9)
    ax.axvline(0, color=GREY, linewidth=1)
    ax.set_title("Home fortress index (home win % minus away win %, " + metrics.season_range_text(matches) + ")")
    ax.set_xlabel("Percentage points")
    ax.set_ylabel("Franchise")
    limit = table["fortress_index"].abs().max() * 2.2
    ax.set_xlim(-limit, limit)
    save_chart(fig, "home_fortress.png")


def plot_finishers(deliveries, matches):
    """Fastest death-over scorers, labelled with their not-out % in chases."""
    table = metrics.finishers(deliveries, matches, min_death_balls=150, n=10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(table["batter"], table["death_strike_rate"], color=SLATE)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["death_strike_rate"], i, " " + str(row["death_strike_rate"]) + "  (not out in "
                + str(row["not_out_pct"]) + "% of chases)", va="center", fontsize=9)
    ax.set_title("Finishers: best strike rate in overs 16-20 (min 150 balls there)")
    ax.set_xlabel("Death-over strike rate")
    ax.set_ylabel("Batter")
    ax.set_xlim(0, table["death_strike_rate"].max() * 1.5)
    save_chart(fig, "finishers.png")


def plot_partnerships(deliveries, matches, n=10):
    """The n biggest partnerships, built from the ball data."""
    table = metrics.partnerships(deliveries, matches).head(n).iloc[::-1]
    labels = [table["pair"].iloc[i] + " (" + str(table["season"].iloc[i]) + ")" for i in range(len(table))]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(labels, table["runs"], color=SLATE)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["runs"], i, " " + str(row["runs"]) + " off " + str(row["balls"]) + " balls, wicket "
                + str(row["wicket"]), va="center", fontsize=9)
    ax.set_title("Biggest partnerships (" + metrics.season_range_text(matches) + ")")
    ax.set_xlabel("Runs while together")
    ax.set_ylabel("Partnership")
    ax.set_xlim(0, table["runs"].max() * 1.35)
    save_chart(fig, "top_partnerships.png")


def plot_impact_era(deliveries, matches):
    """Two panels: run rate by phase in each era, and scoring and chasing numbers per era."""
    phases = metrics.impact_era_phase_run_rate(deliveries)
    summary = metrics.impact_era_summary(deliveries, matches)
    era_colours = {metrics.ERA_BEFORE: GREY, metrics.ERA_IMPACT: RED}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    sns.barplot(data=phases, x="phase", y="run_rate", hue="era", order=["Powerplay", "Middle", "Death"],
                palette=era_colours, ax=ax1)
    for bars in ax1.containers:
        ax1.bar_label(bars, fmt="%.2f", padding=2, fontsize=9)
    ax1.set_title("Run rate by phase")
    ax1.set_xlabel("Phase")
    ax1.set_ylabel("Runs per over")
    ax1.set_ylim(0, phases["run_rate"].max() * 1.35)   # room above the bars for the legend
    ax1.legend(title="", loc="upper left")

    ax2.bar(summary["era"].str.split(" ").str[0], summary["avg_first_innings"], color=[GREY, RED])
    for i in range(len(summary)):
        row = summary.iloc[i]
        ax2.text(i, row["avg_first_innings"] + 2, str(row["avg_first_innings"]) + " avg\n"
                 + str(row["totals_200_plus"]) + " totals of 200+\nchases won " + str(row["chase_win_pct"]) + "%",
                 ha="center", fontsize=9)
    ax2.set_title("Average first-innings score")
    ax2.set_xlabel("Era")
    ax2.set_ylabel("Runs")
    ax2.set_ylim(0, summary["avg_first_innings"].max() * 1.35)
    fig.suptitle("Before and after the Impact Player rule (2023)", fontweight="bold")
    save_chart(fig, "impact_player_era.png")


def plot_impact_choices(impact, deliveries, matches):
    """How teams used their Impact Player, and their win % with each choice."""
    choices = metrics.impact_player_choices(impact, deliveries, matches)
    table = metrics.impact_choice_summary(choices, by_team=False).sort_values("times")
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.barh(table["role"], table["win_pct"], color=SLATE)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["win_pct"], i, " " + str(row["win_pct"]) + "% won (" + str(row["times"]) + " times)", va="center", fontsize=9)
    ax.axvline(50, color=GREY, linestyle="--", linewidth=1)
    ax.set_title("Impact Player choices 2023+: what the substitute did, and win %")
    ax.set_xlabel("Win % of the team that made this choice")
    ax.set_ylabel("What the Impact Player did")
    ax.set_xlim(0, 110)
    save_chart(fig, "impact_player_choices.png")


def plot_scoring_inflation(deliveries, matches):
    """Two panels: average first-innings score and sixes per match, every season."""
    table = metrics.scoring_inflation(deliveries, matches)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    ax1.plot(table["season"], table["avg_first_innings"], color=SLATE, marker="o", linewidth=2)
    ax1.set_title("Scoring inflation " + metrics.season_range_text(matches))
    ax1.set_ylabel("Average 1st-innings score")
    ax2.bar(table["season"], table["sixes_per_match"], color=RED)
    ax2.set_ylabel("Sixes per match")
    ax2.set_xlabel("Season")
    ax2.set_xticks(table["season"])
    ax2.tick_params(axis="x", rotation=45)
    for ax in [ax1, ax2]:
        ax.axvline(2022.5, color=GREY, linestyle="--", linewidth=1)
    ax1.text(2022.6, table["avg_first_innings"].min(), "Impact Player rule", fontsize=9, color=GREY)
    save_chart(fig, "scoring_inflation.png")


def chase_model_table(model):
    """The weights the logistic regression learned, as a small table (saved for the dashboard)."""
    names = ["intercept", "runs_needed", "balls_left", "wickets_left", "required_rate"]
    values = [model.intercept_[0]] + list(model.coef_[0])
    return pd.DataFrame({"term": names, "weight": [round(value, 6) for value in values]})


def plot_chase_curve(model):
    """Chance of winning a chase with 60 balls left, by runs needed and wickets in hand."""
    fig, ax = plt.subplots(figsize=(11, 6))
    runs_needed = list(range(10, 151, 5))
    colours = {10: SLATE, 7: GREEN, 5: RED, 3: "#7a5c8a", 1: GREY}
    for wickets in [10, 7, 5, 3, 1]:
        chances = [metrics.win_probability(model, runs, 60, wickets) for runs in runs_needed]
        ax.plot(runs_needed, chances, linewidth=2.5, color=colours[wickets], label=str(wickets) + (" wicket left" if wickets == 1 else " wickets left"))
    ax.axhline(50, color=GREY, linestyle="--", linewidth=1)
    ax.set_title("Chase win probability with 10 overs (60 balls) left")
    ax.set_xlabel("Runs still needed")
    ax.set_ylabel("Chance the chasing team wins (%)")
    ax.set_ylim(0, 100)
    ax.legend()
    save_chart(fig, "chase_win_probability.png")


def plot_impact_scores(deliveries, season, n=10):
    """Top n season impact scores, split into batting and bowling points."""
    table = metrics.season_impact_scores(deliveries)
    table = table[table["season"] == season].head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(table["player"], table["batting_points"], color=SLATE, label="Batting points (runs x phase weight)")
    ax.barh(table["player"], table["bowling_points"], left=table["batting_points"], color=RED,
            label="Bowling points (wickets x runs per wicket in that phase)")
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["impact"], i, " " + str(row["impact"]) + " (" + str(row["runs"]) + " runs, " + str(row["wickets"]) + " wkts)",
                va="center", fontsize=9)
    ax.set_title("Season impact score, IPL " + str(season))
    ax.set_xlabel("Impact score")
    ax.set_ylabel("Player")
    ax.set_xlim(0, table["impact"].max() * 1.4)
    ax.legend(loc="lower right")
    save_chart(fig, "impact_scores_" + str(season) + ".png")


def plot_ground_map(deliveries, matches, min_matches=20):
    """
    How each ground plays: runs index (x) against wickets index (y), both 100 = league
    average in the same seasons. The dashed lines at 100 split the chart into four kinds of ground.
    """
    table = metrics.pitch_profile(deliveries, matches, min_matches=min_matches)
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.scatter(table["runs_index"], table["wickets_index"], s=table["matches"] * 3, color=SLATE, alpha=0.7,
               edgecolor="white", linewidth=1)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.annotate(row["venue"].split(",")[0] + " (" + str(row["matches"]) + ")", (row["runs_index"], row["wickets_index"]),
                    xytext=(6, 4), textcoords="offset points", fontsize=9)
    ax.axvline(100, color=GREY, linestyle="--")
    ax.axhline(100, color=GREY, linestyle="--")
    ax.text(0.98, 0.98, "More runs, more wickets", transform=ax.transAxes, ha="right", va="top", fontsize=11, weight="bold")
    ax.text(0.98, 0.02, "Batting paradise", transform=ax.transAxes, ha="right", va="bottom", fontsize=11, weight="bold")
    ax.text(0.02, 0.98, "Bowler-friendly", transform=ax.transAxes, ha="left", va="top", fontsize=11, weight="bold")
    ax.text(0.02, 0.02, "Slow, low-risk", transform=ax.transAxes, ha="left", va="bottom", fontsize=11, weight="bold")
    ax.set_title("How each ground plays, " + metrics.season_range_text(matches) + " (min " + str(min_matches)
                 + " matches; dot size = matches)")
    ax.set_xlabel("Runs index (100 = league average in the same seasons)")
    ax.set_ylabel("Wickets index (100 = league average in the same seasons)")
    save_chart(fig, "ground_map.png")


def plot_player_ground_fit(deliveries, matches, player, min_balls=150):
    """A batter's strike rate at each ground minus his strike rate elsewhere in the same seasons."""
    table = metrics.player_ground_batting(deliveries, matches)
    table = table[(table["batter"] == player) & (table["balls"] >= min_balls)].sort_values("strike_rate_diff")
    colours = [RED if value >= 0 else SLATE for value in table["strike_rate_diff"]]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(table["venue"].str.split(",").str[0], table["strike_rate_diff"], color=colours)
    for i in range(len(table)):
        row = table.iloc[i]
        ax.text(row["strike_rate_diff"], i, " " + str(row["strike_rate"]) + " vs " + str(row["else_strike_rate"])
                + " (" + str(row["balls"]) + " balls) ", va="center", ha="left" if row["strike_rate_diff"] >= 0 else "right", fontsize=9)
    ax.axvline(0, color=GREY, linewidth=1)
    limit = table["strike_rate_diff"].abs().max() * 1.9
    ax.set_xlim(-limit, limit)
    ax.set_title(player + ": strike rate at each ground minus elsewhere in the same seasons (min " + str(min_balls) + " balls)")
    ax.set_xlabel("Strike-rate difference (red = faster at this ground)")
    ax.set_ylabel("Ground")
    save_chart(fig, "player_ground_fit_" + safe_file_name(player) + ".png")


# ---------------------------------------------------------------------------
# Main: run everything in order
# ---------------------------------------------------------------------------
def main():
    matplotlib.use("Agg")   # draw charts to files only (no pop-up windows)
    setup_style()
    pd.set_option("display.width", 140)

    print("Loading cleaned data ...")
    matches, deliveries = metrics.load_processed_data()
    print("Matches:", len(matches), " Balls:", len(deliveries))

    print("\n=== Top 10 run scorers (all seasons) ===")
    print(metrics.top_performers(deliveries, None, "runs")[
        ["batter", "runs", "innings", "average", "strike_rate", "fifties", "hundreds"]].to_string())

    print("\n=== Top 10 wicket takers (all seasons) ===")
    print(metrics.top_performers(deliveries, None, "wickets")[
        ["bowler", "wickets", "overs", "economy", "bowling_avg", "dot_pct"]].to_string())

    caps = metrics.cap_winners(deliveries)
    print("\n=== Orange Cap and Purple Cap winners ===")
    print(caps.to_string())

    toss_table, toss_overall = metrics.toss_impact(matches)
    print("\n=== Toss impact ===")
    print("Toss winner won the match in", toss_overall, "% of matches")
    print(toss_table.to_string())

    print("\n=== Player of the Match awards ===")
    potm = metrics.player_of_match_counts(matches)
    print(potm.to_string())

    print("\nSaving charts ...")
    # Section 6: player form
    plot_player_form(deliveries, FORM_BATTER, CHOSEN_SEASON)
    plot_player_career(deliveries, FORM_BATTER)
    plot_bowler_career(deliveries, CAREER_BOWLER)
    compare_players(deliveries, COMPARE_PLAYERS[0], COMPARE_PLAYERS[1])

    # Section 7: teams
    plot_season_win_pct(matches, CHOSEN_SEASON)
    plot_alltime_win_pct(matches)
    plot_phase_run_rate(deliveries)
    plot_bat_first_vs_chase(deliveries, matches)
    plot_first_innings_trend(deliveries, matches)
    plot_home_away(matches)
    plot_head_to_head(matches, HEAD_TO_HEAD_TEAMS[0], HEAD_TO_HEAD_TEAMS[1])

    # Section 8: top performers
    plot_cap_winners(caps)
    season_text = str(CHOSEN_SEASON)
    top_sr = metrics.top_performers(deliveries, CHOSEN_SEASON, "strike_rate", n=10, min_balls=200)
    plot_top_bar(top_sr, "batter", "strike_rate", "Top 10 strike rates, IPL " + season_text + " (min 200 balls)",
                 "Strike rate", "top_strike_rate_" + season_text + ".png")
    top_eco = metrics.top_performers(deliveries, CHOSEN_SEASON, "economy", n=10, min_balls=180)
    plot_top_bar(top_eco, "bowler", "economy", "Best economy, IPL " + season_text + " (min 30 overs)",
                 "Economy (runs per over, lower is better)", "top_economy_" + season_text + ".png")
    top_six = metrics.top_performers(deliveries, CHOSEN_SEASON, "sixes", n=10)
    plot_top_bar(top_six, "batter", "sixes", "Most sixes, IPL " + season_text,
                 "Sixes", "top_sixes_" + season_text + ".png")
    plot_batting_quadrant(deliveries)
    death = metrics.death_over_bowling(deliveries, min_overs=20).head(10)
    plot_top_bar(death, "bowler", "economy", "Death-over specialists: best economy in overs 16-20 (min 20 overs)",
                 "Economy (lower is better)", "death_over_specialists.png")
    plot_top_bar(potm, "player", "awards", "Most Player of the Match awards (" + metrics.season_range_text(matches) + ")",
                 "Awards", "player_of_match.png")

    # Section 9: heatmap
    plot_team_season_heatmap(matches)

    # Section 10: analyst views
    impact = metrics.load_impact_players()
    latest_season = int(matches["season"].max())
    plot_rivalry(matches, RIVALRY_TEAMS[0], RIVALRY_TEAMS[1])
    plot_batter_vs_bowlers(deliveries, MATCHUP_BATTER)
    plot_ground_profile(deliveries, matches, PROFILE_GROUND)
    plot_fortress(matches)
    plot_finishers(deliveries, matches)
    plot_partnerships(deliveries, matches)
    plot_impact_era(deliveries, matches)
    plot_impact_choices(impact, deliveries, matches)
    plot_scoring_inflation(deliveries, matches)
    plot_impact_scores(deliveries, latest_season)
    plot_ground_map(deliveries, matches)
    plot_player_ground_fit(deliveries, matches, MATCHUP_BATTER)

    print("\nFitting the chase win-probability model (logistic regression) ...")
    model = metrics.win_probability_model(metrics.chase_states(deliveries, matches))
    chase_model_table(model).to_csv(os.path.join(OUTPUT_FOLDER, "chase_win_probability_model.csv"), index=False)
    plot_chase_curve(model)
    print("\nDone. All charts are in:", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()
