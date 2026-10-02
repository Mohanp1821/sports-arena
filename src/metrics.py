"""
metrics.py
----------
All the CRICKET CALCULATIONS for Sports Arena live in this file.
analysis.py and the test file import these functions.

Each function does ONE job and uses simple pandas steps:
    filter rows -> groupby -> sum/count -> merge -> calculate a ratio

Column names used from data/processed/deliveries_clean.csv.gz:
    match_id, inning, over (1-20), ball, batter, non_striker, bowler,
    batting_team / bowling_team             (the name used THAT season, for display)
    batting_team_franchise / bowling_team_franchise   (today's name, for stats)
    batsman_runs, wide_runs, noball_runs, bye_runs, legbye_runs, total_runs,
    player_dismissed, dismissal_kind, fielder, is_super_over,
    season, date, stage (League / Playoff), phase (Powerplay / Middle / Death)

Team statistics always use the FRANCHISE columns, so Delhi Daredevils (to 2018)
and Delhi Capitals (from 2019) count as one team.
"""

import os
import pandas as pd


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
SCRIPT_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(SCRIPT_FOLDER)
PROCESSED_FOLDER = os.path.join(PROJECT_FOLDER, "data", "processed")


def load_processed_data(folder=PROCESSED_FOLDER):
    """Read the cleaned CSV files made by prepare_data.py (the .gz file is read directly)."""
    matches = pd.read_csv(os.path.join(folder, "matches_clean.csv"), parse_dates=["date"])
    deliveries = pd.read_csv(os.path.join(folder, "deliveries_clean.csv.gz"),
                             parse_dates=["date"], low_memory=False)
    # Empty text cells are read as "missing"; give the text columns an empty string instead.
    for column in ["playoff_name", "player_of_match", "winner", "winner_franchise"]:
        matches[column] = matches[column].fillna("")
    return matches, deliveries


def load_impact_players(folder=PROCESSED_FOLDER):
    """Read the Impact Player substitutions (2023 onwards) made by prepare_data.py."""
    return pd.read_csv(os.path.join(folder, "impact_players_clean.csv"))


def season_range_text(matches):
    """The seasons covered, as text, e.g. "2008-2026" (calculated, never typed in)."""
    return str(matches["season"].min()) + "-" + str(matches["season"].max())


# ---------------------------------------------------------------------------
# Ball-level helper columns
# ---------------------------------------------------------------------------
# Dismissal types that give the BOWLER a wicket.
# NOT included: "run out" (a fielding dismissal), "retired hurt" (not out),
# and "obstructing the field" (the batter's fault, not the bowler's).
BOWLER_WICKET_KINDS = ["bowled", "caught", "caught and bowled", "lbw",
                       "stumped", "hit wicket"]


def remove_super_overs(deliveries):
    """
    Remove super over balls. A super over is a one-over tie-breaker.
    Official IPL player records do NOT include super overs, so we leave
    them out of every player and team statistic.
    """
    return deliveries[deliveries["is_super_over"] == 0].copy()


def phase_of_over(over_number):
    """
    Return the match phase for an over number (overs are numbered 1-20):
        Powerplay = overs 1-6   (only 2 fielders allowed outside the circle)
        Middle    = overs 7-15
        Death     = overs 16-20 (the last 5 overs, when batters attack)
    """
    if over_number <= 6:
        return "Powerplay"
    elif over_number <= 15:
        return "Middle"
    else:
        return "Death"


def add_ball_columns(deliveries):
    """
    Add simple True/False and number columns that the stats need.
    We remove super overs first.
    """
    df = remove_super_overs(deliveries)

    # BALL FACED by the batter: every ball EXCEPT a wide.
    # (A wide is too far from the batter to hit, so it is not counted as
    # faced. A no-ball IS counted as faced because the batter can hit it.)
    df["is_ball_faced"] = df["wide_runs"] == 0

    # LEGAL BALL for the bowler: not a wide AND not a no-ball.
    # Wides and no-balls must be bowled again, so they do not count
    # towards the 6 balls of an over.
    df["is_legal_ball"] = (df["wide_runs"] == 0) & (df["noball_runs"] == 0)

    # RUNS CONCEDED by the bowler = runs off the bat + wides + no-balls.
    # Byes and leg-byes are NOT the bowler's fault (the ball missed the bat),
    # so they are not added to the bowler's figures.
    df["runs_conceded"] = df["batsman_runs"] + df["wide_runs"] + df["noball_runs"]

    # BOWLER WICKET: True if the dismissal type is in our list above.
    df["is_bowler_wicket"] = df["dismissal_kind"].isin(BOWLER_WICKET_KINDS)

    # DOT BALL for the bowler: a legal ball where the bowler gave away 0 runs.
    df["is_dot_ball"] = df["is_legal_ball"] & (df["runs_conceded"] == 0)

    # BOUNDARIES hit by the batter.
    df["is_four"] = df["batsman_runs"] == 4
    df["is_six"] = df["batsman_runs"] == 6

    # Phase of the match (Powerplay / Middle / Death). prepare_data.py already
    # adds it; small hand-made test tables may not have it, so add it if missing.
    if "phase" not in df.columns:
        df["phase"] = df["over"].apply(phase_of_over)
    return df


