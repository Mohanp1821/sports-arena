"""
predict_ml.py
-------------
Step 6 of the Sports Arena pipeline: MODEL B (machine learning) for IPL 2027,
and the COMPARISON of Model A and Model B.

MODEL B IN FIVE STEPS

  1. FEATURES. For every match we describe the two teams with numbers that are
     known BEFORE THE SEASON STARTS (nothing from the match itself, and not the
     toss, which nobody knows before the season):
       elo_diff     Elo rating difference. Elo is a chess-style rating: beat a
                    stronger team and you gain more points. Ratings move 1/3 of the
                    way back to 1500 before each season (squads change).
       form_diff    win % in each team's last 10 matches, team A minus team B
       h2h          team A's win % against team B in the last 3 seasons, minus 50
       venue_diff   win % at this ground (smoothed with 5 imaginary 50% games), A minus B
       home         +1 if it is team A's home ground, -1 if team B's, 0 if neutral
       squad_diff   squad strength: the 11 best previous-season impact scores
                    (metrics.season_impact_scores) of the players in each squad
       impact_era   1 from 2023 (Impact Player rule), else 0
  2. TWO MODELS learn from past matches (scikit-learn):
       - logistic regression: a weighted sum of the features turned into a chance
       - gradient boosting: many small decision trees, each fixing the last ones' mistakes
     Each match is used twice (A v B and B v A) so the models treat both teams fairly.
  3. Model B's chance = the AVERAGE of the two models.
  4. The chances go into the SAME season simulator as Model A (src/predict.py):
     10,000 seasons in the real format.
  5. AWARDS: a linear regression predicts each 2027 squad player's runs, wickets,
     sixes and Player of the Match awards from his previous two seasons.

COMPARISON: a walk-forward backtest for 2021-2026. For each season, both models
learn only from earlier seasons, then predict every match and the title. The
scores (accuracy, log loss, Brier, calibration, where the real champion ranked)
are compared with a random guess (50% per match; 1 in 8 or 1 in 10 for the title).

Everything is deterministic: fixed random seeds, so every run gives the same numbers.

Run it from the project folder (after src/predict.py) with:
    python src/predict_ml.py
"""

import os
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import metrics    # our own file: src/metrics.py (cricket formulas)
import analysis   # our own file: src/analysis.py (chart style)
import predict    # our own file: src/predict.py (Model A, squads and the season simulator)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
FEATURES = ["elo_diff", "form_diff", "h2h", "venue_diff", "home", "squad_diff", "impact_era"]
FIRST_TRAINING_SEASON = 2009   # the first season with a previous season to learn from
ELO_START = 1500               # a new team's Elo rating
ELO_K = 20                     # how many points one match can move a rating
ELO_CARRY = 2 / 3              # share of a rating kept between seasons (1/3 goes back to 1500)
FORM_MATCHES = 10              # "recent form" = the last 10 matches
VENUE_PRIOR_GAMES = 5          # imaginary 50% games added to a venue record (smoothing)
SQUAD_TOP = 11                 # how many players count towards squad strength
SEED = predict.RANDOM_SEED
OUTPUT_FOLDER = analysis.OUTPUT_FOLDER


# ---------------------------------------------------------------------------
# 1. Pre-season information for every season
# ---------------------------------------------------------------------------
def elo_at_season_starts(matches):
    """
    Elo ratings of every franchise at the START of every season (and of the
    season after the data ends). Returns {season: {team: rating}}.
    Elo update after a match:  new = old + K * (result - expected),
    expected = 1 / (1 + 10 ** ((other rating - own rating) / 400)).
    """
    played = matches[matches["no_result"] == False].sort_values(["date", "match_id"])
    ratings = {}
    at_start = {}
    seasons = sorted(matches["season"].unique()) + [int(matches["season"].max()) + 1]
    for season in seasons:
        # Before the season: move every rating 1/3 of the way back to 1500.
        for team in ratings:
            ratings[team] = ELO_START + ELO_CARRY * (ratings[team] - ELO_START)
        at_start[season] = dict(ratings)
        for i in range(len(played[played["season"] == season])):
            match = played[played["season"] == season].iloc[i]
            a, b = match["team1_franchise"], match["team2_franchise"]
            rating_a = ratings.get(a, ELO_START)
            rating_b = ratings.get(b, ELO_START)
            expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
            result_a = 1 if match["winner_franchise"] == a else 0
            ratings[a] = rating_a + ELO_K * (result_a - expected_a)
            ratings[b] = rating_b - ELO_K * (result_a - expected_a)
    return at_start


