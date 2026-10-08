"""
metrics.py - every cricket calculation in the project.

Each function does one job with simple pandas steps:
    filter rows -> groupby -> sum / count -> merge -> work out a ratio

Team statistics use the *_franchise columns, so Delhi Daredevils (to 2018)
and Delhi Capitals (from 2019) count as one team.
"""

import os
import pandas as pd

PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_FOLDER = os.path.join(PROJECT_FOLDER, "src")
PROCESSED_FOLDER = os.path.join(PROJECT_FOLDER, "data", "processed")


# ---------------------------------------------------------------------------
# Loading and small helpers
# ---------------------------------------------------------------------------
def load_processed_data(folder=PROCESSED_FOLDER):
    """The cleaned files made by prepare_data.py."""
    matches = pd.read_csv(os.path.join(folder, "matches_clean.csv"), parse_dates=["date"])
    deliveries = pd.read_csv(os.path.join(folder, "deliveries_clean.csv.gz"), parse_dates=["date"], low_memory=False)
    for column in ["playoff_name", "player_of_match", "winner", "winner_franchise"]:
        matches[column] = matches[column].fillna("")     # empty text, not "missing"
    return matches, deliveries


def load_impact_players(folder=PROCESSED_FOLDER):
    return pd.read_csv(os.path.join(folder, "impact_players_clean.csv"))


def season_range_text(matches):
    """e.g. "2008-2026", worked out from the data."""
    return str(matches["season"].min()) + "-" + str(matches["season"].max())


def per_over(runs, legal_balls):
    """Run rate (or economy) = runs / overs, where overs = legal balls / 6."""
    return runs / (legal_balls / 6)


def percent(part, whole):
    return part / whole * 100


def full_matches(table):
    """Leave out no-result and rain-shortened matches (their scores are not normal 20-over scores)."""
    return table[(table["no_result"] == False) & (table["rain_affected"] == False)]


def overs_text(legal_balls):
    """Overs the cricket way: 117 legal balls = 19 overs and 3 balls = "19.3"."""
    return str(int(legal_balls) // 6) + "." + str(int(legal_balls) % 6)


# ---------------------------------------------------------------------------
# Cricket rules for every ball
# ---------------------------------------------------------------------------
# Dismissals that count as the BOWLER's wicket (not run out, retired hurt or obstructing the field).
BOWLER_WICKET_KINDS = ["bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"]


def remove_super_overs(deliveries):
    """Super overs (one-over tie-breakers) are not part of official player records."""
    return deliveries[deliveries["is_super_over"] == 0].copy()


def phase_of_over(over_number):
    """Powerplay = overs 1-6, Middle = 7-15, Death = 16-20."""
    if over_number <= 6:
        return "Powerplay"
    elif over_number <= 15:
        return "Middle"
    else:
        return "Death"


def add_ball_columns(deliveries):
    """True/False columns for the cricket rules (super overs removed first)."""
    df = remove_super_overs(deliveries)
    df["is_ball_faced"] = df["wide_runs"] == 0                                # a wide is out of the batter's reach
    df["is_legal_ball"] = (df["wide_runs"] == 0) & (df["noball_runs"] == 0)   # counts towards the 6 balls of an over
    df["runs_conceded"] = df["batsman_runs"] + df["wide_runs"] + df["noball_runs"]   # byes are not the bowler's fault
    df["is_bowler_wicket"] = df["dismissal_kind"].isin(BOWLER_WICKET_KINDS)
    df["is_wicket"] = df["player_dismissed"].notna() & (df["dismissal_kind"] != "retired hurt")   # any batter out
    df["is_dot_ball"] = df["is_legal_ball"] & (df["runs_conceded"] == 0)
    df["is_four"] = df["batsman_runs"] == 4
    df["is_six"] = df["batsman_runs"] == 6
    if "phase" not in df.columns:            # small hand-made test tables have no phase column
        df["phase"] = df["over"].apply(phase_of_over)
    return df


def find_player(deliveries, name_part):
    """Every player whose name contains the text, e.g. find_player(deliveries, "kohli")."""
    all_names = sorted(set(deliveries["batter"]) | set(deliveries["bowler"]))
    return [name for name in all_names if name_part.lower() in name.lower()]


# ---------------------------------------------------------------------------
# Batting and bowling
# ---------------------------------------------------------------------------
def batting_innings(deliveries):
    """One row per batter per innings (runs and balls), in the order they were played."""
    df = add_ball_columns(deliveries)
    keys = ["batter", "match_id", "inning", "season", "date"]
    for column in ["batting_team_franchise", "bowling_team_franchise", "venue"]:
        if column in df.columns:
            keys.append(column)
    innings = df.groupby(keys).agg(runs=("batsman_runs", "sum"), balls=("is_ball_faced", "sum")).reset_index()
    innings = innings.sort_values(["batter", "date", "match_id", "inning"])
    return innings.reset_index(drop=True)


def batting_stats(deliveries, group_columns=["batter"]):
    """
    One row per batter (or per batter and season, etc.):
      average     = runs / dismissals        (empty if never out)
      strike_rate = runs / balls faced * 100
    """
    df = add_ball_columns(deliveries)
    stats = df.groupby(group_columns).agg(
        runs=("batsman_runs", "sum"),
        balls_faced=("is_ball_faced", "sum"),
        fours=("is_four", "sum"),
        sixes=("is_six", "sum"),
    ).reset_index()

    # Innings, fifties, hundreds and highest score come from the innings table.
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

    # Dismissals: the player who is out is "player_dismissed" (in a run out it can be the non-striker).
    outs = df[df["is_wicket"]].rename(columns={"player_dismissed": "out_player"})
    out_group = ["out_player"] + group_columns[1:]
    dismissals = outs.groupby(out_group).size().reset_index(name="dismissals")
    dismissals = dismissals.rename(columns={"out_player": "batter"})
    stats = stats.merge(dismissals, on=group_columns, how="left")
    stats["dismissals"] = stats["dismissals"].fillna(0).astype(int)

    stats["average"] = pd.to_numeric(stats["runs"] / stats["dismissals"].replace(0, pd.NA)).round(2)
    stats["strike_rate"] = percent(stats["runs"], stats["balls_faced"]).round(2)
    boundary_runs = stats["fours"] * 4 + stats["sixes"] * 6
    stats["boundary_pct"] = pd.to_numeric(percent(boundary_runs, stats["runs"].replace(0, pd.NA))).round(2)
    return stats


def bowling_stats(deliveries, group_columns=["bowler"]):
    """
    One row per bowler (or per bowler and season, etc.):
      economy     = runs conceded / overs
      bowling_avg = runs conceded / wickets,  bowling_sr = legal balls / wickets
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
    stats["economy"] = per_over(stats["runs_conceded"], stats["legal_balls"]).round(2)
    no_zero_wickets = stats["wickets"].replace(0, pd.NA)        # no wickets: leave the ratio empty
    stats["bowling_avg"] = pd.to_numeric(stats["runs_conceded"] / no_zero_wickets).round(2)
    stats["bowling_sr"] = pd.to_numeric(stats["legal_balls"] / no_zero_wickets).round(2)
    stats["dot_pct"] = percent(stats["dot_balls"], stats["legal_balls"]).round(2)
    return stats


def death_over_bowling(deliveries, min_overs=20):
    """Bowling in overs 16-20, best economy first."""
    death_balls = remove_super_overs(deliveries)
    death_balls = death_balls[death_balls["over"] >= 16]
    stats = bowling_stats(death_balls)
    stats = stats[stats["overs"] >= min_overs]
    return stats.sort_values("economy").reset_index(drop=True)


BATTING_METRICS = ["runs", "strike_rate", "average", "sixes", "fours", "boundary_pct"]
BOWLING_METRICS = ["wickets", "economy", "bowling_avg", "bowling_sr", "dot_pct"]
LOWER_IS_BETTER = ["economy", "bowling_avg", "bowling_sr"]


def top_performers(deliveries, season, metric, n=10, min_balls=0):
    """Top n players for one metric (season=None for all seasons); min_balls stops 2 lucky balls topping a list."""
    df = deliveries if season is None else deliveries[deliveries["season"] == season]
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
    table = table.dropna(subset=[metric])
    table = table.sort_values([metric, name_column], ascending=[metric in LOWER_IS_BETTER, True])
    return table.head(n).reset_index(drop=True)


def cap_winners(deliveries):
    """Orange Cap = most runs in a season; Purple Cap = most wickets (a tie goes to the better economy)."""
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
    """Each match as two rows, one per team, with won = True/False (no-results left out)."""
    played = matches[matches["no_result"] == False]
    keep = ["match_id", "season", "date", "venue", "city", "stage", "winner_franchise"]

    side1 = played[keep].copy()
    side1["team"] = played["team1_franchise"]
    side1["team_name"] = played["team1"]          # the name used that season
    side1["opponent"] = played["team2_franchise"]

    side2 = played[keep].copy()
    side2["team"] = played["team2_franchise"]
    side2["team_name"] = played["team2"]
    side2["opponent"] = played["team1_franchise"]

    results = pd.concat([side1, side2], ignore_index=True)
    results["won"] = results["team"] == results["winner_franchise"]
    return results.sort_values(["date", "match_id", "team"]).reset_index(drop=True)


def team_win_percent(matches, by_season=True):
    """Win % = wins / played * 100, per season or all-time."""
    results = team_results(matches)
    group_columns = ["team", "season"] if by_season else ["team"]
    table = results.groupby(group_columns).agg(played=("match_id", "count"), wins=("won", "sum")).reset_index()
    table["win_pct"] = percent(table["wins"], table["played"]).round(1)
    return table


def phase_run_rate(deliveries):
    """Each franchise's run rate in the Powerplay, Middle and Death overs."""
    df = add_ball_columns(deliveries)
    table = df.groupby(["batting_team_franchise", "phase"]).agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
    ).reset_index()
    table = table.rename(columns={"batting_team_franchise": "batting_team"})
    table["run_rate"] = per_over(table["runs"], table["legal_balls"]).round(2)
    return table