def find_player(deliveries, name_part):
    """
    List every player name that contains the text you type.
    The dataset uses short names like "V Kohli" or "MS Dhoni", so use this
    before choosing a player.   Example: find_player(deliveries, "kohli")
    """
    batters = deliveries["batter"].unique().tolist()
    bowlers = deliveries["bowler"].unique().tolist()
    all_names = sorted(set(batters + bowlers))

    matches = []
    for name in all_names:
        if name_part.lower() in name.lower():
            matches.append(name)
    return matches


# ---------------------------------------------------------------------------
# Batting
# ---------------------------------------------------------------------------
def batting_innings(deliveries):
    """
    One row per batter per innings: runs, balls faced, match date.
    Used for fifties/hundreds and for the form (rolling average) chart.
    """
    df = add_ball_columns(deliveries)
    innings = df.groupby(["batter", "match_id", "inning", "season", "date"]).agg(
        runs=("batsman_runs", "sum"),
        balls=("is_ball_faced", "sum"),
    ).reset_index()

    # Sort each player's innings in the order they were played.
    innings = innings.sort_values(["batter", "date", "match_id", "inning"])
    return innings.reset_index(drop=True)


def batting_stats(deliveries, group_columns=["batter"]):
    """
    Batting table. By default one row per batter for the whole IPL.
    Use group_columns=["batter", "season"] to get one row per batter per season.

    Formulas (cricket rules):
      runs            = total runs scored off the bat
      balls_faced     = all balls except wides
      innings         = number of innings in which the batter faced a ball
      dismissals      = times the batter was out (retired hurt is NOT out)
      average         = runs / dismissals     (empty if never dismissed)
      strike_rate     = runs / balls_faced * 100  (runs per 100 balls)
      boundary_pct    = runs from 4s and 6s / runs * 100
      fifties         = innings with 50-99 runs;  hundreds = innings with 100+
    """
    df = add_ball_columns(deliveries)

    # Step 1: add up runs, balls, fours, sixes for each group.
    stats = df.groupby(group_columns).agg(
        runs=("batsman_runs", "sum"),
        balls_faced=("is_ball_faced", "sum"),
        fours=("is_four", "sum"),
        sixes=("is_six", "sum"),
    ).reset_index()

    # Step 2: count innings, fifties and hundreds from the innings table.
    innings = batting_innings(deliveries)
    innings["is_fifty"] = (innings["runs"] >= 50) & (innings["runs"] < 100)
    innings["is_hundred"] = innings["runs"] >= 100
    innings_count = innings.groupby(group_columns).agg(
        innings=("match_id", "count"),
        fifties=("is_fifty", "sum"),
        hundreds=("is_hundred", "sum"),
        highest_score=("runs", "max"),
    ).reset_index()
    stats = stats.merge(innings_count, on=group_columns, how="left")

    # Step 3: count dismissals. The person who is OUT is in "player_dismissed"
    # (this can be the non-striker in a run out, so we cannot use "batter").
    outs = df[df["player_dismissed"].notna()]
    outs = outs[outs["dismissal_kind"] != "retired hurt"]
    outs = outs.rename(columns={"player_dismissed": "out_player"})
    out_group = ["out_player"] + group_columns[1:]   # e.g. ["out_player", "season"]
    dismissals = outs.groupby(out_group).size().reset_index(name="dismissals")
    dismissals = dismissals.rename(columns={"out_player": "batter"})
    stats = stats.merge(dismissals, on=group_columns, how="left")
    stats["dismissals"] = stats["dismissals"].fillna(0).astype(int)

    # Step 4: ratios.
    # Average: if a batter was never out we cannot divide by zero, so we
    # leave the average empty (NaN) instead of showing "infinity".
    stats["average"] = stats["runs"] / stats["dismissals"].replace(0, pd.NA)
    stats["average"] = pd.to_numeric(stats["average"]).round(2)
    stats["strike_rate"] = (stats["runs"] / stats["balls_faced"] * 100).round(2)
    boundary_runs = stats["fours"] * 4 + stats["sixes"] * 6
    stats["boundary_pct"] = (boundary_runs / stats["runs"].replace(0, pd.NA) * 100)
    stats["boundary_pct"] = pd.to_numeric(stats["boundary_pct"]).round(2)
    return stats


