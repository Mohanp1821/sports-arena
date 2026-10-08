"""
chat_facts.py - every number the "Ask Sports Arena" chatbot is allowed to say.

The chatbot never makes up a number: if a fact is not here, it says so.
  1. structured facts (dictionaries and lists) for the offline chatbot (src/chatbot.js)
  2. the same facts as short sentences ("IPL 2016 Orange Cap: V Kohli, 973 runs.")
     for the optional local-AI server (src/chat_server.py)
Saved as outputs/chat_facts.json; build_report.py puts the structured part in the page.
"""

import json
import os
import pandas as pd
import metrics
import predict
from dashboard_data import clean_value as clean, read_output

OUTPUT_FOLDER = os.path.join(metrics.PROJECT_FOLDER, "outputs")
FACTS_FILE = os.path.join(OUTPUT_FOLDER, "chat_facts.json")

# Short names and old names people use for teams (all point to today's franchise).
TEAM_ALIASES = {
    "Chennai Super Kings": ["csk", "chennai", "super kings", "chennai super kings"],
    "Mumbai Indians": ["mi", "mumbai indians", "mumbai"],
    "Royal Challengers Bengaluru": ["rcb", "royal challengers", "bangalore", "bengaluru",
                                    "royal challengers bangalore", "royal challengers bengaluru"],
    "Kolkata Knight Riders": ["kkr", "kolkata", "knight riders", "kolkata knight riders"],
    "Sunrisers Hyderabad": ["srh", "sunrisers", "hyderabad", "sunrisers hyderabad"],
    "Delhi Capitals": ["dc", "delhi", "delhi capitals", "delhi daredevils", "daredevils", "dd"],
    "Punjab Kings": ["pbks", "punjab", "punjab kings", "kings xi punjab", "kings xi", "kxip"],
    "Rajasthan Royals": ["rr", "rajasthan", "rajasthan royals"],
    "Gujarat Titans": ["gt", "gujarat titans", "titans", "gujarat"],
    "Lucknow Super Giants": ["lsg", "lucknow", "lucknow super giants", "super giants"],
    "Deccan Chargers": ["deccan chargers", "deccan", "dch"],
    "Kochi Tuskers Kerala": ["kochi tuskers kerala", "kochi tuskers", "kochi", "ktk"],
    "Pune Warriors": ["pune warriors", "pwi"],
    "Gujarat Lions": ["gujarat lions", "lions", "gl"],
    "Rising Pune Supergiant": ["rising pune supergiant", "rising pune supergiants", "rising pune", "rps"],
}

# Nicknames for players (the dataset uses short names like "V Kohli").
PLAYER_NICKNAMES = {
    "sky": "SA Yadav", "surya": "SA Yadav", "suryakumar": "SA Yadav", "msd": "MS Dhoni", "thala": "MS Dhoni",
    "dhoni": "MS Dhoni", "virat": "V Kohli", "kohli": "V Kohli", "rohit": "RG Sharma", "hitman": "RG Sharma",
    "abd": "AB de Villiers", "de villiers": "AB de Villiers", "jaddu": "RA Jadeja", "jadeja": "RA Jadeja",
    "bhuvi": "B Kumar", "bhuvneshwar": "B Kumar", "hardik": "HH Pandya", "krunal": "KH Pandya",
    "kl rahul": "KL Rahul", "rahul": "KL Rahul", "pant": "RR Pant", "rishabh": "RR Pant", "gayle": "CH Gayle",
    "warner": "DA Warner", "buttler": "JC Buttler", "bumrah": "JJ Bumrah", "malinga": "SL Malinga",
    "chahal": "YS Chahal", "narine": "SP Narine", "russell": "AD Russell", "dre russ": "AD Russell",
    "raina": "SK Raina", "gill": "Shubman Gill", "suryavanshi": "V Suryavanshi", "vaibhav": "V Suryavanshi",
    "sai sudharsan": "B Sai Sudharsan", "sudharsan": "B Sai Sudharsan", "rabada": "K Rabada",
    "siraj": "Mohammed Siraj", "shami": "Mohammed Shami", "ashwin": "R Ashwin", "dhawan": "S Dhawan",
    "pollard": "KA Pollard", "watson": "SR Watson", "faf": "F du Plessis", "du plessis": "F du Plessis",
    "samson": "SV Samson", "sanju": "SV Samson", "ruturaj": "RD Gaikwad", "gaikwad": "RD Gaikwad",
    "jaiswal": "YBK Jaiswal", "travis head": "TM Head", "klaasen": "H Klaasen", "abhishek": "Abhishek Sharma",
    "shreyas": "SS Iyer", "iyer": "SS Iyer", "harshal": "HV Patel", "prasidh": "M Prasidh Krishna",
    "tendulkar": "SR Tendulkar", "sachin": "SR Tendulkar", "sehwag": "V Sehwag", "gambhir": "G Gambhir",
    "uthappa": "RV Uthappa", "yuvraj": "Yuvraj Singh", "rashid": "Rashid Khan", "boult": "TA Boult",
    "archer": "JC Archer", "hazlewood": "JR Hazlewood", "starc": "MA Starc", "cummins": "PJ Cummins",
}

