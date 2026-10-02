"""
predict.py
----------
Step 5 of the Sports Arena pipeline: PREDICTIONS for the next season.

The data ends in 2019, so the "next season" is 2020. This file predicts:
  1. the IPL champion (each team's chance of winning the title)
  2. the award winners: Orange Cap, Purple Cap, Most Sixes and
     Most Player of the Match awards

HOW THE PREDICTION WORKS (simple and explainable, no black box):

  a) FORM SCORE = a weighted average of the last 3 seasons.
     The most recent season counts most:  last season x3, the one before x2,
     the one before that x1.  Example: a batter with 600, 400 and 300 runs
         form = (3*600 + 2*400 + 1*300) / (3 + 2 + 1) = 483 runs

  b) CHAMPION: we give each team a strength = its form win %, then PLAY THE
     WHOLE SEASON 10,000 TIMES on the computer (a "Monte Carlo simulation"):
       - league stage: every team plays every other team twice
       - in one match, team A beats team B with chance  A / (A + B)
         (e.g. strength 60 vs 40 -> team A wins 60% of the time)
       - the top 4 go to the IPL playoffs (Qualifier 1, Eliminator,
         Qualifier 2, Final)
     A team's title chance = how many of the 10,000 seasons it won.

  c) AWARDS: the player with the best form score is our pick.

  d) BACKTEST: to check whether this method works, we pretend it is the start
     of each past season (2011-2019), predict using only the seasons BEFORE it,
     and compare with what really happened.

Run it from the project folder with:
    python src/predict.py
"""

import os
import numpy as np        # installed together with pandas; used for random numbers
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

import metrics    # our own file: src/metrics.py (cricket formulas)
import analysis   # our own file: src/analysis.py (chart style and save_chart)


# ---------------------------------------------------------------------------
# Settings you can change
# ---------------------------------------------------------------------------
FORM_WEIGHTS = [3, 2, 1]   # weight of last season, season before, season before that
SIMULATIONS = 10000        # how many times the season is played on the computer
RANDOM_SEED = 42           # fixed seed, so the results are the same every run
NEW_TEAM_STRENGTH = 50.0   # a team with no history gets an average strength (50% wins)
TOP_N = 5                  # how many candidates to show for each award
FIRST_BACKTEST_SEASON = 2011   # first season with 3 earlier seasons of history

# The awards we predict:
#   (award name, which season table, name column, value column)
AWARDS = [
    ("Orange Cap (most runs)", "batting", "batter", "runs"),
    ("Purple Cap (most wickets)", "bowling", "bowler", "wickets"),
    ("Most sixes", "batting", "batter", "sixes"),
    ("Most Player of the Match awards", "potm", "player", "awards"),
]

# The REAL results of a predicted season, if they are known, to check the
# prediction afterwards. The data ends in 2026 and we predict 2027, which has
# not been played yet, so this is empty (nothing is typed in by hand).
ACTUAL_RESULTS = {}

OUTPUT_FOLDER = analysis.OUTPUT_FOLDER


# ---------------------------------------------------------------------------
# Past results we need
# ---------------------------------------------------------------------------
def season_champions(matches):
    """The champion (franchise) of each season. The formula lives in metrics.py."""
    return metrics.season_champions(matches)


def season_tables(matches, deliveries):
    """
    One row per player per season, for each award:
      batting : runs and sixes      (from metrics.batting_stats)
      bowling : wickets and economy (from metrics.bowling_stats)
      potm    : Player of the Match awards won in the season
    """
    batting = metrics.batting_stats(deliveries, ["batter", "season"])
    bowling = metrics.bowling_stats(deliveries, ["bowler", "season"])
    potm = matches.groupby(["player_of_match", "season"]).size().reset_index(name="awards")
    potm = potm.rename(columns={"player_of_match": "player"})
    return {"batting": batting, "bowling": bowling, "potm": potm}