# ---------------------------------------------------------------------------
# Bowling
# ---------------------------------------------------------------------------
def bowling_stats(deliveries, group_columns=["bowler"]):
    """
    Bowling table. By default one row per bowler for the whole IPL.
    Use group_columns=["bowler", "season"] for one row per bowler per season.

    Formulas (cricket rules):
      legal_balls    = balls that are not wides or no-balls
      overs          = legal_balls / 6
      runs_conceded  = bat runs + wides + no-balls (not byes / leg-byes)
      wickets        = bowled, caught, c&b, lbw, stumped, hit wicket
      economy        = runs_conceded / overs         (runs given per over)
      bowling_avg    = runs_conceded / wickets       (runs given per wicket)
      bowling_sr     = legal_balls / wickets         (balls needed per wicket)
      dot_pct        = dot balls / legal_balls * 100
    """
    df = add_ball_columns(deliveries)
    stats = df.groupby(group_columns).agg(
        legal_balls=("is_legal_ball", "sum"),
        runs_conceded=("runs_conceded", "sum"),
        wickets=("is_bowler_wicket", "sum"),
        dot_balls=("is_dot_ball", "sum"),
        matches=("match_id", "nunique"),
    ).reset_index()

    stats["overs"] = (stats["legal_balls"] / 6).round(1)
    stats["economy"] = (stats["runs_conceded"] / (stats["legal_balls"] / 6)).round(2)

    # Bowlers with 0 wickets would cause a divide-by-zero, so leave empty.
    no_zero_wickets = stats["wickets"].replace(0, pd.NA)
    stats["bowling_avg"] = pd.to_numeric(stats["runs_conceded"] / no_zero_wickets).round(2)
    stats["bowling_sr"] = pd.to_numeric(stats["legal_balls"] / no_zero_wickets).round(2)
    stats["dot_pct"] = (stats["dot_balls"] / stats["legal_balls"] * 100).round(2)
    return stats


def death_over_bowling(deliveries, min_overs=20):
    """Bowling stats for overs 16-20 only, for bowlers with at least min_overs there."""
    df = remove_super_overs(deliveries)
    death_balls = df[df["over"] >= 16]
    stats = bowling_stats(death_balls)
    stats = stats[stats["overs"] >= min_overs]
    return stats.sort_values("economy").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Top performers
# ---------------------------------------------------------------------------
BATTING_METRICS = ["runs", "strike_rate", "average", "sixes", "fours", "boundary_pct"]
BOWLING_METRICS = ["wickets", "economy", "bowling_avg", "bowling_sr", "dot_pct"]
# For these metrics a SMALLER number is better, so we sort from low to high.
LOWER_IS_BETTER = ["economy", "bowling_avg", "bowling_sr"]


def top_performers(deliveries, season, metric, n=10, min_balls=0):
    """
    Return the top n players for one metric.
      season    : a year like 2016, or None for all seasons together
      metric    : e.g. "runs", "strike_rate", "wickets", "economy"
      min_balls : minimum balls faced (batting) or legal balls (bowling),
                  so a player with 2 lucky balls does not top the list
    """
    df = deliveries
    if season is not None:
        df = deliveries[deliveries["season"] == season]

    if metric in BATTING_METRICS:
        table = batting_stats(df)
        table = table[table["balls_faced"] >= min_balls]
        name_column = "batter"
    elif metric in BOWLING_METRICS:
        table = bowling_stats(df)
        table = table[table["legal_balls"] >= min_balls]
        name_column = "bowler"
    else:
        raise ValueError("Unknown metric: " + metric)

    ascending = metric in LOWER_IS_BETTER
    # Sort by the metric; if two players tie, sort by name so the order is fixed.
    table = table.dropna(subset=[metric])
    table = table.sort_values([metric, name_column], ascending=[ascending, True])
    return table.head(n).reset_index(drop=True)


def cap_winners(deliveries):
    """
    Orange Cap = most runs in a season. Purple Cap = most wickets in a season.
    (If two bowlers have the same wickets, the real Purple Cap goes to the
    better economy; we do the same.)
    """
    bat = batting_stats(deliveries, ["batter", "season"])
    bat = bat.sort_values(["season", "runs"], ascending=[True, False])
    orange = bat.groupby("season").head(1)[["season", "batter", "runs"]]

    bowl = bowling_stats(deliveries, ["bowler", "season"])
    bowl = bowl.sort_values(["season", "wickets", "economy"], ascending=[True, False, True])
    purple = bowl.groupby("season").head(1)[["season", "bowler", "wickets", "economy"]]

    caps = orange.merge(purple, on="season")
    caps.columns = ["season", "orange_cap", "runs", "purple_cap", "wickets", "economy"]
    return caps.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------