# Surnames that are also English words ("TM Head", "JE Root") are not used as aliases,
# so "head to head" or "most runs" never finds a player.
COMMON_WORDS = {"short", "little", "hope", "root", "head", "green", "wood", "young", "best", "most", "king",
                "will", "park", "ball", "stone", "rose", "bird", "cook", "hill", "price", "ward", "good", "case",
                "bell", "winter", "jordan", "smith", "white", "black", "brown", "rich", "mark", "lamb", "wade",
                "miller", "hunt", "hall", "parks", "james", "allen", "daniel", "henry", "owen", "taylor", "lewis",
                "morgan", "carey", "stokes", "david", "neser", "match", "season", "runs", "team", "career"}

# Short names people use for grounds.
VENUE_ALIASES = {
    "MA Chidambaram Stadium, Chepauk": ["chepauk", "chidambaram", "chennai stadium"],
    "Wankhede Stadium": ["wankhede"],
    "Eden Gardens": ["eden gardens", "eden"],
    "M Chinnaswamy Stadium": ["chinnaswamy"],
    "Arun Jaitley Stadium": ["arun jaitley", "kotla", "feroz shah kotla"],
    "Narendra Modi Stadium": ["narendra modi stadium", "motera", "ahmedabad"],
    "Rajiv Gandhi International Stadium, Uppal": ["uppal", "rajiv gandhi"],
    "Punjab Cricket Association IS Bindra Stadium": ["mohali", "is bindra", "pca stadium"],
    "Maharaja Yadavindra Singh International Cricket Stadium": ["mullanpur", "new chandigarh", "maharaja yadavindra"],
    "Ekana Cricket Stadium": ["ekana"],
    "Sawai Mansingh Stadium": ["sawai mansingh", "jaipur"],
    "Dubai International Cricket Stadium": ["dubai"],
    "Sharjah Cricket Stadium": ["sharjah"],
    "Zayed Cricket Stadium": ["abu dhabi", "sheikh zayed", "zayed"],
    "Brabourne Stadium": ["brabourne"],
    "Dr DY Patil Sports Academy": ["dy patil"],
    "Maharashtra Cricket Association Stadium": ["mca stadium", "pune stadium", "gahunje"],
    "Himachal Pradesh Cricket Association Stadium": ["dharamsala"],
    "Barsapara Cricket Stadium": ["guwahati", "barsapara"],
}


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------
BAT_CAREER = ["innings", "runs", "balls_faced", "dismissals", "highest_score", "fifties", "hundreds", "sixes"]
BOWL_CAREER = ["wickets", "legal_balls", "runs_conceded"]


