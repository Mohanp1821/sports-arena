"""
test_facts.py
-------------
Fact-check tests: compare our results with well-known IPL records.
If a cleaning step or formula is wrong, one of these checks will fail.

Run it from the project folder with:
    python tests/test_facts.py

Each check uses a plain "assert": if the condition is False, Python stops
and shows the message.
"""

import os
import sys

# Let Python find our src/ folder so we can import metrics.py.
TESTS_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(TESTS_FOLDER)
sys.path.append(os.path.join(PROJECT_FOLDER, "src"))

import metrics
import predict


# Official Orange Cap and Purple Cap winners (source: iplt20.com records).
# Names are written the way this dataset writes them (Cricsheet names from 2020).
OFFICIAL_CAPS = {
    # season: (orange cap, official runs, purple cap, official wickets)
    2008: ("SE Marsh", 616, "Sohail Tanvir", 22),
    2009: ("ML Hayden", 572, "RP Singh", 23),
    2010: ("SR Tendulkar", 618, "PP Ojha", 21),
    2011: ("CH Gayle", 608, "SL Malinga", 28),
    2012: ("CH Gayle", 733, "M Morkel", 25),
    2013: ("MEK Hussey", 733, "DJ Bravo", 32),
    2014: ("RV Uthappa", 660, "MM Sharma", 23),
    2015: ("DA Warner", 562, "DJ Bravo", 26),
    2016: ("V Kohli", 973, "B Kumar", 23),
    2017: ("DA Warner", 641, "B Kumar", 26),
    2018: ("KS Williamson", 735, "AJ Tye", 24),
    2019: ("DA Warner", 692, "Imran Tahir", 26),
    2020: ("KL Rahul", 670, "K Rabada", 30),
    2021: ("RD Gaikwad", 635, "HV Patel", 32),
    2022: ("JC Buttler", 863, "YS Chahal", 27),
    2023: ("Shubman Gill", 890, "Mohammed Shami", 28),
    2024: ("V Kohli", 741, "HV Patel", 24),
    2025: ("B Sai Sudharsan", 759, "M Prasidh Krishna", 25),
    2026: ("V Suryavanshi", 776, "K Rabada", 29),
}

# Official IPL champions (source: iplt20.com), as today's franchise names.
OFFICIAL_CHAMPIONS = {
    2008: "Rajasthan Royals", 2009: "Deccan Chargers", 2010: "Chennai Super Kings",
    2011: "Chennai Super Kings", 2012: "Kolkata Knight Riders", 2013: "Mumbai Indians",
    2014: "Kolkata Knight Riders", 2015: "Mumbai Indians", 2016: "Sunrisers Hyderabad",
    2017: "Mumbai Indians", 2018: "Chennai Super Kings", 2019: "Mumbai Indians",
    2020: "Mumbai Indians", 2021: "Chennai Super Kings", 2022: "Gujarat Titans",
    2023: "Chennai Super Kings", 2024: "Kolkata Knight Riders", 2025: "Royal Challengers Bengaluru",
    2026: "Royal Challengers Bengaluru",
}

# We allow a difference of up to 2 runs, because a few ball-by-ball scorecards
# miss a delivery compared with the official scorecard.
RUN_TOLERANCE = 2


def test_dataset_size(matches, deliveries):
    """The cleaned data must keep every match and every ball of the merged dataset."""
    assert len(matches) == 1243, "expected 1,243 matches, got " + str(len(matches))
    assert len(deliveries) == 295729, "expected 295,729 balls, got " + str(len(deliveries))
    assert matches["season"].nunique() == 19, "expected 19 seasons"
    assert metrics.season_range_text(matches) == "2008-2026"
    assert matches["no_result"].sum() == 9, "expected 9 no-result matches"
    print("PASS  dataset size: 1,243 matches, 295,729 balls, 19 seasons (2008-2026), 9 no-results")