def innings_totals(deliveries, matches):
    """One row per innings: runs, wickets, legal balls and who batted. Inning 1 = batting first, 2 = chasing."""
    df = add_ball_columns(deliveries)
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
    return totals.merge(info, on="match_id", how="left")


def first_innings_scores(deliveries, matches):
    """Average first-innings score per season (shortened matches would pull it down, so they are left out)."""
    totals = full_matches(innings_totals(deliveries, matches))
    first = totals[totals["inning"] == 1]
    by_season = first.groupby("season")["runs"].mean().round(1).reset_index()
    return by_season.rename(columns={"runs": "avg_first_innings"})


def bat_first_vs_chase(deliveries, matches):
    """Per season: % of matches won batting first vs chasing (who batted first comes from the ball data)."""
    first = deliveries[deliveries["inning"] == 1]
    bat_first = first.groupby("match_id")["batting_team_franchise"].first().reset_index()
    bat_first = bat_first.rename(columns={"batting_team_franchise": "bat_first_team"})

    played = matches[matches["no_result"] == False].merge(bat_first, on="match_id", how="inner")
    played["bat_first_won"] = played["winner_franchise"] == played["bat_first_team"]
    table = played.groupby("season").agg(
        matches=("match_id", "count"),
        bat_first_wins=("bat_first_won", "sum"),
    ).reset_index()
    table["bat_first_win_pct"] = percent(table["bat_first_wins"], table["matches"]).round(1)
    table["chase_win_pct"] = (100 - table["bat_first_win_pct"]).round(1)
    return table


def toss_impact(matches):
    """% of matches won by the toss winner: overall, and split by bat / field."""
    played = matches[matches["no_result"] == False].copy()
    played["toss_winner_won"] = played["toss_winner_franchise"] == played["winner_franchise"]
    table = played.groupby("toss_decision").agg(
        matches=("match_id", "count"),
        toss_winner_wins=("toss_winner_won", "sum"),
    ).reset_index()
    table["win_pct"] = percent(table["toss_winner_wins"], table["matches"]).round(1)
    return table, round(played["toss_winner_won"].mean() * 100, 1)


# Home grounds of the 10 current franchises (a list: Punjab Kings moved to Mullanpur in 2024).
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
    return venue in HOME_GROUNDS.get(team, [])


def home_away_performance(matches):
    """Win % at home and away for the 10 current franchises."""
    results = team_results(matches)
    results = results[results["team"].isin(CURRENT_FRANCHISES)].copy()
    results["location"] = "Away"
    for i in results.index:
        if is_home_match(results.at[i, "team"], results.at[i, "venue"]):
            results.at[i, "location"] = "Home"
    table = results.groupby(["team", "location"]).agg(played=("match_id", "count"), wins=("won", "sum")).reset_index()
    table["win_pct"] = percent(table["wins"], table["played"]).round(1)
    return table


def head_to_head(matches, team_a, team_b):
    """Wins for each team, per season, in matches between the two."""
    results = team_results(matches)
    games = results[(results["team"] == team_a) & (results["opponent"] == team_b)]
    table = games.groupby("season").agg(played=("match_id", "count"), wins_a=("won", "sum")).reset_index()
    table["wins_b"] = table["played"] - table["wins_a"]
    return table.rename(columns={"wins_a": team_a, "wins_b": team_b})


def season_champions(matches):
    """The champion = the winner of the final, the last match of each season."""
    finals = matches.sort_values(["date", "match_id"]).groupby("season").tail(1)
    finals = finals[["season", "winner_franchise", "winner"]]
    finals = finals.rename(columns={"winner_franchise": "champion", "winner": "champion_name"})
    return finals.sort_values("season").reset_index(drop=True)


def player_of_match_counts(matches, n=10):
    counts = matches["player_of_match"].value_counts().reset_index()
    counts.columns = ["player", "awards"]
    counts = counts.sort_values(["awards", "player"], ascending=[False, True])
    return counts.head(n).reset_index(drop=True)


def margin_text(match):
    """How a match was won, e.g. 'won by 140 runs' or 'won by 7 wickets (D/L)'."""
    if match["no_result"]:
        return "No result"
    if match["result"] == "tie":
        return "Tie, won the super over"
    if match["win_by_runs"] > 0:
        text = "won by " + str(match["win_by_runs"]) + " run" + ("s" if match["win_by_runs"] != 1 else "")
    else:
        text = "won by " + str(match["win_by_wickets"]) + " wicket" + ("s" if match["win_by_wickets"] != 1 else "")
    if match["dl_applied"] == 1:
        text += " (D/L)"          # rain-shortened (Duckworth-Lewis method)
    return text


def most_common_team(df, name_column, team_column):
    """The franchise each player played most balls for (to label tables)."""
    counts = df.groupby([name_column, team_column]).size().reset_index(name="balls")
    counts = counts.sort_values([name_column, "balls", team_column], ascending=[True, False, True])
    return counts.groupby(name_column).head(1).set_index(name_column)[team_column]


# ---------------------------------------------------------------------------
# Rivalries: any two franchises
# ---------------------------------------------------------------------------
def rivalry_matches(matches, team_a, team_b):
    """Every match between the two franchises, oldest first."""
    a_v_b = (matches["team1_franchise"] == team_a) & (matches["team2_franchise"] == team_b)
    b_v_a = (matches["team1_franchise"] == team_b) & (matches["team2_franchise"] == team_a)
    return matches[a_v_b | b_v_a].sort_values(["date", "match_id"]).reset_index(drop=True)