def season_start_info(matches, results, elo, squad_strength, season):
    """
    Everything known before `season` starts:
      elo     : rating of each team
      form    : win % in the last 10 matches
      h2h     : (team, opponent) -> team's win % in the last 3 seasons
      venue   : (team, venue) -> smoothed win %
      squad   : squad strength
    `results` = metrics.team_results(matches) (one row per team per match).
    """
    before = results[results["season"] < season]
    form = {}
    for team, rows in before.groupby("team"):
        form[team] = rows.tail(FORM_MATCHES)["won"].mean() * 100

    h2h = {}
    recent = before[before["season"] >= season - 3]
    for (team, opponent), rows in recent.groupby(["team", "opponent"]):
        h2h[(team, opponent)] = rows["won"].mean() * 100

    venue = {}
    for (team, ground), rows in before.groupby(["team", "venue"]):
        venue[(team, ground)] = (rows["won"].sum() + VENUE_PRIOR_GAMES * 0.5) / (len(rows) + VENUE_PRIOR_GAMES) * 100

    return {"elo": elo.get(season, {}), "form": form, "h2h": h2h, "venue": venue,
            "squad": squad_strength.get(season, {}), "season": season}


def feature_row(info, team_a, team_b, ground):
    """The features for team_a v team_b at a ground, using pre-season information."""
    return {
        "elo_diff": info["elo"].get(team_a, ELO_START) - info["elo"].get(team_b, ELO_START),
        "form_diff": info["form"].get(team_a, 50.0) - info["form"].get(team_b, 50.0),
        "h2h": info["h2h"].get((team_a, team_b), 50.0) - 50.0,
        "venue_diff": info["venue"].get((team_a, ground), 50.0) - info["venue"].get((team_b, ground), 50.0),
        "home": (1 if metrics.is_home_match(team_a, ground) else 0) - (1 if metrics.is_home_match(team_b, ground) else 0),
        "squad_diff": info["squad"].get(team_a, 0.0) - info["squad"].get(team_b, 0.0),
        "impact_era": 1 if info["season"] >= 2023 else 0,
    }


def squad_strengths(deliveries, impact, matches, squads_next):
    """
    Squad strength of every franchise in every season = the sum of the SQUAD_TOP
    best impact scores from the PREVIOUS season among its players.
    Squads: for past seasons, the players each franchise used that season
    (the squad is picked before the season, so this is known in advance, apart
    from injury replacements); for the next season, data/squads_2027.csv.
    Returns {season: {team: strength}}.
    """
    scores = metrics.season_impact_scores(deliveries)
    strengths = {}
    seasons = sorted(matches["season"].unique())
    next_season = int(matches["season"].max()) + 1
    for season in seasons + [next_season]:
        if season == next_season:
            squads = squads_next
        else:
            squads = predict.players_used(deliveries, impact, season)
        previous = scores[scores["season"] == season - 1]
        score_of = dict(zip(previous["player"], previous["impact"]))
        strengths[season] = {}
        for team, members in squads.groupby("team"):
            values = sorted([score_of.get(player, 0.0) for player in members["player"]], reverse=True)
            strengths[season][team] = round(sum(values[:SQUAD_TOP]), 1)
    return strengths