def player_facts(matches, deliveries):
    """
    Every player's career and seasons, as short lists:
      career  = [matches, innings, runs, balls, outs, highest, 50s, 100s, sixes, wickets, legal balls, runs conceded]
      seasons = {season: [team, runs, balls, outs, sixes, wickets, legal balls, runs conceded]}
    """
    df = metrics.remove_super_overs(deliveries)
    appearances = pd.concat([df[["match_id", "batter"]].rename(columns={"batter": "player"}),
                             df[["match_id", "non_striker"]].rename(columns={"non_striker": "player"}),
                             df[["match_id", "bowler"]].rename(columns={"bowler": "player"})]).drop_duplicates()
    matches_played = appearances.groupby("player")["match_id"].nunique()

    bat = metrics.batting_stats(deliveries).set_index("batter")
    bowl = metrics.bowling_stats(deliveries).set_index("bowler")
    teams = metrics.season_impact_scores(deliveries)
    team_of = {(player, int(season)): team for player, season, team in zip(teams["player"], teams["season"], teams["team"])}

    def career_numbers(table, player, columns):
        """The player's numbers from a career table, or zeros if he is not in it."""
        if player not in table.index:
            return [0] * len(columns)
        return [clean(table.loc[player][column]) for column in columns]

    players = {}
    for player in sorted(matches_played.index):
        career = [clean(matches_played[player])] + career_numbers(bat, player, BAT_CAREER) + career_numbers(bowl, player, BOWL_CAREER)
        players[player] = {"career": career, "seasons": {}}

    def season_entry(player, season):
        empty = [team_of.get((player, int(season)), ""), 0, 0, 0, 0, 0, 0, 0]
        return players[player]["seasons"].setdefault(str(int(season)), empty)

    for row in metrics.batting_stats(deliveries, ["batter", "season"]).to_dict("records"):
        entry = season_entry(row["batter"], row["season"])
        entry[1:5] = [clean(row["runs"]), clean(row["balls_faced"]), clean(row["dismissals"]), clean(row["sixes"])]
    for row in metrics.bowling_stats(deliveries, ["bowler", "season"]).to_dict("records"):
        if row["bowler"] in players:
            entry = season_entry(row["bowler"], row["season"])
            entry[5:8] = [clean(row["wickets"]), clean(row["legal_balls"]), clean(row["runs_conceded"])]
    return players


def player_aliases(players):
    """
    Lower-case words that point to a player: the full name ("v kohli"), nicknames ("sky"),
    and a surname or first name (if several players share it, the chatbot asks which one).
    """
    aliases = {}
    for name in players:
        aliases[name.lower()] = [name]
    words = {}
    for name in players:
        parts = name.replace("(2)", "").split()
        candidates = [parts[-1]] if len(parts) > 1 else []
        if len(parts) > 1 and len(parts[0]) > 2 and parts[0].upper() != parts[0]:
            candidates.append(parts[0])           # a full first name like "Shubman" (not initials like "MS")
        for word in candidates:
            key = word.lower()
            if len(key) >= 4 and key not in aliases and key not in COMMON_WORDS:
                words.setdefault(key, []).append(name)
    for key in words:
        aliases[key] = sorted(words[key])
    for key in PLAYER_NICKNAMES:
        if PLAYER_NICKNAMES[key] in players:
            aliases[key] = [PLAYER_NICKNAMES[key]]
    return aliases


