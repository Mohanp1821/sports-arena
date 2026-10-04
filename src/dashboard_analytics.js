// =============================================================================
// dashboard_analytics.js
// -----------------------------------------------------------------------------
// The ANALYST VIEWS of the Sports Arena dashboard:
//   1. Rivalry centre        (pick any two teams)
//   2. Matchups              (batter vs bowler, a player against each team,
//                             how a batter gets out)
//   3. Grounds               (pick a ground, and a team at that ground)
//   4. Specialists           (phase leaders, finishers, partnerships)
//   5. Impact Player era     (2020-22 vs 2023-26, each team's choices)
//   6. Trends                (scoring inflation, points tables, chase
//                             win-probability calculator, impact scores)
//
// How it works: build_report.py puts the tables calculated by
// src/dashboard_data.py into the page as JSON (<script id="analyst-data">).
// This script only LOOKS UP rows when a drop-down changes, and works out a few
// simple ratios (strike rate = runs / balls x 100) the same way metrics.py does.
//
// It uses the small helpers defined in dashboard_explorer.js (byId, safe,
// round, oversText, htmlTable, htmlBars), which is loaded first on the page.
// Plain JavaScript, no libraries, so the page works offline.
// =============================================================================

const AD = JSON.parse(document.getElementById("analyst-data").textContent);
const TEAMS = AD.teams;
const PLAYERS = AD.players;
const VENUES = AD.venues;


// ---------------------------------------------------------------------------
// Small helpers for this file
// ---------------------------------------------------------------------------
// "-" for a missing number (e.g. an average when the batter was never out).
function show(value) {
    return value === null || value === undefined ? "-" : value;
}

// A link that opens one match in the match centre page.
function matchLink(matchId, text) {
    return "<a href='match_centre.html#" + matchId + "'>" + safe(text) + "</a>";
}

// htmlTable() makes every cell safe text; this version allows links in cells.
function linkTable(titles, rows) {
    if (rows.length === 0) {
        return "<p class='note'>No data for this choice.</p>";
    }
    let html = "<table><thead><tr>";
    titles.forEach(function (title) { html += "<th>" + title + "</th>"; });
    html += "</tr></thead><tbody>";
    rows.forEach(function (row) {
        html += "<tr>";
        row.forEach(function (cell) { html += "<td>" + cell + "</td>"; });
        html += "</tr>";
    });
    return html + "</tbody></table>";
}

// Fill a <select> with options: values = list of [value, text].
function fillSelect(select, values, chosen) {
    select.innerHTML = "";
    values.forEach(function (pair) {
        const option = document.createElement("option");
        option.value = String(pair[0]);
        option.textContent = String(pair[1]);
        if (String(pair[0]) === String(chosen)) {
            option.selected = true;
        }
        select.appendChild(option);
    });
}

// A <datalist> of every player, shared by all the player boxes.
function addPlayerList() {
    const list = document.createElement("datalist");
    list.id = "analyst-players";
    PLAYERS.forEach(function (name) {
        const option = document.createElement("option");
        option.value = name;
        list.appendChild(option);
    });
    document.body.appendChild(list);
}

function playerIndex(name) {
    return PLAYERS.indexOf(name.trim());
}

function noPlayer(name) {
    return "<p class='note'>No player called \"" + safe(name) + "\". Pick a name from the list "
         + "(the data uses short names such as V Kohli, JJ Bumrah, MS Dhoni).</p>";
}

function strikeRate(runs, balls) {
    return balls > 0 ? round(runs / balls * 100, 1) : "-";
}

function economy(runs, legalBalls) {
    return legalBalls > 0 ? round(runs / (legalBalls / 6), 2) : "-";
}


