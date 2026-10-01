// =============================================================================
// dashboard_explorer.js
// -----------------------------------------------------------------------------
// The INTERACTIVE part of the Sports Arena dashboard ("Explore the data").
//
// How it works:
//   1. build_report.py puts small data tables into the page as JSON text
//      (inside <script id="explorer-data">) and copies this file into the page.
//   2. This script reads that JSON once.
//   3. Every time a filter changes (season, team or player), it filters the
//      rows, adds them up, and redraws the cards, bar chart and tables.
//
// Plain JavaScript only: no libraries and no internet needed, so the page
// still works when it is opened straight from the outputs/ folder.
// =============================================================================


// ---------------------------------------------------------------------------
// 1. Read the data
// ---------------------------------------------------------------------------
const DATA = JSON.parse(document.getElementById("explorer-data").textContent);

// To keep the page small, every row is stored as a list, e.g.
//   ["V Kohli", 2016, "Royal Challengers Bengaluru", 973, 640, 38, 16]
// Here we turn each list into an object with named fields, which is easier to read.
const MATCHES = DATA.matches.map(function (row) {
    return { season: row[0], date: row[1], team1: row[2], team2: row[3],
             winner: row[4], margin: row[5], potm: row[6] };
});
const BATTING = DATA.batting.map(function (row) {
    return { player: row[0], season: row[1], team: row[2],
             runs: row[3], balls: row[4], sixes: row[5], innings: row[6] };
});
const BOWLING = DATA.bowling.map(function (row) {
    return { player: row[0], season: row[1], team: row[2],
             wickets: row[3], balls: row[4], runs: row[5] };
});
const CHAMPIONS = DATA.champions;     // e.g. { "2016": "Sunrisers Hyderabad", ... }


// ---------------------------------------------------------------------------
// 2. Small helpers
// ---------------------------------------------------------------------------
function byId(id) {
    return document.getElementById(id);
}

// Make text safe to put inside HTML (player names can contain characters like ').
function safe(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                       .replace(/>/g, "&gt;").replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}

// Round a number to a number of decimal places, e.g. round(53.456, 1) = 53.5
function round(value, places) {
    const factor = Math.pow(10, places);
    return Math.round(value * factor) / factor;
}

// Overs the cricket way: 148 balls = 24 overs and 4 balls, written "24.4" (not 24.7).
function oversText(balls) {
    return Math.floor(balls / 6) + "." + (balls % 6);
}

// Keep only the rows for the chosen season and team ("all" = no filter).
function filterRows(rows, season, team) {
    return rows.filter(function (row) {
        const seasonOk = season === "all" || row.season === Number(season);
        const teamOk = team === "all" || row.team === team;
        return seasonOk && teamOk;
    });
}

// Add up the number columns for each player (like pandas groupby + sum).
function totalsByPlayer(rows, numberColumns) {
    const totals = {};
    rows.forEach(function (row) {
        if (!(row.player in totals)) {
            totals[row.player] = { player: row.player };
            numberColumns.forEach(function (column) { totals[row.player][column] = 0; });
        }
        numberColumns.forEach(function (column) { totals[row.player][column] += row[column]; });
    });
    return Object.values(totals);
}

// Build an HTML table from a list of column titles and a list of rows.
function htmlTable(titles, rows) {
    if (rows.length === 0) {
        return "<p class='note'>No data for this choice.</p>";
    }
    let html = "<table><thead><tr>";
    titles.forEach(function (title) { html += "<th>" + title + "</th>"; });
    html += "</tr></thead><tbody>";
    rows.forEach(function (row) {
        html += "<tr>";
        row.forEach(function (cell) { html += "<td>" + safe(cell) + "</td>"; });
        html += "</tr>";
    });
    return html + "</tbody></table>";
}

