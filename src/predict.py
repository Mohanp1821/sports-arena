"""
predict.py - Step 5: Model A, the explainable prediction of the next IPL season.

Model A in four steps:
  a) strength of a team = its win % over the last 3 seasons, weighted 3, 2, 1
     (60%, 50%, 40%, latest first -> (3*60 + 2*50 + 1*40) / 6 = 53.3)
  b) one match: team A beats team B with chance A / (A + B)
  c) the season is played 10,000 times in the real IPL format (league, then
     Qualifier 1, Eliminator, Qualifier 2, Final); title chance = % of seasons won
  d) awards: the player in a 2027 squad with the best weighted form

The season simulator here is also used by Model B (predict_ml.py).
data/squads_2027.csv says who plays for whom; edit it after trades and the auction.

Run:  python src/predict.py
"""

import math
import os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

import metrics
import analysis

# Settings you can change
FORM_WEIGHTS = [3, 2, 1]   # last season, the one before, the one before that
SIMULATIONS = 10000
RANDOM_SEED = 42           # a fixed seed gives the same results every run
NEW_TEAM_STRENGTH = 50.0   # a team with no history counts as average
TOP_N = 5                  # candidates shown for each award
BACKTEST_SEASONS = list(range(2021, 2027))   # each predicted from earlier seasons only
SQUADS_FILE = os.path.join(metrics.PROJECT_FOLDER, "data", "squads_2027.csv")
OUTPUT_FOLDER = analysis.OUTPUT_FOLDER

# (award, season table, name column, value column)
AWARDS = [
    ("Orange Cap (most runs)", "batting", "batter", "runs"),
    ("Purple Cap (most wickets)", "bowling", "bowler", "wickets"),
    ("Most sixes", "batting", "batter", "sixes"),
    ("Most Player of the Match awards", "potm", "player", "awards"),
]


# ---------------------------------------------------------------------------
# Past results
# ---------------------------------------------------------------------------
def season_tables(matches, deliveries):
    """Per player per season: batting (runs, sixes), bowling (wickets) and Player of the Match awards."""
    batting = metrics.batting_stats(deliveries, ["batter", "season"])
    bowling = metrics.bowling_stats(deliveries, ["bowler", "season"])
    named = matches[matches["player_of_match"] != ""]
    potm = named.groupby(["player_of_match", "season"]).size().reset_index(name="awards")
    potm = potm.rename(columns={"player_of_match": "player"})
    return {"batting": batting, "bowling": bowling, "potm": potm}


def season_teams(matches, season):
    rows = matches[matches["season"] == season]
    return sorted(set(rows["team1_franchise"]) | set(rows["team2_franchise"]))


# ---------------------------------------------------------------------------
# Squads (data/squads_2027.csv)
# ---------------------------------------------------------------------------
def players_used(deliveries, impact, season):
    """Every player a franchise used in a season (batted, bowled, fielded or Impact Player), at his main team."""
    balls = deliveries[deliveries["season"] == season]
    pieces = [balls[["batter", "batting_team_franchise"]].rename(columns={"batter": "player", "batting_team_franchise": "team"}),
              balls[["non_striker", "batting_team_franchise"]].rename(columns={"non_striker": "player", "batting_team_franchise": "team"}),
              balls[["bowler", "bowling_team_franchise"]].rename(columns={"bowler": "player", "bowling_team_franchise": "team"})]
    fielders = []
    for i in balls.index[balls["fielder"].notna()]:
        for name in str(balls.at[i, "fielder"]).split(", "):
            if not name.endswith("(sub)"):          # substitute fielders are not in the team
                fielders.append([name, balls.at[i, "bowling_team_franchise"]])
    pieces.append(pd.DataFrame(fielders, columns=["player", "team"]))
    subs = impact[impact["season"] == season][["player_in", "franchise"]]
    pieces.append(subs.rename(columns={"player_in": "player", "franchise": "team"}))

    counts = pd.concat(pieces, ignore_index=True).groupby(["player", "team"]).size().reset_index(name="appearances")
    counts = counts.sort_values(["player", "appearances", "team"], ascending=[True, False, True])
    squads = counts.groupby("player").head(1)[["team", "player"]]
    return squads.sort_values(["team", "player"]).reset_index(drop=True)