# ---------------------------------------------------------------------------
# a) Form score
# ---------------------------------------------------------------------------
def weighted_form(table, name_column, value_column, last_season):
    """
    Form score = weighted average of value_column over the 3 seasons up to
    last_season (weights 3, 2, 1). A season the player/team missed is skipped,
    so a young player is not punished for seasons before their debut.
    Only names that played in last_season are kept, so retired players drop out.
    (Limitation: a player who missed last season, like Warner in 2018, drops out too.)
    """
    # Keep only the last 3 seasons.
    first_season = last_season - len(FORM_WEIGHTS) + 1
    recent = table[(table["season"] >= first_season) & (table["season"] <= last_season)].copy()

    # Give each season its weight: last_season -> 3, last_season-1 -> 2, ...
    season_weight = {}
    for years_back in range(len(FORM_WEIGHTS)):
        season_weight[last_season - years_back] = FORM_WEIGHTS[years_back]
    recent["weight"] = recent["season"].map(season_weight)
    recent["weighted_value"] = recent[value_column] * recent["weight"]

    # Weighted average = sum(weight * value) / sum(weights of seasons played)
    form = recent.groupby(name_column).agg(
        weighted_total=("weighted_value", "sum"),
        weight_sum=("weight", "sum"),
    ).reset_index()
    form["form"] = (form["weighted_total"] / form["weight_sum"]).round(1)

    # Keep only names that played in the latest season.
    active = table[table["season"] == last_season][name_column]
    form = form[form[name_column].isin(active)]

    # Best form first; if two are equal, sort by name so the order is fixed.
    form = form.sort_values(["form", name_column], ascending=[False, True])
    return form[[name_column, "form"]].reset_index(drop=True)


def team_strengths(matches, last_season, teams):
    """
    Strength of each team = its form win % (weighted, last 3 seasons).
    teams = the teams that will play in the predicted season.
    """
    win_table = metrics.team_win_percent(matches[matches["season"] <= last_season], by_season=True)
    form = weighted_form(win_table, "team", "win_pct", last_season)
    form_by_team = dict(zip(form["team"], form["form"]))

    strengths = {}
    for team in teams:
        # A team that did not play last season (e.g. a new team) gets 50.
        strengths[team] = form_by_team.get(team, NEW_TEAM_STRENGTH)
    return strengths


# ---------------------------------------------------------------------------
# b) Simulating a season
# ---------------------------------------------------------------------------
def play_match(team_a, team_b, strengths, rng):
    """Play one match. Team A wins with chance  A / (A + B)."""
    chance_a = strengths[team_a] / (strengths[team_a] + strengths[team_b])
    if rng.random() < chance_a:     # rng.random() = a random number between 0 and 1
        return team_a
    return team_b


def simulate_season(strengths, rng):
    """Play one full IPL season. Returns (champion, the 4 playoff teams)."""
    teams = list(strengths.keys())
    wins = {}
    for team in teams:
        wins[team] = 0

    # League stage: every pair of teams plays twice (home and away).
    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            for game in range(2):
                winner = play_match(teams[i], teams[j], strengths, rng)
                wins[winner] += 1

    # Points table: sort by wins. A tiny random number breaks ties
    # (in the real IPL, net run rate breaks ties).
    table_score = {}
    for team in teams:
        table_score[team] = wins[team] + rng.random() / 10
    points_table = sorted(teams, key=table_score.get, reverse=True)
    first, second, third, fourth = points_table[0:4]

    # Playoffs (the IPL format used since 2011).
    q1_winner = play_match(first, second, strengths, rng)
    q1_loser = second if q1_winner == first else first
    eliminator_winner = play_match(third, fourth, strengths, rng)
    q2_winner = play_match(q1_loser, eliminator_winner, strengths, rng)
    champion = play_match(q1_winner, q2_winner, strengths, rng)
    return champion, points_table[0:4]