// Draw a horizontal bar chart with plain HTML: one row per bar.
//   bars = [{ label: "Mumbai Indians", value: 58.3, text: "58.3%", key: "Mumbai Indians" }, ...]
// "key" makes the bar clickable (clicking a team bar selects that team).
function htmlBars(bars, maxValue, highlightLabel) {
    if (bars.length === 0) {
        return "<p class='note'>No data for this choice.</p>";
    }
    let html = "";
    bars.forEach(function (bar) {
        const width = maxValue > 0 ? (bar.value / maxValue) * 100 : 0;
        const classes = "bar-row" + (bar.label === highlightLabel ? " highlight" : "")
                        + (bar.key ? " clickable" : "");
        const keyAttribute = bar.key ? " data-key='" + safe(bar.key) + "'" : "";
        html += "<div class='" + classes + "'" + keyAttribute + ">"
              + "<span class='bar-label'>" + safe(bar.label) + "</span>"
              + "<span class='bar-track'><span class='bar-fill' style='width:" + width + "%'></span></span>"
              + "<span class='bar-value'>" + safe(bar.text) + "</span></div>";
    });
    return html;
}


// ---------------------------------------------------------------------------
// 3. Calculations (the same cricket formulas as metrics.py)
// ---------------------------------------------------------------------------
// Matches in the chosen season that involve the chosen team.
function chosenMatches(season, team) {
    return MATCHES.filter(function (match) {
        const seasonOk = season === "all" || match.season === Number(season);
        const teamOk = team === "all" || match.team1 === team || match.team2 === team;
        return seasonOk && teamOk;
    });
}

// Win % for every team: wins / matches played * 100 (no-result matches left out).
function winTable(matches) {
    const table = {};
    matches.forEach(function (match) {
        if (match.winner === "") {
            return;                       // no result: nobody won, so skip it
        }
        [match.team1, match.team2].forEach(function (team) {
            if (!(team in table)) {
                table[team] = { team: team, played: 0, wins: 0 };
            }
            table[team].played += 1;
            if (match.winner === team) {
                table[team].wins += 1;
            }
        });
    });
    return Object.values(table).map(function (row) {
        row.winPct = round(row.wins / row.played * 100, 1);
        return row;
    });
}

// Top run scorers: strike rate = runs / balls faced * 100
function topBatters(season, team, howMany) {
    const totals = totalsByPlayer(filterRows(BATTING, season, team), ["runs", "balls", "sixes", "innings"]);
    totals.sort(function (a, b) { return b.runs - a.runs || a.player.localeCompare(b.player); });
    return totals.slice(0, howMany);
}

// Top wicket takers: economy = runs conceded / overs (ties broken by economy, like the Purple Cap)
function topBowlers(season, team, howMany) {
    const totals = totalsByPlayer(filterRows(BOWLING, season, team), ["wickets", "balls", "runs"]);
    totals.forEach(function (row) { row.economy = row.balls > 0 ? row.runs / (row.balls / 6) : 0; });
    totals.sort(function (a, b) { return b.wickets - a.wickets || a.economy - b.economy; });
    return totals.slice(0, howMany);
}

// Titles won by a team (in one season, or in all seasons).
function titlesWon(season, team) {
    let titles = 0;
    Object.keys(CHAMPIONS).forEach(function (year) {
        const seasonOk = season === "all" || year === season;
        if (seasonOk && CHAMPIONS[year] === team) {
            titles += 1;
        }
    });
    return titles;
}


// ---------------------------------------------------------------------------
// 4. Drawing each part of the section
// ---------------------------------------------------------------------------
function card(label, value) {
    return "<div class='number'><b>" + safe(value) + "</b><span>" + safe(label) + "</span></div>";
}