# ---------------------------------------------------------------------------
# 2. Training data and models
# ---------------------------------------------------------------------------
def build_match_rows(matches, infos, seasons):
    """
    One row per match AND per side (A v B and B v A), with the features and
    whether team A won. No-result matches are left out.
    """
    rows = []
    for season in seasons:
        info = infos[season]
        results = predict.season_results(matches, season)
        for i in range(len(results)):
            match = results.iloc[i]
            for team_a, team_b, won in [(match["team1"], match["team2"], match["team1_won"]),
                                        (match["team2"], match["team1"], 1 - match["team1_won"])]:
                row = feature_row(info, team_a, team_b, match["venue"])
                row.update({"season": season, "match_id": match["match_id"], "team_a": team_a,
                            "team_b": team_b, "a_won": won})
                rows.append(row)
    return pd.DataFrame(rows)


def train_models(training_rows):
    """Fit logistic regression and gradient boosting on the training rows."""
    logistic = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    logistic.fit(training_rows[FEATURES], training_rows["a_won"])
    boosting = GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.05, random_state=SEED)
    boosting.fit(training_rows[FEATURES], training_rows["a_won"])
    return {"Logistic regression": logistic, "Gradient boosting": boosting}


def fair_chance(model, info, team_a, team_b, ground):
    """
    Chance that team_a beats team_b at a ground. The model is asked both ways
    round and the answers are averaged, so P(A beats B) + P(B beats A) = 1.
    """
    forward = pd.DataFrame([feature_row(info, team_a, team_b, ground)])[FEATURES]
    backward = pd.DataFrame([feature_row(info, team_b, team_a, ground)])[FEATURES]
    return (model.predict_proba(forward)[0][1] + 1 - model.predict_proba(backward)[0][1]) / 2


def model_b_chance(models, info, team_a, team_b, ground):
    """Model B = the average of logistic regression and gradient boosting."""
    chances = [fair_chance(models[name], info, team_a, team_b, ground) for name in sorted(models)]
    return sum(chances) / len(chances)


def home_ground(matches, team, last_season):
    """
    The ground a team will use at home: of its home grounds (metrics.HOME_GROUNDS),
    the one it played at most in its latest season there (Punjab Kings -> Mullanpur).
    """
    grounds = metrics.HOME_GROUNDS.get(team)
    if not grounds:
        return ""
    games = matches[(matches["season"] <= last_season) & matches["venue"].isin(grounds)
                    & ((matches["team1_franchise"] == team) | (matches["team2_franchise"] == team))]
    if len(games) == 0:
        return grounds[0]
    latest = games[games["season"] == games["season"].max()]
    return latest["venue"].value_counts().sort_index().idxmax()


def season_chance_table(models, info, matches, teams, last_season):
    """chance[(home, away)] for every ordered pair, at the home team's ground (for the simulator)."""
    chance = {}
    for home in teams:
        ground = home_ground(matches, home, last_season)
        for away in teams:
            if home != away:
                chance[(home, away)] = model_b_chance(models, info, home, away, ground)
    return chance


# ---------------------------------------------------------------------------
# 3. Awards: linear regression on the previous seasons
# ---------------------------------------------------------------------------
AWARD_TARGETS = [("Orange Cap (most runs)", "runs"), ("Purple Cap (most wickets)", "wickets"),
                 ("Most sixes", "sixes"), ("Most Player of the Match awards", "awards")]


def player_seasons(tables, deliveries):
    """One row per player per season: runs, sixes, balls, wickets, balls bowled, awards, impact score."""
    batting = tables["batting"][["batter", "season", "runs", "sixes", "balls_faced", "innings"]].rename(columns={"batter": "player"})
    bowling = tables["bowling"][["bowler", "season", "wickets", "legal_balls", "economy"]].rename(columns={"bowler": "player"})
    potm = tables["potm"][["player", "season", "awards"]]
    scores = metrics.season_impact_scores(deliveries)[["player", "season", "impact"]]
    table = batting.merge(bowling, on=["player", "season"], how="outer")
    table = table.merge(potm, on=["player", "season"], how="left").merge(scores, on=["player", "season"], how="left")
    for column in ["runs", "sixes", "balls_faced", "innings", "wickets", "legal_balls", "awards", "impact"]:
        table[column] = table[column].fillna(0)
    return table