def team_results(matches):
    """
    Turn each match into TWO rows, one for each team, with won = True/False.
    "team" is the FRANCHISE (today's name), "team_name" the name used that season.
    No-result matches are removed because nobody won or lost them.
    """
    played = matches[matches["no_result"] == False]
    keep = ["match_id", "season", "date", "venue", "city", "stage", "winner_franchise"]

    # Rows from team1's point of view.
    side1 = played[keep].copy()
    side1["team"] = played["team1_franchise"]
    side1["team_name"] = played["team1"]
    side1["opponent"] = played["team2_franchise"]

    # Rows from team2's point of view.
    side2 = played[keep].copy()
    side2["team"] = played["team2_franchise"]
    side2["team_name"] = played["team2"]
    side2["opponent"] = played["team1_franchise"]

    results = pd.concat([side1, side2], ignore_index=True)
    results["won"] = results["team"] == results["winner_franchise"]
    results = results.sort_values(["date", "match_id", "team"]).reset_index(drop=True)
    return results


def team_win_percent(matches, by_season=True):
    """Win % = wins / matches played * 100 (per season, or all-time), per franchise."""
    results = team_results(matches)
    group_columns = ["team", "season"] if by_season else ["team"]
    table = results.groupby(group_columns).agg(
        played=("match_id", "count"),
        wins=("won", "sum"),
    ).reset_index()
    table["win_pct"] = (table["wins"] / table["played"] * 100).round(1)
    return table


def team_run_rate(deliveries):
    """
    Team run rate per season = all runs scored (including extras) / overs faced.
    Overs faced = legal balls / 6.
    """
    df = add_ball_columns(deliveries)
    table = df.groupby(["batting_team_franchise", "season"]).agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
    ).reset_index()
    table = table.rename(columns={"batting_team_franchise": "batting_team"})
    table["run_rate"] = (table["runs"] / (table["legal_balls"] / 6)).round(2)
    return table


def phase_run_rate(deliveries):
    """Run rate for each franchise in each phase (Powerplay / Middle / Death), all seasons."""
    df = add_ball_columns(deliveries)
    table = df.groupby(["batting_team_franchise", "phase"]).agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
    ).reset_index()
    table = table.rename(columns={"batting_team_franchise": "batting_team"})
    table["run_rate"] = (table["runs"] / (table["legal_balls"] / 6)).round(2)
    return table


def innings_totals(deliveries, matches):
    """
    One row per match innings (super overs removed): runs, wickets, legal balls,
    and who batted. Used by many team and ground functions.
    inning 1 = batting first, inning 2 = chasing.
    """
    df = add_ball_columns(deliveries)
    df["is_wicket"] = df["player_dismissed"].notna() & (df["dismissal_kind"] != "retired hurt")
    totals = df.groupby(["match_id", "inning"]).agg(
        batting_team=("batting_team_franchise", "first"),
        bowling_team=("bowling_team_franchise", "first"),
        runs=("total_runs", "sum"),
        wickets=("is_wicket", "sum"),
        legal_balls=("is_legal_ball", "sum"),
        sixes=("is_six", "sum"),
    ).reset_index()
    info = matches[["match_id", "season", "date", "venue", "city", "stage", "no_result",
                    "rain_affected", "winner_franchise"]]
    totals = totals.merge(info, on="match_id", how="left")
    return totals


def first_innings_scores(deliveries, matches):
    """
    Total of the first innings in every match, and the season average.
    Rain-affected (D/L) and no-result matches are removed, because a
    shortened innings would pull the average down unfairly.
    """
    totals = innings_totals(deliveries, matches)
    first = totals[(totals["inning"] == 1) & (totals["no_result"] == False) & (totals["rain_affected"] == False)]
    by_season = first.groupby("season")["runs"].mean().round(1).reset_index()
    by_season = by_season.rename(columns={"runs": "avg_first_innings"})
    return by_season