def test_franchises(matches, deliveries):
    """Season names are kept for display; the franchise column joins renamed teams."""
    season_2015 = matches[matches["season"] == 2015]
    assert "Delhi Daredevils" in set(season_2015["team1"]) | set(season_2015["team2"]), \
        "the 2015 team name should still be Delhi Daredevils"
    pairs = set(zip(matches["team1"], matches["team1_franchise"])) | set(zip(matches["team2"], matches["team2_franchise"]))
    assert ("Delhi Daredevils", "Delhi Capitals") in pairs
    assert ("Kings XI Punjab", "Punjab Kings") in pairs
    assert ("Royal Challengers Bangalore", "Royal Challengers Bengaluru") in pairs
    assert ("Deccan Chargers", "Deccan Chargers") in pairs, "Deccan Chargers is not Sunrisers Hyderabad"
    # Every ball's batting franchise must agree with the matches table.
    assert deliveries["batting_team_franchise"].isna().sum() == 0
    print("PASS  franchises: Delhi Daredevils -> Delhi Capitals, Kings XI Punjab -> Punjab Kings, "
          "RCB Bangalore -> Bengaluru; Deccan Chargers kept separate")


def test_venues(matches):
    """One name and one city per ground across all 19 seasons."""
    wankhede = matches[matches["venue"] == "Wankhede Stadium"]
    assert wankhede["season"].min() == 2008 and wankhede["season"].max() == 2026, "Wankhede should span 2008-2026"
    assert "Feroz Shah Kotla" not in set(matches["venue"]), "Feroz Shah Kotla should be Arun Jaitley Stadium"
    assert matches.groupby("venue")["city"].nunique().max() == 1, "a ground has more than one city"
    assert (matches["city"].fillna("") == "").sum() == 0, "a match has no city"
    assert "Bangalore" not in set(matches["city"])
    print("PASS  venues: Wankhede spans 2008-2026, " + str(matches["venue"].nunique())
          + " grounds, one city each")


def test_player_names(deliveries, matches):
    """One name per player across Kaggle (2008-19) and Cricsheet (2020-26)."""
    gill = deliveries[deliveries["batter"] == "Shubman Gill"]
    assert sorted(gill["season"].unique()) == list(range(2018, 2027)), "Shubman Gill should bat in every season 2018-2026"
    for old_name in ["S Gill", "J Archer", "P Shaw"]:
        assert (deliveries["batter"] == old_name).sum() == 0, old_name + " was not renamed"
    # Suryakumar Yadav played for Mumbai 2018-19 as "AS Yadav" in Kaggle; now SA Yadav.
    mi_2018 = deliveries[(deliveries["season"] == 2018) & (deliveries["batting_team"] == "Mumbai Indians")]
    assert "SA Yadav" in set(mi_2018["batter"]) and "AS Yadav" not in set(mi_2018["batter"])
    # The AS Yadav of Deccan Chargers 2008 is a different person and keeps his name.
    deccan_2008 = deliveries[(deliveries["season"] == 2008) & (deliveries["batting_team"] == "Deccan Chargers")]
    assert "AS Yadav" in set(deccan_2008["batter"]), "AS Yadav (Deccan 2008) must not be renamed"
    # Two different people called Harmeet Singh stay apart.
    assert "Harmeet Singh (2)" in set(deliveries["bowler"]), "Harmeet Singh (2) must be kept"
    # "Ankit Sharma" at Rajasthan 2018 is a real, different player from Abhishek Sharma.
    rr_2018 = deliveries[(deliveries["season"] == 2018) & (deliveries["batting_team"] == "Rajasthan Royals")]
    dd_2018 = deliveries[(deliveries["season"] == 2018) & (deliveries["batting_team"] == "Delhi Daredevils")]
    players_rr = set(rr_2018["batter"]) | set(rr_2018["non_striker"])
    assert "Ankit Sharma" in players_rr or "Ankit Sharma" in set(deliveries[(deliveries["season"] == 2018)
        & (deliveries["bowling_team"] == "Rajasthan Royals")]["bowler"]), "RR's Ankit Sharma must keep his name"
    assert "Ankit Sharma" not in set(dd_2018["batter"]) | set(dd_2018["non_striker"]), "DD's 'Ankit Sharma' is Abhishek Sharma"
    print("PASS  player names: Shubman Gill 2018-2026 under one name; AS Yadav, Ankit Sharma and Harmeet Singh traps handled")


def test_impact_players(impact):
    """Impact Player substitutions come from the Cricsheet files (rule started in 2023)."""
    assert len(impact) == 557, "expected 557 Impact Player substitutions, got " + str(len(impact))
    assert impact["season"].min() == 2023, "the Impact Player rule started in 2023"
    print("PASS  Impact Players: 557 substitutions, 2023-2026")