def award_feature_table(seasons_table, target_season):
    """
    Features for predicting `target_season`: each player's numbers from the
    season before (prev_...) and two seasons before (prev2_...).
    Only players who played in the season before are included.
    """
    numbers = ["runs", "sixes", "balls_faced", "innings", "wickets", "legal_balls", "awards", "impact"]
    prev = seasons_table[seasons_table["season"] == target_season - 1][["player"] + numbers]
    prev = prev.rename(columns={column: "prev_" + column for column in numbers})
    prev2 = seasons_table[seasons_table["season"] == target_season - 2][["player"] + numbers]
    prev2 = prev2.rename(columns={column: "prev2_" + column for column in numbers})
    table = prev.merge(prev2, on="player", how="left").fillna(0)
    table["target_season"] = target_season
    return table


AWARD_FEATURES = ["prev_runs", "prev_sixes", "prev_balls_faced", "prev_innings", "prev_wickets", "prev_legal_balls",
                  "prev_awards", "prev_impact", "prev2_runs", "prev2_sixes", "prev2_wickets", "prev2_awards"]


def award_predictions(seasons_table, target_season, candidates=None):
    """
    For each award: train a linear regression on every (season before -> season)
    pair BEFORE target_season, then predict target_season for the candidates.
    Returns one row per award per player, best first.
    """
    training = []
    for season in range(FIRST_TRAINING_SEASON + 1, target_season):
        features = award_feature_table(seasons_table, season)
        actual = seasons_table[seasons_table["season"] == season][["player", "runs", "wickets", "sixes", "awards"]]
        training.append(features.merge(actual, on="player", how="inner"))   # players who played both seasons
    training = pd.concat(training, ignore_index=True)

    to_predict = award_feature_table(seasons_table, target_season)
    if candidates is not None:
        to_predict = to_predict[to_predict["player"].isin(candidates)]
    rows = []
    for award, target in AWARD_TARGETS:
        model = LinearRegression()
        model.fit(training[AWARD_FEATURES], training[target])
        predicted = model.predict(to_predict[AWARD_FEATURES])
        part = pd.DataFrame({"award": award, "player": to_predict["player"].values, "predicted": predicted.round(1),
                             "measure": target})
        part = part.sort_values(["predicted", "player"], ascending=[False, True]).reset_index(drop=True)
        part["rank"] = range(1, len(part) + 1)
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# 4. Backtest 2021-2026 and comparison with Model A
# ---------------------------------------------------------------------------
def model_b_backtest(matches, infos, tables, seasons_table):
    """
    Walk-forward: for each backtest season, train on earlier seasons only, then
    predict every match (logistic regression, gradient boosting, Model B) and
    simulate the title; also rank the award winners.
    """
    champions = predict.season_champions(matches)
    predictions = []
    titles = []
    awards = []
    for season in predict.BACKTEST_SEASONS:
        training = build_match_rows(matches, infos, range(FIRST_TRAINING_SEASON, season))
        models = train_models(training)
        info = infos[season]
        results = predict.season_results(matches, season)
        for i in range(len(results)):
            match = results.iloc[i]
            chances = {name: fair_chance(models[name], info, match["team1"], match["team2"], match["venue"]) for name in models}
            chances["Model B"] = sum(chances.values()) / len(models)
            for name in chances:
                predictions.append({"model": name, "season": season, "match_id": match["match_id"],
                                    "team1": match["team1"], "team2": match["team2"],
                                    "p_team1": round(chances[name], 4), "team1_won": match["team1_won"]})

        teams = predict.season_teams(matches, season)
        fixtures = predict.league_fixtures(matches, season - 1, teams)
        chance = season_chance_table(models, info, matches, teams, season - 1)
        table = predict.title_chances(teams, fixtures, chance)
        champion = champions[champions["season"] == season]["champion"].iloc[0]
        ranking = list(table["team"])
        titles.append({"model": "Model B", "season": season, "teams": len(teams), "favourite": ranking[0],
                       "champion": champion, "champion_rank": predict.rank_of(champion, ranking),
                       "champion_title_pct": table[table["team"] == champion]["title_pct"].iloc[0]})

        picks = award_predictions(seasons_table, season)
        for award, table_name, name_column, value_column in predict.AWARDS:
            winners = predict.actual_award_winners(tables[table_name], name_column, value_column, season)
            ranked = list(picks[picks["award"] == award]["player"])
            awards.append({"model": "Model B", "season": season, "award": award, "pick": ranked[0],
                           "actual": " / ".join(winners), "actual_rank": predict.best_rank(winners, ranked)})
    return pd.DataFrame(predictions), pd.DataFrame(titles), pd.DataFrame(awards)