def bat_first_vs_chase(deliveries, matches):
    """
    For each season: % of matches won by the team batting first vs chasing.
    We find the team that batted first from the ball-by-ball data (inning 1),
    which is more reliable than guessing from the toss decision.
    """
    first = deliveries[deliveries["inning"] == 1]
    bat_first = first.groupby("match_id")["batting_team_franchise"].first().reset_index()
    bat_first = bat_first.rename(columns={"batting_team_franchise": "bat_first_team"})

    played = matches[matches["no_result"] == False]
    played = played.merge(bat_first, on="match_id", how="inner")
    played["bat_first_won"] = played["winner_franchise"] == played["bat_first_team"]

    table = played.groupby("season").agg(
        matches=("match_id", "count"),
        bat_first_wins=("bat_first_won", "sum"),
    ).reset_index()
    table["bat_first_win_pct"] = (table["bat_first_wins"] / table["matches"] * 100).round(1)
    table["chase_win_pct"] = (100 - table["bat_first_win_pct"]).round(1)
    return table


def toss_impact(matches):
    """
    Does winning the toss help? Returns the % of matches won by the toss
    winner, overall and split by what they chose (bat or field).
    """
    played = matches[matches["no_result"] == False].copy()
    played["toss_winner_won"] = played["toss_winner_franchise"] == played["winner_franchise"]
    table = played.groupby("toss_decision").agg(
        matches=("match_id", "count"),
        toss_winner_wins=("toss_winner_won", "sum"),
    ).reset_index()
    table["win_pct"] = (table["toss_winner_wins"] / table["matches"] * 100).round(1)

    overall = played["toss_winner_won"].mean() * 100
    return table, round(overall, 1)


# Home grounds of the 10 current franchises (standard venue names from prepare_data.py).
# A list, because a team can move: Punjab Kings left Mohali for Mullanpur in 2024.
HOME_GROUNDS = {
    "Chennai Super Kings": ["MA Chidambaram Stadium, Chepauk"],
    "Delhi Capitals": ["Arun Jaitley Stadium"],
    "Gujarat Titans": ["Narendra Modi Stadium"],
    "Kolkata Knight Riders": ["Eden Gardens"],
    "Lucknow Super Giants": ["Ekana Cricket Stadium"],
    "Mumbai Indians": ["Wankhede Stadium"],
    "Punjab Kings": ["Punjab Cricket Association IS Bindra Stadium",
                     "Maharaja Yadavindra Singh International Cricket Stadium"],
    "Rajasthan Royals": ["Sawai Mansingh Stadium"],
    "Royal Challengers Bengaluru": ["M Chinnaswamy Stadium"],
    "Sunrisers Hyderabad": ["Rajiv Gandhi International Stadium, Uppal"],
}
CURRENT_FRANCHISES = list(HOME_GROUNDS.keys())


def is_home_match(team, venue):
    """True if the venue is one of the team's home grounds."""
    return venue in HOME_GROUNDS.get(team, [])


def home_away_performance(matches):
    """Win % at the home ground(s) vs everywhere else, for the 10 current franchises."""
    results = team_results(matches)
    results = results[results["team"].isin(CURRENT_FRANCHISES)].copy()

    # Compare each match venue with the team's list of home grounds.
    results["location"] = "Away"
    for i in results.index:
        if is_home_match(results.at[i, "team"], results.at[i, "venue"]):
            results.at[i, "location"] = "Home"

    table = results.groupby(["team", "location"]).agg(
        played=("match_id", "count"),
        wins=("won", "sum"),
    ).reset_index()
    table["win_pct"] = (table["wins"] / table["played"] * 100).round(1)
    return table


def head_to_head(matches, team_a, team_b):
    """
    Head-to-head record: in matches between team_a and team_b only,
    how many did each team win in each season? No-results are left out.
    """
    results = team_results(matches)
    # Keep only rows where team_a played against team_b.
    games = results[(results["team"] == team_a) & (results["opponent"] == team_b)]

    table = games.groupby("season").agg(
        played=("match_id", "count"),
        wins_a=("won", "sum"),
    ).reset_index()
    table["wins_b"] = table["played"] - table["wins_a"]
    table = table.rename(columns={"wins_a": team_a, "wins_b": team_b})
    return table


def season_champions(matches):
    """
    The champion of each season = the winner of the FINAL,
    which is the last match of the season (the latest date).
    Returns the franchise and the name the team used that season.
    """
    finals = matches.sort_values(["date", "match_id"]).groupby("season").tail(1)
    finals = finals[["season", "winner_franchise", "winner"]]
    finals = finals.rename(columns={"winner_franchise": "champion", "winner": "champion_name"})
    return finals.sort_values("season").reset_index(drop=True)


def player_of_match_counts(matches, n=10):
    """Players with the most Player of the Match awards."""
    counts = matches["player_of_match"].value_counts().reset_index()
    counts.columns = ["player", "awards"]
    counts = counts.sort_values(["awards", "player"], ascending=[False, True])
    return counts.head(n).reset_index(drop=True)