// ---------------------------------------------------------------------------
// 1. Rivalry centre
// ---------------------------------------------------------------------------
function drawRivalry() {
    const a = Number(byId("riv-a").value);
    const b = Number(byId("riv-b").value);
    const out = byId("riv-out");
    if (a === b) {
        out.innerHTML = "<p class='note'>Pick two different teams.</p>";
        return;
    }
    // The data is stored once per pair, with the smaller team number first.
    const first = Math.min(a, b);
    const second = Math.max(a, b);
    const r = AD.rivalry[first + "|" + second];
    if (!r) {
        out.innerHTML = "<p class='note'>" + safe(TEAMS[a]) + " and " + safe(TEAMS[b])
                      + " never played each other.</p>";
        return;
    }
    const teamA = TEAMS[first];
    const teamB = TEAMS[second];
    let html = "<div class='numbers'>"
        + card("matches", r.overall[0]) + card(teamA + " wins", r.overall[1])
        + card(teamB + " wins", r.overall[2]) + card("no result", r.overall[3]) + "</div>";

    // Season by season, as bars of team A's share of wins.
    const seasonRows = r.seasons.map(function (row) { return [row[0], row[1], row[2], row[3], row[4]]; });
    html += "<div class='two-columns'>"
        + "<div class='panel'><h4>Season by season</h4><div class='table-box scroll'>"
        + htmlTable(["Season", "Played", teamA, teamB, "No result"], seasonRows) + "</div></div>"
        + "<div class='panel'><h4>League vs playoffs</h4>"
        + htmlTable(["Stage", "Played", teamA, teamB, "No result"], r.stages)
        + "<h4>At each ground</h4><div class='table-box scroll'>"
        + htmlTable(["Ground", "Played", teamA, teamB, "No result"], r.grounds) + "</div></div></div>";

    const last = r.last.map(function (row) {
        return [matchLink(row[0], row[1]), safe(row[3]), safe(row[4]), safe(row[5] || "-"), safe(row[6])];
    });
    html += "<div class='panel'><h4>Last " + r.last.length + " meetings (click a date to open the match)</h4>"
          + linkTable(["Date", "Ground", "Stage", "Winner", "Result"], last) + "</div>";

    function totalRows(rows) {
        return rows.map(function (row) {
            return [matchLink(row[6], row[0]), safe(row[1]), safe(row[2]), safe(row[3]), safe(row[4])];
        });
    }
    html += "<div class='two-columns'>"
        + "<div class='panel'><h4>Highest totals</h4>"
        + linkTable(["Score", "Overs", "Team", "Season", "Ground"], totalRows(r.high)) + "</div>"
        + "<div class='panel'><h4>Lowest totals</h4><p class='note'>Leaves out rain-shortened matches and "
        + "chases that were won.</p>"
        + linkTable(["Score", "Overs", "Team", "Season", "Ground"], totalRows(r.low)) + "</div></div>";

    html += "<div class='two-columns'>"
        + "<div class='panel'><h4>Top run-scorers in this fixture</h4>"
        + htmlTable(["Batter", "Team", "Inns", "Runs", "Balls", "SR", "Avg"],
                    r.bat.map(function (row) { return row.map(show); })) + "</div>"
        + "<div class='panel'><h4>Top wicket-takers in this fixture</h4>"
        + htmlTable(["Bowler", "Team", "Matches", "Wkts", "Overs", "Econ"],
                    r.bowl.map(function (row) { return row.map(show); })) + "</div></div>";
    out.innerHTML = html;
}

function setupRivalry() {
    const teamOptions = TEAMS.map(function (team, i) { return [i, team]; });
    fillSelect(byId("riv-a"), teamOptions, TEAMS.indexOf("Chennai Super Kings"));
    fillSelect(byId("riv-b"), teamOptions, TEAMS.indexOf("Mumbai Indians"));
    byId("riv-a").addEventListener("change", drawRivalry);
    byId("riv-b").addEventListener("change", drawRivalry);
    drawRivalry();
}


