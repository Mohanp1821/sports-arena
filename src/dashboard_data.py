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


# ---------------------------------------------------------------------------
# 7. Pitch and player fit
# ---------------------------------------------------------------------------
FIT_MIN_BALLS = 12        # batting/bowling rows with fewer balls at a ground are left out of the page
FIT_MIN_MATCHES = 2       # fielding rows with fewer matches at a ground are left out


def pitch_periods(matches):
    """The time periods you can pick: all seasons, the Impact Player era, and each season (newest first)."""
    seasons = sorted(matches["season"].unique())
    periods = [["all", "All seasons " + metrics.season_range_text(matches), seasons],
               ["2023-" + str(seasons[-1]), "Impact Player era (2023-" + str(seasons[-1]) + ")", [s for s in seasons if s >= 2023]]]
    for season in reversed(seasons):
        periods.append([str(season), str(season), [season]])
    return periods


def pitch_data(matches, deliveries, players, venues):
    """
    Ground profiles for every period (looked up by the page), how batters got out there,
    and every player's record at every ground vs other grounds in the same seasons.
    """
    venue_position = index_of(venues)
    player_position = index_of(players)
    parts = metrics.pitch_components(deliveries, matches)
    phase_parts = metrics.pitch_phase_components(deliveries, matches)
    df = metrics.add_venue(deliveries, matches)
    outs = df[df["is_wicket"]].groupby(["venue", "season", "dismissal_kind"]).size().reset_index(name="count")
    kinds = sorted(outs["dismissal_kind"].unique())

    profiles = {}
    phases = {}
    dismissals = {}
    periods = pitch_periods(matches)
    for key, label, seasons in periods:
        profile = metrics.profile_from_components(parts, seasons)
        profile["v"] = profile["venue"].map(venue_position)
        profiles[key] = table_rows(profile, ["v", "matches", "run_rate", "runs_index", "wickets_index", "boundary_index",
                                             "dot_index", "avg_first_innings", "chase_win_pct", "label"])
        phase = metrics.phase_index_from_components(phase_parts, seasons)
        phase["v"] = phase["venue"].map(venue_position)
        phases[key] = table_rows(phase, ["v", "phase", "run_rate", "runs_index"])
        # Dismissal mix: % of dismissals of each kind here, and in the whole league in the same seasons.
        part = outs[outs["season"].isin(seasons)]
        league = part.groupby("dismissal_kind")["count"].sum()
        league_pct = league / league.sum() * 100
        here = part.groupby(["venue", "dismissal_kind"])["count"].sum().reset_index()
        here["pct"] = here["count"] / here.groupby("venue")["count"].transform("sum") * 100
        rows = []
        for i in range(len(here)):
            row = here.iloc[i]
            rows.append([venue_position[row["venue"]], kinds.index(row["dismissal_kind"]), int(row["count"]),
                         round(float(row["pct"]), 1), round(float(league_pct[row["dismissal_kind"]]), 1)])
        dismissals[key] = rows

    batting = metrics.player_ground_batting(deliveries, matches)
    bowling = metrics.player_ground_bowling(deliveries, matches)
    fielding = metrics.player_ground_fielding(deliveries, matches)
    batting = batting[(batting["balls"] >= FIT_MIN_BALLS) & batting["batter"].isin(player_position)].copy()
    bowling = bowling[(bowling["legal_balls"] >= FIT_MIN_BALLS) & bowling["bowler"].isin(player_position)].copy()
    fielding = fielding[(fielding["matches"] >= FIT_MIN_MATCHES) & fielding["player"].isin(player_position)].copy()
    batting["p"] = batting["batter"].map(player_position)
    bowling["p"] = bowling["bowler"].map(player_position)
    fielding["p"] = fielding["player"].map(player_position)
    for table in [batting, bowling, fielding]:
        table["v"] = table["venue"].map(venue_position)

    best = {}
    full_batting = metrics.player_ground_batting(deliveries, matches)
    full_bowling = metrics.player_ground_bowling(deliveries, matches)
    for venue in venues:
        bat, bowl = metrics.best_ground_fits(full_batting, full_bowling, venue)
        best[str(venue_position[venue])] = {
            "bat": table_rows(bat, ["batter", "balls", "strike_rate", "else_strike_rate", "strike_rate_diff"]),
            "bowl": table_rows(bowl, ["bowler", "legal_balls", "economy", "else_economy", "economy_diff"])}

    return {
        "pitch_thresholds": [metrics.PITCH_HIGH, metrics.PITCH_LOW],
        "pitch_periods": [[key, label] for key, label, seasons in periods],
        "pitch": profiles, "pitch_phase": phases, "pitch_out_kinds": kinds, "pitch_outs": dismissals,
        # [player, ground, innings, balls, runs, outs, fours, sixes, dots, then the same 6 counts elsewhere]
        "fit_bat": table_rows(batting, ["p", "v", "innings", "balls", "runs", "outs", "fours", "sixes", "dots",
                                        "else_balls", "else_runs", "else_outs", "else_fours", "else_sixes", "else_dots"]),
        # [player, ground, matches, legal balls, runs, wickets, dots, then the same 4 counts elsewhere]
        "fit_bowl": table_rows(bowling, ["p", "v", "matches", "legal_balls", "runs", "wickets", "dots",
                                         "else_legal_balls", "else_runs", "else_wickets", "else_dots"]),
        # [player, ground, matches, catches, run outs, stumpings, then the same 4 counts elsewhere]
        "fit_field": table_rows(fielding, ["p", "v", "matches", "catches", "run_outs", "stumpings",
                                           "else_matches", "else_catches", "else_run_outs", "else_stumpings"]),
        "fit_best": best,
    }