def title_chances(strengths, simulations=SIMULATIONS, seed=RANDOM_SEED):
    """
    Play the season many times and count:
      title_pct   = % of seasons the team won the final
      playoff_pct = % of seasons the team finished in the top 4
    """
    rng = np.random.default_rng(seed)   # random number generator with a fixed seed
    titles = {}
    playoffs = {}
    for team in strengths:
        titles[team] = 0
        playoffs[team] = 0

    for run in range(simulations):
        champion, top4 = simulate_season(strengths, rng)
        titles[champion] += 1
        for team in top4:
            playoffs[team] += 1

    rows = []
    for team in strengths:
        rows.append({
            "team": team,
            "strength": strengths[team],
            "playoff_pct": round(playoffs[team] / simulations * 100, 1),
            "title_pct": round(titles[team] / simulations * 100, 1),
        })
    table = pd.DataFrame(rows)
    table = table.sort_values(["title_pct", "team"], ascending=[False, True])
    return table.reset_index(drop=True)


# ---------------------------------------------------------------------------
# c) Award predictions
# ---------------------------------------------------------------------------
def award_candidates(tables, last_season, n=TOP_N):
    """The top n candidates for every award, by form score."""
    rows = []
    for award, table_name, name_column, value_column in AWARDS:
        form = weighted_form(tables[table_name], name_column, value_column, last_season)
        for rank in range(min(n, len(form))):
            rows.append({
                "award": award,
                "rank": rank + 1,
                "player": form.iloc[rank][name_column],
                "form": form.iloc[rank]["form"],
                "measure": value_column,
            })
    return pd.DataFrame(rows)


def actual_award_winners(table, name_column, value_column, season):
    """
    Who really won an award in a season (a list, because players can tie).
    For wickets, a tie goes to the better economy, like the real Purple Cap.
    """
    rows = table[table["season"] == season]
    rows = rows[rows[value_column] == rows[value_column].max()]
    if value_column == "wickets":
        rows = rows[rows["economy"] == rows["economy"].min()]
    return sorted(rows[name_column])


# ---------------------------------------------------------------------------
# d) Backtest: would this method have worked in the past?
# ---------------------------------------------------------------------------
def rank_of(name, ranking):
    """Position (1, 2, 3 ...) of a name in our ranked list, or None if missing."""
    if name in ranking:
        return ranking.index(name) + 1
    return None


def backtest(matches, tables):
    """
    For every past season from 2011, predict it using ONLY the seasons before,
    then compare with the real result. The favourite team is the one with the
    best form win % (the simulation always ranks teams in this same order).
    """
    champions = season_champions(matches)
    rows = []
    last_data_season = int(matches["season"].max())
    for season in range(FIRST_BACKTEST_SEASON, last_data_season + 1):
        history_end = season - 1

        # Champion: rank the teams that actually took part in this season.
        teams = sorted(set(matches[matches["season"] == season]["team1_franchise"]))
        strengths = team_strengths(matches, history_end, teams)
        team_ranking = sorted(teams, key=strengths.get, reverse=True)
        actual = champions[champions["season"] == season]["champion"].iloc[0]
        rows.append({
            "season": season, "award": "IPL champion",
            "predicted": team_ranking[0], "actual": actual,
            "actual_rank": rank_of(actual, team_ranking),
        })

        # Awards: rank the players who were active in the season before.
        for award, table_name, name_column, value_column in AWARDS:
            form = weighted_form(tables[table_name], name_column, value_column, history_end)
            player_ranking = list(form[name_column])
            winners = actual_award_winners(tables[table_name], name_column, value_column, season)
            # If players tied for the award, use the best-ranked of them.
            ranks = [rank_of(w, player_ranking) for w in winners if rank_of(w, player_ranking)]
            rows.append({
                "season": season, "award": award,
                "predicted": player_ranking[0], "actual": " / ".join(winners),
                "actual_rank": min(ranks) if ranks else None,
            })

    table = pd.DataFrame(rows)
    # "Int64" = whole numbers that may be empty (a winner who was not in our list).
    table["actual_rank"] = table["actual_rank"].astype("Int64")
    table["correct"] = (table["actual_rank"] == 1).fillna(False)
    table["in_top_5"] = (table["actual_rank"] <= 5).fillna(False)   # empty rank -> False
    return table


