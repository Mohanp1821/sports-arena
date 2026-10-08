"""
predict.py
----------
Step 5 of the Sports Arena pipeline: MODEL A, the explainable prediction
for the next IPL season (2027), plus the SEASON SIMULATOR that Model B
(src/predict_ml.py) also uses.

MODEL A IN FOUR STEPS (no black box):

  a) STRENGTH of each team = its FORM win %: a weighted average of its win %
     in the last 3 seasons, the most recent season counting most (3, 2, 1).
     Example: 60%, 50% and 40% (latest first) -> (3*60 + 2*50 + 1*40) / 6 = 53.3

  b) ONE MATCH: team A beats team B with chance  A / (A + B).
     (strength 60 vs 40 -> team A wins 60% of the time)

  c) THE SEASON is played 10,000 times on the computer (a "Monte Carlo
     simulation") in the REAL IPL FORMAT:
       - 8 or 9 teams: everyone plays everyone twice (home and away)
       - 10 teams (2011, and since 2022): two groups of 5. A team plays the
         teams in its own group twice, the other group once, and ONE team of
         the other group (its "row-mate") a second time: 4x2 + 5 + 1 = 14 games.
         Groups are seeded by titles won (then finals reached), like the IPL does.
       - the top 4 go to the playoffs: Qualifier 1 (1st v 2nd), Eliminator
         (3rd v 4th), Qualifier 2 (loser of Q1 v winner of Eliminator), Final.
     A team's title chance = in how many of the 10,000 seasons it won the final.

  d) AWARDS: the player in a 2027 squad with the best form score
     (runs, wickets, sixes, Player of the Match awards; weights 3, 2, 1).

SQUADS: data/squads_2027.csv lists who plays for whom in 2027. If the file
does not exist, it is created from the players each franchise used in 2026.
You can edit it after trades and the auction; both models read it.

BACKTEST: for 2021-2026, each season is predicted using ONLY earlier seasons,
and compared with what really happened (src/predict_ml.py compares Model A
with Model B on these numbers).

Run it from the project folder with:
    python src/predict.py
"""

import math
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
BACKTEST_SEASONS = list(range(2021, 2027))   # seasons predicted using only earlier seasons
SQUADS_FILE = os.path.join(metrics.PROJECT_FOLDER, "data", "squads_2027.csv")
OUTPUT_FOLDER = analysis.OUTPUT_FOLDER

# The awards we predict:
#   (award name, which season table, name column, value column)
AWARDS = [
    ("Orange Cap (most runs)", "batting", "batter", "runs"),
    ("Purple Cap (most wickets)", "bowling", "bowler", "wickets"),
    ("Most sixes", "batting", "batter", "sixes"),
    ("Most Player of the Match awards", "potm", "player", "awards"),
]


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
    named = matches[matches["player_of_match"] != ""]
    potm = named.groupby(["player_of_match", "season"]).size().reset_index(name="awards")
    potm = potm.rename(columns={"player_of_match": "player"})
    return {"batting": batting, "bowling": bowling, "potm": potm}


def season_teams(matches, season):
    """The franchises that played in one season, sorted by name."""
    rows = matches[matches["season"] == season]
    return sorted(set(rows["team1_franchise"]) | set(rows["team2_franchise"]))