# ---------------------------------------------------------------------------
# 8. Player and ground pages (the new site design, src/site.js)
# ---------------------------------------------------------------------------
LAST_N = 10     # how many recent innings / bowling matches the "form" chart shows


def site_data(matches, deliveries, players, venues, squads):
    """
    Extra tables for the player and ground pages (the rest comes from the
    analyst data and the chat facts, so nothing is stored twice):
      phase splits, the last 10 innings and bowling spells, Player of the Match
      awards, fielding totals, the 2027 squad and each ground's home teams.
    """
    player_position = index_of(players)
    phases = ["Powerplay", "Middle", "Death"]
    df = metrics.add_ball_columns(deliveries)
    df["is_wicket"] = df["player_dismissed"].notna() & (df["dismissal_kind"] != "retired hurt")

    # Phase splits. Batting: [player, phase, runs, balls faced, outs]; bowling: [player, phase, legal balls, runs, wickets]
    faced = df[df["is_ball_faced"]]
    bat = faced.groupby(["batter", "phase"]).agg(runs=("batsman_runs", "sum"), balls=("batsman_runs", "size")).reset_index()
    outs = df[df["is_wicket"]].groupby(["player_dismissed", "phase"]).size().reset_index(name="outs")
    bat = bat.merge(outs.rename(columns={"player_dismissed": "batter"}), on=["batter", "phase"], how="left").fillna({"outs": 0})
    bat["p"] = bat["batter"].map(player_position)
    bat["ph"] = bat["phase"].map(lambda phase: phases.index(phase))
    bowl = df.groupby(["bowler", "phase"]).agg(legal=("is_legal_ball", "sum"), runs=("runs_conceded", "sum"),
                                               wickets=("is_bowler_wicket", "sum")).reset_index()
    bowl["p"] = bowl["bowler"].map(player_position)
    bowl["ph"] = bowl["phase"].map(lambda phase: phases.index(phase))

    # The last 10 innings of every batter: [date, opponent, runs, balls, out (1/0), match id]
    innings = metrics.batting_innings(deliveries)
    dismissed = set(zip(df.loc[df["is_wicket"], "match_id"], df.loc[df["is_wicket"], "player_dismissed"]))
    last_bat = {}
    for batter, rows in innings.groupby("batter"):
        rows = rows.tail(LAST_N)
        last_bat[str(player_position[batter])] = [
            [rows["date"].iloc[i].strftime("%Y-%m-%d"), rows["bowling_team_franchise"].iloc[i], int(rows["runs"].iloc[i]),
             int(rows["balls"].iloc[i]), 1 if (rows["match_id"].iloc[i], batter) in dismissed else 0, int(rows["match_id"].iloc[i])]
            for i in range(len(rows))]

    # The last 10 bowling matches: [date, opponent, legal balls, runs, wickets, match id]
    spells = df.groupby(["bowler", "match_id", "date"]).agg(opponent=("batting_team_franchise", "first"),
                                                            legal=("is_legal_ball", "sum"), runs=("runs_conceded", "sum"),
                                                            wickets=("is_bowler_wicket", "sum")).reset_index()
    spells = spells.sort_values(["bowler", "date", "match_id"])
    last_bowl = {}
    for bowler, rows in spells.groupby("bowler"):
        rows = rows.tail(LAST_N)
        last_bowl[str(player_position[bowler])] = [
            [rows["date"].iloc[i].strftime("%Y-%m-%d"), rows["opponent"].iloc[i], int(rows["legal"].iloc[i]),
             int(rows["runs"].iloc[i]), int(rows["wickets"].iloc[i]), int(rows["match_id"].iloc[i])] for i in range(len(rows))]

    potm = matches[matches["player_of_match"] != ""]["player_of_match"].value_counts()
    events = metrics.fielding_events(deliveries)
    fielding = events.groupby(["player", "event"]).size().unstack(fill_value=0)
    field = {}
    for player in fielding.index:
        if player in player_position:
            field[str(player_position[player])] = [int(fielding.loc[player].get(event, 0)) for event in ["catch", "run_out", "stumping"]]

    home = {}
    for team in metrics.HOME_GROUNDS:
        for ground in metrics.HOME_GROUNDS[team]:
            if ground in venues:
                home.setdefault(ground, []).append(team)

    return {
        "phases": phases,
        "bat_phase": table_rows(bat, ["p", "ph", "runs", "balls", "outs"]),
        "bowl_phase": table_rows(bowl, ["p", "ph", "legal", "runs", "wickets"]),
        "last_bat": last_bat, "last_bowl": last_bowl,
        "potm": {str(player_position[name]): int(count) for name, count in potm.items() if name in player_position},
        "field": field,
        "squads": {row["player"]: row["team"] for row in squads.to_dict("records")},
        "home": home,
        "team": team_data(matches, deliveries, venues),
    }