def rivalry_split(games, team_a, team_b, column):
    """Wins for each team split by one column (season, stage or venue)."""
    rows = []
    for value in sorted(games[column].unique()):
        part = games[games[column] == value]
        rows.append({column: value, "played": len(part),
                     team_a: int((part["winner_franchise"] == team_a).sum()),
                     team_b: int((part["winner_franchise"] == team_b).sum()),
                     "no_result": int(part["no_result"].sum())})
    return pd.DataFrame(rows, columns=[column, "played", team_a, team_b, "no_result"])


def rivalry_record(matches, team_a, team_b):
    """Overall record, then by season, league vs playoffs, and at each ground."""
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
    """The last n meetings, newest first."""
    games = rivalry_matches(matches, team_a, team_b).tail(n).iloc[::-1]
    rows = []
    for match in games.to_dict("records"):
        rows.append({"match_id": int(match["match_id"]), "date": match["date"].strftime("%Y-%m-%d"),
                     "season": int(match["season"]), "venue": match["venue"],
                     "stage": match["playoff_name"] if match["stage"] == "Playoff" else "League",
                     "winner": "" if match["no_result"] else match["winner"], "margin": margin_text(match)})
    return pd.DataFrame(rows, columns=["match_id", "date", "season", "venue", "stage", "winner", "margin"])


def rivalry_totals(deliveries, matches, team_a, team_b, n=5):
    """
    Highest and lowest totals in the fixture. Lowest totals leave out shortened
    matches and won chases (a winning chase stops early on purpose).
    """
    games = rivalry_matches(matches, team_a, team_b)
    totals = innings_totals(deliveries[deliveries["match_id"].isin(games["match_id"])], matches)
    totals["score"] = totals["runs"].astype(str) + "/" + totals["wickets"].astype(str)
    totals["overs"] = totals["legal_balls"].apply(overs_text)
    totals["date"] = totals["date"].dt.strftime("%Y-%m-%d")
    columns = ["score", "runs", "overs", "batting_team_name", "season", "venue", "date", "match_id"]

    highest = totals.sort_values(["runs", "date"], ascending=[False, True]).head(n)
    finished = full_matches(totals)
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

    batting_columns = ["batter", "team", "innings", "runs", "balls_faced", "strike_rate", "average"]
    bowling_columns = ["bowler", "team", "matches", "wickets", "overs", "economy"]
    return batting[batting_columns].reset_index(drop=True), bowling[bowling_columns].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Batter vs bowler
# ---------------------------------------------------------------------------
def matchup_table(deliveries, min_balls=1):
    """
    One row per batter-bowler pair. Dismissals count only this bowler's wickets
    (a run out is not the bowler's). Strike rate = runs / balls * 100.
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
    table["strike_rate"] = percent(table["runs"], table["balls"]).round(1)
    table["dot_pct"] = percent(table["dots"], table["balls"]).round(1)
    table["boundary_pct"] = percent(table["fours"] + table["sixes"], table["balls"]).round(1)
    table["runs_per_dismissal"] = pd.to_numeric(table["runs"] / table["dismissals"].replace(0, pd.NA)).round(1)
    return table.reset_index(drop=True)


def batter_vs_bowler(deliveries, batter, bowler):
    balls = deliveries[(deliveries["batter"] == batter) & (deliveries["bowler"] == bowler)]
    return matchup_table(balls)


def batting_vs_teams(deliveries, batter=None):
    """A batter's record against each opposing franchise."""
    df = deliveries if batter is None else deliveries[deliveries["batter"] == batter]
    table = batting_stats(df, ["batter", "bowling_team_franchise"])
    table = table.rename(columns={"bowling_team_franchise": "opponent"})
    columns = ["batter", "opponent", "innings", "runs", "balls_faced", "dismissals", "average", "strike_rate", "sixes"]
    return table[columns].reset_index(drop=True)


def dismissal_types(deliveries, batter=None):
    """How a batter gets out: count and % of each dismissal type."""
    df = add_ball_columns(deliveries)
    outs = df[df["is_wicket"]]
    if batter is not None:
        outs = outs[outs["player_dismissed"] == batter]
    table = outs.groupby(["player_dismissed", "dismissal_kind"]).size().reset_index(name="times")
    totals = table.groupby("player_dismissed")["times"].transform("sum")
    table["pct"] = percent(table["times"], totals).round(1)
    table = table.rename(columns={"player_dismissed": "batter"})
    return table.sort_values(["batter", "times", "dismissal_kind"], ascending=[True, False, True]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Grounds
# ---------------------------------------------------------------------------
def ground_first_innings_by_season(deliveries, matches, venue=None):
    totals = full_matches(innings_totals(deliveries, matches))
    first = totals[totals["inning"] == 1]
    if venue is not None:
        first = first[first["venue"] == venue]
    table = first.groupby(["venue", "season"]).agg(matches=("match_id", "count"), avg_first_innings=("runs", "mean"))
    table["avg_first_innings"] = table["avg_first_innings"].round(1)
    return table.reset_index()


def ground_summary(deliveries, matches):
    """One row per ground: average first innings, chase win %, how toss choices worked, highest total."""
    totals = innings_totals(deliveries, matches)
    first = full_matches(totals)
    first = first[first["inning"] == 1]
    avg_first = first.groupby("venue")["runs"].mean().round(1)
    highest = totals.groupby("venue")["runs"].max()

    bat_first = totals[totals["inning"] == 1][["match_id", "batting_team"]].rename(columns={"batting_team": "bat_first"})
    played = matches[matches["no_result"] == False].merge(bat_first, on="match_id", how="inner")
    played["chase_won"] = played["winner_franchise"] != played["bat_first"]
    played["toss_winner_won"] = played["toss_winner_franchise"] == played["winner_franchise"]

    def win_pct(games, column):
        return round(games[column].mean() * 100, 1) if len(games) else None

    rows = []
    for venue in sorted(matches["venue"].unique()):
        at_ground = matches[matches["venue"] == venue]
        games = played[played["venue"] == venue]
        chose_bat = games[games["toss_decision"] == "bat"]
        chose_field = games[games["toss_decision"] == "field"]
        rows.append({
            "venue": venue,
            "city": at_ground["city"].iloc[0],
            "matches": len(at_ground),
            "first_season": int(at_ground["season"].min()),
            "last_season": int(at_ground["season"].max()),
            "avg_first_innings": avg_first.get(venue),
            "chase_win_pct": win_pct(games, "chase_won"),
            "toss_bat_matches": len(chose_bat),
            "toss_bat_win_pct": win_pct(chose_bat, "toss_winner_won"),
            "toss_field_matches": len(chose_field),
            "toss_field_win_pct": win_pct(chose_field, "toss_winner_won"),
            "highest_total": highest.get(venue),
        })
    return pd.DataFrame(rows)


def ground_phase_run_rate(deliveries, matches):
    df = add_ball_columns(deliveries).merge(matches[["match_id", "venue"]], on="match_id", how="left")
    table = df.groupby(["venue", "phase"]).agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
    ).reset_index()
    table["run_rate"] = per_over(table["runs"], table["legal_balls"]).round(2)
    return table


def ground_highest_totals(deliveries, matches, venue, n=5):
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
    table = results.groupby(["team", "venue", "season"]).agg(
        played=("match_id", "count"),
        wins=("won", "sum"),
    ).reset_index()
    table["win_pct"] = percent(table["wins"], table["played"]).round(1)
    return table


def home_fortress_index(matches):
    """Fortress index = home win % - away win %: a big number means much stronger at home."""
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
# Specialists
# ---------------------------------------------------------------------------
def phase_batting_leaders(deliveries, phase, min_balls=120, season=None, n=10):
    """Most runs in one phase, for batters with at least min_balls there."""
    df = deliveries[deliveries["phase"] == phase]
    if season is not None:
        df = df[df["season"] == season]
    table = batting_stats(df)
    table = table[table["balls_faced"] >= min_balls]
    table = table.sort_values(["runs", "batter"], ascending=[False, True]).head(n)
    return table[["batter", "runs", "balls_faced", "strike_rate", "sixes", "dismissals"]].reset_index(drop=True)