def compare_matches(predictions):
    """Accuracy, log loss and Brier score for every model (overall and per season), plus a random guess."""
    rows = []
    for model in list(dict.fromkeys(predictions["model"])):
        part = predictions[predictions["model"] == model]
        overall = predict.match_scores(list(part["p_team1"]), list(part["team1_won"]))
        overall.update({"model": model, "season": "2021-2026"})
        rows.append(overall)
        for season in sorted(part["season"].unique()):
            one = part[part["season"] == season]
            scores = predict.match_scores(list(one["p_team1"]), list(one["team1_won"]))
            scores.update({"model": model, "season": str(season)})
            rows.append(scores)
    # Random guess: 50% for every match.
    model_a = predictions[predictions["model"] == "Model A"]
    coin = predict.match_scores([0.5] * len(model_a), list(model_a["team1_won"]))
    coin.update({"model": "Random guess (50%)", "season": "2021-2026"})
    rows.append(coin)
    table = pd.DataFrame(rows)
    return table[["model", "season", "matches", "accuracy_pct", "log_loss", "brier"]]


def compare_titles(titles_a, titles_b):
    """Where the real champion ranked, with a random pick as the baseline (1 in 8, then 1 in 10)."""
    table = titles_a.merge(titles_b, on=["season", "teams", "champion"], suffixes=("_a", "_b"))
    table["random_title_pct"] = (100 / table["teams"]).round(1)
    table["random_expected_rank"] = (table["teams"] + 1) / 2
    return table[["season", "teams", "champion", "favourite_a", "champion_rank_a", "champion_title_pct_a",
                  "favourite_b", "champion_rank_b", "champion_title_pct_b", "random_title_pct", "random_expected_rank"]]


# ---------------------------------------------------------------------------
# 5. Charts
# ---------------------------------------------------------------------------
MODEL_COLOURS = {"Model A": analysis.SLATE, "Model B": analysis.RED, "Logistic regression": analysis.GREEN,
                 "Gradient boosting": "#7a5c8a", "Random guess (50%)": analysis.GREY}