def backtest_summary(backtest_table, number_of_teams=8):
    """Hit rate per award, next to a random guess for comparison."""
    summary = backtest_table.groupby("award", sort=False).agg(
        seasons=("season", "count"),
        correct=("correct", "sum"),
        in_top_5=("in_top_5", "sum"),
    ).reset_index()
    summary["correct_pct"] = (summary["correct"] / summary["seasons"] * 100).round(0)
    # Picking a champion at random from 8 teams is right 1 time in 8 (12.5%).
    summary["random_guess_pct"] = None
    summary.loc[summary["award"] == "IPL champion", "random_guess_pct"] = round(100 / number_of_teams, 1)
    return summary


# ---------------------------------------------------------------------------
# e) Explaining and checking the prediction
# ---------------------------------------------------------------------------
def strength_breakdown(matches, last_season, teams):
    """
    WHY each team got its strength: its win % in each of the last 3 seasons,
    and the weighted form that comes out of them (the "strength").
    Example, Mumbai: (3 x 2019 + 2 x 2018 + 1 x 2017) / 6
    """
    win_table = metrics.team_win_percent(matches, by_season=True)
    first_season = last_season - len(FORM_WEIGHTS) + 1
    recent = win_table[(win_table["season"] >= first_season) & (win_table["season"] <= last_season)]
    # pivot: one row per team, one column per season
    grid = recent.pivot(index="team", columns="season", values="win_pct").reset_index()
    grid.columns = ["team"] + ["win_pct_" + str(season) for season in grid.columns[1:]]

    strengths = team_strengths(matches, last_season, teams)
    grid = grid[grid["team"].isin(teams)].copy()
    grid["strength"] = grid["team"].map(strengths)
    return grid.sort_values("strength", ascending=False).reset_index(drop=True)


def verdict(rank):
    """Turn the real winner's position in our list into words."""
    if rank is None:
        return "Not in our list"
    if rank == 1:
        return "Correct"
    if rank <= TOP_N:
        return "Our #" + str(rank) + " pick"
    return "Not in our top " + str(TOP_N) + " (#" + str(rank) + ")"


def check_against_actual(chances, tables, last_season, actual):
    """
    Compare our predictions for a season with what really happened.
    actual_rank = where the real winner was in our ranked list.
    """
    rows = []

    # Champion: our ranking is the title-chance table (best first).
    team_ranking = list(chances["team"])
    champion, details = actual["IPL champion"]
    rank = rank_of(champion, team_ranking)
    rows.append({"prediction": "IPL champion", "our_pick": team_ranking[0],
                 "actual": champion + " (" + details + ")", "actual_rank": rank, "verdict": verdict(rank)})

    # Awards: our ranking is the full form list for that award.
    for award, table_name, name_column, value_column in AWARDS:
        if award not in actual:
            continue   # no official result typed in for this award
        form = weighted_form(tables[table_name], name_column, value_column, last_season)
        player_ranking = list(form[name_column])
        winner, details = actual[award]
        rank = rank_of(winner, player_ranking)
        rows.append({"prediction": award, "our_pick": player_ranking[0],
                     "actual": winner + " (" + details + ")", "actual_rank": rank, "verdict": verdict(rank)})

    # Playoffs: our 4 teams with the best playoff chance vs the real top 4.
    our_top4 = list(chances.sort_values("playoff_pct", ascending=False)["team"].head(4))
    real_top4, details = actual["Playoff teams"]
    correct = [team for team in real_top4 if team in our_top4]
    rows.append({"prediction": "Playoff teams (top 4)", "our_pick": ", ".join(our_top4),
                 "actual": ", ".join(real_top4), "actual_rank": None,
                 "verdict": str(len(correct)) + " of 4 correct (" + ", ".join(correct) + ")"})

    table = pd.DataFrame(rows)
    table["actual_rank"] = table["actual_rank"].astype("Int64")
    return table


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def plot_title_chances(chances, season):
    """Horizontal bars: playoff chance and title chance for every team."""
    long_table = pd.melt(chances, id_vars="team", value_vars=["playoff_pct", "title_pct"],
                         var_name="outcome", value_name="chance")
    long_table["outcome"] = long_table["outcome"].replace(
        {"playoff_pct": "Reach playoffs (top 4)", "title_pct": "Win the title"})

    fig, ax = plt.subplots(figsize=(11, 6))
    sns.barplot(data=long_table, y="team", x="chance", hue="outcome",
                palette={"Reach playoffs (top 4)": analysis.BLUE, "Win the title": analysis.ORANGE},
                ax=ax)
    for bars in ax.containers:
        ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.set_title("Predicted IPL " + str(season) + ": chances from " + format(SIMULATIONS, ",")
                 + " simulated seasons")
    ax.set_xlabel("Chance (%)")
    ax.set_ylabel("Team")
    ax.set_xlim(0, 100)
    ax.legend(title="", loc="lower right")
    analysis.save_chart(fig, "prediction_title_" + str(season) + ".png")


