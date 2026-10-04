"""
dashboard_data.py
-----------------
Prepares the data for the ANALYST VIEWS of the dashboard (rivalries,
matchups, grounds, specialists, the Impact Player era and trends).

Why a separate file?
    The dashboard is one HTML page that must work OFFLINE, so all the numbers
    it shows have to be inside the page. Python (this file, using metrics.py)
    calculates every table once; the page's JavaScript (src/dashboard_analytics.js)
    only looks rows up when you change a drop-down, and divides a few counts
    (e.g. strike rate = runs / balls x 100) the same way metrics.py does.

To keep the page small, names are stored once in lists ("players", "teams",
"venues") and table rows hold the POSITION of a name in its list (a number).

Used by build_report.py:
    data = dashboard_data.analyst_data(matches, deliveries, impact)
"""

import os
import pandas as pd
import metrics   # our own file: src/metrics.py (every cricket formula)


# Minimum balls for the phase-leader tables, so 2 lucky balls cannot top a list.
MIN_BALLS_ALL_SEASONS = 300   # 50 overs
MIN_BALLS_ONE_SEASON = 60     # 10 overs


def clean_value(value):
    """
    Turn one pandas value into something JSON can store:
    numpy numbers -> normal numbers, missing values -> None (shown as "-").
    """
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):       # numpy number, e.g. numpy.int64(5)
        value = value.item()
        if isinstance(value, float) and pd.isna(value):
            return None
    return value


def table_rows(table, columns):
    """A pandas table as a list of plain lists (one list per row), in the given column order."""
    rows = []
    for i in range(len(table)):
        rows.append([clean_value(table[column].iloc[i]) for column in columns])
    return rows


def index_of(names):
    """A dictionary from each name to its position in the list, e.g. {"CSK": 0, ...}."""
    positions = {}
    for position in range(len(names)):
        positions[names[position]] = position
    return positions


# ---------------------------------------------------------------------------
# 1. Rivalries: every pair of franchises that has played each other
# ---------------------------------------------------------------------------
def rivalry_data(matches, deliveries, teams):
    """
    One entry per pair of franchises, with the key "i|j" (positions in the
    team list, smaller first). Team A is always teams[i] and team B teams[j].
    """
    results = metrics.team_results(matches)
    pairs = set()
    for i in range(len(results)):
        a, b = sorted([results["team"].iloc[i], results["opponent"].iloc[i]])
        pairs.add((a, b))
    # Matches that were all no-results are not in team_results, so add those pairs too.
    for i in range(len(matches)):
        a, b = sorted([matches["team1_franchise"].iloc[i], matches["team2_franchise"].iloc[i]])
        pairs.add((a, b))

    position = index_of(teams)
    data = {}
    for team_a, team_b in sorted(pairs):
        overall, by_season, by_stage, by_ground = metrics.rivalry_record(matches, team_a, team_b)
        last = metrics.rivalry_last_meetings(matches, team_a, team_b)
        highest, lowest = metrics.rivalry_totals(deliveries, matches, team_a, team_b)
        batting, bowling = metrics.rivalry_top_players(deliveries, matches, team_a, team_b)
        key = str(position[team_a]) + "|" + str(position[team_b])
        data[key] = {
            "overall": [overall["played"], overall[team_a], overall[team_b], overall["no_result"]],
            "seasons": table_rows(by_season, ["season", "played", team_a, team_b, "no_result"]),
            "stages": table_rows(by_stage, ["stage", "played", team_a, team_b, "no_result"]),
            "grounds": table_rows(by_ground, ["venue", "played", team_a, team_b, "no_result"]),
            "last": table_rows(last, ["match_id", "date", "season", "venue", "stage", "winner", "margin"]),
            "high": table_rows(highest, ["score", "overs", "batting_team_name", "season", "venue", "date", "match_id"]),
            "low": table_rows(lowest, ["score", "overs", "batting_team_name", "season", "venue", "date", "match_id"]),
            "bat": table_rows(batting, ["batter", "team", "innings", "runs", "balls_faced", "strike_rate", "average"]),
            "bowl": table_rows(bowling, ["bowler", "team", "matches", "wickets", "overs", "economy"]),
        }
    return data