# ---------------------------------------------------------------------------
# Teams, grounds, matches
# ---------------------------------------------------------------------------
def team_facts(matches, deliveries):
    """Titles, rivalries (overall record), team-at-ground records and matches by date."""
    champions = metrics.season_champions(matches)
    finals = matches[matches["playoff_name"] == "Final"]
    champion_rows = {}
    for champion in champions.to_dict("records"):
        season = int(champion["season"])
        final = finals[finals["season"] == season].iloc[0]
        runner_up = final["team2"] if final["winner"] == final["team1"] else final["team1"]
        champion_rows[str(season)] = [champion["champion"], champion["champion_name"], runner_up,
                                      metrics.margin_text(final), final["venue"]]

    cap_rows = {str(int(row["season"])): [row["orange_cap"], clean(row["runs"]), row["purple_cap"], clean(row["wickets"])]
                for row in metrics.cap_winners(deliveries).to_dict("records")}

    results = metrics.team_results(matches)
    rivalry = {}
    rivalry_ground = {}
    for (team, opponent), rows in results.groupby(["team", "opponent"]):
        if team < opponent:
            games = metrics.rivalry_matches(matches, team, opponent)
            last = games.iloc[-1]
            last_text = (last["date"].strftime("%Y-%m-%d") + ": " + (last["winner"] + " " + metrics.margin_text(last)
                         if not last["no_result"] else "no result") + " at " + last["venue"])
            # The same record at each ground: [played, team wins, opponent wins, no result]
            for venue, at_ground in games.groupby("venue"):
                rivalry_ground.setdefault(team + "|" + opponent, {})[venue] = [
                    len(at_ground), int((at_ground["winner_franchise"] == team).sum()),
                    int((at_ground["winner_franchise"] == opponent).sum()), int(at_ground["no_result"].sum())]
            rivalry[team + "|" + opponent] = [len(games), int((games["winner_franchise"] == team).sum()),
                                              int((games["winner_franchise"] == opponent).sum()),
                                              int(games["no_result"].sum()), last_text]

    at_ground = results.groupby(["team", "venue"]).agg(
        played=("match_id", "count"),
        wins=("won", "sum"),
        first=("season", "min"),
        last=("season", "max"),
    ).reset_index()
    ground = {row["team"] + "|" + row["venue"]: [clean(row["played"]), clean(row["wins"]), clean(row["first"]), clean(row["last"])]
              for row in at_ground.to_dict("records")}

    match_list = []
    for m in matches.to_dict("records"):
        result = "No result" if m["no_result"] else (
            "Tied, " + m["winner"] + " won the super over" if m["result"] == "tie" else m["winner"] + " " + metrics.margin_text(m))
        match_list.append([m["date"].strftime("%Y-%m-%d"), m["team1"], m["team2"], m["team1_franchise"], m["team2_franchise"],
                           result, m["venue"], m["player_of_match"], int(m["match_id"]),
                           m["playoff_name"] if m["stage"] == "Playoff" else "League"])
    return champion_rows, cap_rows, rivalry, ground, match_list, rivalry_ground


MIN_MATCHUP_BALLS = 6      # batter-vs-bowler pairs with fewer balls are left out


def matchup_facts(deliveries, names):
    """[batter, bowler, balls, runs, dismissals, dots, fours, sixes] (names as positions in the name list)."""
    position = {name: i for i, name in enumerate(names)}
    table = metrics.matchup_table(deliveries, min_balls=MIN_MATCHUP_BALLS)
    return [[position[row["batter"]], position[row["bowler"]]]
            + [clean(row[column]) for column in ["balls", "runs", "dismissals", "dots", "fours", "sixes"]]
            for row in table.to_dict("records")]


FIT_MIN_BALLS = 30   # player-at-ground records with fewer balls are too small to quote


def pitch_facts(matches, deliveries):
    """How each ground plays, all seasons and 2023+: {venue: [matches, run rate, the 4 indexes, avg 1st innings, chase win %, label]}."""
    parts = metrics.pitch_components(deliveries, matches)
    seasons = sorted(matches["season"].unique())
    columns = ["matches", "run_rate", "runs_index", "wickets_index", "boundary_index",
               "dot_index", "avg_first_innings", "chase_win_pct", "label"]
    result = {}
    for key, chosen in [("all", None), ("recent", [season for season in seasons if season >= 2023])]:
        profile = metrics.profile_from_components(parts, chosen)
        result[key] = {row["venue"]: [clean(row[column]) for column in columns] for row in profile.to_dict("records")}
    return result


def fit_facts(matches, deliveries):
    """Each player at each ground (at least 30 balls there): here, then elsewhere in the same seasons."""
    batting = metrics.player_ground_batting(deliveries, matches)
    bowling = metrics.player_ground_bowling(deliveries, matches)
    bat_columns = ["balls", "runs", "outs", "else_balls", "else_runs", "else_outs"]
    bowl_columns = ["legal_balls", "runs", "wickets", "else_legal_balls", "else_runs", "else_wickets"]
    bat = {row["batter"] + "|" + row["venue"]: [clean(row[c]) for c in bat_columns]
           for row in batting.to_dict("records") if row["balls"] >= FIT_MIN_BALLS}
    bowl = {row["bowler"] + "|" + row["venue"]: [clean(row[c]) for c in bowl_columns]
            for row in bowling.to_dict("records") if row["legal_balls"] >= FIT_MIN_BALLS}
    return {"bat": bat, "bowl": bowl}


