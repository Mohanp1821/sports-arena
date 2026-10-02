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
    # The team columns are the same on every ball of an innings, so we keep them
    # (when they exist) to allow tables like "runs against each team".
    keys = ["batter", "match_id", "inning", "season", "date"]
    for column in ["batting_team_franchise", "bowling_team_franchise"]:
        if column in df.columns:
            keys.append(column)
    innings = df.groupby(keys).agg(
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
        batting_team_name=("batting_team", "first"),
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


# ===========================================================================
# ANALYST VIEWS (Phase 2): rivalries, matchups, grounds, specialists,
# the Impact Player era and long-term trends.
# Every function returns a pandas table calculated from the ball-by-ball data.
# ===========================================================================

def overs_text(legal_balls):
    """Overs the cricket way: 117 legal balls = 19 overs and 3 balls = "19.3"."""
    return str(int(legal_balls) // 6) + "." + str(int(legal_balls) % 6)


def margin_text(match):
    """How a match was won, in words, e.g. 'won by 140 runs' or 'won by 7 wickets (D/L)'."""
    if match["no_result"]:
        return "No result"
    if match["result"] == "tie":
        return "Tie, won the super over"
    if match["win_by_runs"] > 0:
        text = "won by " + str(match["win_by_runs"]) + " run" + ("s" if match["win_by_runs"] != 1 else "")
    else:
        text = "won by " + str(match["win_by_wickets"]) + " wicket" + ("s" if match["win_by_wickets"] != 1 else "")
    if match["dl_applied"] == 1:
        text += " (D/L)"   # rain-shortened match, Duckworth-Lewis(-Stern) method
    return text


def most_common_team(df, name_column, team_column):
    """For each player, the franchise they played most balls for (used to label tables)."""
    counts = df.groupby([name_column, team_column]).size().reset_index(name="balls")
    counts = counts.sort_values([name_column, "balls", team_column], ascending=[True, False, True])
    return counts.groupby(name_column).head(1).set_index(name_column)[team_column]


# ---------------------------------------------------------------------------
# 1. Rivalry centre: any two franchises
# ---------------------------------------------------------------------------
def rivalry_matches(matches, team_a, team_b):
    """Every match between the two franchises (no-results included), oldest first."""
    pair = ((matches["team1_franchise"] == team_a) & (matches["team2_franchise"] == team_b)) | \
           ((matches["team1_franchise"] == team_b) & (matches["team2_franchise"] == team_a))
    return matches[pair].sort_values(["date", "match_id"]).reset_index(drop=True)


def rivalry_split(games, team_a, team_b, column):
    """
    Wins for each team, split by one column (season, stage or venue).
    played counts every match, including no-results (shown separately).
    """
    rows = []
    for value in sorted(games[column].unique()):
        part = games[games[column] == value]
        rows.append({column: value, "played": len(part),
                     team_a: int((part["winner_franchise"] == team_a).sum()),
                     team_b: int((part["winner_franchise"] == team_b).sum()),
                     "no_result": int(part["no_result"].sum())})
    return pd.DataFrame(rows, columns=[column, "played", team_a, team_b, "no_result"])


def rivalry_record(matches, team_a, team_b):
    """Overall record, then season by season, league vs playoffs, and at each ground."""
    games = rivalry_matches(matches, team_a, team_b)
    overall = {"played": len(games),
               team_a: int((games["winner_franchise"] == team_a).sum()),
               team_b: int((games["winner_franchise"] == team_b).sum()),
               "no_result": int(games["no_result"].sum())}
    by_season = rivalry_split(games, team_a, team_b, "season")
    by_stage = rivalry_split(games, team_a, team_b, "stage")
    by_ground = rivalry_split(games, team_a, team_b, "venue")
    by_ground = by_ground.sort_values(["played", "venue"], ascending=[False, True]).reset_index(drop=True)
    return overall, by_season, by_stage, by_ground


def rivalry_last_meetings(matches, team_a, team_b, n=5):
    """The last n meetings: date, ground, stage, winner (season name) and margin."""
    games = rivalry_matches(matches, team_a, team_b).tail(n).iloc[::-1]
    rows = []
    for i in range(len(games)):
        match = games.iloc[i]
        stage = match["playoff_name"] if match["stage"] == "Playoff" else "League"
        winner = "" if match["no_result"] else match["winner"]
        rows.append({"match_id": int(match["match_id"]), "date": match["date"].strftime("%Y-%m-%d"),
                     "season": int(match["season"]), "venue": match["venue"], "stage": stage,
                     "winner": winner, "margin": margin_text(match)})
    return pd.DataFrame(rows, columns=["match_id", "date", "season", "venue", "stage", "winner", "margin"])


def rivalry_totals(deliveries, matches, team_a, team_b, n=5):
    """
    Highest and lowest team totals in the fixture.
    Lowest totals leave out no-result and rain-shortened matches, and second
    innings that were won (a team that wins a chase stops early on purpose).
    """
    games = rivalry_matches(matches, team_a, team_b)
    balls = deliveries[deliveries["match_id"].isin(games["match_id"])]
    totals = innings_totals(balls, matches)
    totals["score"] = totals["runs"].astype(str) + "/" + totals["wickets"].astype(str)
    totals["overs"] = totals["legal_balls"].apply(overs_text)
    totals["date"] = totals["date"].dt.strftime("%Y-%m-%d")
    columns = ["score", "runs", "overs", "batting_team_name", "season", "venue", "date", "match_id"]

    highest = totals.sort_values(["runs", "date"], ascending=[False, True]).head(n)
    finished = totals[(totals["no_result"] == False) & (totals["rain_affected"] == False)]
    won_chase = (finished["inning"] == 2) & (finished["winner_franchise"] == finished["batting_team"])
    lowest = finished[~won_chase].sort_values(["runs", "date"]).head(n)
    return highest[columns].reset_index(drop=True), lowest[columns].reset_index(drop=True)


def rivalry_top_players(deliveries, matches, team_a, team_b, n=5):
    """Top run-scorers and wicket-takers in matches between the two franchises."""
    games = rivalry_matches(matches, team_a, team_b)
    balls = deliveries[deliveries["match_id"].isin(games["match_id"])]
    batting = batting_stats(balls)
    batting["team"] = batting["batter"].map(most_common_team(balls, "batter", "batting_team_franchise"))
    batting = batting.sort_values(["runs", "batter"], ascending=[False, True]).head(n)
    bowling = bowling_stats(balls)
    bowling["team"] = bowling["bowler"].map(most_common_team(balls, "bowler", "bowling_team_franchise"))
    bowling = bowling.sort_values(["wickets", "economy", "bowler"], ascending=[False, True, True]).head(n)
    bowling["overs"] = bowling["legal_balls"].apply(overs_text)
    return (batting[["batter", "team", "innings", "runs", "balls_faced", "strike_rate", "average"]].reset_index(drop=True),
            bowling[["bowler", "team", "matches", "wickets", "overs", "economy"]].reset_index(drop=True))


# ---------------------------------------------------------------------------
# 2. Batter vs bowler matchups
# ---------------------------------------------------------------------------
def matchup_table(deliveries, min_balls=1):
    """
    One row per batter-bowler pair (super overs removed):
      balls          = balls the batter faced from this bowler (wides not counted)
      runs           = runs off the bat
      dismissals     = times this bowler got this batter out (bowler's wickets only,
                       so a run out does not count against the bowler)
      strike_rate    = runs / balls * 100
      dot_pct        = balls with no run off the bat / balls * 100
      boundary_pct   = fours and sixes / balls * 100
      runs_per_dismissal = runs / dismissals (empty if never out)
    """
    df = add_ball_columns(deliveries)
    df = df[df["is_ball_faced"]].copy()
    df["is_dot"] = df["batsman_runs"] == 0
    df["is_out"] = df["is_bowler_wicket"] & (df["player_dismissed"] == df["batter"])
    table = df.groupby(["batter", "bowler"]).agg(
        balls=("batsman_runs", "size"),
        runs=("batsman_runs", "sum"),
        dismissals=("is_out", "sum"),
        dots=("is_dot", "sum"),
        fours=("is_four", "sum"),
        sixes=("is_six", "sum"),
    ).reset_index()
    table = table[table["balls"] >= min_balls].copy()
    table["strike_rate"] = (table["runs"] / table["balls"] * 100).round(1)
    table["dot_pct"] = (table["dots"] / table["balls"] * 100).round(1)
    table["boundary_pct"] = ((table["fours"] + table["sixes"]) / table["balls"] * 100).round(1)
    table["runs_per_dismissal"] = pd.to_numeric(table["runs"] / table["dismissals"].replace(0, pd.NA)).round(1)
    return table.reset_index(drop=True)


def batter_vs_bowler(deliveries, batter, bowler):
    """The matchup row for one batter against one bowler (empty table if they never met)."""
    balls = deliveries[(deliveries["batter"] == batter) & (deliveries["bowler"] == bowler)]
    return matchup_table(balls)


def batting_vs_teams(deliveries, batter=None):
    """A batter's record against each opposing franchise (all batters if batter is None)."""
    df = deliveries if batter is None else deliveries[deliveries["batter"] == batter]
    table = batting_stats(df, ["batter", "bowling_team_franchise"])
    table = table.rename(columns={"bowling_team_franchise": "opponent"})
    return table[["batter", "opponent", "innings", "runs", "balls_faced", "dismissals", "average",
                  "strike_rate", "sixes"]].reset_index(drop=True)


def bowling_vs_teams(deliveries, bowler=None):
    """A bowler's record against each opposing franchise (all bowlers if bowler is None)."""
    df = deliveries if bowler is None else deliveries[deliveries["bowler"] == bowler]
    table = bowling_stats(df, ["bowler", "batting_team_franchise"])
    table = table.rename(columns={"batting_team_franchise": "opponent"})
    return table[["bowler", "opponent", "matches", "wickets", "overs", "economy", "bowling_avg"]].reset_index(drop=True)


def dismissal_types(deliveries, batter=None):
    """
    How a batter usually gets out: count and % of each dismissal type.
    (Retired hurt is not a dismissal, so it is left out.)
    """
    df = remove_super_overs(deliveries)
    outs = df[df["player_dismissed"].notna() & (df["dismissal_kind"] != "retired hurt")]
    if batter is not None:
        outs = outs[outs["player_dismissed"] == batter]
    table = outs.groupby(["player_dismissed", "dismissal_kind"]).size().reset_index(name="times")
    totals = table.groupby("player_dismissed")["times"].transform("sum")
    table["pct"] = (table["times"] / totals * 100).round(1)
    table = table.rename(columns={"player_dismissed": "batter"})
    return table.sort_values(["batter", "times", "dismissal_kind"], ascending=[True, False, True]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Ground profiles
# ---------------------------------------------------------------------------
def ground_first_innings_by_season(deliveries, matches, venue=None):
    """Average first-innings score at each ground in each season (no rain or no-result matches)."""
    totals = innings_totals(deliveries, matches)
    first = totals[(totals["inning"] == 1) & (totals["no_result"] == False) & (totals["rain_affected"] == False)]
    if venue is not None:
        first = first[first["venue"] == venue]
    table = first.groupby(["venue", "season"]).agg(matches=("match_id", "count"), avg_first_innings=("runs", "mean"))
    table["avg_first_innings"] = table["avg_first_innings"].round(1)
    return table.reset_index()


def ground_summary(deliveries, matches):
    """
    One row per ground:
      matches, average first-innings score, chase win %,
      toss winners who chose to BAT: how often they won (bat_first_toss_win_pct),
      toss winners who chose to FIELD: how often they won (field_first_toss_win_pct),
      highest total.
    """
    totals = innings_totals(deliveries, matches)
    first = totals[(totals["inning"] == 1) & (totals["no_result"] == False) & (totals["rain_affected"] == False)]
    avg_first = first.groupby("venue")["runs"].mean().round(1)
    highest = totals.groupby("venue")["runs"].max()

    played = matches[matches["no_result"] == False].copy()
    bat_first = totals[totals["inning"] == 1][["match_id", "batting_team"]].rename(columns={"batting_team": "bat_first"})
    played = played.merge(bat_first, on="match_id", how="inner")
    played["chase_won"] = played["winner_franchise"] != played["bat_first"]
    played["toss_winner_won"] = played["toss_winner_franchise"] == played["winner_franchise"]

    rows = []
    for venue in sorted(matches["venue"].unique()):
        games = played[played["venue"] == venue]
        chose_bat = games[games["toss_decision"] == "bat"]
        chose_field = games[games["toss_decision"] == "field"]
        rows.append({
            "venue": venue,
            "city": matches[matches["venue"] == venue]["city"].iloc[0],
            "matches": int((matches["venue"] == venue).sum()),
            "first_season": int(matches[matches["venue"] == venue]["season"].min()),
            "last_season": int(matches[matches["venue"] == venue]["season"].max()),
            "avg_first_innings": avg_first.get(venue),
            "chase_win_pct": round(games["chase_won"].mean() * 100, 1) if len(games) else None,
            "toss_bat_matches": len(chose_bat),
            "toss_bat_win_pct": round(chose_bat["toss_winner_won"].mean() * 100, 1) if len(chose_bat) else None,
            "toss_field_matches": len(chose_field),
            "toss_field_win_pct": round(chose_field["toss_winner_won"].mean() * 100, 1) if len(chose_field) else None,
            "highest_total": highest.get(venue),
        })
    return pd.DataFrame(rows)


def ground_phase_run_rate(deliveries, matches):
    """Run rate in each phase at each ground."""
    df = add_ball_columns(deliveries)
    df = df.merge(matches[["match_id", "venue"]], on="match_id", how="left")
    table = df.groupby(["venue", "phase"]).agg(runs=("total_runs", "sum"), legal_balls=("is_legal_ball", "sum")).reset_index()
    table["run_rate"] = (table["runs"] / (table["legal_balls"] / 6)).round(2)
    return table


def ground_highest_totals(deliveries, matches, venue, n=5):
    """The n highest team totals at one ground."""
    totals = innings_totals(deliveries, matches)
    totals = totals[totals["venue"] == venue].sort_values(["runs", "date"], ascending=[False, True]).head(n).copy()
    totals["score"] = totals["runs"].astype(str) + "/" + totals["wickets"].astype(str)
    totals["date"] = totals["date"].dt.strftime("%Y-%m-%d")
    return totals[["score", "batting_team_name", "bowling_team", "season", "date", "match_id"]].reset_index(drop=True)


def team_at_ground(matches, team=None, venue=None):
    """A franchise's record at a ground, season by season (e.g. CSK at Chepauk)."""
    results = team_results(matches)
    if team is not None:
        results = results[results["team"] == team]
    if venue is not None:
        results = results[results["venue"] == venue]
    table = results.groupby(["team", "venue", "season"]).agg(played=("match_id", "count"), wins=("won", "sum")).reset_index()
    table["win_pct"] = (table["wins"] / table["played"] * 100).round(1)
    return table


def home_fortress_index(matches):
    """
    For each current franchise: win % at its home ground(s) and away.
    Fortress index = home win % - away win % (in percentage points).
    A big positive number means the team is much stronger at home.
    """
    table = home_away_performance(matches)
    home = table[table["location"] == "Home"].set_index("team")
    away = table[table["location"] == "Away"].set_index("team")
    rows = []
    for team in CURRENT_FRANCHISES:
        if team not in home.index or team not in away.index:
            continue
        rows.append({"team": team, "home_grounds": " / ".join(HOME_GROUNDS[team]),
                     "home_played": int(home.at[team, "played"]), "home_win_pct": home.at[team, "win_pct"],
                     "away_played": int(away.at[team, "played"]), "away_win_pct": away.at[team, "win_pct"],
                     "fortress_index": round(home.at[team, "win_pct"] - away.at[team, "win_pct"], 1)})
    result = pd.DataFrame(rows)
    return result.sort_values(["fortress_index", "team"], ascending=[False, True]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. Phase and role specialists
# ---------------------------------------------------------------------------
def phase_batting_leaders(deliveries, phase, min_balls=120, season=None, n=10):
    """Most runs in one phase (with strike rate), for batters with at least min_balls there."""
    df = deliveries[deliveries["phase"] == phase]
    if season is not None:
        df = df[df["season"] == season]
    table = batting_stats(df)
    table = table[table["balls_faced"] >= min_balls]
    table = table.sort_values(["runs", "batter"], ascending=[False, True]).head(n)
    return table[["batter", "runs", "balls_faced", "strike_rate", "sixes", "dismissals"]].reset_index(drop=True)


def phase_bowling_leaders(deliveries, phase, min_balls=120, season=None, n=10):
    """Most wickets in one phase (with economy), for bowlers with at least min_balls there."""
    df = deliveries[deliveries["phase"] == phase]
    if season is not None:
        df = df[df["season"] == season]
    table = bowling_stats(df)
    table = table[table["legal_balls"] >= min_balls]
    table = table.sort_values(["wickets", "economy", "bowler"], ascending=[False, True, True]).head(n)
    table["overs"] = table["legal_balls"].apply(overs_text)
    return table[["bowler", "wickets", "overs", "economy", "dot_pct"]].reset_index(drop=True)


def finishers(deliveries, matches, min_death_balls=150, n=10):
    """
    Finishers: who scores fastest at the death AND stays not out in chases.
      death_strike_rate = strike rate in overs 16-20
      chase_innings     = innings batted while chasing (2nd innings)
      not_out_pct       = % of those chase innings the batter was NOT out
      won_not_out       = chases the team won with this batter not out at the end
    """
    death = batting_stats(deliveries[deliveries["phase"] == "Death"])
    death = death[death["balls_faced"] >= min_death_balls][["batter", "runs", "balls_faced", "strike_rate"]]
    death = death.rename(columns={"runs": "death_runs", "balls_faced": "death_balls", "strike_rate": "death_strike_rate"})

    # Every chase innings: who batted (striker or non-striker) and who got out.
    df = remove_super_overs(deliveries)
    chase = df[df["inning"] == 2]
    batted = pd.concat([chase[["match_id", "batter", "batting_team_franchise"]],
                        chase[["match_id", "non_striker", "batting_team_franchise"]].rename(columns={"non_striker": "batter"})])
    batted = batted.drop_duplicates(["match_id", "batter"])
    outs = chase[chase["player_dismissed"].notna() & (chase["dismissal_kind"] != "retired hurt")]
    outs = outs[["match_id", "player_dismissed"]].drop_duplicates().rename(columns={"player_dismissed": "batter"})
    outs["out_marker"] = 1
    batted = batted.merge(outs, on=["match_id", "batter"], how="left")
    batted["out"] = batted["out_marker"] == 1      # empty (no match in outs) means not out
    batted = batted.merge(matches[["match_id", "winner_franchise"]], on="match_id", how="left")
    batted["won_not_out"] = (~batted["out"]) & (batted["winner_franchise"] == batted["batting_team_franchise"])

    chase_table = batted.groupby("batter").agg(chase_innings=("match_id", "count"),
                                               not_outs=("out", lambda column: int((~column).sum())),
                                               won_not_out=("won_not_out", "sum")).reset_index()
    chase_table["not_out_pct"] = (chase_table["not_outs"] / chase_table["chase_innings"] * 100).round(1)
    table = death.merge(chase_table, on="batter", how="left")
    table = table.sort_values(["death_strike_rate", "batter"], ascending=[False, True]).head(n)
    return table.reset_index(drop=True)


def partnerships(deliveries, matches):
    """
    Every partnership, built from the ball data. Two batters are "together" from
    the ball they first appear as striker/non-striker pair until one gets out.
      wicket = which wicket the partnership was for (1st, 2nd ...)
      runs   = all runs scored while they were together (extras included)
      balls  = legal balls bowled while they were together
    """
    df = add_ball_columns(deliveries)
    # Write each pair in alphabetical order, so (A, B) and (B, A) are the same pair.
    first_name = df[["batter", "non_striker"]].min(axis=1)
    second_name = df[["batter", "non_striker"]].max(axis=1)
    df["pair"] = first_name + " & " + second_name
    df["is_wicket"] = df["player_dismissed"].notna() & (df["dismissal_kind"] != "retired hurt")
    # Wickets that fell BEFORE this ball in the innings -> the partnership is for wicket number + 1.
    df["wickets_before"] = df.groupby(["match_id", "inning"])["is_wicket"].cumsum() - df["is_wicket"]
    table = df.groupby(["match_id", "inning", "pair"]).agg(
        wicket=("wickets_before", "min"),
        runs=("total_runs", "sum"),
        balls=("is_legal_ball", "sum"),
        team=("batting_team_franchise", "first"),
        team_name=("batting_team", "first"),
        season=("season", "first"),
    ).reset_index()
    table["wicket"] = table["wicket"] + 1
    table = table.merge(matches[["match_id", "venue", "date"]], on="match_id", how="left")
    table["date"] = table["date"].dt.strftime("%Y-%m-%d")
    return table.sort_values(["runs", "date"], ascending=[False, True]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 5. Impact Player era: 2020-22 (before) vs 2023-26 (with the rule)
# ---------------------------------------------------------------------------
ERA_BEFORE = "2020-22 (before Impact Player)"
ERA_IMPACT = "2023-26 (Impact Player era)"


def era_of(season):
    """Which era a season belongs to (None for seasons before 2020)."""
    if 2020 <= season <= 2022:
        return ERA_BEFORE
    if season >= 2023:
        return ERA_IMPACT
    return None


def impact_era_summary(deliveries, matches):
    """
    Compare the eras: average first-innings score, 200+ totals (and per match),
    and chase success. Rain-shortened and no-result matches are left out.
    """
    totals = innings_totals(deliveries, matches)
    totals = totals[(totals["no_result"] == False) & (totals["rain_affected"] == False)].copy()
    totals["era"] = totals["season"].apply(era_of)
    totals = totals[totals["era"].notna()]
    rows = []
    for era in [ERA_BEFORE, ERA_IMPACT]:
        part = totals[totals["era"] == era]
        first = part[part["inning"] == 1]
        second = part[part["inning"] == 2]
        chase_won = (second["winner_franchise"] == second["batting_team"]).sum()
        rows.append({"era": era, "matches": int(first["match_id"].nunique()),
                     "avg_first_innings": round(first["runs"].mean(), 1),
                     "totals_200_plus": int((part["runs"] >= 200).sum()),
                     "totals_200_plus_per_match": round((part["runs"] >= 200).sum() / first["match_id"].nunique(), 2),
                     "chase_win_pct": round(chase_won / len(second) * 100, 1)})
    return pd.DataFrame(rows)


def impact_era_phase_run_rate(deliveries):
    """Run rate in each phase, in each era."""
    df = add_ball_columns(deliveries)
    df["era"] = df["season"].apply(era_of)
    df = df[df["era"].notna()]
    table = df.groupby(["era", "phase"]).agg(runs=("total_runs", "sum"), legal_balls=("is_legal_ball", "sum")).reset_index()
    table["run_rate"] = (table["runs"] / (table["legal_balls"] / 6)).round(2)
    return table


def impact_player_choices(impact, deliveries, matches):
    """
    What did each team use its Impact Player for, and did it work?
    The role comes from what the player who came IN did in that match:
      "Batter"     = batted but did not bowl
      "Bowler"     = bowled but did not bat
      "Batted and bowled"
      "Did not bat or bowl"
    Returns one row per substitution, with won = did that team win the match.
    """
    df = remove_super_overs(deliveries)
    batted = set(zip(df["match_id"], df["batter"])) | set(zip(df["match_id"], df["non_striker"]))
    bowled = set(zip(df["match_id"], df["bowler"]))
    rows = impact.merge(matches[["match_id", "winner_franchise", "no_result"]], on="match_id", how="left")
    roles = []
    for i in range(len(rows)):
        key = (rows["match_id"].iloc[i], rows["player_in"].iloc[i])
        did_bat = key in batted
        did_bowl = key in bowled
        if did_bat and did_bowl:
            roles.append("Batted and bowled")
        elif did_bat:
            roles.append("Batter")
        elif did_bowl:
            roles.append("Bowler")
        else:
            roles.append("Did not bat or bowl")
    rows["role"] = roles
    rows["won"] = rows["winner_franchise"] == rows["franchise"]
    return rows


def impact_choice_summary(choices, by_team=True):
    """Count of each Impact Player role and the win % with it (no-result matches left out)."""
    played = choices[choices["no_result"] == False]
    group_columns = ["franchise", "role"] if by_team else ["role"]
    table = played.groupby(group_columns).agg(times=("match_id", "count"), wins=("won", "sum")).reset_index()
    table["win_pct"] = (table["wins"] / table["times"] * 100).round(1)
    return table


# ---------------------------------------------------------------------------
# 6. Trends
# ---------------------------------------------------------------------------
def scoring_inflation(deliveries, matches):
    """
    Per season: average first-innings score, sixes per match and run rate
    (no-result and rain-shortened matches are left out).
    """
    totals = innings_totals(deliveries, matches)
    full = totals[(totals["no_result"] == False) & (totals["rain_affected"] == False)]
    table = full.groupby("season").agg(matches=("match_id", "nunique"), sixes=("sixes", "sum"),
                                       runs=("runs", "sum"), legal_balls=("legal_balls", "sum")).reset_index()
    first = full[full["inning"] == 1].groupby("season")["runs"].mean().round(1)
    table["avg_first_innings"] = table["season"].map(first)
    table["sixes_per_match"] = (table["sixes"] / table["matches"]).round(1)
    table["run_rate"] = (table["runs"] / (table["legal_balls"] / 6)).round(2)
    return table[["season", "matches", "avg_first_innings", "sixes_per_match", "run_rate"]]


def points_table(deliveries, matches, season):
    """
    Rebuild the league table of one season from the results:
      2 points for a win (a super-over win counts as a win), 1 for a no-result.
      Net run rate (NRR) = runs scored per over - runs conceded per over.
      A team bowled out counts its full 20 overs in NRR (the official rule).
      Rain-shortened matches use the overs actually bowled (the data does not
      store the revised overs), so NRR can differ slightly from the official table.
    Sorted by points, then NRR. Only league matches count; playoffs are excluded.
    """
    league = matches[(matches["season"] == season) & (matches["stage"] == "League")]
    totals = innings_totals(deliveries[deliveries["match_id"].isin(league["match_id"])], matches)
    totals = totals[totals["inning"] <= 2].copy()
    # All out: count the full 20 overs (120 balls), as the NRR rule says.
    totals["nrr_balls"] = totals["legal_balls"]
    totals.loc[totals["wickets"] >= 10, "nrr_balls"] = 120
    totals = totals[totals["no_result"] == False]

    teams = sorted(set(league["team1_franchise"]) | set(league["team2_franchise"]))
    rows = []
    for team in teams:
        games = league[(league["team1_franchise"] == team) | (league["team2_franchise"] == team)]
        wins = int((games["winner_franchise"] == team).sum())
        no_results = int(games["no_result"].sum())
        losses = len(games) - wins - no_results
        batting = totals[totals["batting_team"] == team]
        bowling = totals[totals["bowling_team"] == team]
        runs_for_rate = batting["runs"].sum() / (batting["nrr_balls"].sum() / 6)
        runs_against_rate = bowling["runs"].sum() / (bowling["nrr_balls"].sum() / 6)
        rows.append({"team": team, "played": len(games), "won": wins, "lost": losses, "no_result": no_results,
                     "points": wins * 2 + no_results, "nrr": round(runs_for_rate - runs_against_rate, 3)})
    table = pd.DataFrame(rows).sort_values(["points", "nrr", "team"], ascending=[False, False, True]).reset_index(drop=True)
    table.insert(0, "position", range(1, len(table) + 1))
    table.insert(1, "season", season)
    return table


def chase_states(deliveries, matches):
    """
    The situation before every ball of every chase (2nd innings), and whether the
    chasing team went on to win. Rain-shortened, tied and no-result matches are
    left out (their target or result is not a normal chase).
      runs_needed  = target - runs scored so far     (target = 1st innings total + 1)
      balls_left   = 120 - legal balls bowled so far
      wickets_left = 10 - wickets fallen so far
    """
    df = add_ball_columns(deliveries)
    df["is_wicket"] = df["player_dismissed"].notna() & (df["dismissal_kind"] != "retired hurt")
    good = matches[(matches["no_result"] == False) & (matches["rain_affected"] == False) & (matches["result"] != "tie")]
    df = df[df["match_id"].isin(good["match_id"])]
    first = df[df["inning"] == 1].groupby("match_id")["total_runs"].sum().rename("first_innings")
    chase = df[df["inning"] == 2].copy()
    chase = chase.merge(first, left_on="match_id", right_index=True)
    # Runs, balls and wickets BEFORE this ball = running total minus this ball.
    group = chase.groupby("match_id")
    chase["runs_before"] = group["total_runs"].cumsum() - chase["total_runs"]
    chase["balls_before"] = group["is_legal_ball"].cumsum() - chase["is_legal_ball"]
    chase["wickets_before"] = group["is_wicket"].cumsum() - chase["is_wicket"]
    chase["runs_needed"] = chase["first_innings"] + 1 - chase["runs_before"]
    chase["balls_left"] = 120 - chase["balls_before"]
    chase["wickets_left"] = 10 - chase["wickets_before"]
    chase = chase.merge(good[["match_id", "winner_franchise"]], on="match_id")
    chase["chase_won"] = (chase["winner_franchise"] == chase["batting_team_franchise"]).astype(int)
    chase = chase[(chase["balls_left"] > 0) & (chase["runs_needed"] > 0)]
    return chase[["match_id", "season", "runs_needed", "balls_left", "wickets_left", "chase_won"]].reset_index(drop=True)


def win_probability_features(runs_needed, balls_left, wickets_left):
    """
    The 4 numbers the chase model looks at. The required run rate (runs needed
    per over) is added because "40 off 24 balls" is much harder than "40 off 60".
    Works on single numbers or on whole pandas columns.
    """
    required_rate = runs_needed * 6 / balls_left
    return pd.DataFrame({"runs_needed": runs_needed, "balls_left": balls_left,
                         "wickets_left": wickets_left, "required_rate": required_rate})


def win_probability_model(states):
    """
    Chase win probability with LOGISTIC REGRESSION (scikit-learn).
    Logistic regression turns a weighted sum of the 4 numbers into a chance
    between 0 and 1:  chance = 1 / (1 + e^-(b0 + b1*runs_needed + b2*balls_left + ...))
    It learns the weights b0..b4 from about 140,000 real chase situations.
    No randomness is used, so the result is the same every run.
    """
    from sklearn.linear_model import LogisticRegression
    features = win_probability_features(states["runs_needed"], states["balls_left"], states["wickets_left"])
    model = LogisticRegression(max_iter=2000)
    model.fit(features, states["chase_won"])
    return model


def win_probability(model, runs_needed, balls_left, wickets_left):
    """Chance (0-100 %) that the chasing team wins from this situation."""
    features = win_probability_features(pd.Series([runs_needed]), pd.Series([balls_left]), pd.Series([wickets_left]))
    return round(model.predict_proba(features)[0][1] * 100, 1)


def season_impact_scores(deliveries):
    """
    A season IMPACT SCORE for every player: runs and wickets, weighted by phase.
    The weights are calculated from each season's own data:
      - a run is worth  (season run rate / run rate in that phase)
        so a run in the Powerplay (where scoring is slower) is worth a bit more
        than a run at the Death (where scoring is easier)
      - a wicket is worth  (average runs per wicket in that phase of the season)
        i.e. the runs a wicket "saves" on average
    impact = batting points + bowling points.
    """
    df = add_ball_columns(deliveries)
    df["is_wicket"] = df["player_dismissed"].notna() & (df["dismissal_kind"] != "retired hurt")

    # Step 1: weights per season and phase.
    phase = df.groupby(["season", "phase"]).agg(runs=("total_runs", "sum"), legal_balls=("is_legal_ball", "sum"),
                                                wickets=("is_wicket", "sum")).reset_index()
    season = df.groupby("season").agg(season_runs=("total_runs", "sum"), season_balls=("is_legal_ball", "sum")).reset_index()
    phase = phase.merge(season, on="season")
    phase["run_weight"] = (phase["season_runs"] / phase["season_balls"]) / (phase["runs"] / phase["legal_balls"])
    phase["wicket_value"] = phase["runs"] / phase["wickets"]
    weights = phase[["season", "phase", "run_weight", "wicket_value"]]

    # Step 2: each player's runs and wickets per season and phase, times the weights.
    batting = df.groupby(["batter", "season", "phase"])["batsman_runs"].sum().reset_index()
    batting = batting.merge(weights, on=["season", "phase"])
    batting["points"] = batting["batsman_runs"] * batting["run_weight"]
    bowling = df.groupby(["bowler", "season", "phase"])["is_bowler_wicket"].sum().reset_index()
    bowling = bowling.merge(weights, on=["season", "phase"])
    bowling["points"] = bowling["is_bowler_wicket"] * bowling["wicket_value"]

    bat = batting.groupby(["batter", "season"]).agg(runs=("batsman_runs", "sum"), batting_points=("points", "sum")).reset_index()
    bowl = bowling.groupby(["bowler", "season"]).agg(wickets=("is_bowler_wicket", "sum"), bowling_points=("points", "sum")).reset_index()
    bat = bat.rename(columns={"batter": "player"})
    bowl = bowl.rename(columns={"bowler": "player"})
    table = bat.merge(bowl, on=["player", "season"], how="outer").fillna(0)
    table["runs"] = table["runs"].astype(int)
    table["wickets"] = table["wickets"].astype(int)
    table["batting_points"] = table["batting_points"].round(1)
    table["bowling_points"] = table["bowling_points"].round(1)
    table["impact"] = (table["batting_points"] + table["bowling_points"]).round(1)

    # The franchise each player played most balls for in that season (batting or bowling).
    appearances = pd.concat([df[["batter", "season", "batting_team_franchise"]].rename(
                                 columns={"batter": "player", "batting_team_franchise": "team"}),
                             df[["bowler", "season", "bowling_team_franchise"]].rename(
                                 columns={"bowler": "player", "bowling_team_franchise": "team"})])
    counts = appearances.groupby(["player", "season", "team"]).size().reset_index(name="balls")
    counts = counts.sort_values(["player", "season", "balls", "team"], ascending=[True, True, False, True])
    main_team = counts.groupby(["player", "season"]).head(1)[["player", "season", "team"]]
    table = table.merge(main_team, on=["player", "season"], how="left")
    return table.sort_values(["season", "impact", "player"], ascending=[True, False, True]).reset_index(drop=True)