function drawCards(season, team) {
    const matches = chosenMatches(season, team);
    let html = "";
    if (team === "all") {
        const bestBatter = topBatters(season, "all", 1)[0];
        const bestBowler = topBowlers(season, "all", 1)[0];
        let titleCard;
        if (season === "all") {
            // Count titles per team, then pick the team with the most.
            const counts = {};
            Object.values(CHAMPIONS).forEach(function (t) { counts[t] = (counts[t] || 0) + 1; });
            const most = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })[0];
            titleCard = card("most titles (" + counts[most] + ")", most);
        } else {
            titleCard = card("champion " + season, CHAMPIONS[season]);
        }
        html += card("matches", matches.length) + titleCard
              + card("top run scorer (" + bestBatter.runs + " runs)", bestBatter.player)
              + card("top wicket taker (" + bestBowler.wickets + " wickets)", bestBowler.player);
    } else {
        const row = winTable(matches).find(function (r) { return r.team === team; });
        const played = row ? row.played : 0;
        const wins = row ? row.wins : 0;
        const winPct = row ? row.winPct + "%" : "-";
        html += card("matches played", played) + card("matches won", wins)
              + card("win %", winPct) + card("titles", titlesWon(season, team));
    }
    byId("explore-cards").innerHTML = html;
}

function drawWinChart(season, team) {
    let bars;
    let title;
    if (team === "all") {
        // One bar per team, best win % at the top. Click a bar to pick that team.
        const table = winTable(chosenMatches(season, "all"));
        table.sort(function (a, b) { return b.winPct - a.winPct; });
        bars = table.map(function (row) {
            return { label: row.team, value: row.winPct, key: row.team,
                     text: row.winPct + "% (" + row.wins + "/" + row.played + ")" };
        });
        title = "Win % by team, " + (season === "all" ? "2008-2019" : season) + " (click a team to select it)";
    } else {
        // One bar per season for the chosen team. Click a bar to pick that season.
        bars = [];
        DATA.seasons.forEach(function (year) {
            const row = winTable(chosenMatches(String(year), team)).find(function (r) { return r.team === team; });
            if (row) {
                const champion = CHAMPIONS[String(year)] === team ? " 🏆" : "";
                bars.push({ label: String(year), value: row.winPct, key: String(year),
                            text: row.winPct + "% (" + row.wins + "/" + row.played + ")" + champion });
            }
        });
        title = team + ": win % by season (🏆 = champion, click a season to select it)";
    }
    byId("explore-chart-title").textContent = title;
    byId("explore-chart").innerHTML = htmlBars(bars, 100, team === "all" ? team : season);
}

function drawTopTables(season, team) {
    const batters = topBatters(season, team, 10).map(function (row, i) {
        const strikeRate = row.balls > 0 ? round(row.runs / row.balls * 100, 1) : 0;
        return [i + 1, row.player, row.runs, row.innings, strikeRate, row.sixes];
    });
    byId("explore-batting").innerHTML =
        htmlTable(["#", "Batter", "Runs", "Innings", "Strike rate", "Sixes"], batters);

    const bowlers = topBowlers(season, team, 10).map(function (row, i) {
        return [i + 1, row.player, row.wickets, oversText(row.balls), round(row.economy, 2)];
    });
    byId("explore-bowling").innerHTML =
        htmlTable(["#", "Bowler", "Wickets", "Overs", "Economy"], bowlers);
}

function drawResults(season, team) {
    if (season === "all") {
        byId("explore-results").innerHTML =
            "<p class='note'>Choose a season above to see every match result.</p>";
        return;
    }
    const rows = chosenMatches(season, team).map(function (match) {
        const winner = match.winner === "" ? "-" : match.winner;
        return [match.date, match.team1 + " v " + match.team2, winner, match.margin, match.potm];
    });
    byId("explore-results").innerHTML =
        htmlTable(["Date", "Match", "Winner", "Margin", "Player of the Match"], rows);
}

// Redraw everything that depends on the season and team filters.
function drawAll() {
    const season = byId("filter-season").value;
    const team = byId("filter-team").value;
    drawCards(season, team);
    drawWinChart(season, team);
    drawTopTables(season, team);
    drawResults(season, team);
}