// ---------------------------------------------------------------------------
// 2. Matchups
// ---------------------------------------------------------------------------
function drawMatchup() {
    const batter = byId("mu-batter").value;
    const bowler = byId("mu-bowler").value;
    const b = playerIndex(batter);
    const w = playerIndex(bowler);
    const out = byId("mu-out");
    if (b < 0) { out.innerHTML = noPlayer(batter); return; }
    if (w < 0) { out.innerHTML = noPlayer(bowler); return; }
    // Row: [batter, bowler, balls, runs, dismissals, dots, fours, sixes]
    const row = AD.matchups.find(function (r) { return r[0] === b && r[1] === w; });
    if (!row) {
        out.innerHTML = "<p class='note'>" + safe(batter) + " never faced " + safe(bowler) + " in the data.</p>";
        return;
    }
    const balls = row[2], runs = row[3], outs = row[4];
    out.innerHTML = "<div class='numbers'>"
        + card("balls faced", balls) + card("runs", runs) + card("strike rate", strikeRate(runs, balls))
        + card("dismissals by " + bowler, outs)
        + card("dot balls %", round(row[5] / balls * 100, 1))
        + card("boundary %", round((row[6] + row[7]) / balls * 100, 1))
        + card("runs per dismissal", outs > 0 ? round(runs / outs, 1) : "never out")
        + card("4s / 6s", row[6] + " / " + row[7]) + "</div>"
        + "<p class='note'>Balls faced leave out wides. A dismissal here is a wicket credited to the bowler "
        + "(run outs are not).</p>";
}

function drawPlayerTeams() {
    const name = byId("pt-player").value;
    const p = playerIndex(name);
    const out = byId("pt-out");
    if (p < 0) { out.innerHTML = noPlayer(name); return; }
    // Batting rows: [player, opponent, innings, runs, balls, dismissals, sixes]
    const bat = AD.bat_vs.filter(function (r) { return r[0] === p; }).map(function (r) {
        return [TEAMS[r[1]], r[2], r[3], r[4], r[5] > 0 ? round(r[3] / r[5], 1) : "-", strikeRate(r[3], r[4]), r[6]];
    });
    bat.sort(function (x, y) { return y[2] - x[2]; });
    // Bowling rows: [player, opponent, matches, wickets, legal balls, runs]
    const bowl = AD.bowl_vs.filter(function (r) { return r[0] === p; }).map(function (r) {
        return [TEAMS[r[1]], r[2], r[3], oversText(r[4]), economy(r[5], r[4])];
    });
    bowl.sort(function (x, y) { return y[2] - x[2]; });
    // How the batter gets out: [player, kind, times]
    const outs = AD.outs.filter(function (r) { return r[0] === p; });
    const totalOuts = outs.reduce(function (sum, r) { return sum + r[2]; }, 0);
    const bars = outs.map(function (r) {
        const pct = round(r[2] / totalOuts * 100, 1);
        return { label: AD.out_kinds[r[1]], value: pct, text: r[2] + " times (" + pct + "%)" };
    });
    out.innerHTML = "<div class='two-columns'>"
        + "<div class='panel'><h4>Batting against each team</h4><div class='table-box'>"
        + htmlTable(["Opponent", "Inns", "Runs", "Balls", "Avg", "SR", "6s"], bat) + "</div></div>"
        + "<div class='panel'><h4>How " + safe(name) + " gets out (" + totalOuts + " dismissals)</h4>"
        + (bars.length ? htmlBars(bars, 100, "") : "<p class='note'>Never dismissed.</p>") + "</div></div>"
        + "<div class='panel'><h4>Bowling against each team</h4><div class='table-box'>"
        + htmlTable(["Opponent", "Matches", "Wickets", "Overs", "Economy"], bowl) + "</div></div>";
}

function setupMatchups() {
    byId("mu-batter").value = "V Kohli";
    byId("mu-bowler").value = "JJ Bumrah";
    byId("pt-player").value = "V Kohli";
    ["mu-batter", "mu-bowler"].forEach(function (id) { byId(id).addEventListener("change", drawMatchup); });
    byId("pt-player").addEventListener("change", drawPlayerTeams);
    drawMatchup();
    drawPlayerTeams();
}