def impact_facts(matches, deliveries, impact):
    """The Impact Player era comparison and how teams used the substitute."""
    summary = metrics.impact_era_summary(deliveries, matches)
    phases = metrics.impact_era_phase_run_rate(deliveries)
    choices = metrics.impact_choice_summary(metrics.impact_player_choices(impact, deliveries, matches), by_team=False)
    return {"eras": [[clean(v) for v in row] for row in summary.itertuples(index=False)],
            "phases": [[era, phase, clean(rate)] for era, phase, rate in zip(phases["era"], phases["phase"], phases["run_rate"])],
            "choices": [[clean(v) for v in row] for row in choices.itertuples(index=False)],
            "substitutions": len(impact)}


def prediction_facts(next_season):
    """Both models' predictions and backtest scores, from the prediction CSV files."""
    comparison = read_output("prediction_" + str(next_season) + "_comparison.csv")
    if comparison is None:
        return None
    chances_a = read_output("prediction_title_chances.csv")
    chances_b = read_output("prediction_model_b_title_chances.csv")
    awards_a = read_output("prediction_awards.csv")
    awards_b = read_output("prediction_model_b_awards.csv")
    scores = read_output("model_comparison_matches.csv")
    titles = read_output("model_comparison_titles.csv")
    overall = scores[scores["season"] == "2021-2026"]
    strengths = dict(zip(chances_a["team"], chances_a["strength"]))
    squad = dict(zip(chances_b["team"], chances_b["squad_strength"]))
    elo = dict(zip(chances_b["team"], chances_b["elo"]))
    return {
        "season": next_season, "simulations": predict.SIMULATIONS,
        "teams": [[row["team"], clean(row["title_pct_a"]), clean(row["playoff_pct_a"]),
                   clean(row["title_pct_b"]), clean(row["playoff_pct_b"]), clean(strengths.get(row["team"])),
                   clean(squad.get(row["team"])), clean(elo.get(row["team"]))] for row in comparison.to_dict("records")],
        "awards_a": [[row["award"], int(row["rank"]), row["player"], row["team"], clean(row["form"]), row["measure"]]
                     for row in awards_a.to_dict("records")],
        "awards_b": [[row["award"], int(row["rank"]), row["player"], row["team"], clean(row["predicted"]), row["measure"]]
                     for row in awards_b.to_dict("records")],
        "backtest": [[row["model"], clean(row["matches"]), clean(row["accuracy_pct"]), clean(row["log_loss"]), clean(row["brier"])]
                     for row in overall.to_dict("records")],
        "titles": [[clean(row[column]) for column in ["season", "teams", "champion", "champion_rank_a", "champion_rank_b"]]
                   for row in titles.to_dict("records")],
    }


# ---------------------------------------------------------------------------
# Fact lines (for the local-AI server)
# ---------------------------------------------------------------------------
overs = metrics.overs_text      # 117 legal balls -> "19.3"