# ---------------------------------------------------------------------------
# 2. Matchups and player-vs-team records
# ---------------------------------------------------------------------------
def matchup_data(deliveries, players, teams):
    """Batter-vs-bowler counts, records against each team, and how batters get out."""
    player_position = index_of(players)
    team_position = index_of(teams)

    matchups = metrics.matchup_table(deliveries)
    matchups["b"] = matchups["batter"].map(player_position)
    matchups["w"] = matchups["bowler"].map(player_position)

    batting = metrics.batting_vs_teams(deliveries)
    batting["p"] = batting["batter"].map(player_position)
    batting["t"] = batting["opponent"].map(team_position)

    bowling = metrics.bowling_stats(deliveries, ["bowler", "batting_team_franchise"])
    bowling["p"] = bowling["bowler"].map(player_position)
    bowling["t"] = bowling["batting_team_franchise"].map(team_position)

    outs = metrics.dismissal_types(deliveries)
    kinds = sorted(outs["dismissal_kind"].unique())
    outs["p"] = outs["batter"].map(player_position)
    outs["k"] = outs["dismissal_kind"].map(index_of(kinds))

    return {
        # [batter, bowler, balls, runs, dismissals, dot balls, fours, sixes]
        "matchups": table_rows(matchups, ["b", "w", "balls", "runs", "dismissals", "dots", "fours", "sixes"]),
        # [batter, opponent, innings, runs, balls faced, dismissals, sixes]
        "bat_vs": table_rows(batting, ["p", "t", "innings", "runs", "balls_faced", "dismissals", "sixes"]),
        # [bowler, opponent, matches, wickets, legal balls, runs conceded]
        "bowl_vs": table_rows(bowling, ["p", "t", "matches", "wickets", "legal_balls", "runs_conceded"]),
        "out_kinds": kinds,
        # [batter, dismissal type, times]
        "outs": table_rows(outs, ["p", "k", "times"]),
    }


# ---------------------------------------------------------------------------
# 3. Grounds
# ---------------------------------------------------------------------------
def ground_data(matches, deliveries, venues, teams):
    """Ground summaries, scores by season, run rate by phase, highest totals, team at ground."""
    venue_position = index_of(venues)
    team_position = index_of(teams)

    summary = metrics.ground_summary(deliveries, matches)
    summary["v"] = summary["venue"].map(venue_position)

    seasons = metrics.ground_first_innings_by_season(deliveries, matches)
    seasons["v"] = seasons["venue"].map(venue_position)

    phases = metrics.ground_phase_run_rate(deliveries, matches)
    phases["v"] = phases["venue"].map(venue_position)

    highest = {}
    for venue in venues:
        top = metrics.ground_highest_totals(deliveries, matches, venue)
        highest[str(venue_position[venue])] = table_rows(
            top, ["score", "batting_team_name", "bowling_team", "season", "date", "match_id"])

    at_ground = metrics.team_at_ground(matches)
    at_ground["t"] = at_ground["team"].map(team_position)
    at_ground["v"] = at_ground["venue"].map(venue_position)

    fortress = metrics.home_fortress_index(matches)
    return {
        "grounds": table_rows(summary, ["v", "city", "matches", "first_season", "last_season", "avg_first_innings",
                                        "chase_win_pct", "toss_bat_matches", "toss_bat_win_pct",
                                        "toss_field_matches", "toss_field_win_pct", "highest_total"]),
        "ground_seasons": table_rows(seasons, ["v", "season", "matches", "avg_first_innings"]),
        "ground_phases": table_rows(phases, ["v", "phase", "run_rate"]),
        "ground_high": highest,
        # [team, venue, season, played, wins]
        "team_ground": table_rows(at_ground, ["t", "v", "season", "played", "wins"]),
        "fortress": table_rows(fortress, ["team", "home_grounds", "home_played", "home_win_pct",
                                          "away_played", "away_win_pct", "fortress_index"]),
    }


# ---------------------------------------------------------------------------
# 4. Specialists
# ---------------------------------------------------------------------------
def specialist_data(matches, deliveries, teams):
    """Phase leaders (all seasons and each season), finishers and partnerships."""
    leaders = {}
    season_choices = ["all"] + sorted(matches["season"].unique())
    for season in season_choices:
        for phase in ["Powerplay", "Middle", "Death"]:
            if season == "all":
                bat = metrics.phase_batting_leaders(deliveries, phase, MIN_BALLS_ALL_SEASONS)
                bowl = metrics.phase_bowling_leaders(deliveries, phase, MIN_BALLS_ALL_SEASONS)
            else:
                bat = metrics.phase_batting_leaders(deliveries, phase, MIN_BALLS_ONE_SEASON, season=season)
                bowl = metrics.phase_bowling_leaders(deliveries, phase, MIN_BALLS_ONE_SEASON, season=season)
            leaders[str(season) + "|" + phase] = {
                "bat": table_rows(bat, ["batter", "runs", "balls_faced", "strike_rate", "sixes", "dismissals"]),
                "bowl": table_rows(bowl, ["bowler", "wickets", "overs", "economy", "dot_pct"]),
            }

    finishers = metrics.finishers(deliveries, matches, min_death_balls=150, n=15)
    stands = metrics.partnerships(deliveries, matches)
    partnership_columns = ["pair", "wicket", "runs", "balls", "team_name", "season", "venue", "date", "match_id"]
    partnerships = {"all": table_rows(stands.head(10), partnership_columns)}
    for team in teams:
        partnerships[team] = table_rows(stands[stands["team"] == team].head(10), partnership_columns)

    return {
        "min_balls": [MIN_BALLS_ALL_SEASONS, MIN_BALLS_ONE_SEASON],
        "phase_leaders": leaders,
        "finishers": table_rows(finishers, ["batter", "death_runs", "death_balls", "death_strike_rate",
                                            "chase_innings", "not_outs", "not_out_pct", "won_not_out"]),
        "partnerships": partnerships,
    }