def phase_bowling_leaders(deliveries, phase, min_balls=120, season=None, n=10):
    """Most wickets in one phase, for bowlers with at least min_balls there."""
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
    Who scores fastest in overs 16-20 AND stays not out in chases:
      not_out_pct = % of chase innings not out;  won_not_out = chases won with him not out.
    """
    death = batting_stats(deliveries[deliveries["phase"] == "Death"])
    death = death[death["balls_faced"] >= min_death_balls][["batter", "runs", "balls_faced", "strike_rate"]]
    death = death.rename(columns={"runs": "death_runs", "balls_faced": "death_balls", "strike_rate": "death_strike_rate"})

    # Every chase innings: who was at the crease, and who got out.
    chase = add_ball_columns(deliveries)
    chase = chase[chase["inning"] == 2]
    strikers = chase[["match_id", "batter", "batting_team_franchise"]]
    non_strikers = chase[["match_id", "non_striker", "batting_team_franchise"]].rename(columns={"non_striker": "batter"})
    batted = pd.concat([strikers, non_strikers]).drop_duplicates(["match_id", "batter"])
    outs = chase[chase["is_wicket"]][["match_id", "player_dismissed"]].drop_duplicates()
    outs = outs.rename(columns={"player_dismissed": "batter"})
    outs["out_marker"] = 1
    batted = batted.merge(outs, on=["match_id", "batter"], how="left")
    batted["out"] = batted["out_marker"] == 1
    batted = batted.merge(matches[["match_id", "winner_franchise"]], on="match_id", how="left")
    batted["won_not_out"] = (~batted["out"]) & (batted["winner_franchise"] == batted["batting_team_franchise"])

    chase_table = batted.groupby("batter").agg(
        chase_innings=("match_id", "count"),
        not_outs=("out", lambda column: int((~column).sum())),
        won_not_out=("won_not_out", "sum"),
    ).reset_index()
    chase_table["not_out_pct"] = percent(chase_table["not_outs"], chase_table["chase_innings"]).round(1)
    table = death.merge(chase_table, on="batter", how="left")
    table = table.sort_values(["death_strike_rate", "batter"], ascending=[False, True]).head(n)
    return table.reset_index(drop=True)


def partnerships(deliveries, matches):
    """
    Every partnership: the runs and legal balls while two batters were together.
    wicket = 1st, 2nd ... (wickets fallen before + 1).
    """
    df = add_ball_columns(deliveries)
    # (A, B) and (B, A) are the same pair, so write them in alphabetical order.
    first_name = df[["batter", "non_striker"]].min(axis=1)
    second_name = df[["batter", "non_striker"]].max(axis=1)
    df["pair"] = first_name + " & " + second_name
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
# Impact Player era: 2020-22 (before) vs 2023-26 (with the rule)
# ---------------------------------------------------------------------------
ERA_BEFORE = "2020-22 (before Impact Player)"
ERA_IMPACT = "2023-26 (Impact Player era)"


def era_of(season):
    if 2020 <= season <= 2022:
        return ERA_BEFORE
    if season >= 2023:
        return ERA_IMPACT
    return None


def impact_era_summary(deliveries, matches):
    """Per era: average first-innings score, 200+ totals and chase win %."""
    totals = full_matches(innings_totals(deliveries, matches)).copy()
    totals["era"] = totals["season"].apply(era_of)
    totals = totals[totals["era"].notna()]
    rows = []
    for era in [ERA_BEFORE, ERA_IMPACT]:
        part = totals[totals["era"] == era]
        first = part[part["inning"] == 1]
        second = part[part["inning"] == 2]
        matches_played = first["match_id"].nunique()
        totals_200 = (part["runs"] >= 200).sum()
        chase_won = (second["winner_franchise"] == second["batting_team"]).sum()
        rows.append({"era": era, "matches": int(matches_played),
                     "avg_first_innings": round(first["runs"].mean(), 1),
                     "totals_200_plus": int(totals_200),
                     "totals_200_plus_per_match": round(totals_200 / matches_played, 2),
                     "chase_win_pct": round(chase_won / len(second) * 100, 1)})
    return pd.DataFrame(rows)


def impact_era_phase_run_rate(deliveries):
    df = add_ball_columns(deliveries)
    df["era"] = df["season"].apply(era_of)
    df = df[df["era"].notna()]
    table = df.groupby(["era", "phase"]).agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
    ).reset_index()
    table["run_rate"] = per_over(table["runs"], table["legal_balls"]).round(2)
    return table


def impact_player_choices(impact, deliveries, matches):
    """
    One row per Impact Player substitution: what the player who came in did
    (Batter, Bowler, Batted and bowled, Did not bat or bowl) and whether his team won.
    """
    df = remove_super_overs(deliveries)
    batted = set(zip(df["match_id"], df["batter"])) | set(zip(df["match_id"], df["non_striker"]))
    bowled = set(zip(df["match_id"], df["bowler"]))
    rows = impact.merge(matches[["match_id", "winner_franchise", "no_result"]], on="match_id", how="left")
    roles = []
    for key in zip(rows["match_id"], rows["player_in"]):
        if key in batted and key in bowled:
            roles.append("Batted and bowled")
        elif key in batted:
            roles.append("Batter")
        elif key in bowled:
            roles.append("Bowler")
        else:
            roles.append("Did not bat or bowl")
    rows["role"] = roles
    rows["won"] = rows["winner_franchise"] == rows["franchise"]
    return rows


def impact_choice_summary(choices, by_team=True):
    """How often each Impact Player role was used and the win % with it."""
    played = choices[choices["no_result"] == False]
    group_columns = ["franchise", "role"] if by_team else ["role"]
    table = played.groupby(group_columns).agg(times=("match_id", "count"), wins=("won", "sum")).reset_index()
    table["win_pct"] = percent(table["wins"], table["times"]).round(1)
    return table


# ---------------------------------------------------------------------------
# Trends, points tables and the chase model
# ---------------------------------------------------------------------------
def scoring_inflation(deliveries, matches):
    """Per season: average first-innings score, sixes per match and run rate."""
    full = full_matches(innings_totals(deliveries, matches))
    table = full.groupby("season").agg(
        matches=("match_id", "nunique"),
        sixes=("sixes", "sum"),
        runs=("runs", "sum"),
        legal_balls=("legal_balls", "sum"),
    ).reset_index()
    first = full[full["inning"] == 1].groupby("season")["runs"].mean().round(1)
    table["avg_first_innings"] = table["season"].map(first)
    table["sixes_per_match"] = (table["sixes"] / table["matches"]).round(1)
    table["run_rate"] = per_over(table["runs"], table["legal_balls"]).round(2)
    return table[["season", "matches", "avg_first_innings", "sixes_per_match", "run_rate"]]


def points_table(deliveries, matches, season):
    """
    One season's league table rebuilt from the results: 2 points a win, 1 a no-result.
    Net run rate = runs scored per over - runs conceded per over; a team bowled out
    counts its full 20 overs (the official rule).
    """
    league = matches[(matches["season"] == season) & (matches["stage"] == "League")]
    totals = innings_totals(deliveries[deliveries["match_id"].isin(league["match_id"])], matches)
    totals = totals[totals["inning"] <= 2].copy()
    totals["nrr_balls"] = totals["legal_balls"]
    totals.loc[totals["wickets"] >= 10, "nrr_balls"] = 120
    totals = totals[totals["no_result"] == False]

    rows = []
    for team in sorted(set(league["team1_franchise"]) | set(league["team2_franchise"])):
        games = league[(league["team1_franchise"] == team) | (league["team2_franchise"] == team)]
        wins = int((games["winner_franchise"] == team).sum())
        no_results = int(games["no_result"].sum())
        batting = totals[totals["batting_team"] == team]
        bowling = totals[totals["bowling_team"] == team]
        nrr = per_over(batting["runs"].sum(), batting["nrr_balls"].sum()) - per_over(bowling["runs"].sum(), bowling["nrr_balls"].sum())
        rows.append({"team": team, "played": len(games), "won": wins, "lost": len(games) - wins - no_results,
                     "no_result": no_results, "points": wins * 2 + no_results, "nrr": round(nrr, 3)})
    table = pd.DataFrame(rows).sort_values(["points", "nrr", "team"], ascending=[False, False, True]).reset_index(drop=True)
    table.insert(0, "position", range(1, len(table) + 1))
    table.insert(1, "season", season)
    return table


def chase_states(deliveries, matches):
    """
    The situation before every ball of every normal chase, and whether the chase was won:
      runs_needed = target - runs so far,  balls_left = 120 - legal balls so far,  wickets_left = 10 - wickets so far
    """
    df = add_ball_columns(deliveries)
    good = full_matches(matches)
    good = good[good["result"] != "tie"]
    df = df[df["match_id"].isin(good["match_id"])]
    first = df[df["inning"] == 1].groupby("match_id")["total_runs"].sum().rename("first_innings")
    chase = df[df["inning"] == 2].copy().merge(first, left_on="match_id", right_index=True)

    # Before this ball = running total minus this ball.
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
    """The 4 numbers the chase model uses (required rate: 40 off 24 is harder than 40 off 60)."""
    required_rate = runs_needed * 6 / balls_left
    return pd.DataFrame({"runs_needed": runs_needed, "balls_left": balls_left,
                         "wickets_left": wickets_left, "required_rate": required_rate})


def win_probability_model(states):
    """Logistic regression: chance = 1 / (1 + e^-(b0 + b1*runs_needed + ...)), learned from real chases."""
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
    A season impact score per player = batting points + bowling points:
      a run is worth (season run rate / run rate in that phase), so a Powerplay run counts a bit more
      a wicket is worth the average runs per wicket in that phase
    """
    df = add_ball_columns(deliveries)

    # Step 1: the weights of each season and phase.
    phase = df.groupby(["season", "phase"]).agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
        wickets=("is_wicket", "sum"),
    ).reset_index()
    season = df.groupby("season").agg(
        season_runs=("total_runs", "sum"),
        season_balls=("is_legal_ball", "sum"),
    ).reset_index()
    phase = phase.merge(season, on="season")
    phase["run_weight"] = (phase["season_runs"] / phase["season_balls"]) / (phase["runs"] / phase["legal_balls"])
    phase["wicket_value"] = phase["runs"] / phase["wickets"]
    weights = phase[["season", "phase", "run_weight", "wicket_value"]]

    # Step 2: each player's runs and wickets times the weights.
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

    # Step 3: the franchise each player played most balls for that season.
    as_batter = df[["batter", "season", "batting_team_franchise"]].rename(columns={"batter": "player", "batting_team_franchise": "team"})
    as_bowler = df[["bowler", "season", "bowling_team_franchise"]].rename(columns={"bowler": "player", "bowling_team_franchise": "team"})
    counts = pd.concat([as_batter, as_bowler]).groupby(["player", "season", "team"]).size().reset_index(name="balls")
    counts = counts.sort_values(["player", "season", "balls", "team"], ascending=[True, True, False, True])
    main_team = counts.groupby(["player", "season"]).head(1)[["player", "season", "team"]]
    table = table.merge(main_team, on=["player", "season"], how="left")
    return table.sort_values(["season", "impact", "player"], ascending=[True, False, True]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pitch and player fit
# The data has no pitch reports or ball-tracking, so "how a pitch plays" means
# how the GROUND has played compared with the league in the SAME seasons.
# ---------------------------------------------------------------------------
PITCH_HIGH = 105    # index 105+ = high-scoring (5% more runs than the league)
PITCH_LOW = 95      # index 95 or less = low-scoring


def add_venue(deliveries, matches):
    """Ball columns plus the ground of each ball."""
    df = add_ball_columns(deliveries)
    df = df.merge(matches[["match_id", "venue"]], on="match_id", how="left")
    df["is_boundary"] = df["is_four"] | df["is_six"]
    return df


def league_rates(df):
    """The league average per ball in each season: runs, wickets and dots per legal ball, boundaries per ball faced."""
    season = df.groupby("season").agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
        wickets=("is_wicket", "sum"),
        dots=("is_dot_ball", "sum"),
        balls_faced=("is_ball_faced", "sum"),
        boundaries=("is_boundary", "sum"),
    ).reset_index()
    season["runs_per_ball"] = season["runs"] / season["legal_balls"]
    season["wickets_per_ball"] = season["wickets"] / season["legal_balls"]
    season["dots_per_ball"] = season["dots"] / season["legal_balls"]
    season["boundaries_per_ball"] = season["boundaries"] / season["balls_faced"]
    return season[["season", "runs_per_ball", "wickets_per_ball", "dots_per_ball", "boundaries_per_ball"]]


