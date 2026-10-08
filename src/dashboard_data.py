"""
dashboard_data.py - the numbers for the website's analyst views, team, player and ground pages.

The site is one HTML page that works offline, so every number it shows is
calculated here (with metrics.py) and stored inside the page as JSON.
The page's JavaScript only looks rows up.

To keep the page small, names are stored once in lists (players, teams,
venues) and table rows hold a name's POSITION in its list.
"""

import os
import pandas as pd
import metrics

OUTPUT_FOLDER = os.path.join(metrics.PROJECT_FOLDER, "outputs")

MIN_BALLS_ALL_SEASONS = 300   # phase leaders over all seasons: at least 50 overs
MIN_BALLS_ONE_SEASON = 60     # in one season: at least 10 overs
FIT_MIN_BALLS = 12            # player-at-ground rows with fewer balls are left out
FIT_MIN_MATCHES = 2           # fielding rows with fewer matches are left out
LAST_N = 10                   # recent innings shown on a player page
PHASES = ["Powerplay", "Middle", "Death"]

NOTES_FILE = os.path.join(metrics.PROJECT_FOLDER, "data", "analyst_notes.csv")
NOTE_AUTHOR = "Mohan's note"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clean_value(value):
    """A pandas value JSON can store: numpy number -> normal number, missing -> None."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):           # a numpy number
        value = value.item()
        if isinstance(value, float) and pd.isna(value):
            return None
    return value


def read_output(file_name):
    """A CSV saved in outputs/ by an earlier step, or None if it has not been made yet."""
    path = os.path.join(OUTPUT_FOLDER, file_name)
    return pd.read_csv(path) if os.path.exists(path) else None


def table_rows(table, columns):
    """A table as a list of plain lists, one per row, in the given column order."""
    return [[clean_value(table[column].iloc[i]) for column in columns] for i in range(len(table))]


def index_of(names):
    """{name: position in the list}."""
    return {name: position for position, name in enumerate(names)}


def date_text(column):
    return column.dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Rivalries: every pair of franchises that has met
# ---------------------------------------------------------------------------
def rivalry_data(matches, deliveries, teams):
    """One entry per pair, keyed "i|j" by team positions (team A = teams[i])."""
    pairs = set()
    results = metrics.team_results(matches)
    for team, opponent in zip(results["team"], results["opponent"]):
        pairs.add(tuple(sorted([team, opponent])))
    for team1, team2 in zip(matches["team1_franchise"], matches["team2_franchise"]):   # pairs with only no-results
        pairs.add(tuple(sorted([team1, team2])))

    position = index_of(teams)
    data = {}
    for team_a, team_b in sorted(pairs):
        overall, by_season, by_stage, by_ground = metrics.rivalry_record(matches, team_a, team_b)
        last = metrics.rivalry_last_meetings(matches, team_a, team_b)
        highest, lowest = metrics.rivalry_totals(deliveries, matches, team_a, team_b)
        batting, bowling = metrics.rivalry_top_players(deliveries, matches, team_a, team_b)
        totals_columns = ["score", "overs", "batting_team_name", "season", "venue", "date", "match_id"]
        data[str(position[team_a]) + "|" + str(position[team_b])] = {
            "overall": [overall["played"], overall[team_a], overall[team_b], overall["no_result"]],
            "seasons": table_rows(by_season, ["season", "played", team_a, team_b, "no_result"]),
            "stages": table_rows(by_stage, ["stage", "played", team_a, team_b, "no_result"]),
            "grounds": table_rows(by_ground, ["venue", "played", team_a, team_b, "no_result"]),
            "last": table_rows(last, ["match_id", "date", "season", "venue", "stage", "winner", "margin"]),
            "high": table_rows(highest, totals_columns),
            "low": table_rows(lowest, totals_columns),
            "bat": table_rows(batting, ["batter", "team", "innings", "runs", "balls_faced", "strike_rate", "average"]),
            "bowl": table_rows(bowling, ["bowler", "team", "matches", "wickets", "overs", "economy"]),
        }
    return data


# ---------------------------------------------------------------------------
# Matchups and player-vs-team records
# ---------------------------------------------------------------------------
def matchup_data(deliveries, players, teams):
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
        "matchups": table_rows(matchups, ["b", "w", "balls", "runs", "dismissals", "dots", "fours", "sixes"]),
        "bat_vs": table_rows(batting, ["p", "t", "innings", "runs", "balls_faced", "dismissals", "sixes"]),
        "bowl_vs": table_rows(bowling, ["p", "t", "matches", "wickets", "legal_balls", "runs_conceded"]),
        "out_kinds": kinds,
        "outs": table_rows(outs, ["p", "k", "times"]),
    }


# ---------------------------------------------------------------------------
# Grounds
# ---------------------------------------------------------------------------
def ground_data(matches, deliveries, venues, teams):
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
        "team_ground": table_rows(at_ground, ["t", "v", "season", "played", "wins"]),
        "fortress": table_rows(fortress, ["team", "home_grounds", "home_played", "home_win_pct",
                                          "away_played", "away_win_pct", "fortress_index"]),
    }


# ---------------------------------------------------------------------------
# Specialists, Impact Player era, trends
# ---------------------------------------------------------------------------
def specialist_data(matches, deliveries, teams):
    """Phase leaders (all seasons and each season), finishers and partnerships."""
    leaders = {}
    for season in ["all"] + sorted(matches["season"].unique()):
        for phase in PHASES:
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


def impact_data(matches, deliveries, impact):
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


def points_note(table):
    """A note when some teams have fewer league matches: a match abandoned before a ball is not in the data."""
    most = table["played"].max()
    short = table[table["played"] < most]
    if len(short) == 0:
        return ""
    return (", ".join(short["team"]) + " played " + str(short["played"].min()) + " league matches in the data, "
            "the others " + str(most) + ": a match abandoned without a ball being bowled is not in the "
            "ball-by-ball data, so their points can be lower than the official table.")


def trend_data(matches, deliveries, players, chase_model_file):
    """Scoring inflation, points tables, the chase model weights and season impact scores."""
    inflation = metrics.scoring_inflation(deliveries, matches)
    points = {}
    for season in sorted(matches["season"].unique()):
        table = metrics.points_table(deliveries, matches, season)
        points[str(season)] = {
            "rows": table_rows(table, ["position", "team", "played", "won", "lost", "no_result", "points", "nrr"]),
            "note": points_note(table),
        }

    weights = {}            # saved by analysis.py, so the model is fitted only once
    if os.path.exists(chase_model_file):
        model_table = pd.read_csv(chase_model_file)
        weights = {term: float(weight) for term, weight in zip(model_table["term"], model_table["weight"])}

    impact = metrics.season_impact_scores(deliveries)
    impact["p"] = impact["player"].map(index_of(players))
    return {
        "inflation": table_rows(inflation, ["season", "matches", "avg_first_innings", "sixes_per_match", "run_rate"]),
        "points": points,
        "chase_model": weights,
        "impact_scores": table_rows(impact, ["p", "season", "team", "runs", "wickets",
                                             "batting_points", "bowling_points", "impact"]),
    }


# ---------------------------------------------------------------------------
# Pitch and player fit
# ---------------------------------------------------------------------------
def pitch_periods(matches):
    """The periods you can pick: all seasons, the Impact Player era, then each season (newest first)."""
    seasons = sorted(matches["season"].unique())
    era = "2023-" + str(seasons[-1])
    periods = [["all", "All seasons " + metrics.season_range_text(matches), seasons],
               [era, "Impact Player era (" + era + ")", [s for s in seasons if s >= 2023]]]
    for season in reversed(seasons):
        periods.append([str(season), str(season), [season]])
    return periods


def pitch_data(matches, deliveries, players, venues):
    """Ground profiles for every period, how batters got out, and every player at every ground."""
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

        # % of dismissals of each kind at each ground, next to the league in the same seasons
        part = outs[outs["season"].isin(seasons)]
        league = part.groupby("dismissal_kind")["count"].sum()
        league_pct = league / league.sum() * 100
        here = part.groupby(["venue", "dismissal_kind"])["count"].sum().reset_index()
        here["pct"] = here["count"] / here.groupby("venue")["count"].transform("sum") * 100
        dismissals[key] = [[venue_position[row["venue"]], kinds.index(row["dismissal_kind"]), int(row["count"]),
                            round(float(row["pct"]), 1), round(float(league_pct[row["dismissal_kind"]]), 1)]
                           for row in here.to_dict("records")]

    all_batting = metrics.player_ground_batting(deliveries, matches)
    all_bowling = metrics.player_ground_bowling(deliveries, matches)
    fielding = metrics.player_ground_fielding(deliveries, matches)
    batting = all_batting[(all_batting["balls"] >= FIT_MIN_BALLS) & all_batting["batter"].isin(player_position)].copy()
    bowling = all_bowling[(all_bowling["legal_balls"] >= FIT_MIN_BALLS) & all_bowling["bowler"].isin(player_position)].copy()
    fielding = fielding[(fielding["matches"] >= FIT_MIN_MATCHES) & fielding["player"].isin(player_position)].copy()
    batting["p"] = batting["batter"].map(player_position)
    bowling["p"] = bowling["bowler"].map(player_position)
    fielding["p"] = fielding["player"].map(player_position)
    for table in [batting, bowling, fielding]:
        table["v"] = table["venue"].map(venue_position)

    best = {}
    for venue in venues:
        bat, bowl = metrics.best_ground_fits(all_batting, all_bowling, venue)
        best[str(venue_position[venue])] = {
            "bat": table_rows(bat, ["batter", "balls", "strike_rate", "else_strike_rate", "strike_rate_diff"]),
            "bowl": table_rows(bowl, ["bowler", "legal_balls", "economy", "else_economy", "economy_diff"])}

    return {
        "pitch_thresholds": [metrics.PITCH_HIGH, metrics.PITCH_LOW],
        "pitch_periods": [[key, label] for key, label, seasons in periods],
        "pitch": profiles, "pitch_phase": phases, "pitch_out_kinds": kinds, "pitch_outs": dismissals,
        "fit_bat": table_rows(batting, ["p", "v", "innings", "balls", "runs", "outs", "fours", "sixes", "dots",
                                        "else_balls", "else_runs", "else_outs", "else_fours", "else_sixes", "else_dots"]),
        "fit_bowl": table_rows(bowling, ["p", "v", "matches", "legal_balls", "runs", "wickets", "dots",
                                         "else_legal_balls", "else_runs", "else_wickets", "else_dots"]),
        "fit_field": table_rows(fielding, ["p", "v", "matches", "catches", "run_outs", "stumpings",
                                           "else_matches", "else_catches", "else_run_outs", "else_stumpings"]),
        "fit_best": best,
    }


# ---------------------------------------------------------------------------
# Player, ground and team pages
# ---------------------------------------------------------------------------
def analyst_notes():
    """data/analyst_notes.csv (page, name, note) as {"player|V Kohli": "the note"}. No file = no notes."""
    if not os.path.exists(NOTES_FILE):
        return {}
    notes = pd.read_csv(NOTES_FILE, dtype=str).fillna("")
    return {row["page"].strip() + "|" + row["name"].strip(): row["note"].strip()
            for row in notes.to_dict("records") if row["note"].strip()}


def site_data(matches, deliveries, players, venues, squads):
    """Phase splits, the last 10 innings and spells, awards, fielding, squads and home grounds."""
    player_position = index_of(players)
    df = metrics.add_ball_columns(deliveries)

    # Phase splits: batting [player, phase, runs, balls, outs]; bowling [player, phase, legal balls, runs, wickets]
    faced = df[df["is_ball_faced"]]
    bat = faced.groupby(["batter", "phase"]).agg(runs=("batsman_runs", "sum"), balls=("batsman_runs", "size")).reset_index()
    outs = df[df["is_wicket"]].groupby(["player_dismissed", "phase"]).size().reset_index(name="outs")
    bat = bat.merge(outs.rename(columns={"player_dismissed": "batter"}), on=["batter", "phase"], how="left").fillna({"outs": 0})
    bat["p"] = bat["batter"].map(player_position)
    bat["ph"] = bat["phase"].map(PHASES.index)
    bowl = df.groupby(["bowler", "phase"]).agg(
        legal=("is_legal_ball", "sum"),
        runs=("runs_conceded", "sum"),
        wickets=("is_bowler_wicket", "sum"),
    ).reset_index()
    bowl["p"] = bowl["bowler"].map(player_position)
    bowl["ph"] = bowl["phase"].map(PHASES.index)

    # Last 10 innings: [date, opponent, runs, balls, out (1/0), match id]
    innings = metrics.batting_innings(deliveries)
    dismissed = set(zip(df.loc[df["is_wicket"], "match_id"], df.loc[df["is_wicket"], "player_dismissed"]))
    last_bat = {}
    for batter, rows in innings.groupby("batter"):
        last_bat[str(player_position[batter])] = [
            [row["date"].strftime("%Y-%m-%d"), row["bowling_team_franchise"], int(row["runs"]), int(row["balls"]),
             1 if (row["match_id"], batter) in dismissed else 0, int(row["match_id"])]
            for row in rows.tail(LAST_N).to_dict("records")]

    # Last 10 bowling matches: [date, opponent, legal balls, runs, wickets, match id]
    spells = df.groupby(["bowler", "match_id", "date"]).agg(
        opponent=("batting_team_franchise", "first"),
        legal=("is_legal_ball", "sum"),
        runs=("runs_conceded", "sum"),
        wickets=("is_bowler_wicket", "sum"),
    ).reset_index().sort_values(["bowler", "date", "match_id"])
    last_bowl = {}
    for bowler, rows in spells.groupby("bowler"):
        last_bowl[str(player_position[bowler])] = [
            [row["date"].strftime("%Y-%m-%d"), row["opponent"], int(row["legal"]), int(row["runs"]),
             int(row["wickets"]), int(row["match_id"])]
            for row in rows.tail(LAST_N).to_dict("records")]

    potm = matches[matches["player_of_match"] != ""]["player_of_match"].value_counts()
    fielding = metrics.fielding_events(deliveries).groupby(["player", "event"]).size().unstack(fill_value=0)
    field = {str(player_position[player]): [int(fielding.loc[player].get(event, 0)) for event in ["catch", "run_out", "stumping"]]
             for player in fielding.index if player in player_position}

    home = {}
    for team, grounds in metrics.HOME_GROUNDS.items():
        for ground in grounds:
            if ground in venues:
                home.setdefault(ground, []).append(team)

    return {
        "phases": PHASES,
        "bat_phase": table_rows(bat, ["p", "ph", "runs", "balls", "outs"]),
        "bowl_phase": table_rows(bowl, ["p", "ph", "legal", "runs", "wickets"]),
        "last_bat": last_bat, "last_bowl": last_bowl,
        "potm": {str(player_position[name]): int(count) for name, count in potm.items() if name in player_position},
        "field": field,
        "squads": {row["player"]: row["team"] for row in squads.to_dict("records")},
        "home": home,
        "team": team_data(matches, deliveries, venues),
        "notes": analyst_notes(), "note_author": NOTE_AUTHOR,
    }


def team_data(matches, deliveries, venues):
    """Everything the team pages and the two-teams-at-one-ground comparison need."""
    teams = sorted(set(matches["team1_franchise"]) | set(matches["team2_franchise"]))
    team_position = index_of(teams)
    venue_position = index_of(venues)

    def pair_key(team, venue):
        return str(team_position[team]) + "|" + str(venue_position[venue])

    # Season by season: [season, name used that season, played, won, win %, position, points, finish]
    names = metrics.team_names_by_season(matches)
    name_of = {(team, int(season)): name for team, season, name in zip(names["team"], names["season"], names["name"])}
    seasons = {}
    for row in metrics.team_season_summary(deliveries, matches).to_dict("records"):
        season = int(row["season"])
        seasons.setdefault(row["team"], []).append(
            [season, name_of.get((row["team"], season), row["team"]), int(row["played"]), int(row["won"]),
             float(row["win_pct"]), clean_value(row["position"]), clean_value(row["points"]), row["stage"]])

    phase_parts = metrics.team_phase_components(deliveries)
    phase_parts["t"] = phase_parts["team"].map(team_position)
    phase_parts["ph"] = phase_parts["phase"].map(PHASES.index)
    for column in ["bat_expected", "bowl_expected"]:
        phase_parts[column] = phase_parts[column].round(1)

    style = metrics.team_style(deliveries, matches)
    style_rows = {row["team"]: [int(row[column]) for column in style.columns[1:]] for row in style.to_dict("records")}

    batting, bowling = metrics.team_top_players(deliveries)
    top_bat = {team: table_rows(rows, ["batter", "innings", "runs", "strike_rate", "average"])
               for team, rows in batting.groupby("team")}
    top_bowl = {team: table_rows(rows, ["bowler", "matches", "wickets", "economy"]) for team, rows in bowling.groupby("team")}
    extremes = {team: table_rows(rows, ["side", "kind", "margin", "opponent", "date", "venue", "match_id"])
                for team, rows in metrics.team_extremes(matches).groupby("team")}

    ground = metrics.team_ground_stats(deliveries, matches)
    ground["t"] = ground["team"].map(team_position)
    ground["v"] = ground["venue"].map(venue_position)
    ground_phase = metrics.team_ground_phases(deliveries, matches)
    ground_phase["t"] = ground_phase["team"].map(team_position)
    ground_phase["v"] = ground_phase["venue"].map(venue_position)
    ground_phase["ph"] = ground_phase["phase"].map(PHASES.index)
    ground_bat, ground_bowl = metrics.team_ground_top_players(deliveries, matches)
    tg_bat = {pair_key(team, venue): table_rows(rows, ["batter", "innings", "runs", "strike_rate"])
              for (team, venue), rows in ground_bat.groupby(["team", "venue"])}
    tg_bowl = {pair_key(team, venue): table_rows(rows, ["bowler", "matches", "wickets", "economy"])
               for (team, venue), rows in ground_bowl.groupby(["team", "venue"])}

    return {
        "seasons": seasons,
        "phases": table_rows(phase_parts, ["t", "season", "ph", "bat_runs", "bat_balls", "bat_expected",
                                           "bowl_runs", "bowl_balls", "bowl_expected"]),
        "style": style_rows, "top_bat": top_bat, "top_bowl": top_bowl, "extremes": extremes,
        "ground": table_rows(ground, ["t", "v", "played", "won", "runs_for", "balls_for", "wickets_lost", "highest",
                                      "runs_against", "balls_against", "wickets_taken", "bat_first_played", "bat_first_won",
                                      "first_innings_runs", "chase_played", "chase_won"]),
        "ground_phase": table_rows(ground_phase, ["t", "v", "ph", "runs", "balls", "runs_against", "balls_against"]),
        "ground_bat": tg_bat, "ground_bowl": tg_bowl,
    }


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
def records_data(deliveries):
    """Every record row; the page keeps the top 10 for the chosen season."""
    fifties = metrics.fastest_milestones(deliveries, 50)
    fifties["date"] = date_text(fifties["date"])
    hundreds = metrics.fastest_milestones(deliveries, 100)
    hundreds["date"] = date_text(hundreds["date"])
    bowling = metrics.best_bowling_figures(deliveries)
    bowling["date"] = date_text(bowling["date"])
    milestone_columns = ["batter", "season", "balls", "batting_team", "against", "date", "match_id"]
    return {"records": {
        "fifties": table_rows(fifties, milestone_columns),
        "hundreds": table_rows(hundreds, milestone_columns),
        "bowling": table_rows(bowling, ["bowler", "season", "wickets", "runs", "bowling_team", "against", "date", "match_id"]),
        "fielding": table_rows(metrics.fielding_records(deliveries, by_season=True),
                               ["player", "season", "catches", "stumpings", "run_outs"]),
    }}


def analyst_data(matches, deliveries, impact, chase_model_file):
    """Everything the analyst views need, as one dictionary."""
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
    data.update(records_data(deliveries))
    return data