# ---------------------------------------------------------------------------
# Squads (data/squads_2027.csv)
# ---------------------------------------------------------------------------
def players_used(deliveries, impact, season):
    """
    Every player each franchise USED in one season: anyone who batted, bowled,
    fielded (not as a substitute fielder) or came on as an Impact Player.
    A player who appeared for two teams is listed with the one he played most balls for.
    """
    balls = deliveries[deliveries["season"] == season]
    pieces = [balls[["batter", "batting_team_franchise"]].rename(columns={"batter": "player", "batting_team_franchise": "team"}),
              balls[["non_striker", "batting_team_franchise"]].rename(columns={"non_striker": "player", "batting_team_franchise": "team"}),
              balls[["bowler", "bowling_team_franchise"]].rename(columns={"bowler": "player", "bowling_team_franchise": "team"})]
    # Fielders: a run out can name two fielders ("A, B"); substitutes "(sub)" are not in the team.
    fielders = []
    for i in balls.index[balls["fielder"].notna()]:
        for name in str(balls.at[i, "fielder"]).split(", "):
            if not name.endswith("(sub)"):
                fielders.append([name, balls.at[i, "bowling_team_franchise"]])
    pieces.append(pd.DataFrame(fielders, columns=["player", "team"]))
    subs = impact[impact["season"] == season][["player_in", "franchise"]]
    pieces.append(subs.rename(columns={"player_in": "player", "franchise": "team"}))

    used = pd.concat(pieces, ignore_index=True)
    counts = used.groupby(["player", "team"]).size().reset_index(name="appearances")
    counts = counts.sort_values(["player", "appearances", "team"], ascending=[True, False, True])
    squads = counts.groupby("player").head(1)[["team", "player"]]
    return squads.sort_values(["team", "player"]).reset_index(drop=True)