def pitch_components(deliveries, matches):
    """
    Per ground and season: what HAPPENED and what the league average would EXPECT
    from the same balls (exp_runs = legal balls x league runs per ball).
    Index = happened / expected x 100, so 100 = an average ground.
    """
    df = add_venue(deliveries, matches)
    parts = df.groupby(["venue", "season"]).agg(
        matches=("match_id", "nunique"),
        legal_balls=("is_legal_ball", "sum"),
        runs=("total_runs", "sum"),
        wickets=("is_wicket", "sum"),
        dots=("is_dot_ball", "sum"),
        balls_faced=("is_ball_faced", "sum"),
        boundaries=("is_boundary", "sum"),
    ).reset_index()
    parts = parts.merge(league_rates(df), on="season")
    parts["exp_runs"] = parts["legal_balls"] * parts["runs_per_ball"]
    parts["exp_wickets"] = parts["legal_balls"] * parts["wickets_per_ball"]
    parts["exp_dots"] = parts["legal_balls"] * parts["dots_per_ball"]
    parts["exp_boundaries"] = parts["balls_faced"] * parts["boundaries_per_ball"]

    # First-innings scores and chases at each ground and season.
    good = full_matches(innings_totals(deliveries, matches))
    first = good[good["inning"] == 1].groupby(["venue", "season"]).agg(
        first_innings_runs=("runs", "sum"),
        first_innings_count=("runs", "count"),
    ).reset_index()
    second = good[good["inning"] == 2].copy()
    second["chase_won"] = second["winner_franchise"] == second["batting_team"]
    chases = second.groupby(["venue", "season"]).agg(
        chases=("match_id", "count"),
        chase_wins=("chase_won", "sum"),
    ).reset_index()
    parts = parts.merge(first, on=["venue", "season"], how="left").merge(chases, on=["venue", "season"], how="left")
    for column in ["first_innings_runs", "first_innings_count", "chases", "chase_wins"]:
        parts[column] = parts[column].fillna(0).astype(int)
    columns = ["venue", "season", "matches", "legal_balls", "runs", "exp_runs", "wickets", "exp_wickets",
               "balls_faced", "boundaries", "exp_boundaries", "dots", "exp_dots",
               "first_innings_runs", "first_innings_count", "chases", "chase_wins"]
    return parts[columns].sort_values(["venue", "season"]).reset_index(drop=True)


def pitch_label(runs_index, wickets_index):
    """A ground in words, from its runs and wickets indexes."""
    if runs_index >= PITCH_HIGH:
        scoring = "high-scoring"
    elif runs_index <= PITCH_LOW:
        scoring = "low-scoring"
    else:
        scoring = "average-scoring"
    if wickets_index >= PITCH_HIGH:
        wickets = "wickets fall more often than average"
    elif wickets_index <= PITCH_LOW:
        wickets = "wickets are harder to take than average"
    else:
        wickets = "wickets fall at about the average rate"
    return scoring + ", " + wickets


def pitch_profile(deliveries, matches, seasons=None, min_matches=1):
    """How every ground plays over the chosen seasons (None = all): runs, wickets, boundary and dot indexes."""
    return profile_from_components(pitch_components(deliveries, matches), seasons, min_matches)