// ---------------------------------------------------------------------------
// 3. Grounds
// ---------------------------------------------------------------------------
function drawGround() {
    const v = Number(byId("gr-venue").value);
    // Summary row: [venue, city, matches, first, last, avg 1st inns, chase win %,
    //               chose bat (n), chose bat win %, chose field (n), chose field win %, highest]
    const g = AD.grounds.find(function (r) { return r[0] === v; });
    let html = "<p class='note'>" + safe(VENUES[v]) + ", " + safe(g[1]) + ": IPL matches " + g[3] + "-" + g[4] + "</p>"
        + "<div class='numbers'>" + card("matches", g[2]) + card("avg 1st-innings score", show(g[5]))
        + card("chasing team won", show(g[6]) + "%") + card("highest total", show(g[11]))
        + card("toss winner chose to bat: won", show(g[8]) + "% (" + g[7] + ")")
        + card("toss winner chose to field: won", show(g[10]) + "% (" + g[9] + ")") + "</div>";

    const seasons = AD.ground_seasons.filter(function (r) { return r[0] === v; });
    const maxAvg = Math.max.apply(null, seasons.map(function (r) { return r[3]; }).concat([1]));
    const bars = seasons.map(function (r) {
        return { label: String(r[1]), value: r[3], text: r[3] + " (" + r[2] + " matches)" };
    });
    const phases = ["Powerplay", "Middle", "Death"].map(function (phase) {
        const row = AD.ground_phases.find(function (r) { return r[0] === v && r[1] === phase; });
        return [phase, row ? row[2] : "-"];
    });
    const high = (AD.ground_high[String(v)] || []).map(function (r) {
        return [matchLink(r[5], r[0]), safe(r[1]), safe(r[2]), safe(r[3])];
    });
    html += "<div class='two-columns'>"
        + "<div class='panel'><h4>Average first-innings score by season</h4>" + htmlBars(bars, maxAvg, "") + "</div>"
        + "<div class='panel'><h4>Run rate by phase</h4>" + htmlTable(["Phase", "Runs per over"], phases)
        + "<h4>Highest totals</h4>" + linkTable(["Score", "Team", "Against", "Season"], high) + "</div></div>";
    byId("gr-out").innerHTML = html;
    drawTeamAtGround();
}

function drawTeamAtGround() {
    const v = Number(byId("gr-venue").value);
    const t = Number(byId("gr-team").value);
    // Rows: [team, venue, season, played, wins]
    const rows = AD.team_ground.filter(function (r) { return r[0] === t && r[1] === v; });
    let played = 0, wins = 0;
    const table = rows.map(function (r) {
        played += r[3];
        wins += r[4];
        return [r[2], r[3], r[4], round(r[4] / r[3] * 100, 1) + "%"];
    });
    byId("gr-team-out").innerHTML = rows.length === 0
        ? "<p class='note'>" + safe(TEAMS[t]) + " never played at this ground (no-results not counted).</p>"
        : "<p><b>" + safe(TEAMS[t]) + "</b> here: " + wins + " wins in " + played + " matches ("
          + round(wins / played * 100, 1) + "%)</p>" + htmlTable(["Season", "Played", "Won", "Win %"], table);
}

function setupGrounds() {
    fillSelect(byId("gr-venue"), VENUES.map(function (v, i) { return [i, v]; }),
               VENUES.indexOf("MA Chidambaram Stadium, Chepauk"));
    fillSelect(byId("gr-team"), TEAMS.map(function (t, i) { return [i, t]; }), TEAMS.indexOf("Chennai Super Kings"));
    byId("gr-venue").addEventListener("change", drawGround);
    byId("gr-team").addEventListener("change", drawTeamAtGround);
    byId("gr-fortress").innerHTML = htmlTable(
        ["Team", "Home ground(s)", "Home played", "Home win %", "Away played", "Away win %", "Fortress index"],
        AD.fortress);
    drawGround();
}


