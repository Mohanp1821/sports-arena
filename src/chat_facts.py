"""
chat_facts.py
-------------
Builds the FACTS FILE for the "Ask Sports Arena" chatbot: every number the
chatbot is allowed to say, calculated from the data and the prediction files.
The chatbot never makes up a number: if a fact is not in this file, it says so.

Two parts:
  1. STRUCTURED facts (dictionaries and lists) for the offline answer engine
     in src/chatbot.js, embedded in the dashboard page by build_report.py
  2. FACT LINES: the same facts as short sentences, e.g.
        "IPL 2016 Orange Cap: V Kohli, 973 runs."
     used by the optional local-LLM server (src/chat_server.py), which picks
     the lines that match a question and gives only those to the model.

Saved as outputs/chat_facts.json. Used by build_report.py:
    facts = chat_facts.build_facts(matches, deliveries, impact)
"""

import json
import os
import re
import pandas as pd
import metrics   # our own file: src/metrics.py
import predict   # our own file: src/predict.py (number of simulations, award list)

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

# English words that are also surnames ("D Short", "TM Head", "JE Root"): they are
# NOT used as player aliases, so "head to head" or "most runs" never finds a player.
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


def clean(value):
    """numpy numbers -> normal numbers, missing -> None (so JSON can store them)."""
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def read_output(file_name):
    """A CSV made by predict.py / predict_ml.py, or None if it is missing."""
    path = os.path.join(OUTPUT_FOLDER, file_name)
    return pd.read_csv(path) if os.path.exists(path) else None


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------
def player_facts(matches, deliveries):
    """
    For every player: career batting and bowling, and each season.
    Row lists keep the file small:
      career  = [matches, innings, runs, balls, outs, highest, fifties, hundreds, sixes,
                 wickets, legal balls bowled, runs conceded]
      seasons = {season: [team, runs, balls, outs, sixes, wickets, legal balls, runs conceded]}
    """
    df = metrics.remove_super_overs(deliveries)
    appearances = pd.concat([df[["match_id", "batter"]].rename(columns={"batter": "player"}),
                             df[["match_id", "non_striker"]].rename(columns={"non_striker": "player"}),
                             df[["match_id", "bowler"]].rename(columns={"bowler": "player"})]).drop_duplicates()
    matches_played = appearances.groupby("player")["match_id"].nunique()

    bat = metrics.batting_stats(deliveries).set_index("batter")
    bowl = metrics.bowling_stats(deliveries).set_index("bowler")
    bat_season = metrics.batting_stats(deliveries, ["batter", "season"])
    bowl_season = metrics.bowling_stats(deliveries, ["bowler", "season"])
    teams = metrics.season_impact_scores(deliveries)[["player", "season", "team"]]
    team_of = {}
    for i in range(len(teams)):
        team_of[(teams["player"].iloc[i], int(teams["season"].iloc[i]))] = teams["team"].iloc[i]

    players = {}
    for player in sorted(matches_played.index):
        b = bat.loc[player] if player in bat.index else None
        w = bowl.loc[player] if player in bowl.index else None
        players[player] = {"career": [
            clean(matches_played[player]),
            clean(b["innings"]) if b is not None else 0, clean(b["runs"]) if b is not None else 0,
            clean(b["balls_faced"]) if b is not None else 0, clean(b["dismissals"]) if b is not None else 0,
            clean(b["highest_score"]) if b is not None else 0, clean(b["fifties"]) if b is not None else 0,
            clean(b["hundreds"]) if b is not None else 0, clean(b["sixes"]) if b is not None else 0,
            clean(w["wickets"]) if w is not None else 0, clean(w["legal_balls"]) if w is not None else 0,
            clean(w["runs_conceded"]) if w is not None else 0], "seasons": {}}

    for i in range(len(bat_season)):
        row = bat_season.iloc[i]
        entry = players[row["batter"]]["seasons"].setdefault(str(int(row["season"])), [team_of.get((row["batter"], int(row["season"])), ""), 0, 0, 0, 0, 0, 0, 0])
        entry[1:5] = [clean(row["runs"]), clean(row["balls_faced"]), clean(row["dismissals"]), clean(row["sixes"])]
    for i in range(len(bowl_season)):
        row = bowl_season.iloc[i]
        if row["bowler"] not in players:
            continue
        entry = players[row["bowler"]]["seasons"].setdefault(str(int(row["season"])), [team_of.get((row["bowler"], int(row["season"])), ""), 0, 0, 0, 0, 0, 0, 0])
        entry[5:8] = [clean(row["wickets"]), clean(row["legal_balls"]), clean(row["runs_conceded"])]
    return players