def test_no_extras_in_batter_runs(deliveries):
    """Cricket rule: no batter runs on wides, byes or leg-byes."""
    extras = (deliveries["wide_runs"] > 0) | (deliveries["bye_runs"] > 0) | (deliveries["legbye_runs"] > 0)
    bad_rows = deliveries[extras & (deliveries["batsman_runs"] > 0)]
    assert len(bad_rows) == 0, str(len(bad_rows)) + " balls still double-count extras"
    print("PASS  no extras counted as batter runs")


def test_cap_winners(deliveries):
    """Our Orange/Purple Cap winners must match the official ones."""
    caps = metrics.cap_winners(deliveries)
    assert len(caps) == 19, "expected caps for 19 seasons"
    for i in range(len(caps)):
        row = caps.iloc[i]
        season = row["season"]
        orange, runs, purple, wickets = OFFICIAL_CAPS[season]

        assert row["orange_cap"] == orange, str(season) + " Orange Cap should be " + orange + ", got " + row["orange_cap"]
        difference = abs(row["runs"] - runs)
        assert difference <= RUN_TOLERANCE, str(season) + " runs " + str(row["runs"]) + " vs official " + str(runs)
        assert row["purple_cap"] == purple, str(season) + " Purple Cap should be " + purple + ", got " + row["purple_cap"]
        assert row["wickets"] == wickets, str(season) + " wickets " + str(row["wickets"]) + " vs official " + str(wickets)

        note = "" if difference == 0 else "  (runs differ by " + str(difference) + ")"
        print("PASS  " + str(season) + " caps: " + orange + " " + str(row["runs"]) + " / " + purple
              + " " + str(row["wickets"]) + note)


def test_formulas():
    """Check the formulas on a tiny hand-made example we can work out on paper."""
    import pandas as pd
    # 4 balls by bowler "B" to batter "A":
    #   ball 1: 4 runs          ball 2: a wide (1 run)
    #   ball 3: 1 leg-bye       ball 4: bowled (out)
    tiny = pd.DataFrame({
        "match_id": [1, 1, 1, 1], "inning": [1, 1, 1, 1], "over": [1, 1, 1, 1],
        "ball": [1, 2, 3, 4], "batter": ["A"] * 4, "bowler": ["B"] * 4,
        "batting_team": ["X"] * 4, "bowling_team": ["Y"] * 4,
        "batsman_runs": [4, 0, 0, 0], "wide_runs": [0, 1, 0, 0],
        "noball_runs": [0, 0, 0, 0], "bye_runs": [0, 0, 0, 0],
        "legbye_runs": [0, 0, 1, 0], "total_runs": [4, 1, 1, 0],
        "player_dismissed": [None, None, None, "A"],
        "dismissal_kind": [None, None, None, "bowled"],
        "is_super_over": [0, 0, 0, 0], "season": [2020] * 4,
        "date": pd.to_datetime(["2020-01-01"] * 4),
    })
    bat = metrics.batting_stats(tiny).iloc[0]
    assert bat["runs"] == 4 and bat["balls_faced"] == 3, "wide must not count as faced"
    assert bat["strike_rate"] == round(4 / 3 * 100, 2)
    assert bat["average"] == 4.0

    bowl = metrics.bowling_stats(tiny).iloc[0]
    assert bowl["legal_balls"] == 3, "wide is not a legal ball"
    assert bowl["runs_conceded"] == 5, "4 + wide 1; the leg-bye is not the bowler's"
    assert bowl["wickets"] == 1
    assert bowl["economy"] == 10.0, "5 runs in half an over = 10 per over"
    print("PASS  formulas on a hand-made example")


def test_champions(matches):
    """The winner of each season's final must be the official champion."""
    champions = metrics.season_champions(matches)
    assert len(champions) == 19, "expected 19 champions"
    for i in range(len(champions)):
        row = champions.iloc[i]
        official = OFFICIAL_CHAMPIONS[row["season"]]
        assert row["champion"] == official, str(row["season"]) + " champion should be " + official
    # The final is also labelled as a playoff match by prepare_data.py.
    finals = matches[matches["playoff_name"] == "Final"]
    assert len(finals) == 19, "expected 19 finals"
    print("PASS  all 19 champions match the official list (2008-2026)")