# ---------------------------------------------------------------------------
# 5. Impact Player era
# ---------------------------------------------------------------------------
def impact_data(matches, deliveries, impact):
    """The era comparison and each team's Impact Player choices."""
    summary = metrics.impact_era_summary(deliveries, matches)
    phases = metrics.impact_era_phase_run_rate(deliveries)
    choices = metrics.impact_player_choices(impact, deliveries, matches)
    by_team = metrics.impact_choice_summary(choices, by_team=True)
    overall = metrics.impact_choice_summary(choices, by_team=False)
    return {
        "era_summary": table_rows(summary, ["era", "matches", "avg_first_innings", "totals_200_plus",
                                            "totals_200_plus_per_match", "chase_win_pct"]),
        "era_phases": table_rows(phases, ["era", "phase", "run_rate"]),
        "choices_team": table_rows(by_team, ["franchise", "role", "times", "wins", "win_pct"]),
        "choices_all": table_rows(overall, ["role", "times", "wins", "win_pct"]),
        "substitutions": len(impact),
    }


# ---------------------------------------------------------------------------
# 6. Trends
# ---------------------------------------------------------------------------
def points_note(table):
    """
    A note (worked out from the table, not typed in) when some teams played
    fewer league matches than others: an abandoned match with no ball bowled is
    not in the ball-by-ball data, so those teams may be 1 point below official.
    """
    most = table["played"].max()
    short = table[table["played"] < most]
    if len(short) == 0:
        return ""
    return (", ".join(short["team"]) + " played " + str(short["played"].min()) + " league matches in the data, "
            "the others " + str(most) + ": a match abandoned without a ball being bowled is not in the "
            "ball-by-ball data, so their points can be lower than the official table.")


def trend_data(matches, deliveries, players, chase_model_file):
    """Scoring inflation, points tables, the chase model and season impact scores."""
    inflation = metrics.scoring_inflation(deliveries, matches)
    points = {}
    for season in sorted(matches["season"].unique()):
        table = metrics.points_table(deliveries, matches, season)
        points[str(season)] = {
            "rows": table_rows(table, ["position", "team", "played", "won", "lost", "no_result", "points", "nrr"]),
            "note": points_note(table),
        }

    # The chase model weights were saved by analysis.py (so the model is fitted once).
    weights = {}
    if os.path.exists(chase_model_file):
        model_table = pd.read_csv(chase_model_file)
        for i in range(len(model_table)):
            weights[model_table["term"].iloc[i]] = float(model_table["weight"].iloc[i])

    impact = metrics.season_impact_scores(deliveries)
    impact["p"] = impact["player"].map(index_of(players))
    return {
        "inflation": table_rows(inflation, ["season", "matches", "avg_first_innings", "sixes_per_match", "run_rate"]),
        "points": points,
        "chase_model": weights,
        # [player, season, team, runs, wickets, batting points, bowling points, impact]
        "impact_scores": table_rows(impact, ["p", "season", "team", "runs", "wickets",
                                             "batting_points", "bowling_points", "impact"]),
    }


def analyst_data(matches, deliveries, impact, chase_model_file):
    """Everything the analyst views need, as one dictionary (saved into the page as JSON)."""
    teams = sorted(set(matches["team1_franchise"]) | set(matches["team2_franchise"]))
    players = sorted(set(deliveries["batter"]) | set(deliveries["bowler"]) | set(deliveries["non_striker"]))
    venues = sorted(matches["venue"].unique())
    data = {"teams": teams, "current_teams": metrics.CURRENT_FRANCHISES, "players": players, "venues": venues,
            "seasons": [int(season) for season in sorted(matches["season"].unique())],
            "season_range": metrics.season_range_text(matches)}
    data["rivalry"] = rivalry_data(matches, deliveries, teams)
    data.update(matchup_data(deliveries, players, teams))
    data.update(ground_data(matches, deliveries, venues, teams))
    data.update(specialist_data(matches, deliveries, teams))
    data.update(impact_data(matches, deliveries, impact))
    data.update(trend_data(matches, deliveries, players, chase_model_file))
    return data