def player_aliases(players):
    """
    Lower-case words that point to a player:
      - the full name ("v kohli"), nicknames ("sky", "kohli")
      - a surname or a full first name, but only if ONE player has it; if several
        players share it, the alias lists them all and the chatbot asks which one
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
    for i in range(len(champions)):
        season = int(champions["season"].iloc[i])
        final = finals[finals["season"] == season].iloc[0]
        runner_up = final["team2"] if final["winner"] == final["team1"] else final["team1"]
        champion_rows[str(season)] = [champions["champion"].iloc[i], champions["champion_name"].iloc[i], runner_up,
                                      metrics.margin_text(final), final["venue"]]

    caps = metrics.cap_winners(deliveries)
    cap_rows = {}
    for i in range(len(caps)):
        row = caps.iloc[i]
        cap_rows[str(int(row["season"]))] = [row["orange_cap"], clean(row["runs"]), row["purple_cap"], clean(row["wickets"])]

    results = metrics.team_results(matches)
    rivalry = {}
    rivalry_ground = {}
    for (team, opponent), rows in results.groupby(["team", "opponent"]):
        if team < opponent:
            games = metrics.rivalry_matches(matches, team, opponent)
            last = games.iloc[-1]
            last_text = (last["date"].strftime("%Y-%m-%d") + ": " + (last["winner"] + " " + metrics.margin_text(last)
                         if not last["no_result"] else "no result") + " at " + last["venue"])
            # The same record at each ground: {venue: [played, team wins, opponent wins, no result]}
            for venue, at_ground in games.groupby("venue"):
                rivalry_ground.setdefault(team + "|" + opponent, {})[venue] = [
                    len(at_ground), int((at_ground["winner_franchise"] == team).sum()),
                    int((at_ground["winner_franchise"] == opponent).sum()), int(at_ground["no_result"].sum())]
            rivalry[team + "|" + opponent] = [len(games), int((games["winner_franchise"] == team).sum()),
                                              int((games["winner_franchise"] == opponent).sum()),
                                              int(games["no_result"].sum()), last_text]

    at_ground = results.groupby(["team", "venue"]).agg(played=("match_id", "count"), wins=("won", "sum"),
                                                       first=("season", "min"), last=("season", "max")).reset_index()
    ground = {}
    for i in range(len(at_ground)):
        row = at_ground.iloc[i]
        ground[row["team"] + "|" + row["venue"]] = [clean(row["played"]), clean(row["wins"]), clean(row["first"]), clean(row["last"])]

    match_list = []
    for i in range(len(matches)):
        m = matches.iloc[i]
        result = "No result" if m["no_result"] else (
            "Tied, " + m["winner"] + " won the super over" if m["result"] == "tie" else m["winner"] + " " + metrics.margin_text(m))
        match_list.append([m["date"].strftime("%Y-%m-%d"), m["team1"], m["team2"], m["team1_franchise"], m["team2_franchise"],
                           result, m["venue"], m["player_of_match"], int(m["match_id"]),
                           m["playoff_name"] if m["stage"] == "Playoff" else "League"])
    return champion_rows, cap_rows, rivalry, ground, match_list, rivalry_ground


MIN_MATCHUP_BALLS = 6      # batter-vs-bowler pairs that met at least this many balls


def matchup_facts(deliveries, names):
    """
    Batter vs bowler for every pair with at least MIN_MATCHUP_BALLS balls:
    [batter, bowler, balls, runs, dismissals, dots, fours, sixes]
    (batter and bowler are positions in the sorted player-name list).
    """
    position = {}
    for i in range(len(names)):
        position[names[i]] = i
    table = metrics.matchup_table(deliveries, min_balls=MIN_MATCHUP_BALLS)
    rows = []
    for i in range(len(table)):
        row = table.iloc[i]
        rows.append([position[row["batter"]], position[row["bowler"]], clean(row["balls"]), clean(row["runs"]),
                     clean(row["dismissals"]), clean(row["dots"]), clean(row["fours"]), clean(row["sixes"])])
    return rows


FIT_MIN_BALLS = 30   # player-at-ground records with fewer balls are too small to quote


def pitch_facts(matches, deliveries):
    """
    How each ground plays (all seasons, and the Impact Player era 2023+):
    {venue: [matches, run rate, runs index, wickets index, boundary index, dot index,
             avg first innings, chase win %, label]}   (indexes: 100 = league in the same seasons)
    """
    parts = metrics.pitch_components(deliveries, matches)
    seasons = sorted(matches["season"].unique())
    result = {}
    for key, chosen in [("all", None), ("recent", [season for season in seasons if season >= 2023])]:
        profile = metrics.profile_from_components(parts, chosen)
        result[key] = {}
        for i in range(len(profile)):
            row = profile.iloc[i]
            result[key][row["venue"]] = [clean(row[column]) for column in
                                         ["matches", "run_rate", "runs_index", "wickets_index", "boundary_index",
                                          "dot_index", "avg_first_innings", "chase_win_pct", "label"]]
    return result


def fit_facts(matches, deliveries):
    """
    Each player at each ground vs other grounds in the same seasons (at least FIT_MIN_BALLS here):
      bat  "player|venue": [balls, runs, outs, else balls, else runs, else outs]
      bowl "player|venue": [legal balls, runs, wickets, else legal balls, else runs, else wickets]
    """
    batting = metrics.player_ground_batting(deliveries, matches)
    bowling = metrics.player_ground_bowling(deliveries, matches)
    bat = {}
    for i in range(len(batting)):
        row = batting.iloc[i]
        if row["balls"] >= FIT_MIN_BALLS:
            bat[row["batter"] + "|" + row["venue"]] = [clean(row[c]) for c in ["balls", "runs", "outs", "else_balls", "else_runs", "else_outs"]]
    bowl = {}
    for i in range(len(bowling)):
        row = bowling.iloc[i]
        if row["legal_balls"] >= FIT_MIN_BALLS:
            bowl[row["bowler"] + "|" + row["venue"]] = [clean(row[c]) for c in ["legal_balls", "runs", "wickets", "else_legal_balls",
                                                                                 "else_runs", "else_wickets"]]
    return {"bat": bat, "bowl": bowl}


def impact_facts(matches, deliveries, impact):
    """The Impact Player era comparison and how teams used the substitute."""
    summary = metrics.impact_era_summary(deliveries, matches)
    phases = metrics.impact_era_phase_run_rate(deliveries)
    choices = metrics.impact_choice_summary(metrics.impact_player_choices(impact, deliveries, matches), by_team=False)
    return {"eras": [[clean(v) for v in summary.iloc[i]] for i in range(len(summary))],
            "phases": [[phases["era"].iloc[i], phases["phase"].iloc[i], clean(phases["run_rate"].iloc[i])] for i in range(len(phases))],
            "choices": [[clean(v) for v in choices.iloc[i]] for i in range(len(choices))],
            "substitutions": len(impact)}


def prediction_facts(next_season):
    """Both models' 2027 predictions and the backtest scores (from the prediction CSV files)."""
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
        "teams": [[comparison["team"].iloc[i], clean(comparison["title_pct_a"].iloc[i]), clean(comparison["playoff_pct_a"].iloc[i]),
                   clean(comparison["title_pct_b"].iloc[i]), clean(comparison["playoff_pct_b"].iloc[i]),
                   clean(strengths.get(comparison["team"].iloc[i])), clean(squad.get(comparison["team"].iloc[i])),
                   clean(elo.get(comparison["team"].iloc[i]))] for i in range(len(comparison))],
        "awards_a": [[awards_a["award"].iloc[i], int(awards_a["rank"].iloc[i]), awards_a["player"].iloc[i], awards_a["team"].iloc[i],
                      clean(awards_a["form"].iloc[i]), awards_a["measure"].iloc[i]] for i in range(len(awards_a))],
        "awards_b": [[awards_b["award"].iloc[i], int(awards_b["rank"].iloc[i]), awards_b["player"].iloc[i], awards_b["team"].iloc[i],
                      clean(awards_b["predicted"].iloc[i]), awards_b["measure"].iloc[i]] for i in range(len(awards_b))],
        "backtest": [[overall["model"].iloc[i], clean(overall["matches"].iloc[i]), clean(overall["accuracy_pct"].iloc[i]),
                      clean(overall["log_loss"].iloc[i]), clean(overall["brier"].iloc[i])] for i in range(len(overall))],
        "titles": [[clean(v) for v in titles.iloc[i][["season", "teams", "champion", "champion_rank_a", "champion_rank_b"]]]
                   for i in range(len(titles))],
    }


# ---------------------------------------------------------------------------
# Fact lines (for the local-LLM server)
# ---------------------------------------------------------------------------
def overs(legal_balls):
    """117 -> "19.3"."""
    return str(int(legal_balls) // 6) + "." + str(int(legal_balls) % 6)


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
    venue_aliases = {}
    for venue in venues:
        venue_aliases[venue.lower()] = venue
    for venue in VENUE_ALIASES:
        for alias in VENUE_ALIASES[venue]:
            venue_aliases[alias] = venue
    # "at Chennai" means the main ground in Chennai (the ground with the most matches in that city).
    for city in sorted(matches["city"].unique()):
        rows = matches[matches["city"] == city]
        main_ground = rows["venue"].value_counts().sort_index().idxmax()
        venue_aliases["at " + city.lower()] = main_ground
        venue_aliases["in " + city.lower()] = main_ground
    venue_aliases["at bangalore"] = venue_aliases.get("at bengaluru", "M Chinnaswamy Stadium")
    team_aliases = {}
    for team in TEAM_ALIASES:
        for alias in TEAM_ALIASES[team]:
            team_aliases[alias] = team
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