def test_prediction_model(matches):
    """Check the prediction maths on small examples we can work out on paper."""
    import pandas as pd
    # Form score: 600, 400, 300 runs -> (3*600 + 2*400 + 1*300) / 6 = 483.3
    table = pd.DataFrame({"batter": ["A", "A", "A"], "season": [2017, 2018, 2019],
                          "runs": [300, 400, 600]})
    form = predict.weighted_form(table, "batter", "runs", 2019)
    assert form.iloc[0]["form"] == 483.3, "weighted form should be 483.3"

    # Season format: 10 teams -> 70 league games, 14 per team; 8 teams -> 56, 14 per team.
    teams = predict.season_teams(matches, 2026)
    fixtures = predict.league_fixtures(matches, 2025, teams)
    assert len(fixtures) == 70, "10-team format should have 70 league matches"
    for team in teams:
        games = [f for f in fixtures if team in f]
        assert len(games) == 14, team + " should play 14 league matches"
    group_a, group_b = predict.make_groups(matches, 2025, teams)
    assert len(set(group_a) | set(group_b)) == 10
    eight = predict.season_teams(matches, 2021)
    assert len(predict.league_fixtures(matches, 2020, eight)) == 56

    # Simulation: title chances of all teams must add up to 100%, playoff chances to 400%.
    strengths = predict.team_strengths(matches, 2026, teams)
    chances = predict.title_chances(teams, fixtures, predict.model_a_chances(strengths), simulations=500)
    assert abs(chances["title_pct"].sum() - 100) < 0.5, "title chances should add up to 100%"
    assert abs(chances["playoff_pct"].sum() - 400) < 0.5, "4 playoff places -> 400%"

    # Scoring on a worked example: chances 0.8 and 0.4 for team 1; team 1 won the first, lost the second.
    scores = predict.match_scores([0.8, 0.4], [1, 0])
    assert scores["accuracy_pct"] == 100.0
    assert scores["brier"] == round(((0.8 - 1) ** 2 + (0.4 - 0) ** 2) / 2, 4)     # (0.04 + 0.16) / 2 = 0.1
    import math
    assert scores["log_loss"] == round((-math.log(0.8) - math.log(0.6)) / 2, 4)
    print("PASS  prediction maths: weighted form, season format (70 games, 14 each), title chances, scoring")


def test_dashboard_data(matches, deliveries):
    """The interactive dashboard's data must give the same answers as metrics.py."""
    import build_report
    data = build_report.explorer_data(matches, deliveries)
    assert len(data["matches"]) == 1243, "the dashboard should have all 1,243 matches"
    assert len(data["champions"]) == 19, "the dashboard should have 19 champions"

    # Kohli's 2016 runs, added up the same way the page's JavaScript does it.
    # Columns of a batting row: [player, season, team, runs, balls, sixes, innings]
    kohli_2016 = 0
    for row in data["batting"]:
        if row[0] == "V Kohli" and row[1] == 2016:
            kohli_2016 += row[3]
    assert kohli_2016 == 973, "Kohli 2016 should be 973 runs, got " + str(kohli_2016)
    print("PASS  interactive dashboard data (1,243 matches, 19 champions, Kohli 2016 = 973)")