def plot_backtest(scores):
    """Three panels: accuracy (higher is better), log loss and Brier score (lower is better)."""
    overall = scores[scores["season"] == "2021-2026"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, column, title in [(axes[0], "accuracy_pct", "Accuracy % (higher is better)"),
                              (axes[1], "log_loss", "Log loss (lower is better)"),
                              (axes[2], "brier", "Brier score (lower is better)")]:
        colours = [MODEL_COLOURS[model] for model in overall["model"]]
        ax.bar(range(len(overall)), overall[column], color=colours)
        for i in range(len(overall)):
            ax.text(i, overall[column].iloc[i], str(overall[column].iloc[i]), ha="center", va="bottom", fontsize=9)
        ax.set_xticks(range(len(overall)))
        ax.set_xticklabels([model.replace(" ", "\n", 1) for model in overall["model"]], fontsize=9)
        ax.set_title(title)
        ax.set_xlabel("Model")
        ax.set_ylabel(column.replace("_", " "))
        ax.set_ylim(overall[column].min() * 0.9, overall[column].max() * 1.06)
    fig.suptitle("Backtest 2021-2026: " + str(overall["matches"].iloc[0]) + " matches predicted using only earlier seasons",
                 fontweight="bold")
    analysis.save_chart(fig, "model_comparison_backtest.png")


def plot_calibration(calibration):
    """Predicted chance vs how often the favourite really won. On the dashed line = perfectly calibrated."""
    fig, ax = plt.subplots(figsize=(8, 7))
    for model in ["Model A", "Model B"]:
        # Groups with fewer than 10 matches are too small to judge, so they are not drawn.
        rows = calibration[(calibration["model"] == model) & (calibration["matches"] >= 10)]
        ax.plot(rows["predicted_pct"], rows["actual_pct"], marker="o", linewidth=2.5, color=MODEL_COLOURS[model], label=model)
        for i in range(len(rows)):
            ax.annotate(str(rows["matches"].iloc[i]), (rows["predicted_pct"].iloc[i], rows["actual_pct"].iloc[i]),
                        xytext=(5, 5), textcoords="offset points", fontsize=8, color=MODEL_COLOURS[model])
    ax.plot([50, 100], [50, 100], linestyle="--", color=analysis.GREY, label="Perfect calibration")
    ax.set_title("Calibration, backtest 2021-2026 (numbers = matches; groups under 10 left out)")
    ax.set_xlabel("Chance the model gave its favourite (%)")
    ax.set_ylabel("How often the favourite won (%)")
    ax.set_xlim(48, 80)
    ax.set_ylim(20, 100)
    ax.legend()
    analysis.save_chart(fig, "model_calibration.png")


def plot_2027_comparison(comparison, season):
    """Title chances for 2027: Model A next to Model B."""
    long_table = pd.melt(comparison, id_vars="team", value_vars=["title_pct_a", "title_pct_b"],
                         var_name="model", value_name="title_pct")
    long_table["model"] = long_table["model"].replace({"title_pct_a": "Model A", "title_pct_b": "Model B"})
    fig, ax = plt.subplots(figsize=(11, 6))
    sns.barplot(data=long_table, y="team", x="title_pct", hue="model", palette=MODEL_COLOURS, ax=ax)
    for bars in ax.containers:
        ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.set_title("IPL " + str(season) + " title chances: Model A vs Model B (" + format(predict.SIMULATIONS, ",")
                 + " simulated seasons each)")
    ax.set_xlabel("Title chance (%)")
    ax.set_ylabel("Team")
    ax.set_xlim(0, long_table["title_pct"].max() * 1.3)
    ax.legend(title="")
    analysis.save_chart(fig, "prediction_" + str(season) + "_models.png")


def logistic_weights(models):
    """The logistic regression weights (on standardised features): sign and size show each feature's effect."""
    logistic = models["Logistic regression"].named_steps["logisticregression"]
    importance = models["Gradient boosting"].feature_importances_
    # "+ 0.0" turns a rounded -0.0 into 0.0, so the file is identical on every computer.
    return pd.DataFrame({"feature": FEATURES, "logistic_weight": logistic.coef_[0].round(3) + 0.0,
                         "boosting_importance": importance.round(3) + 0.0})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    matplotlib.use("Agg")
    analysis.setup_style()
    pd.set_option("display.width", 180)

    matches, deliveries = metrics.load_processed_data()
    impact = metrics.load_impact_players()
    tables = predict.season_tables(matches, deliveries)
    last_season = int(matches["season"].max())
    next_season = last_season + 1
    squads = predict.load_squads(deliveries, impact, last_season)
    teams = sorted(squads["team"].unique())

    print("Building pre-season features for every season ...")
    elo = elo_at_season_starts(matches)
    strengths = squad_strengths(deliveries, impact, matches, squads)
    results = metrics.team_results(matches)
    infos = {}
    for season in range(FIRST_TRAINING_SEASON, next_season + 1):
        infos[season] = season_start_info(matches, results, elo, strengths, season)
    seasons_table = player_seasons(tables, deliveries)

    # 1. Backtest 2021-2026 and comparison with Model A (from src/predict.py's files).
    print("Backtest", predict.BACKTEST_SEASONS[0], "-", predict.BACKTEST_SEASONS[-1], "(walk-forward) ...")
    predictions_b, titles_b, awards_b = model_b_backtest(matches, infos, tables, seasons_table)
    predictions_a = pd.read_csv(os.path.join(OUTPUT_FOLDER, "backtest_matches_model_a.csv"))
    titles_a = pd.read_csv(os.path.join(OUTPUT_FOLDER, "backtest_titles_model_a.csv"))
    awards_a = pd.read_csv(os.path.join(OUTPUT_FOLDER, "backtest_awards_model_a.csv"))
    all_predictions = pd.concat([predictions_a, predictions_b], ignore_index=True)
    scores = compare_matches(all_predictions)
    calibration = predict.calibration_table(all_predictions)
    titles = compare_titles(titles_a, titles_b)
    awards = pd.concat([awards_a, awards_b], ignore_index=True)
    print(scores[scores["season"] == "2021-2026"].to_string())
    print(titles.to_string())

    # 2. Model B for 2027: train on every season, simulate the real format.
    models = train_models(build_match_rows(matches, infos, range(FIRST_TRAINING_SEASON, next_season)))
    chance = season_chance_table(models, infos[next_season], matches, teams, last_season)
    fixtures = predict.league_fixtures(matches, last_season, teams)
    chances_b = predict.title_chances(teams, fixtures, chance)
    chances_b.insert(1, "squad_strength", chances_b["team"].map(strengths[next_season]))
    chances_b.insert(2, "elo", chances_b["team"].map(lambda team: round(infos[next_season]["elo"].get(team, ELO_START), 1)))
    print("\n=== Model B: IPL", next_season, "===")
    print(chances_b.to_string())

    picks = award_predictions(seasons_table, next_season, candidates=set(squads["player"]))
    team_of = dict(zip(squads["player"], squads["team"]))
    picks["team"] = picks["player"].map(team_of)
    picks_b = picks[picks["rank"] <= predict.TOP_N].reset_index(drop=True)
    print(picks_b.to_string())

    chances_a = pd.read_csv(os.path.join(OUTPUT_FOLDER, "prediction_title_chances.csv"))
    comparison = chances_a[["team", "playoff_pct", "title_pct"]].merge(
        chances_b[["team", "playoff_pct", "title_pct"]], on="team", suffixes=("_a", "_b"))
    comparison = comparison.sort_values(["title_pct_b", "team"], ascending=[False, True]).reset_index(drop=True)

    # 3. Save tables and charts.
    predictions_b.to_csv(os.path.join(OUTPUT_FOLDER, "backtest_matches_model_b.csv"), index=False)
    scores.to_csv(os.path.join(OUTPUT_FOLDER, "model_comparison_matches.csv"), index=False)
    calibration.to_csv(os.path.join(OUTPUT_FOLDER, "model_comparison_calibration.csv"), index=False)
    titles.to_csv(os.path.join(OUTPUT_FOLDER, "model_comparison_titles.csv"), index=False)
    awards.to_csv(os.path.join(OUTPUT_FOLDER, "model_comparison_awards.csv"), index=False)
    chances_b.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_model_b_title_chances.csv"), index=False)
    picks_b.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_model_b_awards.csv"), index=False)
    comparison.to_csv(os.path.join(OUTPUT_FOLDER, "prediction_" + str(next_season) + "_comparison.csv"), index=False)
    logistic_weights(models).to_csv(os.path.join(OUTPUT_FOLDER, "model_b_features.csv"), index=False)
    print(logistic_weights(models).to_string())
    print("\nSaving charts ...")
    plot_backtest(scores)
    plot_calibration(calibration)
    plot_2027_comparison(comparison, next_season)
    print("\nDone. Model B and comparison files are in:", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()