def plot_award_candidates(candidates, season):
    """One small panel per award: the top candidates and their form scores."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    award_names = list(candidates["award"].unique())
    for i in range(len(award_names)):
        ax = axes.flat[i]
        rows = candidates[candidates["award"] == award_names[i]].iloc[::-1]   # best at the top
        colours = [analysis.GREY] * (len(rows) - 1) + [analysis.ORANGE]        # highlight our pick
        ax.barh(rows["player"], rows["form"], color=colours)
        for j in range(len(rows)):
            ax.text(rows.iloc[j]["form"], j, " " + str(rows.iloc[j]["form"]), va="center", fontsize=9)
        ax.set_title(award_names[i], fontsize=12)
        ax.set_xlabel("Form score (weighted " + rows.iloc[0]["measure"] + " per season)")
        ax.set_xlim(0, rows["form"].max() * 1.2)
    fig.suptitle("Predicted IPL " + str(season) + " award winners (orange = our pick)",
                 fontweight="bold")
    analysis.save_chart(fig, "prediction_awards_" + str(season) + ".png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    matplotlib.use("Agg")
    analysis.setup_style()
    pd.set_option("display.width", 140)

    matches, deliveries = metrics.load_processed_data()
    tables = season_tables(matches, deliveries)
    last_season = int(matches["season"].max())     # the last season in the data
    next_season = last_season + 1                   # the season we predict

    # 1. Champion
    teams = sorted(set(matches[matches["season"] == last_season]["team1_franchise"]))
    strengths = team_strengths(matches, last_season, teams)
    chances = title_chances(strengths)
    print("=== Predicted IPL", next_season, "champion (", SIMULATIONS, "simulated seasons) ===")
    print(chances.to_string())

    # 2. Awards
    candidates = award_candidates(tables, last_season)
    print("\n=== Predicted", next_season, "award winners (top", TOP_N, "by form) ===")
    print(candidates.to_string())

    # 3. Backtest
    test = backtest(matches, tables)
    summary = backtest_summary(test, number_of_teams=len(teams))
    print("\n=== Backtest: predicting", FIRST_BACKTEST_SEASON, "-", last_season,
          "using only earlier seasons ===")
    print(test.to_string())
    print()
    print(summary.to_string())

    # 4. Why each team got its strength, and how the prediction compares with what really happened.
    breakdown = strength_breakdown(matches, last_season, teams)
    print("\n=== Why: each team's win % in the last 3 seasons and its strength ===")
    print(breakdown.to_string())
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    breakdown.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_strengths.csv"), index=False)
    if next_season in ACTUAL_RESULTS:
        check = check_against_actual(chances, tables, last_season, ACTUAL_RESULTS[next_season])
        print("\n=== How did the", next_season, "prediction do? (official results) ===")
        print(check.to_string())
        check.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_vs_actual_" + str(next_season) + ".csv"),
                     index=False)

    # 5. Save tables (the dashboard reads these) and charts.
    chances.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_title_chances.csv"), index=False)
    candidates.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_awards.csv"), index=False)
    test.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_backtest.csv"), index=False)
    summary.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_backtest_summary.csv"), index=False)
    print("\nSaving charts ...")
    plot_title_chances(chances, next_season)
    plot_award_candidates(candidates, next_season)
    print("\nDone. Prediction tables and charts are in:", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()
