// =============================================================================
// match_centre.js
// -----------------------------------------------------------------------------
// Draws the match centre page (outputs/match_centre.html):
//   left  : the list of matches (filter by season, team or a search word)
//   right : one match: Scorecard | Over by over | Raw ball rows
//
// The data is inside the page (<script id="match-data">), written by
// src/match_centre.py. One ball is a list of 14 numbers:
//   [over, ball, batter, non_striker, bowler, batsman_runs, wide_runs,
//    noball_runs, bye_runs, legbye_runs, penalty_runs, player_dismissed,
//    dismissal_kind, fielder]     names are positions in DATA.p, -1 = nobody
//
// Open a match directly with its id after "#", e.g. match_centre.html#1535465
// Plain JavaScript, no libraries, so it works offline.
// =============================================================================

const DATA = JSON.parse(document.getElementById("match-data").textContent);
const NAMES = DATA.p;
const KINDS = DATA.k;
const MATCHES = DATA.m.slice().sort(function (a, b) { return b.d.localeCompare(a.d) || b.id - a.id; });
// Dismissals credited to the bowler (a run out is not).
const BOWLER_KINDS = ["bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"];

let current = null;      // the match on screen
let view = "card";       // "card", "overs" or "raw"


function byId(id) { return document.getElementById(id); }