def safe_ratio(top, bottom):
    """top / bottom, left empty where bottom is 0."""
    return top / bottom.where(bottom > 0)


def profile_from_components(parts, seasons=None, min_matches=1):
    """Add up pitch_components rows over the chosen seasons, then work out the indexes."""
    if seasons is not None:
        parts = parts[parts["season"].isin(seasons)]
    table = parts.groupby("venue").sum(numeric_only=True).reset_index()
    table = table[table["matches"] >= min_matches].copy()
    table["runs_index"] = percent(table["runs"], table["exp_runs"]).round(1)
    table["wickets_index"] = percent(table["wickets"], table["exp_wickets"]).round(1)
    table["boundary_index"] = percent(table["boundaries"], table["exp_boundaries"]).round(1)
    table["dot_index"] = percent(table["dots"], table["exp_dots"]).round(1)
    table["run_rate"] = per_over(table["runs"], table["legal_balls"]).round(2)
    table["avg_first_innings"] = safe_ratio(table["first_innings_runs"], table["first_innings_count"]).round(1)
    table["chase_win_pct"] = (safe_ratio(table["chase_wins"], table["chases"]) * 100).round(1)
    table["label"] = [pitch_label(r, w) for r, w in zip(table["runs_index"], table["wickets_index"])]
    columns = ["venue", "matches", "run_rate", "runs_index", "wickets_index", "boundary_index", "dot_index",
               "avg_first_innings", "chase_win_pct", "label"]
    return table[columns].sort_values(["runs_index", "venue"], ascending=[False, True]).reset_index(drop=True)


def phase_index_from_components(parts, seasons=None):
    """Run rate and runs index per ground and phase."""
    if seasons is not None:
        parts = parts[parts["season"].isin(seasons)]
    table = parts.groupby(["venue", "phase"]).sum(numeric_only=True).reset_index()
    table["run_rate"] = per_over(table["runs"], table["legal_balls"]).round(2)
    table["runs_index"] = percent(table["runs"], table["exp_runs"]).round(1)
    return table[["venue", "phase", "run_rate", "runs_index"]]


def pitch_phase_components(deliveries, matches):
    """Runs and league-expected runs per ground, season and phase."""
    df = add_venue(deliveries, matches)
    league = df.groupby(["season", "phase"]).agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
    ).reset_index()
    league["runs_per_ball"] = league["runs"] / league["legal_balls"]
    parts = df.groupby(["venue", "season", "phase"]).agg(
        runs=("total_runs", "sum"),
        legal_balls=("is_legal_ball", "sum"),
    ).reset_index()
    parts = parts.merge(league[["season", "phase", "runs_per_ball"]], on=["season", "phase"])
    parts["exp_runs"] = parts["legal_balls"] * parts["runs_per_ball"]
    return parts[["venue", "season", "phase", "runs", "legal_balls", "exp_runs"]]


def same_season_split(here_rows, season_totals, keys, count_columns):
    """
    A player at one ground against HIMSELF at other grounds in the SAME seasons:
    elsewhere = his season total - here, added up over the seasons he played at the ground.
    """
    merged = here_rows.merge(season_totals, on=[keys[0], "season"], suffixes=("", "_total"))
    for column in count_columns:
        merged["else_" + column] = merged[column + "_total"] - merged[column]
    keep = list(keys) + count_columns + ["else_" + column for column in count_columns]
    return merged[keep].groupby(list(keys)).sum().reset_index()


def player_ground_batting(deliveries, matches):
    """Every batter at every ground, here vs elsewhere in the same seasons."""
    df = add_venue(deliveries, matches)
    faced = df[df["is_ball_faced"]].copy()
    faced["is_bat_dot"] = faced["batsman_runs"] == 0
    here = faced.groupby(["batter", "venue", "season"]).agg(
        balls=("batsman_runs", "size"),
        runs=("batsman_runs", "sum"),
        fours=("is_four", "sum"),
        sixes=("is_six", "sum"),
        dots=("is_bat_dot", "sum"),
    ).reset_index()
    outs = df[df["is_wicket"]].groupby(["player_dismissed", "venue", "season"]).size().reset_index(name="outs")
    outs = outs.rename(columns={"player_dismissed": "batter"})
    here = here.merge(outs, on=["batter", "venue", "season"], how="left")
    here["outs"] = here["outs"].fillna(0).astype(int)

    count_columns = ["balls", "runs", "outs", "fours", "sixes", "dots"]
    totals = here.groupby(["batter", "season"])[count_columns].sum().reset_index()
    table = same_season_split(here, totals, ["batter", "venue"], count_columns)
    innings = faced.groupby(["batter", "venue"])["match_id"].nunique().reset_index(name="innings")
    table = table.merge(innings, on=["batter", "venue"])
    table["strike_rate"] = percent(table["runs"], table["balls"]).round(1)
    table["else_strike_rate"] = (safe_ratio(table["else_runs"], table["else_balls"]) * 100).round(1)
    table["strike_rate_diff"] = (table["strike_rate"] - table["else_strike_rate"]).round(1)
    table["average"] = safe_ratio(table["runs"], table["outs"]).round(1)
    table["else_average"] = safe_ratio(table["else_runs"], table["else_outs"]).round(1)
    return table


def player_ground_bowling(deliveries, matches):
    """Every bowler at every ground, here vs elsewhere in the same seasons."""
    df = add_venue(deliveries, matches)
    here = df.groupby(["bowler", "venue", "season"]).agg(
        legal_balls=("is_legal_ball", "sum"),
        runs=("runs_conceded", "sum"),
        wickets=("is_bowler_wicket", "sum"),
        dots=("is_dot_ball", "sum"),
    ).reset_index()
    count_columns = ["legal_balls", "runs", "wickets", "dots"]
    totals = here.groupby(["bowler", "season"])[count_columns].sum().reset_index()
    table = same_season_split(here, totals, ["bowler", "venue"], count_columns)
    games = df.groupby(["bowler", "venue"])["match_id"].nunique().reset_index(name="matches")
    table = table.merge(games, on=["bowler", "venue"])
    table["economy"] = per_over(table["runs"], table["legal_balls"]).round(2)
    table["else_economy"] = (table["else_runs"] / (table["else_legal_balls"].where(table["else_legal_balls"] > 0) / 6)).round(2)
    table["economy_diff"] = (table["economy"] - table["else_economy"]).round(2)
    return table


def fielding_events(deliveries):
    """
    One row per fielding dismissal per fielder: a catch ("caught and bowled" is the
    bowler's catch), a run out (every fielder named) or a stumping. Substitutes are left out.
    """
    df = remove_super_overs(deliveries)
    rows = []
    for i in df.index[df["dismissal_kind"].isin(["caught", "caught and bowled", "run out", "stumped"])]:
        kind = df.at[i, "dismissal_kind"]
        if kind == "caught and bowled":
            rows.append([df.at[i, "match_id"], df.at[i, "season"], df.at[i, "bowler"], "catch"])
            continue
        fielders = df.at[i, "fielder"]
        if not isinstance(fielders, str):
            continue
        for name in fielders.split(", "):
            if name.endswith("(sub)"):
                continue
            event = "catch" if kind == "caught" else ("run_out" if kind == "run out" else "stumping")
            rows.append([df.at[i, "match_id"], df.at[i, "season"], name, event])
    return pd.DataFrame(rows, columns=["match_id", "season", "player", "event"])


