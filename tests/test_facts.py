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

    # Simulation: title chances of all teams must add up to 100%.
    teams = sorted(set(matches[matches["season"] == 2026]["team1_franchise"]))
    strengths = predict.team_strengths(matches, 2026, teams)
    chances = predict.title_chances(strengths, simulations=500)
    total = chances["title_pct"].sum()
    assert abs(total - 100) < 0.5, "title chances add up to " + str(total)
    print("PASS  prediction maths: weighted form and title chances")


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
    print("\nAll fact checks passed.")


if __name__ == "__main__":
    main()