def fact_lines(facts):
    """Every structured fact written as one short sentence."""
    lines = []
    for season, row in sorted(facts["champions"].items()):
        lines.append("IPL " + season + " champion: " + row[1] + " (franchise " + row[0] + "), beat " + row[2]
                     + " in the final, " + row[3] + ", at " + row[4] + ".")
    for season, row in sorted(facts["caps"].items()):
        lines.append("IPL " + season + " Orange Cap (most runs): " + row[0] + ", " + str(row[1]) + " runs.")
        lines.append("IPL " + season + " Purple Cap (most wickets): " + row[2] + ", " + str(row[3]) + " wickets.")
    for name, player in facts["players"].items():
        c = player["career"]
        if c[2] >= 300 or c[9] >= 15:
            average = round(c[2] / c[4], 2) if c[4] else "no dismissals"
            sr = round(c[2] / c[3] * 100, 1) if c[3] else "-"
            text = (name + " IPL career " + facts["meta"]["season_range"] + ": " + str(c[0]) + " matches, " + str(c[2])
                    + " runs (average " + str(average) + ", strike rate " + str(sr) + ", highest " + str(c[5]) + ", "
                    + str(c[6]) + " fifties, " + str(c[7]) + " hundreds, " + str(c[8]) + " sixes)")
            if c[9] or c[10]:
                text += ", " + str(c[9]) + " wickets (economy " + (str(round(c[11] / (c[10] / 6), 2)) if c[10] else "-") + ")"
            lines.append(text + ".")
        for season, s in sorted(player["seasons"].items()):
            if s[1] >= 100 or s[5] >= 5:
                lines.append(name + " in IPL " + season + " (" + s[0] + "): " + str(s[1]) + " runs off " + str(s[2])
                             + " balls, " + str(s[4]) + " sixes, " + str(s[5]) + " wickets in " + overs(s[6]) + " overs.")
    names = facts["names"]
    for row in facts["matchups"]:
        if row[2] >= 30:
            lines.append(names[row[0]] + " (batting) vs " + names[row[1]] + " (bowling): " + str(row[2]) + " balls, "
                         + str(row[3]) + " runs, strike rate " + str(round(row[3] / row[2] * 100, 1)) + ", out "
                         + str(row[4]) + " times to him.")
    for key, row in sorted(facts["rivalry"].items()):
        a, b = key.split("|")
        lines.append(a + " vs " + b + ": " + str(row[0]) + " matches, " + a + " won " + str(row[1]) + ", " + b + " won "
                     + str(row[2]) + ", no result " + str(row[3]) + ". Last meeting " + row[4] + ".")
    for key, grounds in sorted(facts["rivalry_ground"].items()):
        a, b = key.split("|")
        for venue, row in sorted(grounds.items()):
            if row[0] >= 3:
                lines.append(a + " vs " + b + " at " + venue + ": " + str(row[0]) + " matches, " + a + " won " + str(row[1])
                             + ", " + b + " won " + str(row[2]) + ".")
    for key, row in sorted(facts["ground"].items()):
        team, venue = key.split("|")
        if row[0] >= 5:
            lines.append(team + " at " + venue + ": won " + str(row[1]) + " of " + str(row[0]) + " matches ("
                         + str(round(row[1] / row[0] * 100, 1)) + "%), " + str(row[2]) + "-" + str(row[3]) + ".")
    for venue, p in sorted(facts["pitch"]["all"].items()):
        if p[0] >= 5:
            lines.append("How " + venue + " plays (pitch and conditions, " + facts["meta"]["season_range"] + ", " + str(p[0])
                         + " matches): " + p[8] + "; runs index " + str(p[2]) + ", wickets index " + str(p[3])
                         + ", boundary index " + str(p[4]) + " (100 = league average in the same seasons); run rate "
                         + str(p[1]) + ", average first innings " + str(p[6]) + ", chasing side won " + str(p[7]) + "%.")
    for key, row in sorted(facts["fit"]["bat"].items()):
        player, venue = key.split("|")
        if row[0] >= 120 and row[3] > 0:
            lines.append(player + " batting at " + venue + ": strike rate " + str(round(row[1] / row[0] * 100, 1)) + " ("
                         + str(row[1]) + " runs off " + str(row[0]) + " balls) vs " + str(round(row[4] / row[3] * 100, 1))
                         + " at other grounds in the same seasons.")
    for key, row in sorted(facts["fit"]["bowl"].items()):
        player, venue = key.split("|")
        if row[0] >= 120 and row[3] > 0:
            lines.append(player + " bowling at " + venue + ": economy " + str(round(row[1] / (row[0] / 6), 2)) + ", "
                         + str(row[2]) + " wickets in " + overs(row[0]) + " overs, vs economy "
                         + str(round(row[4] / (row[3] / 6), 2)) + " at other grounds in the same seasons.")
    for era in facts["impact"]["eras"]:
        lines.append("Impact Player comparison, " + era[0] + ": average first-innings score " + str(era[2]) + ", "
                     + str(era[3]) + " totals of 200+ (" + str(era[4]) + " per match), chases won " + str(era[5]) + "%.")
    for m in facts["matches"]:
        lines.append("Match on " + m[0] + " (" + m[9] + "): " + m[1] + " v " + m[2] + " at " + m[6] + ". " + m[5]
                     + ". Player of the match: " + (m[7] or "not awarded") + ".")
    p = facts.get("predictions")
    if p:
        for t in p["teams"]:
            lines.append("IPL " + str(p["season"]) + " prediction for " + t[0] + ": Model A title " + str(t[1]) + "% (playoffs "
                         + str(t[2]) + "%), Model B title " + str(t[3]) + "% (playoffs " + str(t[4]) + "%), from "
                         + format(p["simulations"], ",") + " simulated seasons each.")
        for a in p["awards_a"]:
            if a[1] == 1:
                lines.append("Model A " + str(p["season"]) + " pick for " + a[0] + ": " + a[2] + " (" + a[3] + "), form "
                             + str(a[4]) + " " + a[5] + " a season.")
        for b in p["awards_b"]:
            if b[1] == 1:
                lines.append("Model B " + str(p["season"]) + " pick for " + b[0] + ": " + b[2] + " (" + b[3] + "), predicts "
                             + str(b[4]) + " " + b[5] + ".")
        for row in p["backtest"]:
            lines.append("Backtest 2021-2026, " + row[0] + ": " + str(row[1]) + " matches, accuracy " + str(row[2])
                         + "%, log loss " + str(row[3]) + ", Brier " + str(row[4]) + ".")
    return lines