def load_squads(deliveries, impact, last_season):
    """
    Read data/squads_2027.csv. The first time, create it from the players each
    franchise used in the last season. After that the file is never overwritten,
    so your edits (trades, auction buys, releases) are kept.
    """
    if not os.path.exists(SQUADS_FILE):
        squads = players_used(deliveries, impact, last_season)
        squads.to_csv(SQUADS_FILE, index=False)
        print("Created", SQUADS_FILE, "from the players each franchise used in", last_season)
    squads = pd.read_csv(SQUADS_FILE)
    return squads.sort_values(["team", "player"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# a) Form score
# ---------------------------------------------------------------------------
def weighted_form(table, name_column, value_column, last_season):
    """
    Form score = weighted average of value_column over the 3 seasons up to
    last_season (weights 3, 2, 1). A season the player/team missed is skipped,
    so a young player is not punished for seasons before their debut.
    Only names that played in last_season are kept, so retired players drop out.
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
# b) The season format
# ---------------------------------------------------------------------------
def seeding_order(matches, last_season, teams):
    """
    Teams in seeding order: most titles first, then most finals reached,
    then name (so the order is fixed). Only seasons up to last_season count.
    """
    finals = matches[(matches["season"] <= last_season) & (matches["playoff_name"] == "Final")]
    titles = {}
    final_count = {}
    for team in teams:
        titles[team] = int((finals["winner_franchise"] == team).sum())
        final_count[team] = int(((finals["team1_franchise"] == team) | (finals["team2_franchise"] == team)).sum())
    return sorted(teams, key=lambda team: (-titles[team], -final_count[team], team))


def make_groups(matches, last_season, teams):
    """
    Two groups of 5 for a 10-team season, seeded in a "snake":
      seeds 1, 4, 5, 8, 9 -> group A      seeds 2, 3, 6, 7, 10 -> group B
    The k-th team of group A and the k-th team of group B are "row-mates"
    and play each other twice.
    """
    order = seeding_order(matches, last_season, teams)
    group_a = [order[0], order[3], order[4], order[7], order[8]]
    group_b = [order[1], order[2], order[5], order[6], order[9]]
    return group_a, group_b


def league_fixtures(matches, last_season, teams):
    """
    The league matches of a season as a list of (home team, away team).
      8 or 9 teams: everyone twice (home and away)
      10 teams: the group format (14 matches each, see make_groups)
    """
    fixtures = []
    if len(teams) != 10:
        for home in teams:
            for away in teams:
                if home != away:
                    fixtures.append((home, away))
        return fixtures

    group_a, group_b = make_groups(matches, last_season, teams)
    # Same group: twice, once at each ground.
    for group in [group_a, group_b]:
        for home in group:
            for away in group:
                if home != away:
                    fixtures.append((home, away))
    # Other group: once each, plus the row-mate a second time.
    for i in range(5):
        for j in range(5):
            if i == j:
                fixtures.append((group_a[i], group_b[j]))     # row-mates: home and away
                fixtures.append((group_b[j], group_a[i]))
            elif (i + j) % 2 == 0:                            # single games: alternate the home team
                fixtures.append((group_a[i], group_b[j]))
            else:
                fixtures.append((group_b[j], group_a[i]))
    return fixtures


# ---------------------------------------------------------------------------
# c) Simulating a season (used by Model A AND Model B)
# ---------------------------------------------------------------------------
def neutral_chance(chance, team_a, team_b):
    """
    Chance that team_a beats team_b at a neutral ground (playoffs):
    the average of "a at home" and "a away".
    chance[(home, away)] = probability that the HOME team wins.
    """
    return (chance[(team_a, team_b)] + 1 - chance[(team_b, team_a)]) / 2


def play(team_a, team_b, probability_a, rng):
    """Play one match: team_a wins if a random number (0 to 1) is below its chance."""
    if rng.random() < probability_a:     # rng.random() = a random number between 0 and 1
        return team_a
    return team_b


def simulate_season(teams, fixtures, chance, rng):
    """Play one full season. Returns (champion, the 4 playoff teams)."""
    points = {}
    for team in teams:
        points[team] = 0

    # League stage: 2 points for a win.
    for home, away in fixtures:
        winner = play(home, away, chance[(home, away)], rng)
        points[winner] += 2

    # Points table: sort by points. A tiny random number breaks ties
    # (in the real IPL, net run rate breaks ties).
    table_score = {}
    for team in teams:
        table_score[team] = points[team] + rng.random() / 10
    table = sorted(teams, key=table_score.get, reverse=True)
    first, second, third, fourth = table[0:4]

    # Playoffs at neutral grounds (the IPL format used since 2011).
    q1_winner = play(first, second, neutral_chance(chance, first, second), rng)
    q1_loser = second if q1_winner == first else first
    eliminator_winner = play(third, fourth, neutral_chance(chance, third, fourth), rng)
    q2_winner = play(q1_loser, eliminator_winner, neutral_chance(chance, q1_loser, eliminator_winner), rng)
    champion = play(q1_winner, q2_winner, neutral_chance(chance, q1_winner, q2_winner), rng)
    return champion, table[0:4]


def title_chances(teams, fixtures, chance, simulations=SIMULATIONS, seed=RANDOM_SEED):
    """
    Play the season many times and count:
      title_pct   = % of seasons the team won the final
      playoff_pct = % of seasons the team finished in the top 4
    """
    rng = np.random.default_rng(seed)   # random number generator with a fixed seed
    titles = {}
    playoffs = {}
    for team in teams:
        titles[team] = 0
        playoffs[team] = 0

    for run in range(simulations):
        champion, top4 = simulate_season(teams, fixtures, chance, rng)
        titles[champion] += 1
        for team in top4:
            playoffs[team] += 1

    rows = []
    for team in teams:
        rows.append({"team": team,
                     "playoff_pct": round(playoffs[team] / simulations * 100, 1),
                     "title_pct": round(titles[team] / simulations * 100, 1)})
    table = pd.DataFrame(rows)
    table = table.sort_values(["title_pct", "playoff_pct", "team"], ascending=[False, False, True])
    return table.reset_index(drop=True)


def model_a_chances(strengths):
    """Model A's match chances: team A beats team B with chance A / (A + B), home or away."""
    chance = {}
    for home in strengths:
        for away in strengths:
            if home != away:
                chance[(home, away)] = strengths[home] / (strengths[home] + strengths[away])
    return chance


# ---------------------------------------------------------------------------
# d) Award predictions
# ---------------------------------------------------------------------------
def award_candidates(tables, last_season, squads=None, n=TOP_N):
    """
    The top n candidates for every award, by form score.
    If squads is given, only players in a squad are kept, with their team.
    """
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
    """
    Who really won an award in a season (a list, because players can tie).
    For wickets, a tie goes to the better economy, like the real Purple Cap.
    """
    rows = table[table["season"] == season]
    rows = rows[rows[value_column] == rows[value_column].max()]
    if value_column == "wickets":
        rows = rows[rows["economy"] == rows["economy"].min()]
    return sorted(rows[name_column])


def rank_of(name, ranking):
    """Position (1, 2, 3 ...) of a name in a ranked list, or None if missing."""
    if name in ranking:
        return ranking.index(name) + 1
    return None


def best_rank(winners, ranking):
    """If players tied for an award, the best position any of them had in our list."""
    ranks = [rank_of(winner, ranking) for winner in winners if rank_of(winner, ranking)]
    return min(ranks) if ranks else None


# ---------------------------------------------------------------------------
# e) Scoring match predictions (used for BOTH models in the backtest)
# ---------------------------------------------------------------------------
def season_results(matches, season):
    """The finished matches of a season (no-results left out): who played, who won, where."""
    rows = matches[(matches["season"] == season) & (matches["no_result"] == False)]
    table = rows[["match_id", "season", "date", "stage", "venue", "team1_franchise", "team2_franchise",
                  "winner_franchise"]].copy()
    table = table.rename(columns={"team1_franchise": "team1", "team2_franchise": "team2"})
    table["team1_won"] = (table["winner_franchise"] == table["team1"]).astype(int)
    return table.reset_index(drop=True)


def match_scores(probabilities, outcomes):
    """
    How good were the match predictions? (probabilities = chance team 1 wins, outcomes = 1/0)
      accuracy  = % of matches where the team we gave more than 50% won
      log loss  = average of -log(chance we gave to what really happened);
                  0 is perfect, 0.693 is a coin flip, being confidently wrong costs a lot
      Brier     = average of (chance - outcome)^2;  0 is perfect, 0.25 is a coin flip
    """
    correct = 0
    log_loss = 0.0
    brier = 0.0
    for p, won in zip(probabilities, outcomes):
        p = min(max(p, 0.001), 0.999)     # keep away from exactly 0 or 1 (log of 0 is impossible)
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
    """
    CALIBRATION: when a model says "70%", does that team win about 70% of the time?
    Each match is counted from the side of the team the model favoured, then
    grouped by that chance: 50-55%, 55-60%, 60-65%, 65%+ (pre-season models
    rarely go higher, so narrow groups show more detail).
    """
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
# f) Model A backtest (2021-2026, using only earlier seasons each time)
# ---------------------------------------------------------------------------
def model_a_backtest(matches, tables):
    """
    For each backtest season S, using only seasons before S:
      - a chance for every real match:  A / (A + B)
      - title chances from 10,000 simulated seasons in S's real format
      - where the real award winners were in the form ranking
    Returns three tables: match predictions, title results, award results.
    """
    champions = season_champions(matches)
    predictions = []
    titles = []
    awards = []
    for season in BACKTEST_SEASONS:
        history_end = season - 1
        teams = season_teams(matches, season)
        strengths = team_strengths(matches, history_end, teams)

        results = season_results(matches, season)
        for i in range(len(results)):
            row = results.iloc[i]
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
            form = weighted_form(tables[table_name], name_column, value_column, history_end)
            ranking = list(form[name_column])
            winners = actual_award_winners(tables[table_name], name_column, value_column, season)
            awards.append({"model": "Model A", "season": season, "award": award, "pick": ranking[0],
                           "actual": " / ".join(winners), "actual_rank": best_rank(winners, ranking)})
    return pd.DataFrame(predictions), pd.DataFrame(titles), pd.DataFrame(awards)


# ---------------------------------------------------------------------------
# g) Explaining the prediction
# ---------------------------------------------------------------------------
def strength_breakdown(matches, last_season, teams):
    """
    WHY each team got its strength: its win % in each of the last 3 seasons,
    and the weighted form that comes out of them (the "strength").
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


def groups_table(matches, last_season, teams):
    """The two simulated groups and the row-mates, for the dashboard."""
    if len(teams) != 10:
        return pd.DataFrame()
    group_a, group_b = make_groups(matches, last_season, teams)
    return pd.DataFrame({"seed_row": range(1, 6), "group_a": group_a, "group_b": group_b})


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def plot_title_chances(chances, season, model_name, file_name):
    """Horizontal bars: playoff chance and title chance for every team."""
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
    """One small panel per award: the top candidates and their form scores."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    award_names = list(candidates["award"].unique())
    for i in range(len(award_names)):
        ax = axes.flat[i]
        rows = candidates[candidates["award"] == award_names[i]].iloc[::-1]   # best at the top
        colours = [analysis.GREY] * (len(rows) - 1) + [analysis.RED]        # highlight our pick
        ax.barh(rows["player"], rows["form"], color=colours)
        for j in range(len(rows)):
            ax.text(rows.iloc[j]["form"], j, " " + str(rows.iloc[j]["form"]), va="center", fontsize=9)
        ax.set_title(award_names[i], fontsize=12)
        ax.set_xlabel("Form score (weighted " + rows.iloc[0]["measure"] + " per season)")
        ax.set_xlim(0, rows["form"].max() * 1.2)
    fig.suptitle("Model A: predicted IPL " + str(season) + " award winners (red = pick, 2027 squads only)",
                 fontweight="bold")
    analysis.save_chart(fig, "prediction_awards_" + str(season) + ".png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    matplotlib.use("Agg")
    analysis.setup_style()
    pd.set_option("display.width", 160)

    matches, deliveries = metrics.load_processed_data()
    impact = metrics.load_impact_players()
    tables = season_tables(matches, deliveries)
    last_season = int(matches["season"].max())     # the last season in the data
    next_season = last_season + 1                   # the season we predict
    squads = load_squads(deliveries, impact, last_season)

    # 1. Champion: the 2027 teams are the teams in the squads file.
    teams = sorted(squads["team"].unique())
    strengths = team_strengths(matches, last_season, teams)
    fixtures = league_fixtures(matches, last_season, teams)
    chances = title_chances(teams, fixtures, model_a_chances(strengths))
    chances.insert(1, "strength", chances["team"].map(strengths))
    print("=== Model A: IPL", next_season, "(", SIMULATIONS, "simulated seasons,", len(fixtures),
          "league matches ) ===")
    print(chances.to_string())

    # 2. Awards (only players in a 2027 squad)
    candidates = award_candidates(tables, last_season, squads)
    print("\n=== Model A:", next_season, "award candidates (top", TOP_N, "by form, 2027 squads) ===")
    print(candidates.to_string())

    # 3. Backtest 2021-2026
    predictions, title_results, award_results = model_a_backtest(matches, tables)
    print("\n=== Model A backtest", BACKTEST_SEASONS[0], "-", BACKTEST_SEASONS[-1], "===")
    print(match_scores(list(predictions["p_team1"]), list(predictions["team1_won"])))
    print(title_results.to_string())

    # 4. Save tables (the dashboard and predict_ml.py read these) and charts.
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    strength_breakdown(matches, last_season, teams).to_csv(os.path.join(OUTPUT_FOLDER, "prediction_strengths.csv"), index=False)
    groups_table(matches, last_season, teams).to_csv(os.path.join(OUTPUT_FOLDER, "prediction_groups.csv"), index=False)
    chances.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_title_chances.csv"), index=False)
    candidates.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_awards.csv"), index=False)
    predictions.to_csv(os.path.join(OUTPUT_FOLDER, "backtest_matches_model_a.csv"), index=False)
    title_results.to_csv(os.path.join(OUTPUT_FOLDER, "backtest_titles_model_a.csv"), index=False)
    award_results.to_csv(os.path.join(OUTPUT_FOLDER, "backtest_awards_model_a.csv"), index=False)
    print("\nSaving charts ...")
    plot_title_chances(chances, next_season, "Model A", "prediction_title_" + str(next_season) + ".png")
    plot_award_candidates(candidates, next_season)
    print("\nDone. Prediction tables and charts are in:", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()