def player_ground_fielding(deliveries, matches):
    """Catches, run outs and stumpings per match at each ground vs elsewhere (played = batted, bowled or fielded)."""
    events = fielding_events(deliveries).merge(matches[["match_id", "venue"]], on="match_id")
    df = remove_super_overs(deliveries).merge(matches[["match_id", "venue"]], on="match_id")
    played = pd.concat([df[["match_id", "season", "venue", "batter"]].rename(columns={"batter": "player"}),
                        df[["match_id", "season", "venue", "non_striker"]].rename(columns={"non_striker": "player"}),
                        df[["match_id", "season", "venue", "bowler"]].rename(columns={"bowler": "player"}),
                        events[["match_id", "season", "venue", "player"]]]).drop_duplicates()
    here = played.groupby(["player", "venue", "season"])["match_id"].nunique().reset_index(name="matches")
    for event, column in [("catch", "catches"), ("run_out", "run_outs"), ("stumping", "stumpings")]:
        counts = events[events["event"] == event].groupby(["player", "venue", "season"]).size().reset_index(name=column)
        here = here.merge(counts, on=["player", "venue", "season"], how="left")
    count_columns = ["matches", "catches", "run_outs", "stumpings"]
    for column in count_columns:
        here[column] = here[column].fillna(0).astype(int)

    totals = here.groupby(["player", "season"])[count_columns].sum().reset_index()
    table = same_season_split(here, totals, ["player", "venue"], count_columns)
    table["dismissals_per_match"] = ((table["catches"] + table["run_outs"] + table["stumpings"]) / table["matches"]).round(2)
    else_dismissals = table["else_catches"] + table["else_run_outs"] + table["else_stumpings"]
    table["else_dismissals_per_match"] = safe_ratio(else_dismissals, table["else_matches"]).round(2)
    return table


def best_ground_fits(batting, bowling, venue, min_balls=120, n=5):
    """Players much better here than elsewhere (min_balls both here and elsewhere): biggest strike-rate gain, biggest economy drop."""
    bat = batting[(batting["venue"] == venue) & (batting["balls"] >= min_balls) & (batting["else_balls"] >= min_balls)]
    bat = bat.sort_values(["strike_rate_diff", "batter"], ascending=[False, True]).head(n)
    bowl = bowling[(bowling["venue"] == venue) & (bowling["legal_balls"] >= min_balls) & (bowling["else_legal_balls"] >= min_balls)]
    bowl = bowl.sort_values(["economy_diff", "bowler"], ascending=[True, True]).head(n)
    return (bat[["batter", "balls", "runs", "strike_rate", "else_strike_rate", "strike_rate_diff"]].reset_index(drop=True),
            bowl[["bowler", "legal_balls", "wickets", "economy", "else_economy", "economy_diff"]].reset_index(drop=True))


# ---------------------------------------------------------------------------
# Team pages
# ---------------------------------------------------------------------------
def team_season_summary(deliveries, matches):
    """Per franchise and season: played, won, league position and finish (Champion, Runner-up, Playoffs, League stage)."""
    results = team_results(matches)
    table = results.groupby(["team", "season"]).agg(played=("match_id", "count"), won=("won", "sum")).reset_index()
    table["win_pct"] = percent(table["won"], table["played"]).round(1)

    positions = []
    for season in sorted(matches["season"].unique()):
        points = points_table(deliveries, matches, season)
        for row in points.to_dict("records"):
            positions.append([row["team"], season, int(row["position"]), int(row["points"])])
    positions = pd.DataFrame(positions, columns=["team", "season", "position", "points"])
    table = table.merge(positions, on=["team", "season"], how="left")

    stages = {}
    for match in matches[matches["stage"] == "Playoff"].to_dict("records"):
        for team in [match["team1_franchise"], match["team2_franchise"]]:
            key = (team, match["season"])
            if match["playoff_name"] == "Final":
                stages[key] = "Champion" if match["winner_franchise"] == team else "Runner-up"
            elif key not in stages:
                stages[key] = "Playoffs"
    table["stage"] = [stages.get(key, "League stage") for key in zip(table["team"], table["season"])]
    return table.sort_values(["team", "season"]).reset_index(drop=True)


def team_names_by_season(matches):
    """The name each franchise used each season, e.g. Delhi Capitals -> Delhi Daredevils in 2015."""
    side1 = matches[["season", "team1", "team1_franchise"]].rename(columns={"team1": "name", "team1_franchise": "team"})
    side2 = matches[["season", "team2", "team2_franchise"]].rename(columns={"team2": "name", "team2_franchise": "team"})
    return pd.concat([side1, side2]).drop_duplicates().sort_values(["team", "season"]).reset_index(drop=True)


def team_phase_components(deliveries):
    """
    Per franchise, season and phase: runs scored and conceded, and the league-expected runs
    from the same balls. Batting index = runs / expected x 100 (higher = faster);
    bowling index = conceded / expected x 100 (lower = better).
    """
    df = add_ball_columns(deliveries)
    league = df.groupby(["season", "phase"]).agg(runs=("total_runs", "sum"), legal=("is_legal_ball", "sum")).reset_index()
    league["runs_per_ball"] = league["runs"] / league["legal"]
    bat = df.groupby(["batting_team_franchise", "season", "phase"]).agg(
        bat_runs=("total_runs", "sum"),
        bat_balls=("is_legal_ball", "sum"),
    ).reset_index().rename(columns={"batting_team_franchise": "team"})
    bowl = df.groupby(["bowling_team_franchise", "season", "phase"]).agg(
        bowl_runs=("total_runs", "sum"),
        bowl_balls=("is_legal_ball", "sum"),
    ).reset_index().rename(columns={"bowling_team_franchise": "team"})
    table = bat.merge(bowl, on=["team", "season", "phase"], how="outer").fillna(0)
    table = table.merge(league[["season", "phase", "runs_per_ball"]], on=["season", "phase"])
    table["bat_expected"] = table["bat_balls"] * table["runs_per_ball"]
    table["bowl_expected"] = table["bowl_balls"] * table["runs_per_ball"]
    return table[["team", "season", "phase", "bat_runs", "bat_balls", "bat_expected", "bowl_runs", "bowl_balls", "bowl_expected"]]


def team_style(deliveries, matches):
    """Per franchise: batting first vs chasing, and what it chose after winning the toss."""
    totals = innings_totals(deliveries, matches)
    first = totals[totals["inning"] == 1][["match_id", "batting_team", "bowling_team"]]
    played = matches[matches["no_result"] == False][["match_id", "winner_franchise", "toss_winner_franchise", "toss_decision"]]
    played = played.merge(first, on="match_id")

    def wins(games, team):
        return int((games["winner_franchise"] == team).sum())

    rows = []
    for team in sorted(set(played["batting_team"]) | set(played["bowling_team"])):
        bat_first = played[played["batting_team"] == team]
        chasing = played[played["bowling_team"] == team]
        tosses = played[played["toss_winner_franchise"] == team]
        chose_bat = tosses[tosses["toss_decision"] == "bat"]
        chose_field = tosses[tosses["toss_decision"] == "field"]
        rows.append({"team": team,
                     "bat_first_played": len(bat_first), "bat_first_won": wins(bat_first, team),
                     "chase_played": len(chasing), "chase_won": wins(chasing, team),
                     "tosses_won": len(tosses),
                     "chose_bat": len(chose_bat), "chose_bat_won": wins(chose_bat, team),
                     "chose_field": len(chose_field), "chose_field_won": wins(chose_field, team)})
    return pd.DataFrame(rows)


def team_top_players(deliveries, n=10):
    """Each franchise's all-time top run-scorers and wicket-takers (for that franchise only)."""
    batting = batting_stats(deliveries, ["batter", "batting_team_franchise"]).rename(columns={"batting_team_franchise": "team"})
    batting = batting.sort_values(["team", "runs", "batter"], ascending=[True, False, True]).groupby("team").head(n)
    bowling = bowling_stats(deliveries, ["bowler", "bowling_team_franchise"]).rename(columns={"bowling_team_franchise": "team"})
    bowling = bowling.sort_values(["team", "wickets", "economy", "bowler"], ascending=[True, False, True, True]).groupby("team").head(n)
    return batting.reset_index(drop=True), bowling.reset_index(drop=True)