// ---------------------------------------------------------------------------
// 4. Specialists
// ---------------------------------------------------------------------------
function drawLeaders() {
    const season = byId("sp-season").value;
    const phase = byId("sp-phase").value;
    const data = AD.phase_leaders[season + "|" + phase];
    const minBalls = season === "all" ? AD.min_balls[0] : AD.min_balls[1];
    byId("sp-out").innerHTML = "<p class='note'>Minimum " + minBalls + " balls in the " + phase
        + " overs" + (season === "all" ? " (all seasons)." : " in " + season + ".") + "</p>"
        + "<div class='two-columns'>"
        + "<div class='panel'><h4>Batting: most runs</h4>"
        + htmlTable(["Batter", "Runs", "Balls", "SR", "6s", "Outs"], data.bat) + "</div>"
        + "<div class='panel'><h4>Bowling: most wickets</h4>"
        + htmlTable(["Bowler", "Wkts", "Overs", "Econ", "Dot %"], data.bowl) + "</div></div>";
}

function drawPartnerships() {
    const team = byId("sp-team").value;
    const rows = AD.partnerships[team].map(function (r) {
        return [safe(r[0]), r[1], r[2], r[3], safe(r[4]), r[5], matchLink(r[8], r[7])];
    });
    byId("sp-partners").innerHTML = linkTable(["Pair", "Wicket", "Runs", "Balls", "Team", "Season", "Date"], rows);
}

function setupSpecialists() {
    fillSelect(byId("sp-season"), [["all", "All seasons"]].concat(AD.seasons.map(function (s) { return [s, s]; })), "all");
    fillSelect(byId("sp-phase"), [["Powerplay", "Powerplay (overs 1-6)"], ["Middle", "Middle (overs 7-15)"],
                                  ["Death", "Death (overs 16-20)"]], "Death");
    fillSelect(byId("sp-team"), [["all", "All teams"]].concat(TEAMS.map(function (t) { return [t, t]; })), "all");
    byId("sp-season").addEventListener("change", drawLeaders);
    byId("sp-phase").addEventListener("change", drawLeaders);
    byId("sp-team").addEventListener("change", drawPartnerships);
    byId("sp-finishers").innerHTML = htmlTable(
        ["Batter", "Death runs", "Death balls", "Death SR", "Chase inns", "Not outs", "Not out %", "Won chase, not out"],
        AD.finishers);
    drawLeaders();
    drawPartnerships();
}


// ---------------------------------------------------------------------------
// 5. Impact Player era
// ---------------------------------------------------------------------------
function drawImpactTeam() {
    const team = byId("ip-team").value;
    const rows = AD.choices_team.filter(function (r) { return r[0] === team; }).map(function (r) {
        return [r[1], r[2], r[3], r[4] + "%"];
    });
    byId("ip-team-out").innerHTML = htmlTable(["What the Impact Player did", "Times", "Wins", "Win %"], rows);
}

function setupImpact() {
    byId("ip-summary").innerHTML = htmlTable(
        ["Era", "Matches", "Avg 1st-innings score", "Totals of 200+", "200+ per match", "Chases won %"], AD.era_summary);
    const phaseRows = ["Powerplay", "Middle", "Death"].map(function (phase) {
        const values = AD.era_summary.map(function (era) {
            const row = AD.era_phases.find(function (r) { return r[0] === era[0] && r[1] === phase; });
            return row ? row[2] : "-";
        });
        return [phase].concat(values);
    });
    byId("ip-phases").innerHTML = htmlTable(["Phase"].concat(AD.era_summary.map(function (e) { return e[0]; })), phaseRows);
    byId("ip-all").innerHTML = htmlTable(["What the Impact Player did", "Times", "Wins", "Win %"],
        AD.choices_all.map(function (r) { return [r[0], r[1], r[2], r[3] + "%"]; }));
    const teamsUsed = AD.current_teams.filter(function (t) {
        return AD.choices_team.some(function (r) { return r[0] === t; });
    });
    fillSelect(byId("ip-team"), teamsUsed.map(function (t) { return [t, t]; }), teamsUsed[0]);
    byId("ip-team").addEventListener("change", drawImpactTeam);
    drawImpactTeam();
}


