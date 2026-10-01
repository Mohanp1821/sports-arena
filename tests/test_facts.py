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
# Names are written the way this dataset writes them.
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
}

# Official IPL champions (source: iplt20.com), with this dataset's team names.
OFFICIAL_CHAMPIONS = {
    2008: "Rajasthan Royals", 2009: "Deccan Chargers", 2010: "Chennai Super Kings",
    2011: "Chennai Super Kings", 2012: "Kolkata Knight Riders", 2013: "Mumbai Indians",
    2014: "Kolkata Knight Riders", 2015: "Mumbai Indians", 2016: "Sunrisers Hyderabad",
    2017: "Mumbai Indians", 2018: "Chennai Super Kings", 2019: "Mumbai Indians",
}

# We allow a difference of up to 2 runs, because the ball-by-ball data can
# differ very slightly from the official scorecards (see EXPLANATION.md).
RUN_TOLERANCE = 2


def test_dataset_size(matches):
    """The cleaned data should keep all 756 matches and 12 seasons."""
    assert len(matches) == 756, "expected 756 matches"
    assert matches["season"].nunique() == 12, "expected 12 seasons"
    assert matches["no_result"].sum() == 4, "expected 4 no-result matches"
    print("PASS  dataset size: 756 matches, 12 seasons, 4 no-results")


def test_team_names(matches):
    """Old team names must be gone after cleaning."""
    all_teams = set(matches["team1"]) | set(matches["team2"])
    for old_name in ["Delhi Daredevils", "Kings XI Punjab", "Rising Pune Supergiants"]:
        assert old_name not in all_teams, old_name + " was not renamed"
    print("PASS  team renames")


def test_no_extras_in_batter_runs(deliveries):
    """Cricket rule: no batter runs on wides, byes or leg-byes."""
    extras = (deliveries["wide_runs"] > 0) | (deliveries["bye_runs"] > 0) | (deliveries["legbye_runs"] > 0)
    bad_rows = deliveries[extras & (deliveries["batsman_runs"] > 0)]
    assert len(bad_rows) == 0, str(len(bad_rows)) + " balls still double-count extras"
    print("PASS  no extras counted as batter runs")


def test_cap_winners(deliveries):
    """Our Orange/Purple Cap winners must match the official ones."""
    caps = metrics.cap_winners(deliveries)
    for i in range(len(caps)):
        row = caps.iloc[i]
        season = row["season"]
        orange, runs, purple, wickets = OFFICIAL_CAPS[season]

        assert row["orange_cap"] == orange, str(season) + " Orange Cap should be " + orange
        difference = abs(row["runs"] - runs)
        assert difference <= RUN_TOLERANCE, str(season) + " runs " + str(row["runs"]) + " vs official " + str(runs)
        assert row["purple_cap"] == purple, str(season) + " Purple Cap should be " + purple
        assert row["wickets"] == wickets, str(season) + " wickets " + str(row["wickets"]) + " vs official " + str(wickets)

        note = "" if difference == 0 else "  (runs differ by " + str(difference) + ")"
        print("PASS  " + str(season) + " caps: " + orange + " / " + purple + note)


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
    champions = predict.season_champions(matches)
    for i in range(len(champions)):
        row = champions.iloc[i]
        official = OFFICIAL_CHAMPIONS[row["season"]]
        assert row["champion"] == official, str(row["season"]) + " champion should be " + official
    print("PASS  all 12 champions match the official list")


def test_prediction_model(matches):
    """Check the prediction maths on small examples we can work out on paper."""
    import pandas as pd
    # Form score: 600, 400, 300 runs -> (3*600 + 2*400 + 1*300) / 6 = 483.3
    table = pd.DataFrame({"batter": ["A", "A", "A"], "season": [2017, 2018, 2019],
                          "runs": [300, 400, 600]})
    form = predict.weighted_form(table, "batter", "runs", 2019)
    assert form.iloc[0]["form"] == 483.3, "weighted form should be 483.3"

    # Simulation: title chances of all teams must add up to 100%.
    teams = sorted(set(matches[matches["season"] == 2019]["team1"]))
    strengths = predict.team_strengths(matches, 2019, teams)
    chances = predict.title_chances(strengths, simulations=500)
    total = chances["title_pct"].sum()
    assert abs(total - 100) < 0.5, "title chances add up to " + str(total)
    print("PASS  prediction maths: weighted form and title chances")


def test_dashboard_data(matches, deliveries):
    """The interactive dashboard's data must give the same answers as metrics.py."""
    import build_report
    data = build_report.explorer_data(matches, deliveries)
    assert len(data["matches"]) == 756, "the dashboard should have all 756 matches"
    assert len(data["champions"]) == 12, "the dashboard should have 12 champions"

    # Kohli's 2016 runs, added up the same way the page's JavaScript does it.
    # Columns of a batting row: [player, season, team, runs, balls, sixes, innings]
    kohli_2016 = 0
    for row in data["batting"]:
        if row[0] == "V Kohli" and row[1] == 2016:
            kohli_2016 += row[3]
    assert kohli_2016 == 973, "Kohli 2016 should be 973 runs, got " + str(kohli_2016)
    print("PASS  interactive dashboard data (756 matches, 12 champions, Kohli 2016 = 973)")


def main():
    matches, deliveries = metrics.load_processed_data()
    test_dataset_size(matches)
    test_team_names(matches)
    test_no_extras_in_batter_runs(deliveries)
    test_formulas()
    test_cap_winners(deliveries)
    test_champions(matches)
    test_prediction_model(matches)
    test_dashboard_data(matches, deliveries)
    print("\nAll fact checks passed.")


if __name__ == "__main__":
    main()