def test_analyst_views(matches, deliveries, impact):
    """Checks on the Phase 2 analyst views: totals that must agree, and small worked examples."""
    import pandas as pd

    # Rivalry: season rows and stage rows must add up to the overall record.
    overall, by_season, by_stage, by_ground = metrics.rivalry_record(matches, "Chennai Super Kings", "Mumbai Indians")
    assert overall["Chennai Super Kings"] + overall["Mumbai Indians"] + overall["no_result"] == overall["played"]
    assert by_season["played"].sum() == overall["played"] and by_stage["played"].sum() == overall["played"]
    assert by_ground["played"].sum() == overall["played"]

    # Matchup on a hand-made example: 4 balls, then a wide, then bowled.
    tiny = pd.DataFrame({
        "match_id": [1] * 6, "inning": [1] * 6, "over": [1] * 6, "ball": [1, 2, 3, 4, 5, 6],
        "batter": ["A"] * 6, "non_striker": ["C"] * 6, "bowler": ["B"] * 6,
        "batsman_runs": [4, 0, 6, 1, 0, 0], "wide_runs": [0, 0, 0, 0, 1, 0], "noball_runs": [0] * 6,
        "bye_runs": [0] * 6, "legbye_runs": [0] * 6, "total_runs": [4, 0, 6, 1, 1, 0],
        "player_dismissed": [None] * 5 + ["A"], "dismissal_kind": [None] * 5 + ["bowled"],
        "is_super_over": [0] * 6, "season": [2026] * 6,
    })
    row = metrics.batter_vs_bowler(tiny, "A", "B").iloc[0]
    assert row["balls"] == 5, "the wide is not a ball faced"
    assert row["runs"] == 11 and row["dismissals"] == 1
    assert row["dot_pct"] == 40.0, "2 dots in 5 balls"
    assert row["boundary_pct"] == 40.0, "a four and a six in 5 balls"
    assert row["runs_per_dismissal"] == 11.0

    # Partnerships: in every innings, the partnership runs add up to the team total.
    stands = metrics.partnerships(deliveries, matches)
    by_innings = stands.groupby(["match_id", "inning"])["runs"].sum()
    totals = metrics.innings_totals(deliveries, matches).set_index(["match_id", "inning"])["runs"]
    assert (by_innings.sort_index() == totals.sort_index()).all(), "partnership runs must add up to the innings total"

    # Points tables: the top 4 must be the 4 playoff teams. 2008 is the one known
    # exception: Delhi v Kolkata was abandoned without a ball, so it is not in the
    # ball-by-ball data and Delhi has 1 point fewer than in the official table.
    for season in range(2008, 2027):
        table = metrics.points_table(deliveries, matches, season)
        playoffs = matches[(matches["season"] == season) & (matches["stage"] == "Playoff")]
        playoff_teams = set(playoffs["team1_franchise"]) | set(playoffs["team2_franchise"])
        if season == 2008:
            assert table[table["team"] == "Delhi Capitals"]["played"].iloc[0] == 13
            continue
        assert set(table["team"].head(4)) == playoff_teams, str(season) + " top 4 does not match the playoff teams"

    # Home fortress index = home win % minus away win %.
    fortress = metrics.home_fortress_index(matches)
    difference = (fortress["home_win_pct"] - fortress["away_win_pct"]).round(1)
    assert (difference == fortress["fortress_index"]).all()

    # Impact Player choices: every one of the 557 substitutions gets a role.
    choices = metrics.impact_player_choices(impact, deliveries, matches)
    assert len(choices) == 557 and choices["role"].notna().all()

    # Chase model: needing more runs (same balls and wickets) can only lower the chance.
    model = metrics.win_probability_model(metrics.chase_states(deliveries, matches))
    chances = [metrics.win_probability(model, runs, 60, 7) for runs in [20, 60, 100, 140]]
    assert chances == sorted(chances, reverse=True), "win chance should fall as runs needed rise"
    assert 0 < chances[-1] < chances[0] < 100

    # Impact scores: batting points of a player with no balls in a phase are 0, and
    # every score is batting points + bowling points.
    scores = metrics.season_impact_scores(deliveries)
    assert ((scores["batting_points"] + scores["bowling_points"]).round(1) - scores["impact"]).abs().max() < 0.11
    print("PASS  analyst views: rivalry totals, matchup example, partnerships = innings totals, "
          "points tables (top 4 = playoff teams 2009-2026), fortress index, Impact Player roles, chase model")


def test_dashboard_analyst_data(matches, deliveries, impact):
    """The analyst views on the page must give the same numbers as metrics.py."""
    import dashboard_data
    data = dashboard_data.analyst_data(matches, deliveries, impact, "missing-file.csv")
    kohli = data["players"].index("V Kohli")
    bumrah = data["players"].index("JJ Bumrah")
    row = [r for r in data["matchups"] if r[0] == kohli and r[1] == bumrah][0]
    expected = metrics.batter_vs_bowler(deliveries, "V Kohli", "JJ Bumrah").iloc[0]
    assert row[2] == expected["balls"] and row[3] == expected["runs"] and row[4] == expected["dismissals"]
    csk = data["teams"].index("Chennai Super Kings")
    mi = data["teams"].index("Mumbai Indians")
    key = str(min(csk, mi)) + "|" + str(max(csk, mi))
    assert data["rivalry"][key]["overall"][0] == len(metrics.rivalry_matches(matches, "Chennai Super Kings", "Mumbai Indians"))
    assert len(data["points"]) == 19
    # Pitch view: the page's Chepauk row (all seasons) must equal metrics.pitch_profile.
    chepauk = data["venues"].index("MA Chidambaram Stadium, Chepauk")
    page_row = [r for r in data["pitch"]["all"] if r[0] == chepauk][0]
    profile = metrics.pitch_profile(deliveries, matches)
    assert page_row[3] == profile[profile["venue"] == "MA Chidambaram Stadium, Chepauk"]["runs_index"].iloc[0]
    print("PASS  dashboard analyst data matches metrics.py (Kohli v Bumrah, CSK v MI, 19 points tables, Chepauk pitch)")