def load_squads(deliveries, impact, last_season):
    """Read the squads file; create it from last season's players the first time (never overwritten after)."""
    if not os.path.exists(SQUADS_FILE):
        players_used(deliveries, impact, last_season).to_csv(SQUADS_FILE, index=False)
        print("Created", SQUADS_FILE, "from the players each franchise used in", last_season)
    squads = pd.read_csv(SQUADS_FILE)
    return squads.sort_values(["team", "player"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# a) Form and strength
# ---------------------------------------------------------------------------
def weighted_form(table, name_column, value_column, last_season):
    """
    Form = sum(weight x value) / sum(weights) over the last 3 seasons (weights 3, 2, 1).
    A missed season is skipped, and only names that played last season are kept.
    """
    first_season = last_season - len(FORM_WEIGHTS) + 1
    recent = table[(table["season"] >= first_season) & (table["season"] <= last_season)].copy()
    season_weight = {last_season - years_back: weight for years_back, weight in enumerate(FORM_WEIGHTS)}
    recent["weight"] = recent["season"].map(season_weight)
    recent["weighted_value"] = recent[value_column] * recent["weight"]

    form = recent.groupby(name_column).agg(
        weighted_total=("weighted_value", "sum"),
        weight_sum=("weight", "sum"),
    ).reset_index()
    form["form"] = (form["weighted_total"] / form["weight_sum"]).round(1)

    active = table[table["season"] == last_season][name_column]
    form = form[form[name_column].isin(active)]
    form = form.sort_values(["form", name_column], ascending=[False, True])
    return form[[name_column, "form"]].reset_index(drop=True)


def team_strengths(matches, last_season, teams):
    """Strength = form win %; a team that did not play last season gets 50."""
    win_table = metrics.team_win_percent(matches[matches["season"] <= last_season], by_season=True)
    form = weighted_form(win_table, "team", "win_pct", last_season)
    form_by_team = dict(zip(form["team"], form["form"]))
    return {team: form_by_team.get(team, NEW_TEAM_STRENGTH) for team in teams}


# ---------------------------------------------------------------------------
# b) The season format
# ---------------------------------------------------------------------------
def seeding_order(matches, last_season, teams):
    """Most titles first, then most finals, then name (like the IPL's group seeding)."""
    finals = matches[(matches["season"] <= last_season) & (matches["playoff_name"] == "Final")]
    titles = {team: int((finals["winner_franchise"] == team).sum()) for team in teams}
    final_count = {team: int(((finals["team1_franchise"] == team) | (finals["team2_franchise"] == team)).sum())
                   for team in teams}
    return sorted(teams, key=lambda team: (-titles[team], -final_count[team], team))


def make_groups(matches, last_season, teams):
    """Two groups of 5 seeded in a snake: seeds 1,4,5,8,9 and 2,3,6,7,10. The k-th teams are "row-mates"."""
    order = seeding_order(matches, last_season, teams)
    group_a = [order[0], order[3], order[4], order[7], order[8]]
    group_b = [order[1], order[2], order[5], order[6], order[9]]
    return group_a, group_b


def league_fixtures(matches, last_season, teams):
    """
    League matches as (home, away):
      8 or 9 teams: everyone plays everyone twice
      10 teams: own group twice, other group once, and the row-mate twice (14 matches each)
    """
    if len(teams) != 10:
        return [(home, away) for home in teams for away in teams if home != away]

    fixtures = []
    group_a, group_b = make_groups(matches, last_season, teams)
    for group in [group_a, group_b]:
        for home in group:
            for away in group:
                if home != away:
                    fixtures.append((home, away))
    for i in range(5):
        for j in range(5):
            if i == j:                                        # row-mates: home and away
                fixtures.append((group_a[i], group_b[j]))
                fixtures.append((group_b[j], group_a[i]))
            elif (i + j) % 2 == 0:                            # single games: alternate the home team
                fixtures.append((group_a[i], group_b[j]))
            else:
                fixtures.append((group_b[j], group_a[i]))
    return fixtures


# ---------------------------------------------------------------------------
# c) Simulating a season (used by Model A and Model B)
# ---------------------------------------------------------------------------
def neutral_chance(chance, team_a, team_b):
    """Chance team_a wins at a neutral ground (playoffs) = average of a at home and a away."""
    return (chance[(team_a, team_b)] + 1 - chance[(team_b, team_a)]) / 2


def play(team_a, team_b, probability_a, rng):
    """One match: team_a wins if a random number between 0 and 1 is below its chance."""
    if rng.random() < probability_a:
        return team_a
    return team_b


def simulate_season(teams, fixtures, chance, rng):
    """One season. chance[(home, away)] = chance the home team wins. Returns (champion, top 4)."""
    points = {team: 0 for team in teams}
    for home, away in fixtures:
        winner = play(home, away, chance[(home, away)], rng)
        points[winner] += 2

    # Sort by points; a tiny random number breaks ties (net run rate does in the real IPL).
    table_score = {}
    for team in teams:
        table_score[team] = points[team] + rng.random() / 10
    table = sorted(teams, key=table_score.get, reverse=True)
    first, second, third, fourth = table[0:4]

    q1_winner = play(first, second, neutral_chance(chance, first, second), rng)
    q1_loser = second if q1_winner == first else first
    eliminator_winner = play(third, fourth, neutral_chance(chance, third, fourth), rng)
    q2_winner = play(q1_loser, eliminator_winner, neutral_chance(chance, q1_loser, eliminator_winner), rng)
    champion = play(q1_winner, q2_winner, neutral_chance(chance, q1_winner, q2_winner), rng)
    return champion, table[0:4]


def title_chances(teams, fixtures, chance, simulations=SIMULATIONS, seed=RANDOM_SEED):
    """Play the season many times: title_pct = % of seasons won, playoff_pct = % in the top 4."""
    rng = np.random.default_rng(seed)
    titles = {team: 0 for team in teams}
    playoffs = {team: 0 for team in teams}
    for run in range(simulations):
        champion, top4 = simulate_season(teams, fixtures, chance, rng)
        titles[champion] += 1
        for team in top4:
            playoffs[team] += 1

    rows = [{"team": team,
             "playoff_pct": round(playoffs[team] / simulations * 100, 1),
             "title_pct": round(titles[team] / simulations * 100, 1)} for team in teams]
    table = pd.DataFrame(rows).sort_values(["title_pct", "playoff_pct", "team"], ascending=[False, False, True])
    return table.reset_index(drop=True)


def model_a_chances(strengths):
    """Model A: team A beats team B with chance A / (A + B), home or away."""
    return {(home, away): strengths[home] / (strengths[home] + strengths[away])
            for home in strengths for away in strengths if home != away}


# ---------------------------------------------------------------------------
# d) Awards
# ---------------------------------------------------------------------------
def award_candidates(tables, last_season, squads=None, n=TOP_N):
    """The top n candidates for every award by form (only squad players, if squads is given)."""
    team_of = {} if squads is None else dict(zip(squads["player"], squads["team"]))
    rows = []
    for award, table_name, name_column, value_column in AWARDS:
        form = weighted_form(tables[table_name], name_column, value_column, last_season)
        if squads is not None:
            form = form[form[name_column].isin(team_of.keys())]
        for rank in range(min(n, len(form))):
            player = form.iloc[rank][name_column]
            rows.append({"award": award, "rank": rank + 1, "player": player,
                         "team": team_of.get(player, ""), "form": form.iloc[rank]["form"], "measure": value_column})
    return pd.DataFrame(rows)


def actual_award_winners(table, name_column, value_column, season):
    """Who really won (a list, because of ties). A wickets tie goes to the better economy, like the Purple Cap."""
    rows = table[table["season"] == season]
    rows = rows[rows[value_column] == rows[value_column].max()]
    if value_column == "wickets":
        rows = rows[rows["economy"] == rows["economy"].min()]
    return sorted(rows[name_column])


def rank_of(name, ranking):
    """Position 1, 2, 3 ... in a ranked list, or None."""
    return ranking.index(name) + 1 if name in ranking else None


def best_rank(winners, ranking):
    """With tied winners, the best position any of them had."""
    ranks = [rank_of(winner, ranking) for winner in winners if rank_of(winner, ranking)]
    return min(ranks) if ranks else None


# ---------------------------------------------------------------------------
# e) Scoring match predictions (both models)
# ---------------------------------------------------------------------------
def season_results(matches, season):
    """The finished matches of a season, with team1_won = 1 or 0."""
    rows = matches[(matches["season"] == season) & (matches["no_result"] == False)]
    table = rows[["match_id", "season", "date", "stage", "venue", "team1_franchise", "team2_franchise",
                  "winner_franchise"]].copy()
    table = table.rename(columns={"team1_franchise": "team1", "team2_franchise": "team2"})
    table["team1_won"] = (table["winner_franchise"] == table["team1"]).astype(int)
    return table.reset_index(drop=True)


def match_scores(probabilities, outcomes):
    """
    accuracy = % of matches the favourite won
    log loss = average of -log(chance given to what happened)   (0 = perfect, 0.693 = coin flip)
    Brier    = average of (chance - outcome)^2                   (0 = perfect, 0.25 = coin flip)
    """
    correct = 0
    log_loss = 0.0
    brier = 0.0
    for p, won in zip(probabilities, outcomes):
        p = min(max(p, 0.001), 0.999)     # log(0) is impossible
        if (p > 0.5 and won == 1) or (p < 0.5 and won == 0):
            correct += 1
        elif p == 0.5:
            correct += 0.5                # a 50-50 call is half right
        chance_of_result = p if won == 1 else 1 - p
        log_loss += -math.log(chance_of_result)
        brier += (p - won) ** 2
    n = len(probabilities)
    return {"matches": n, "accuracy_pct": round(correct / n * 100, 1),
            "log_loss": round(log_loss / n, 4), "brier": round(brier / n, 4)}


def calibration_table(predictions, model_column="model"):
    """When a model says 60%, does the favourite win about 60% of the time? Grouped 50-55%, 55-60%, 60-65%, 65%+."""
    table = predictions.copy()
    table["favourite_chance"] = table["p_team1"].where(table["p_team1"] >= 0.5, 1 - table["p_team1"])
    table["favourite_won"] = table["team1_won"].where(table["p_team1"] >= 0.5, 1 - table["team1_won"])
    edges = [0.5, 0.55, 0.6, 0.65, 1.01]
    labels = ["50-55%", "55-60%", "60-65%", "65%+"]
    table["bin"] = pd.cut(table["favourite_chance"], bins=edges, labels=labels, right=False)
    result = table.groupby([model_column, "bin"], observed=True).agg(
        matches=("match_id", "count"),
        predicted_pct=("favourite_chance", "mean"),
        actual_pct=("favourite_won", "mean"),
    ).reset_index()
    result["predicted_pct"] = (result["predicted_pct"] * 100).round(1)
    result["actual_pct"] = (result["actual_pct"] * 100).round(1)
    return result


# ---------------------------------------------------------------------------
# f) Backtest: each season 2021-2026 predicted from earlier seasons only
# ---------------------------------------------------------------------------
def model_a_backtest(matches, tables):
    """Returns three tables: a chance for every real match, title results, award results."""
    champions = metrics.season_champions(matches)
    predictions = []
    titles = []
    awards = []
    for season in BACKTEST_SEASONS:
        history_end = season - 1
        teams = season_teams(matches, season)
        strengths = team_strengths(matches, history_end, teams)

        for row in season_results(matches, season).to_dict("records"):
            p = strengths[row["team1"]] / (strengths[row["team1"]] + strengths[row["team2"]])
            predictions.append({"model": "Model A", "season": season, "match_id": row["match_id"],
                                "team1": row["team1"], "team2": row["team2"], "p_team1": round(p, 4),
                                "team1_won": row["team1_won"]})

        chances = title_chances(teams, league_fixtures(matches, history_end, teams), model_a_chances(strengths))
        champion = champions[champions["season"] == season]["champion"].iloc[0]
        ranking = list(chances["team"])
        titles.append({"model": "Model A", "season": season, "teams": len(teams), "favourite": ranking[0],
                       "champion": champion, "champion_rank": rank_of(champion, ranking),
                       "champion_title_pct": chances[chances["team"] == champion]["title_pct"].iloc[0]})

        for award, table_name, name_column, value_column in AWARDS:
            ranking = list(weighted_form(tables[table_name], name_column, value_column, history_end)[name_column])
            winners = actual_award_winners(tables[table_name], name_column, value_column, season)
            awards.append({"model": "Model A", "season": season, "award": award, "pick": ranking[0],
                           "actual": " / ".join(winners), "actual_rank": best_rank(winners, ranking)})
    return pd.DataFrame(predictions), pd.DataFrame(titles), pd.DataFrame(awards)


# ---------------------------------------------------------------------------
# g) Explaining the prediction, and charts
# ---------------------------------------------------------------------------
def strength_breakdown(matches, last_season, teams):
    """Each team's win % in each of the last 3 seasons, and the strength made from them."""
    win_table = metrics.team_win_percent(matches, by_season=True)
    first_season = last_season - len(FORM_WEIGHTS) + 1
    recent = win_table[(win_table["season"] >= first_season) & (win_table["season"] <= last_season)]
    grid = recent.pivot(index="team", columns="season", values="win_pct").reset_index()
    grid.columns = ["team"] + ["win_pct_" + str(season) for season in grid.columns[1:]]
    grid = grid[grid["team"].isin(teams)].copy()
    grid["strength"] = grid["team"].map(team_strengths(matches, last_season, teams))
    return grid.sort_values("strength", ascending=False).reset_index(drop=True)


def groups_table(matches, last_season, teams):
    """The two simulated groups and the row-mates (for the dashboard)."""
    if len(teams) != 10:
        return pd.DataFrame()
    group_a, group_b = make_groups(matches, last_season, teams)
    return pd.DataFrame({"seed_row": range(1, 6), "group_a": group_a, "group_b": group_b})


def plot_title_chances(chances, season, model_name, file_name):
    long_table = pd.melt(chances, id_vars="team", value_vars=["playoff_pct", "title_pct"],
                         var_name="outcome", value_name="chance")
    long_table["outcome"] = long_table["outcome"].replace(
        {"playoff_pct": "Reach playoffs (top 4)", "title_pct": "Win the title"})
    fig, ax = plt.subplots(figsize=(11, 6))
    sns.barplot(data=long_table, y="team", x="chance", hue="outcome",
                palette={"Reach playoffs (top 4)": analysis.SLATE, "Win the title": analysis.RED}, ax=ax)
    for bars in ax.containers:
        ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.set_title(model_name + ": IPL " + str(season) + " chances from " + format(SIMULATIONS, ",")
                 + " simulated seasons")
    ax.set_xlabel("Chance (%)")
    ax.set_ylabel("Team")
    ax.set_xlim(0, 100)
    ax.legend(title="", loc="lower right")
    analysis.save_chart(fig, file_name)


def plot_award_candidates(candidates, season):
    """One panel per award, the pick in red."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    award_names = list(candidates["award"].unique())
    for i in range(len(award_names)):
        ax = axes.flat[i]
        rows = candidates[candidates["award"] == award_names[i]].iloc[::-1]   # best at the top
        colours = [analysis.GREY] * (len(rows) - 1) + [analysis.RED]
        ax.barh(rows["player"], rows["form"], color=colours)
        for j in range(len(rows)):
            ax.text(rows.iloc[j]["form"], j, " " + str(rows.iloc[j]["form"]), va="center", fontsize=9)
        ax.set_title(award_names[i], fontsize=12)
        ax.set_xlabel("Form score (weighted " + rows.iloc[0]["measure"] + " per season)")
        ax.set_xlim(0, rows["form"].max() * 1.2)
    fig.suptitle("Model A: predicted IPL " + str(season) + " award winners (red = pick, 2027 squads only)",
                 fontweight="bold")
    analysis.save_chart(fig, "prediction_awards_" + str(season) + ".png")


def main():
    matplotlib.use("Agg")
    analysis.setup_style()
    pd.set_option("display.width", 160)

    matches, deliveries = metrics.load_processed_data()
    impact = metrics.load_impact_players()
    tables = season_tables(matches, deliveries)
    last_season = int(matches["season"].max())
    next_season = last_season + 1
    squads = load_squads(deliveries, impact, last_season)

    # 1. Title chances for the teams in the squads file
    teams = sorted(squads["team"].unique())
    strengths = team_strengths(matches, last_season, teams)
    fixtures = league_fixtures(matches, last_season, teams)
    chances = title_chances(teams, fixtures, model_a_chances(strengths))
    chances.insert(1, "strength", chances["team"].map(strengths))
    print("=== Model A: IPL", next_season, "(", SIMULATIONS, "simulated seasons,", len(fixtures),
          "league matches ) ===")
    print(chances.to_string())

    # 2. Awards (squad players only)
    candidates = award_candidates(tables, last_season, squads)
    print("\n=== Model A:", next_season, "award candidates (top", TOP_N, "by form, 2027 squads) ===")
    print(candidates.to_string())

    # 3. Backtest
    predictions, title_results, award_results = model_a_backtest(matches, tables)
    print("\n=== Model A backtest", BACKTEST_SEASONS[0], "-", BACKTEST_SEASONS[-1], "===")
    print(match_scores(list(predictions["p_team1"]), list(predictions["team1_won"])))
    print(title_results.to_string())

    # 4. Save the tables (the dashboard and predict_ml.py read them) and the charts
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    def save(table, file_name):
        table.to_csv(os.path.join(OUTPUT_FOLDER, file_name), index=False)
    save(strength_breakdown(matches, last_season, teams), "prediction_strengths.csv")
    save(groups_table(matches, last_season, teams), "prediction_groups.csv")
    save(chances, "prediction_title_chances.csv")
    save(candidates, "prediction_awards.csv")
    save(predictions, "backtest_matches_model_a.csv")
    save(title_results, "backtest_titles_model_a.csv")
    save(award_results, "backtest_awards_model_a.csv")
    print("\nSaving charts ...")
    plot_title_chances(chances, next_season, "Model A", "prediction_title_" + str(next_season) + ".png")
    plot_award_candidates(candidates, next_season)
    print("\nDone. Prediction tables and charts are in:", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()