def team_extremes(matches, n=5):
    """Each franchise's biggest wins and heaviest defeats, by runs and by wickets (no rain-rule matches)."""
    normal = matches[(matches["no_result"] == False) & (matches["result"] == "normal") & (matches["dl_applied"] == 0)].copy()
    normal["loser_franchise"] = normal["team1_franchise"].where(normal["winner_franchise"] != normal["team1_franchise"],
                                                                 normal["team2_franchise"])
    rows = []
    for column, kind in [("win_by_runs", "runs"), ("win_by_wickets", "wickets")]:
        part = normal[normal[column] > 0]
        for side, team_column in [("win", "winner_franchise"), ("defeat", "loser_franchise")]:
            ranked = part.sort_values([column, "date"], ascending=[False, True]).groupby(team_column).head(n)
            for match in ranked.to_dict("records"):
                opponent = match["loser_franchise"] if side == "win" else match["winner_franchise"]
                rows.append([match[team_column], side, kind, int(match[column]), opponent,
                             match["date"].strftime("%Y-%m-%d"), match["venue"], int(match["match_id"])])
    return pd.DataFrame(rows, columns=["team", "side", "kind", "margin", "opponent", "date", "venue", "match_id"])


def team_ground_stats(deliveries, matches):
    """Every franchise at every ground: results, runs and wickets for and against, batting first and chasing."""
    totals = innings_totals(deliveries, matches)
    totals = totals[totals["inning"] <= 2]
    record = team_results(matches).groupby(["team", "venue"]).agg(
        played=("match_id", "count"),
        won=("won", "sum"),
    ).reset_index()

    bat = totals.groupby(["batting_team", "venue"]).agg(
        runs_for=("runs", "sum"),
        balls_for=("legal_balls", "sum"),
        wickets_lost=("wickets", "sum"),
        highest=("runs", "max"),
    ).reset_index().rename(columns={"batting_team": "team"})
    bowl = totals.groupby(["bowling_team", "venue"]).agg(
        runs_against=("runs", "sum"),
        balls_against=("legal_balls", "sum"),
        wickets_taken=("wickets", "sum"),
    ).reset_index().rename(columns={"bowling_team": "team"})

    good = full_matches(totals)
    first = good[good["inning"] == 1].copy()
    first["won"] = first["winner_franchise"] == first["batting_team"]
    bat_first = first.groupby(["batting_team", "venue"]).agg(
        bat_first_played=("match_id", "count"),
        bat_first_won=("won", "sum"),
        first_innings_runs=("runs", "sum"),
    ).reset_index().rename(columns={"batting_team": "team"})
    second = good[good["inning"] == 2].copy()
    second["won"] = second["winner_franchise"] == second["batting_team"]
    chase = second.groupby(["batting_team", "venue"]).agg(
        chase_played=("match_id", "count"),
        chase_won=("won", "sum"),
    ).reset_index().rename(columns={"batting_team": "team"})

    table = record.merge(bat, on=["team", "venue"], how="outer").merge(bowl, on=["team", "venue"], how="outer")
    table = table.merge(bat_first, on=["team", "venue"], how="left").merge(chase, on=["team", "venue"], how="left")
    count_columns = ["played", "won", "runs_for", "balls_for", "wickets_lost", "highest", "runs_against", "balls_against",
                     "wickets_taken", "bat_first_played", "bat_first_won", "first_innings_runs", "chase_played", "chase_won"]
    for column in count_columns:
        table[column] = table[column].fillna(0).astype(int)
    return table.sort_values(["team", "venue"]).reset_index(drop=True)


def team_ground_phases(deliveries, matches):
    """Runs scored and conceded in each phase, per franchise and ground."""
    df = add_ball_columns(deliveries).merge(matches[["match_id", "venue"]], on="match_id")
    bat = df.groupby(["batting_team_franchise", "venue", "phase"]).agg(
        runs=("total_runs", "sum"),
        balls=("is_legal_ball", "sum"),
    ).reset_index().rename(columns={"batting_team_franchise": "team"})
    bowl = df.groupby(["bowling_team_franchise", "venue", "phase"]).agg(
        runs_against=("total_runs", "sum"),
        balls_against=("is_legal_ball", "sum"),
    ).reset_index().rename(columns={"bowling_team_franchise": "team"})
    return bat.merge(bowl, on=["team", "venue", "phase"], how="outer").fillna(0)


def team_ground_top_players(deliveries, matches, n=5):
    """Each franchise's top run-scorers and wicket-takers at each ground."""
    df = deliveries.merge(matches[["match_id", "venue"]], on="match_id")
    batting = batting_stats(df, ["batter", "batting_team_franchise", "venue"]).rename(columns={"batting_team_franchise": "team"})
    batting = batting.sort_values(["team", "venue", "runs", "batter"], ascending=[True, True, False, True])
    batting = batting.groupby(["team", "venue"]).head(n)
    bowling = bowling_stats(df, ["bowler", "bowling_team_franchise", "venue"]).rename(columns={"bowling_team_franchise": "team"})
    bowling = bowling[bowling["wickets"] > 0]
    bowling = bowling.sort_values(["team", "venue", "wickets", "economy", "bowler"], ascending=[True, True, False, True, True])
    bowling = bowling.groupby(["team", "venue"]).head(n)
    return batting.reset_index(drop=True), bowling.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
def fastest_milestones(deliveries, milestone=50):
    """
    Fastest fifties (50) or hundreds (100): a running total (cumsum) of runs and balls
    in each innings, then the first ball where runs >= milestone.
    (The cleaned file is in the order the balls were bowled.)
    """
    df = add_ball_columns(deliveries)
    innings_columns = ["match_id", "inning", "batter"]
    df["runs_so_far"] = df.groupby(innings_columns)["batsman_runs"].cumsum()
    df["balls_so_far"] = df.groupby(innings_columns)["is_ball_faced"].cumsum()
    reached = df[df["runs_so_far"] >= milestone]
    first_ball = reached.groupby(innings_columns).head(1)
    table = first_ball[["batter", "season", "date", "match_id", "batting_team", "bowling_team", "balls_so_far"]]
    table = table.rename(columns={"bowling_team": "against", "balls_so_far": "balls"})
    return table.sort_values(["balls", "date"]).reset_index(drop=True)


def best_bowling_figures(deliveries, min_wickets=3):
    """Best bowling in one match (6/12 = 6 wickets for 12 runs): most wickets, then fewest runs."""
    df = add_ball_columns(deliveries)
    figures = df.groupby(["bowler", "match_id", "season", "date", "bowling_team", "batting_team"]).agg(
        wickets=("is_bowler_wicket", "sum"),
        runs=("runs_conceded", "sum"),
        legal_balls=("is_legal_ball", "sum"),
    ).reset_index()
    figures = figures[figures["wickets"] >= min_wickets].copy()
    figures["figures"] = figures["wickets"].astype(str) + "/" + figures["runs"].astype(str)
    figures = figures.rename(columns={"batting_team": "against"})
    figures = figures.sort_values(["wickets", "runs", "date"], ascending=[False, True, True])
    return figures.reset_index(drop=True)


def fielding_records(deliveries, by_season=False):
    """Catches, stumpings and run-outs per fielder (the same rules as fielding_events)."""
    events = fielding_events(deliveries)
    group_columns = ["player", "season"] if by_season else ["player"]
    table = events.pivot_table(index=group_columns, columns="event", values="match_id",
                               aggfunc="count", fill_value=0).reset_index()
    for event in ["catch", "stumping", "run_out"]:
        if event not in table.columns:
            table[event] = 0
    table = table.rename(columns={"catch": "catches", "stumping": "stumpings", "run_out": "run_outs"})
    table["dismissals"] = table["catches"] + table["stumpings"] + table["run_outs"]
    table = table[group_columns + ["catches", "stumpings", "run_outs", "dismissals"]]
    table.columns.name = None
    return table.sort_values(["dismissals", "player"], ascending=[False, True]).reset_index(drop=True)