// ---------------------------------------------------------------------------
// 6. Trends
// ---------------------------------------------------------------------------
function drawPoints() {
    const season = byId("tr-season").value;
    const table = AD.points[season];
    byId("tr-points").innerHTML = htmlTable(["Pos", "Team", "P", "W", "L", "NR", "Pts", "NRR"], table.rows)
        + (table.note ? "<p class='note'>" + safe(table.note) + "</p>" : "");
}

// The logistic regression from metrics.win_probability_model, with the
// weights it learned:  chance = 1 / (1 + e^-(b0 + b1*runs + b2*balls + b3*wickets + b4*rate))
function chaseChance(runsNeeded, ballsLeft, wicketsLeft) {
    const m = AD.chase_model;
    const rate = runsNeeded * 6 / ballsLeft;
    const z = m.intercept + m.runs_needed * runsNeeded + m.balls_left * ballsLeft
            + m.wickets_left * wicketsLeft + m.required_rate * rate;
    return 1 / (1 + Math.exp(-z));
}

function drawChase() {
    const runs = Number(byId("tr-runs").value);
    const balls = Number(byId("tr-balls").value);
    const wickets = Number(byId("tr-wickets").value);
    const out = byId("tr-chance");
    if (!(runs > 0) || !(balls > 0 && balls <= 120) || !(wickets >= 1 && wickets <= 10)) {
        out.innerHTML = "<p class='note'>Enter runs needed (1+), balls left (1-120) and wickets left (1-10).</p>";
        return;
    }
    const chance = round(chaseChance(runs, balls, wickets) * 100, 1);
    out.innerHTML = "<div class='numbers'>" + card("chance the chasing team wins", chance + "%")
        + card("required run rate", round(runs * 6 / balls, 2)) + "</div>";
}

function drawImpactScores() {
    const season = Number(byId("tr-impact-season").value);
    // Rows: [player, season, team, runs, wickets, batting points, bowling points, impact]
    const rows = AD.impact_scores.filter(function (r) { return r[1] === season; }).slice(0, 10)
        .map(function (r, i) { return [i + 1, PLAYERS[r[0]], r[2], r[3], r[4], r[5], r[6], r[7]]; });
    byId("tr-impact").innerHTML = htmlTable(["#", "Player", "Team", "Runs", "Wkts", "Bat pts", "Bowl pts", "Impact"], rows);
}

function drawImpactPlayer() {
    const name = byId("tr-impact-player").value;
    const p = playerIndex(name);
    const out = byId("tr-impact-player-out");
    if (p < 0) { out.innerHTML = noPlayer(name); return; }
    const rows = AD.impact_scores.filter(function (r) { return r[0] === p; })
        .map(function (r) { return [r[1], r[2], r[3], r[4], r[7]]; });
    out.innerHTML = htmlTable(["Season", "Team", "Runs", "Wkts", "Impact score"], rows);
}

function setupTrends() {
    byId("tr-inflation").innerHTML = htmlTable(["Season", "Matches", "Avg 1st-innings score", "Sixes per match",
                                                "Run rate"], AD.inflation);
    const seasonOptions = AD.seasons.slice().reverse().map(function (s) { return [s, s]; });
    fillSelect(byId("tr-season"), seasonOptions, AD.seasons[AD.seasons.length - 1]);
    fillSelect(byId("tr-impact-season"), seasonOptions, AD.seasons[AD.seasons.length - 1]);
    byId("tr-season").addEventListener("change", drawPoints);
    byId("tr-impact-season").addEventListener("change", drawImpactScores);
    ["tr-runs", "tr-balls", "tr-wickets"].forEach(function (id) { byId(id).addEventListener("input", drawChase); });
    byId("tr-impact-player").value = "V Kohli";
    byId("tr-impact-player").addEventListener("change", drawImpactPlayer);
    drawPoints();
    drawChase();
    drawImpactScores();
    drawImpactPlayer();
}


// ---------------------------------------------------------------------------
// Start: draw every view once when the page opens.
// ---------------------------------------------------------------------------
addPlayerList();
setupRivalry();
setupMatchups();
setupGrounds();
setupSpecialists();
setupImpact();
setupTrends();