// ---------------------------------------------------------------------------
// 5. Player search (a career, season by season)
// ---------------------------------------------------------------------------
function drawPlayer() {
    const name = byId("filter-player").value.trim();
    const battingRows = BATTING.filter(function (row) { return row.player === name; });
    const bowlingRows = BOWLING.filter(function (row) { return row.player === name; });
    if (battingRows.length === 0 && bowlingRows.length === 0) {
        byId("player-chart").innerHTML = "";
        byId("player-table").innerHTML = name === "" ? "" :
            "<p class='note'>No player called \"" + safe(name) + "\". Pick a name from the list "
            + "(the data uses short names, e.g. V Kohli, MS Dhoni, JJ Bumrah).</p>";
        return;
    }

    const rows = [];
    const bars = [];
    let maxRuns = 0;
    DATA.seasons.forEach(function (year) {
        const bat = battingRows.filter(function (r) { return r.season === year; });
        const bowl = bowlingRows.filter(function (r) { return r.season === year; });
        if (bat.length === 0 && bowl.length === 0) {
            return;                       // did not play this season
        }
        // A player can appear for 2 teams in one season, so add the rows up.
        let runs = 0, balls = 0, sixes = 0, wickets = 0, ballsBowled = 0, runsConceded = 0;
        const teams = [];
        bat.forEach(function (r) { runs += r.runs; balls += r.balls; sixes += r.sixes; teams.push(r.team); });
        bowl.forEach(function (r) {
            wickets += r.wickets; ballsBowled += r.balls; runsConceded += r.runs; teams.push(r.team);
        });
        const uniqueTeams = teams.filter(function (t, i) { return teams.indexOf(t) === i; });
        const strikeRate = balls > 0 ? round(runs / balls * 100, 1) : "-";
        const economy = ballsBowled > 0 ? round(runsConceded / (ballsBowled / 6), 2) : "-";
        rows.push([year, uniqueTeams.join(", "), runs, strikeRate, sixes, wickets, economy]);
        bars.push({ label: String(year), value: runs, text: runs + " runs" });
        maxRuns = Math.max(maxRuns, runs);
    });

    byId("player-chart").innerHTML = "<h4>" + safe(name) + ": runs per season</h4>" + htmlBars(bars, maxRuns, "");
    byId("player-table").innerHTML =
        htmlTable(["Season", "Team", "Runs", "Strike rate", "Sixes", "Wickets", "Economy"], rows);
}


// ---------------------------------------------------------------------------
// 6. Fill the drop-downs and connect the filters
// ---------------------------------------------------------------------------
function addOptions(selectId, values) {
    const select = byId(selectId);
    values.forEach(function (value) {
        const option = document.createElement("option");
        option.value = String(value);
        option.textContent = String(value);
        select.appendChild(option);
    });
}

addOptions("filter-season", DATA.seasons);
addOptions("filter-team", DATA.teams);
DATA.players.forEach(function (name) {
    const option = document.createElement("option");
    option.value = name;
    byId("player-list").appendChild(option);
});

byId("filter-season").addEventListener("change", drawAll);
byId("filter-team").addEventListener("change", drawAll);
byId("filter-reset").addEventListener("click", function () {
    byId("filter-season").value = "all";
    byId("filter-team").value = "all";
    drawAll();
});

// Clicking a bar in the win % chart selects that team (or that season).
byId("explore-chart").addEventListener("click", function (event) {
    const bar = event.target.closest(".bar-row.clickable");
    if (!bar) {
        return;
    }
    if (byId("filter-team").value === "all") {
        byId("filter-team").value = bar.dataset.key;
    } else {
        byId("filter-season").value = bar.dataset.key;
    }
    drawAll();
});

byId("filter-player").addEventListener("input", drawPlayer);

// Draw the section once when the page opens.
byId("filter-player").value = DATA.default_player;
drawAll();
drawPlayer();