def build_facts(matches, deliveries, impact):
    """Build the facts (structured + lines), save outputs/chat_facts.json, return the structured part."""
    players = player_facts(matches, deliveries)
    champions, caps, rivalry, ground, match_list, rivalry_ground = team_facts(matches, deliveries)
    next_season = int(matches["season"].max()) + 1
    venues = sorted(matches["venue"].unique())
    venue_aliases = {venue.lower(): venue for venue in venues}
    for venue, aliases in VENUE_ALIASES.items():
        for alias in aliases:
            venue_aliases[alias] = venue
    # "at Chennai" = the ground with the most matches in Chennai.
    for city in sorted(matches["city"].unique()):
        rows = matches[matches["city"] == city]
        main_ground = rows["venue"].value_counts().sort_index().idxmax()
        venue_aliases["at " + city.lower()] = main_ground
        venue_aliases["in " + city.lower()] = main_ground
    venue_aliases["at bangalore"] = venue_aliases.get("at bengaluru", "M Chinnaswamy Stadium")
    team_aliases = {alias: team for team, aliases in TEAM_ALIASES.items() for alias in aliases}
    facts = {
        "meta": {"season_range": metrics.season_range_text(matches), "matches": len(matches),
                 "balls": len(deliveries), "seasons": int(matches["season"].nunique()),
                 "first_season": int(matches["season"].min()), "last_season": int(matches["season"].max())},
        "team_aliases": team_aliases, "player_aliases": player_aliases(players), "venue_aliases": venue_aliases,
        "players": players, "names": sorted(players), "matchups": matchup_facts(deliveries, sorted(players)),
        "champions": champions, "caps": caps, "rivalry": rivalry, "rivalry_ground": rivalry_ground, "ground": ground,
        "matches": match_list, "impact": impact_facts(matches, deliveries, impact),
        "pitch": pitch_facts(matches, deliveries), "fit": fit_facts(matches, deliveries),
        "predictions": prediction_facts(next_season),
    }
    lines = fact_lines(facts)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    with open(FACTS_FILE, "w", encoding="utf-8") as file:
        json.dump({"facts": facts, "lines": lines}, file, separators=(",", ":"))
    print("Chat facts saved:", FACTS_FILE, "(" + str(len(lines)) + " fact lines)")
    return facts