def team_data(matches, deliveries, venues):
    """
    Everything the team pages and the "two teams at one ground" comparison need.
    Teams and grounds are stored as positions in the sorted team / ground lists
    (the same lists as the analyst data).
    """
    teams = sorted(set(matches["team1_franchise"]) | set(matches["team2_franchise"]))
    team_position = index_of(teams)
    venue_position = index_of(venues)
    phases = ["Powerplay", "Middle", "Death"]

    summary = metrics.team_season_summary(deliveries, matches)
    names = metrics.team_names_by_season(matches)
    name_of = {}
    for i in range(len(names)):
        name_of[(names["team"].iloc[i], int(names["season"].iloc[i]))] = names["name"].iloc[i]
    seasons = {}
    for i in range(len(summary)):
        row = summary.iloc[i]
        seasons.setdefault(row["team"], []).append(
            [int(row["season"]), name_of.get((row["team"], int(row["season"])), row["team"]), int(row["played"]), int(row["won"]),
             float(row["win_pct"]), clean_value(row["position"]), clean_value(row["points"]), row["stage"]])

    phase_parts = metrics.team_phase_components(deliveries)
    phase_parts["t"] = phase_parts["team"].map(team_position)
    phase_parts["ph"] = phase_parts["phase"].map(lambda phase: phases.index(phase))
    for column in ["bat_expected", "bowl_expected"]:
        phase_parts[column] = phase_parts[column].round(1)

    style = metrics.team_style(deliveries, matches)
    style_rows = {}
    for i in range(len(style)):
        style_rows[style["team"].iloc[i]] = [int(v) for v in style.iloc[i][1:]]

    batting, bowling = metrics.team_top_players(deliveries)
    top_bat = {}
    for team, rows in batting.groupby("team"):
        top_bat[team] = table_rows(rows, ["batter", "innings", "runs", "strike_rate", "average"])
    top_bowl = {}
    for team, rows in bowling.groupby("team"):
        top_bowl[team] = table_rows(rows, ["bowler", "matches", "wickets", "economy"])

    extremes = metrics.team_extremes(matches)
    extreme_rows = {}
    for team, rows in extremes.groupby("team"):
        extreme_rows[team] = table_rows(rows, ["side", "kind", "margin", "opponent", "date", "venue", "match_id"])

    ground = metrics.team_ground_stats(deliveries, matches)
    ground["t"] = ground["team"].map(team_position)
    ground["v"] = ground["venue"].map(venue_position)
    ground_phase = metrics.team_ground_phases(deliveries, matches)
    ground_phase["t"] = ground_phase["team"].map(team_position)
    ground_phase["v"] = ground_phase["venue"].map(venue_position)
    ground_phase["ph"] = ground_phase["phase"].map(lambda phase: phases.index(phase))
    ground_bat, ground_bowl = metrics.team_ground_top_players(deliveries, matches)
    tg_bat = {}
    for (team, venue), rows in ground_bat.groupby(["team", "venue"]):
        tg_bat[str(team_position[team]) + "|" + str(venue_position[venue])] = table_rows(rows, ["batter", "innings", "runs", "strike_rate"])
    tg_bowl = {}
    for (team, venue), rows in ground_bowl.groupby(["team", "venue"]):
        tg_bowl[str(team_position[team]) + "|" + str(venue_position[venue])] = table_rows(rows, ["bowler", "matches", "wickets", "economy"])

    return {
        "seasons": seasons,
        # [team, season, phase, runs scored, legal balls, league-expected runs, runs conceded, legal balls, expected]
        "phases": table_rows(phase_parts, ["t", "season", "ph", "bat_runs", "bat_balls", "bat_expected",
                                           "bowl_runs", "bowl_balls", "bowl_expected"]),
        # bat first played/won, chase played/won, tosses won, chose bat (n, won), chose field (n, won)
        "style": style_rows, "top_bat": top_bat, "top_bowl": top_bowl, "extremes": extreme_rows,
        # [team, ground, played, won, runs for, balls for, wickets lost, highest, runs against, balls against,
        #  wickets taken, bat-first played, bat-first won, first-innings runs, chases, chases won]
        "ground": table_rows(ground, ["t", "v", "played", "won", "runs_for", "balls_for", "wickets_lost", "highest",
                                      "runs_against", "balls_against", "wickets_taken", "bat_first_played", "bat_first_won",
                                      "first_innings_runs", "chase_played", "chase_won"]),
        # [team, ground, phase, runs scored, balls, runs conceded, balls]
        "ground_phase": table_rows(ground_phase, ["t", "v", "ph", "runs", "balls", "runs_against", "balls_against"]),
        "ground_bat": tg_bat, "ground_bowl": tg_bowl,
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
    data.update(pitch_data(matches, deliveries, players, venues))
    return data