function safe(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function nameOf(position) { return position >= 0 ? NAMES[position] : ""; }

// 117 legal balls -> "19.3" overs (19 overs and 3 balls).
function oversText(balls) { return Math.floor(balls / 6) + (balls % 6 ? "." + (balls % 6) : ""); }

// All runs from one ball: bat + wides + no-balls + byes + leg-byes + penalty.
function ballRuns(b) { return b[5] + b[6] + b[7] + b[8] + b[9] + b[10]; }

// A wicket that counts for the team total (retired hurt does not).
function isWicket(b) { return b[11] >= 0 && KINDS[b[12]] !== "retired hurt"; }

// Total, wickets and legal balls of one innings.
function inningsTotal(innings) {
    let runs = 0, wickets = 0, legal = 0;
    innings.b.forEach(function (b) {
        runs += ballRuns(b);
        if (isWicket(b)) { wickets += 1; }
        if (b[6] === 0 && b[7] === 0) { legal += 1; }     // not a wide and not a no-ball
    });
    return { runs: runs, wickets: wickets, legal: legal };
}

function scoreText(innings) {
    const t = inningsTotal(innings);
    return t.runs + "/" + t.wickets + " (" + oversText(t.legal) + ")";
}


// ---------------------------------------------------------------------------
// The match list
// ---------------------------------------------------------------------------
function filteredMatches() {
    const season = byId("season").value;
    const team = byId("team").value;
    const word = byId("search").value.trim().toLowerCase();
    return MATCHES.filter(function (m) {
        const seasonOk = season === "all" || m.s === Number(season);
        const teamOk = team === "all" || m.f1 === team || m.f2 === team;
        const text = (m.t1 + " " + m.t2 + " " + m.v + " " + m.c + " " + m.pom + " " + m.st).toLowerCase();
        return seasonOk && teamOk && (word === "" || text.indexOf(word) >= 0);
    });
}

function drawList() {
    const list = filteredMatches();
    let html = "<p class='note' style='padding:6px 12px;margin:0'>" + list.length + " matches</p>";
    list.slice(0, 400).forEach(function (m) {
        const scores = m.i.filter(function (inn) { return !inn.so; }).map(scoreText).join(" v ");
        html += "<button class='row" + (current && current.id === m.id ? " current" : "") + "' data-id='" + m.id + "'>"
              + "<b>" + safe(m.t1) + " v " + safe(m.t2) + "</b>"
              + "<small>" + m.d + " · " + safe(m.c) + (m.st !== "League" ? " · " + safe(m.st) : "") + "</small>"
              + "<small>" + safe(scores) + "</small><small>" + safe(m.res) + "</small></button>";
    });
    if (list.length > 400) {
        html += "<p class='note' style='padding:6px 12px'>Showing the first 400. Pick a season or team to see the rest.</p>";
    }
    byId("list").innerHTML = html;
}


// ---------------------------------------------------------------------------
// Scorecard
// ---------------------------------------------------------------------------
// How a batter got out, written the cricket way: "c Fielder b Bowler".
function howOut(b) {
    const kind = KINDS[b[12]];
    const bowler = nameOf(b[4]);
    const fielder = nameOf(b[13]).split(", ")[0].replace(" (sub)", "");
    if (kind === "caught") { return "c " + fielder + " b " + bowler; }
    if (kind === "caught and bowled") { return "c & b " + bowler; }
    if (kind === "bowled") { return "b " + bowler; }
    if (kind === "lbw") { return "lbw b " + bowler; }
    if (kind === "stumped") { return "st " + fielder + " b " + bowler; }
    if (kind === "hit wicket") { return "hit wicket b " + bowler; }
    if (kind === "run out") { return "run out" + (b[13] >= 0 ? " (" + nameOf(b[13]).replace(/ \(sub\)/g, "") + ")" : ""); }
    return kind;    // retired hurt, retired out, obstructing the field
}

function scorecardHTML(innings) {
    const batters = [];            // in batting order
    const bat = {};
    function addBatter(p) {
        if (!(p in bat)) { bat[p] = { runs: 0, balls: 0, fours: 0, sixes: 0, out: "not out" }; batters.push(p); }
    }
    const bowlers = [];
    const bowl = {};
    const extras = { wd: 0, nb: 0, b: 0, lb: 0, p: 0 };
    innings.b.forEach(function (b) {
        addBatter(b[2]);
        addBatter(b[3]);
        const x = bat[b[2]];
        x.runs += b[5];
        if (b[6] === 0) { x.balls += 1; }                 // a wide is not a ball faced
        if (b[5] === 4) { x.fours += 1; }
        if (b[5] === 6) { x.sixes += 1; }
        if (b[11] >= 0) { addBatter(b[11]); bat[b[11]].out = howOut(b); }
        if (!(b[4] in bowl)) { bowl[b[4]] = { legal: 0, runs: 0, wickets: 0, dots: 0 }; bowlers.push(b[4]); }
        const y = bowl[b[4]];
        if (b[6] === 0 && b[7] === 0) { y.legal += 1; }
        y.runs += b[5] + b[6] + b[7];                     // byes and leg-byes are not the bowler's
        if (b[11] >= 0 && BOWLER_KINDS.indexOf(KINDS[b[12]]) >= 0) { y.wickets += 1; }
        if (b[5] === 0 && b[6] === 0 && b[7] === 0) { y.dots += 1; }
        extras.wd += b[6]; extras.nb += b[7]; extras.b += b[8]; extras.lb += b[9]; extras.p += b[10];
    });
    let html = "<div class='table-box'><table><thead><tr><th>Batter</th><th style='text-align:left'>Dismissal</th>"
             + "<th>R</th><th>B</th><th>4s</th><th>6s</th><th>SR</th></tr></thead><tbody>";
    batters.forEach(function (p) {
        const x = bat[p];
        html += "<tr><td>" + safe(nameOf(p)) + "</td><td class='how'>" + safe(x.out) + "</td><td><b>" + x.runs
              + "</b></td><td>" + x.balls + "</td><td>" + x.fours + "</td><td>" + x.sixes + "</td><td>"
              + (x.balls ? (x.runs * 100 / x.balls).toFixed(1) : "-") + "</td></tr>";
    });
    const totalExtras = extras.wd + extras.nb + extras.b + extras.lb + extras.p;
    html += "</tbody></table></div><p class='note'>Extras " + totalExtras + ": " + extras.wd + " wides, " + extras.nb
          + " no-balls, " + extras.b + " byes, " + extras.lb + " leg-byes" + (extras.p ? ", " + extras.p + " penalty" : "")
          + "</p><div class='table-box'><table><thead><tr><th>Bowler</th><th>O</th><th>Dots</th><th>R</th><th>W</th>"
          + "<th>Econ</th></tr></thead><tbody>";
    bowlers.forEach(function (p) {
        const y = bowl[p];
        html += "<tr><td>" + safe(nameOf(p)) + "</td><td>" + oversText(y.legal) + "</td><td>" + y.dots + "</td><td>"
              + y.runs + "</td><td><b>" + y.wickets + "</b></td><td>"
              + (y.legal ? (y.runs * 6 / y.legal).toFixed(2) : "-") + "</td></tr>";
    });
    return html + "</tbody></table></div>";
}


// ---------------------------------------------------------------------------
// Over by over
// ---------------------------------------------------------------------------
// The symbol and colour for one ball.
function ballSymbol(b) {
    if (isWicket(b)) { return ["out", "W"]; }
    if (b[6] > 0) { return ["extra", (b[6] > 1 ? b[6] : "") + "wd"]; }
    if (b[7] > 0) { return ["extra", (b[5] > 0 ? b[5] + "+" : "") + "nb"]; }
    if (b[8] > 0) { return ["extra", b[8] + "b"]; }
    if (b[9] > 0) { return ["extra", b[9] + "lb"]; }
    if (b[5] === 6) { return ["six", "6"]; }
    if (b[5] === 4) { return ["four", "4"]; }
    if (b[5] === 0) { return ["dot", "•"]; }
    return ["", String(b[5])];
}

function oversHTML(innings) {
    const overs = {};
    const order = [];
    innings.b.forEach(function (b) {
        if (!(b[0] in overs)) { overs[b[0]] = []; order.push(b[0]); }
        overs[b[0]].push(b);
    });
    let html = "";
    order.forEach(function (o) {
        const balls = overs[o];
        const runs = balls.reduce(function (sum, b) { return sum + ballRuns(b); }, 0);
        const bowlers = balls.map(function (b) { return nameOf(b[4]); })
                             .filter(function (n, i, all) { return all.indexOf(n) === i; }).join(", ");
        html += "<div class='over'><b>" + o + "</b><span class='who'>" + safe(bowlers) + "</span><span>"
              + balls.map(function (b) {
                    const s = ballSymbol(b);
                    return "<span class='ball " + s[0] + "' title='" + safe(nameOf(b[2]) + " to " + nameOf(b[4])) + "'>"
                         + s[1] + "</span>";
                }).join("") + "</span><b style='text-align:right'>" + runs + "</b></div>";
    });
    return html + "<p class='note'>• dot ball · 1-6 runs off the bat · W wicket · wd wide · nb no-ball · "
                + "b bye · lb leg-bye. The number on the right is the runs from the over.</p>";
}


// ---------------------------------------------------------------------------
// Raw ball rows (the same columns as the ball-by-ball CSV file)
// ---------------------------------------------------------------------------
function rawHTML(m) {
    const columns = ["inning", "batting_team", "over", "ball", "batter", "non_striker", "bowler", "is_super_over",
                     "wide_runs", "bye_runs", "legbye_runs", "noball_runs", "penalty_runs", "batsman_runs",
                     "extra_runs", "total_runs", "player_dismissed", "dismissal_kind", "fielder"];
    let html = "<div class='table-box'><table><thead><tr>"
             + columns.map(function (c) { return "<th>" + c + "</th>"; }).join("") + "</tr></thead><tbody>";
    let count = 0;
    m.i.forEach(function (innings, n) {
        innings.b.forEach(function (b) {
            const extras = b[6] + b[7] + b[8] + b[9] + b[10];
            const cells = [n + 1, innings.t, b[0], b[1], nameOf(b[2]), nameOf(b[3]), nameOf(b[4]), innings.so,
                           b[6], b[8], b[9], b[7], b[10], b[5], extras, b[5] + extras,
                           nameOf(b[11]), KINDS[b[12]], nameOf(b[13])];
            html += "<tr>" + cells.map(function (c) { return "<td>" + safe(c) + "</td>"; }).join("") + "</tr>";
            count += 1;
        });
    });
    return "<p class='note'>" + count + " rows for this match (match_id " + m.id + ").</p>" + html + "</tbody></table></div>";
}


// ---------------------------------------------------------------------------
// One match
// ---------------------------------------------------------------------------
function drawMatch() {
    const m = current;
    if (!m) {
        byId("detail").innerHTML = "<p class='note'>Pick a match from the list.</p>";
        return;
    }
    let html = "<h2 style='margin:0'>" + safe(m.t1) + " v " + safe(m.t2) + "</h2><p><b>" + safe(m.res) + "</b></p>"
        + "<div class='meta'><div>Date<b>" + m.d + "</b></div><div>Ground<b>" + safe(m.v) + ", " + safe(m.c) + "</b></div>"
        + "<div>Stage<b>" + safe(m.st) + "</b></div><div>Toss<b>" + safe(m.tw) + ", chose to " + safe(m.td) + "</b></div>"
        + "<div>Player of the match<b>" + safe(m.pom || "Not awarded") + "</b></div>"
        + "<div>Umpires<b>" + safe(m.u.join(", ") || "-") + "</b></div><div>Match id<b>" + m.id + "</b></div></div>"
        + "<div class='tabs'>" + [["card", "Scorecard"], ["overs", "Over by over"], ["raw", "Raw ball rows"]].map(function (t) {
              return "<button data-view='" + t[0] + "' class='" + (view === t[0] ? "on" : "") + "'>" + t[1] + "</button>";
          }).join("") + "</div>";
    if (m.i.length === 0) {
        html += "<p class='note'>No balls were bowled in this match.</p>";
    } else if (view === "raw") {
        html += rawHTML(m);
    } else {
        m.i.forEach(function (innings) {
            html += "<h3>" + (innings.so ? "Super over: " : "") + safe(innings.t) + " " + scoreText(innings) + "</h3>"
                  + (view === "card" ? scorecardHTML(innings) : oversHTML(innings));
        });
    }
    byId("detail").innerHTML = html;
}

function openMatch(id) {
    current = MATCHES.find(function (m) { return m.id === id; }) || null;
    drawMatch();
    drawList();
}


// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
const seasons = MATCHES.map(function (m) { return m.s; })
                       .filter(function (s, i, all) { return all.indexOf(s) === i; }).sort().reverse();
byId("season").innerHTML = "<option value='all'>All seasons</option>"
    + seasons.map(function (s) { return "<option>" + s + "</option>"; }).join("");
const teams = MATCHES.map(function (m) { return m.f1; }).concat(MATCHES.map(function (m) { return m.f2; }))
                     .filter(function (t, i, all) { return all.indexOf(t) === i; }).sort();
byId("team").innerHTML = "<option value='all'>All teams</option>"
    + teams.map(function (t) { return "<option>" + safe(t) + "</option>"; }).join("");

["season", "team"].forEach(function (id) { byId(id).addEventListener("change", drawList); });
byId("search").addEventListener("input", drawList);
byId("list").addEventListener("click", function (event) {
    const row = event.target.closest(".row");
    if (row) {
        location.hash = row.dataset.id;     // also lets the browser's back button work
    }
});
byId("detail").addEventListener("click", function (event) {
    const tab = event.target.closest("[data-view]");
    if (tab) { view = tab.dataset.view; drawMatch(); }
});
window.addEventListener("hashchange", function () { openMatch(Number(location.hash.slice(1))); });

// Open the match in the address (#id), or else the latest match.
const fromAddress = Number(location.hash.slice(1));
if (fromAddress && MATCHES.some(function (m) { return m.id === fromAddress; })) {
    byId("season").value = "all";
    openMatch(fromAddress);
} else {
    byId("season").value = String(seasons[0]);
    openMatch(MATCHES[0].id);
}