def test_model_b(matches, deliveries, impact):
    """Model B: fair chances, and the backtest only learns from EARLIER seasons."""
    import predict_ml
    elo = predict_ml.elo_at_season_starts(matches)
    assert abs(sum(elo[2027].values()) / len(elo[2027]) - 1500) < 60, "Elo ratings should stay around 1500"
    squads = predict.load_squads(deliveries, impact, 2026)
    assert squads["team"].nunique() == 10, "the 2027 squads file should list 10 teams"
    strengths = predict_ml.squad_strengths(deliveries, impact, matches, squads)
    results = metrics.team_results(matches)
    infos = {season: predict_ml.season_start_info(matches, results, elo, strengths, season) for season in range(2009, 2022)}
    training = predict_ml.build_match_rows(matches, infos, range(2009, 2021))
    assert training["season"].max() == 2020, "training for 2021 must stop at 2020"
    # The pre-season form for 2021 must not use any 2021 match.
    before = results[results["season"] < 2021]
    mi_form = before[before["team"] == "Mumbai Indians"].tail(10)["won"].mean() * 100
    assert abs(infos[2021]["form"]["Mumbai Indians"] - mi_form) < 1e-9
    models = predict_ml.train_models(training)
    for name in models:
        p_ab = predict_ml.fair_chance(models[name], infos[2021], "Mumbai Indians", "Chennai Super Kings", "Wankhede Stadium")
        p_ba = predict_ml.fair_chance(models[name], infos[2021], "Chennai Super Kings", "Mumbai Indians", "Wankhede Stadium")
        assert abs(p_ab + p_ba - 1) < 1e-9, name + ": P(A beats B) + P(B beats A) must be 1"
    print("PASS  Model B: fair chances, 10 squads, training and features use only earlier seasons")


def test_site_data(matches, deliveries):
    """The player-page data (last 10 innings, phases) must agree with metrics.py."""
    import pandas as pd
    import dashboard_data
    players = sorted(set(deliveries["batter"]) | set(deliveries["bowler"]) | set(deliveries["non_striker"]))
    squads = pd.read_csv(os.path.join(PROJECT_FOLDER, "data", "squads_2027.csv"))
    data = dashboard_data.site_data(matches, deliveries, players, sorted(matches["venue"].unique()), squads)
    kohli = str(players.index("V Kohli"))
    innings = metrics.batting_innings(deliveries)
    last10 = innings[innings["batter"] == "V Kohli"].tail(10)
    assert [row[2] for row in data["last_bat"][kohli]] == list(last10["runs"]), "last 10 innings must match"
    # Phase runs add up to his career runs.
    career = metrics.batting_stats(deliveries)
    career_runs = career[career["batter"] == "V Kohli"]["runs"].iloc[0]
    assert sum(row[2] for row in data["bat_phase"] if row[0] == int(kohli)) == career_runs
    assert data["home"]["Wankhede Stadium"] == ["Mumbai Indians"]
    # Team pages: season wins add up to the franchise's wins; stages match the official champions.
    seasons = data["team"]["seasons"]["Chennai Super Kings"]
    results = metrics.team_results(matches)
    assert sum(row[3] for row in seasons) == int(results[results["team"] == "Chennai Super Kings"]["won"].sum())
    champion_years = [row[0] for row in seasons if row[7] == "Champion"]
    assert champion_years == [2010, 2011, 2018, 2021, 2023], "CSK title years"
    # Team at a ground: MI's wins at Wankhede equal team_at_ground's.
    venues = sorted(matches["venue"].unique())
    teams = sorted(set(matches["team1_franchise"]) | set(matches["team2_franchise"]))
    row = [r for r in data["team"]["ground"] if r[0] == teams.index("Mumbai Indians") and r[1] == venues.index("Wankhede Stadium")][0]
    at_ground = metrics.team_at_ground(matches, "Mumbai Indians", "Wankhede Stadium")
    assert row[2] == at_ground["played"].sum() and row[3] == at_ground["wins"].sum()
    # Phase indexes: across all teams, runs scored = league-expected runs (index 100), every season.
    phases = metrics.team_phase_components(deliveries)
    by_season = phases.groupby("season")[["bat_runs", "bat_expected"]].sum()
    assert ((by_season["bat_runs"] / by_season["bat_expected"] - 1).abs() < 1e-9).all()
    print("PASS  site data: Kohli's last 10 innings and phase runs match metrics.py; home grounds; team seasons, "
          "CSK title years, MI at Wankhede, team phase indexes = 100 league-wide")


def test_pitch_and_fit(matches, deliveries):
    """Pitch indexes, the here-vs-elsewhere split and fielding credits."""
    import pandas as pd

    # Indexes compare with the league in the same seasons, so the whole league is exactly 100 every season.
    parts = metrics.pitch_components(deliveries, matches)
    by_season = parts.groupby("season")[["runs", "exp_runs", "wickets", "exp_wickets"]].sum()
    assert ((by_season["runs"] / by_season["exp_runs"] - 1).abs() < 1e-9).all(), "league runs index must be 100"
    assert ((by_season["wickets"] / by_season["exp_wickets"] - 1).abs() < 1e-9).all(), "league wickets index must be 100"

    # One ground worked out directly: runs index = runs / expected runs x 100.
    chepauk = parts[parts["venue"] == "MA Chidambaram Stadium, Chepauk"]
    expected = round(chepauk["runs"].sum() / chepauk["exp_runs"].sum() * 100, 1)
    profile = metrics.profile_from_components(parts)
    assert profile[profile["venue"] == "MA Chidambaram Stadium, Chepauk"]["runs_index"].iloc[0] == expected
    assert metrics.pitch_label(106, 100).startswith("high-scoring")
    assert metrics.pitch_label(95, 90).startswith("low-scoring")

    # Here + elsewhere = all of the player's balls in the seasons he played at that ground.
    batting = metrics.player_ground_batting(deliveries, matches)
    row = batting[(batting["batter"] == "V Kohli") & (batting["venue"] == "M Chinnaswamy Stadium")].iloc[0]
    balls = metrics.add_venue(deliveries, matches)
    kohli = balls[(balls["batter"] == "V Kohli") & balls["is_ball_faced"]]
    seasons_here = kohli[kohli["venue"] == "M Chinnaswamy Stadium"]["season"].unique()
    assert row["balls"] + row["else_balls"] == len(kohli[kohli["season"].isin(seasons_here)])

    # Fielding on a hand-made example: a catch by a substitute is not credited; caught and
    # bowled goes to the bowler; a run out naming two fielders credits both.
    tiny = pd.DataFrame({
        "match_id": [1, 1, 1], "season": [2026] * 3, "inning": [1] * 3, "over": [1, 1, 1], "ball": [1, 2, 3],
        "batter": ["A", "B", "C"], "bowler": ["X", "X", "X"], "is_super_over": [0] * 3,
        "player_dismissed": ["A", "B", "C"], "dismissal_kind": ["caught", "caught and bowled", "run out"],
        "fielder": ["S (sub)", None, "Y, Z"]})
    events = metrics.fielding_events(tiny)
    assert len(events) == 3 and list(events["player"]) == ["X", "Y", "Z"]
    assert list(events["event"]) == ["catch", "run_out", "run_out"]
    print("PASS  pitch and player fit: league index = 100 each season, Chepauk index, label rules, "
          "here + elsewhere = all balls (Kohli at Chinnaswamy), fielding credits")


def main():
    matches, deliveries = metrics.load_processed_data()
    impact = metrics.load_impact_players()
    test_dataset_size(matches, deliveries)
    test_franchises(matches, deliveries)
    test_venues(matches)
    test_player_names(deliveries, matches)
    test_impact_players(impact)
    test_no_extras_in_batter_runs(deliveries)
    test_formulas()
    test_cap_winners(deliveries)
    test_champions(matches)
    test_prediction_model(matches)
    test_dashboard_data(matches, deliveries)
    test_analyst_views(matches, deliveries, impact)
    test_dashboard_analyst_data(matches, deliveries, impact)
    test_model_b(matches, deliveries, impact)
    test_pitch_and_fit(matches, deliveries)
    test_site_data(matches, deliveries)
    print("\nAll fact checks passed.")


if __name__ == "__main__":
    main()
