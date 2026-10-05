// =============================================================================
// site.js
// -----------------------------------------------------------------------------
// The NEW SITE DESIGN of the Sports Arena dashboard: one page, several "views",
// and a page for every player and every ground.
//
//   #/home                 Home: headline numbers, champions, caps, 2027 favourites
//   #/players              Player directory      #/player/V Kohli    one player's page
//   #/grounds              Ground directory      #/ground/Eden Gardens  one ground's page
//   #/teams, #/predictions, #/ask, #/analysis    the existing sections, grouped
//   #rivalry, #pitch, ...  old section links still work (the router finds their view)
//
// The address after "#" decides what is shown (a "hash router"), so the browser's
// Back button works and every page has its own link, while everything stays in
// ONE file that works offline.
//
// Every number comes from data that Python calculated (no number is typed here):
//   AD = analyst data (src/dashboard_data.py), CF = chatbot facts (src/chat_facts.py),
//   SD = site data (dashboard_data.site_data).
// Helpers used from the other scripts on the page: byId, safe, round, oversText,
// htmlTable, htmlBars, card (dashboard_explorer.js); indexBar, moreOrFewer,
// linkTable, fillSelect (dashboard_analytics.js).
// Plain JavaScript and inline SVG charts: no libraries, no internet.
// =============================================================================


// ---------------------------------------------------------------------------
// 1. Small functions with no page access (tested with Node: tests/test_site.js)
// ---------------------------------------------------------------------------
// Read the address: "#/player/V%20Kohli" -> { view: "players", player: "V Kohli" }
function parseRoute(hash) {
    const text = (hash || "").replace(/^#/, "");
    if (text === "" || text === "/" || text === "/home") { return { view: "home" }; }
    if (text.charAt(0) !== "/") { return { view: null, section: text }; }     // an old section link like #rivalry
    const parts = text.slice(1).split("/");
    const first = parts[0].split("?")[0];
    const rest = decodeURIComponent(parts.slice(1).join("/"));
    if (first === "player" && rest) { return { view: "players", player: rest }; }
    if (first === "ground" && rest) { return { view: "grounds", ground: rest }; }
    if (first === "ask") {
        const query = text.indexOf("?q=") >= 0 ? decodeURIComponent(text.split("?q=")[1]) : "";
        return { view: "ask", question: query };
    }
    return { view: first };
}

function playerHref(name) { return "#/player/" + encodeURIComponent(name); }
function groundHref(name) { return "#/ground/" + encodeURIComponent(name); }

// What kind of player: from balls faced and balls bowled in his career.
//   career = [matches, innings, runs, balls, outs, highest, 50s, 100s, sixes, wickets, legal balls bowled, runs conceded]
function playerRole(career, stumpings) {
    const batted = career[3];
    const bowled = career[10];
    let role;
    if (batted >= 300 && bowled >= 300) {
        role = "All-rounder";
    } else if (bowled > batted) {
        role = "Bowler";
    } else {
        role = "Batter";
    }
    if (stumpings > 0) { role += " / wicket-keeper"; }
    return role;
}

// Headline numbers of a career, worked out from the counts.
function careerNumbers(career) {
    return {
        matches: career[0], runs: career[2],
        strikeRate: career[3] > 0 ? Math.round(career[2] / career[3] * 1000) / 10 : null,
        average: career[4] > 0 ? Math.round(career[2] / career[4] * 100) / 100 : null,
        highest: career[5], fifties: career[6], hundreds: career[7], sixes: career[8], wickets: career[9],
        economy: career[10] > 0 ? Math.round(career[11] / (career[10] / 6) * 100) / 100 : null,
        ballsPerWicket: career[9] > 0 ? Math.round(career[10] / career[9] * 10) / 10 : null,
    };
}

// Find what a search means, using the chatbot's alias lists ("kohli", "chepauk", "csk").
function resolveSearch(text, names, aliases) {
    const query = text.trim().toLowerCase();
    if (query === "") { return null; }
    for (let i = 0; i < names.players.length; i++) {
        if (names.players[i].toLowerCase() === query) { return { kind: "player", name: names.players[i] }; }
    }
    for (let i = 0; i < names.venues.length; i++) {
        if (names.venues[i].toLowerCase() === query) { return { kind: "ground", name: names.venues[i] }; }
    }
    for (let i = 0; i < names.teams.length; i++) {
        if (names.teams[i].toLowerCase() === query) { return { kind: "team", name: names.teams[i] }; }
    }
    if (aliases.venues[query]) { return { kind: "ground", name: aliases.venues[query] }; }
    if (aliases.teams[query]) { return { kind: "team", name: aliases.teams[query] }; }
    if (aliases.players[query]) {
        const options = aliases.players[query];
        return options.length === 1 ? { kind: "player", name: options[0] } : { kind: "choose", options: options };
    }
    // Last try: names that contain the text (e.g. "dhoni" -> "MS Dhoni").
    const contains = names.players.filter(function (name) { return name.toLowerCase().indexOf(query) >= 0; });
    if (contains.length === 1) { return { kind: "player", name: contains[0] }; }
    if (contains.length > 1) { return { kind: "choose", options: contains.slice(0, 12) }; }
    return null;
}


// ---------------------------------------------------------------------------
// 2. SVG charts (drawn as text; hover a bar or point to see its details)
// ---------------------------------------------------------------------------
function escapeSvg(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/'/g, "&#39;");
}

// Round to a number of decimal places (its own name, so it works in Node tests too).
function siteRound(value, places) {
    const factor = Math.pow(10, places);
    return Math.round(value * factor) / factor;
}

// A nice round top for the y-axis, e.g. 973 -> 1000.
function niceMax(value) {
    if (value <= 0) { return 1; }
    const power = Math.pow(10, Math.floor(Math.log10(value)));
    const steps = [1, 2, 2.5, 5, 10];
    for (let i = 0; i < steps.length; i++) {
        if (steps[i] * power >= value) { return steps[i] * power; }
    }
    return 10 * power;
}

// Bar chart. items = [{ label, value, title, href, highlight }]
function svgBars(items, options) {
    options = options || {};
    if (items.length === 0) { return "<p class='note'>No data.</p>"; }
    const width = 640, height = options.height || 220, left = 44, bottom = 34, top = 12;
    const plotWidth = width - left - 10, plotHeight = height - top - bottom;
    // Top of the axis = 4 "nice" steps (e.g. 973 -> steps of 250 -> 1000), so the grid labels are round.
    let top_value = niceMax(Math.max.apply(null, items.map(function (i) { return i.value; })) / 4) * 4;
    // Counts (wickets, matches) need whole-number grid lines: at least 0, 1, 2, 3, 4.
    if (options.whole && top_value < 4) { top_value = 4; }
    const step = plotWidth / items.length;
    const barWidth = Math.max(4, Math.min(42, step * 0.7));
    let svg = "<svg class='chart' viewBox='0 0 " + width + " " + height + "' role='img' aria-label='"
            + escapeSvg(options.label || "bar chart") + "'>";
    for (let g = 0; g <= 4; g++) {                                         // 4 grid lines with values
        const y = top + plotHeight - plotHeight * g / 4;
        svg += "<line class='grid' x1='" + left + "' x2='" + (width - 10) + "' y1='" + y + "' y2='" + y + "'/>"
             + "<text class='axis' x='" + (left - 6) + "' y='" + (y + 4) + "' text-anchor='end'>"
             + siteRound(top_value * g / 4, 1) + "</text>";
    }
    const labelEvery = Math.ceil(items.length / 12);                       // at most 12 x labels
    items.forEach(function (item, i) {
        const x = left + step * i + (step - barWidth) / 2;
        const h = plotHeight * item.value / top_value;
        let bar = "<rect class='bar" + (item.highlight ? " hl" : "") + "' x='" + x + "' y='" + (top + plotHeight - h)
                + "' width='" + barWidth + "' height='" + Math.max(h, 0.5) + "'><title>" + escapeSvg(item.title || (item.label + ": " + item.value))
                + "</title></rect>";
        if (item.href) { bar = "<a href='" + escapeSvg(item.href) + "'>" + bar + "</a>"; }
        svg += bar;
        if (i % labelEvery === 0) {
            svg += "<text class='axis' x='" + (x + barWidth / 2) + "' y='" + (height - bottom + 16) + "' text-anchor='middle'>"
                 + escapeSvg(item.label) + "</text>";
        }
    });
    return svg + "</svg>";
}

// Line chart with dots. items = [{ label, value, title }] (null values are skipped).
function svgLine(items, options) {
    options = options || {};
    const points = items.filter(function (i) { return i.value !== null && i.value !== undefined; });
    if (points.length === 0) { return "<p class='note'>No data.</p>"; }
    const width = 640, height = options.height || 200, left = 44, bottom = 34, top = 12;
    const plotWidth = width - left - 20, plotHeight = height - top - bottom;
    const values = points.map(function (p) { return p.value; });
    // Round the axis to a "nice" step (e.g. 10 for strike rates, 0.5 for economy).
    const step = niceMax((Math.max.apply(null, values) - Math.min.apply(null, values)) || 1) / 4;
    const low = Math.floor(Math.min.apply(null, values) / step) * step - step;
    const high = Math.ceil(Math.max.apply(null, values) / step) * step + step;
    const span = high - low;
    const xOf = function (i) { return left + (items.length > 1 ? plotWidth * i / (items.length - 1) : plotWidth / 2); };
    const yOf = function (v) { return top + plotHeight - plotHeight * (v - low) / span; };
    let svg = "<svg class='chart' viewBox='0 0 " + width + " " + height + "' role='img' aria-label='"
            + escapeSvg(options.label || "line chart") + "'>";
    for (let v = low; v <= high + step / 1000; v += step) {      // one grid line per step
        svg += "<line class='grid' x1='" + left + "' x2='" + (width - 20) + "' y1='" + yOf(v) + "' y2='" + yOf(v) + "'/>"
             + "<text class='axis' x='" + (left - 6) + "' y='" + (yOf(v) + 4) + "' text-anchor='end'>" + siteRound(v, 1) + "</text>";
    }
    let path = "";
    const labelEvery = Math.ceil(items.length / 12);
    items.forEach(function (item, i) {
        if (item.value === null || item.value === undefined) { return; }
        path += (path === "" ? "M" : "L") + xOf(i) + " " + yOf(item.value) + " ";
    });
    svg += "<path class='line' d='" + path + "'/>";
    items.forEach(function (item, i) {
        if (i % labelEvery === 0) {
            svg += "<text class='axis' x='" + xOf(i) + "' y='" + (height - bottom + 16) + "' text-anchor='middle'>" + escapeSvg(item.label) + "</text>";
        }
        if (item.value === null || item.value === undefined) { return; }
        svg += "<circle class='dot' cx='" + xOf(i) + "' cy='" + yOf(item.value) + "' r='4'><title>"
             + escapeSvg(item.title || (item.label + ": " + item.value)) + "</title></circle>";
    });
    return svg + "</svg>";
}


// ---------------------------------------------------------------------------
// 3. The page (only in a browser)
// ---------------------------------------------------------------------------
function setupSite() {
    const CF = JSON.parse(byId("chat-facts").textContent);
    const SD = JSON.parse(byId("site-data").textContent);
    const NAMES = { players: AD.players, venues: AD.venues, teams: AD.teams };
    const ALIASES = { players: CF.player_aliases, venues: CF.venue_aliases, teams: CF.team_aliases };
    const LAST = CF.meta.last_season;

    function pLink(name) { return "<a href='" + playerHref(name) + "'>" + safe(name) + "</a>"; }
    function gLink(name) { return "<a href='" + groundHref(name) + "'>" + safe(name) + "</a>"; }
    function panel(title, body, note) {
        return "<div class='panel'><h3>" + title + "</h3>" + body + (note ? "<p class='note'>" + note + "</p>" : "") + "</div>";
    }
    function chips(items) {
        return "<div class='chips'>" + items.join("") + "</div>";
    }
    function chip(href, text, sub) {
        return "<a class='chip' href='" + href + "'>" + safe(text) + (sub ? "<small>" + safe(sub) + "</small>" : "") + "</a>";
    }

    // ----- Home -------------------------------------------------------------
    function renderHome() {
        const meta = CF.meta;
        const champion = CF.champions[String(LAST)];
        const caps = CF.caps[String(LAST)];
        const byRuns = Object.keys(CF.players).sort(function (a, b) { return CF.players[b].career[2] - CF.players[a].career[2]; });
        const byWickets = Object.keys(CF.players).sort(function (a, b) { return CF.players[b].career[9] - CF.players[a].career[9]; });
        const grounds = AD.pitch["all"].slice().sort(function (a, b) { return b[1] - a[1]; }).slice(0, 8);
        let html = "<div class='hero'><h1>IPL " + meta.season_range + ", every ball</h1>"
            + "<p>" + meta.matches.toLocaleString("en") + " matches and " + meta.balls.toLocaleString("en") + " deliveries across "
            + meta.seasons + " seasons. Search any player, ground or team above, or start here.</p></div>"
            + "<div class='feature-grid'>"
            + "<a class='feature' href='#/teams'><span>IPL " + LAST + " champion</span><b>" + safe(champion[1]) + "</b><small>beat "
            + safe(champion[2]) + ", " + safe(champion[3]) + "</small></a>"
            + "<a class='feature' href='" + playerHref(caps[0]) + "'><span>Orange Cap " + LAST + "</span><b>" + safe(caps[0])
            + "</b><small>" + caps[1] + " runs</small></a>"
            + "<a class='feature' href='" + playerHref(caps[2]) + "'><span>Purple Cap " + LAST + "</span><b>" + safe(caps[2])
            + "</b><small>" + caps[3] + " wickets</small></a>";
        if (CF.predictions) {
            const fav = CF.predictions.teams.slice().sort(function (a, b) { return b[1] - a[1]; })[0];
            html += "<a class='feature accent' href='#/predictions'><span>IPL " + CF.predictions.season + " favourite</span><b>"
                  + safe(fav[0]) + "</b><small>Model A " + fav[1] + "%, Model B " + fav[3] + "% title chance</small></a>";
        }
        html += "</div>";
        html += "<div class='two-columns'>"
            + panel("Most runs", chips(byRuns.slice(0, 8).map(function (n) { return chip(playerHref(n), n, CF.players[n].career[2] + " runs"); })))
            + panel("Most wickets", chips(byWickets.slice(0, 8).map(function (n) { return chip(playerHref(n), n, CF.players[n].career[9] + " wickets"); })))
            + "</div>"
            + panel("Grounds", chips(grounds.map(function (g) { return chip(groundHref(AD.venues[g[0]]), AD.venues[g[0]], g[1] + " matches · runs index " + g[3]); })),
                    "Runs index: 100 = league average in the same seasons. <a href='#/grounds'>All grounds &rarr;</a>")
            + panel("Ask Sports Arena", chips(["How does the pitch at Chepauk play?", "Kohli vs Bumrah", "Who will win IPL " + (LAST + 1) + "?",
                    "What changed with the Impact Player rule?"].map(function (q) { return chip("#/ask?q=" + encodeURIComponent(q), q); })),
                    "Answers use only numbers calculated from the data.");
        byId("home-page").innerHTML = html;
    }

    // ----- Player directory -------------------------------------------------
    function renderPlayers() {
        const names = Object.keys(CF.players);
        const top = function (column, n) {
            return names.slice().sort(function (a, b) { return CF.players[b].career[column] - CF.players[a].career[column]; }).slice(0, n);
        };
        const runRows = top(2, 25).map(function (n, i) {
            const c = careerNumbers(CF.players[n].career);
            return [i + 1, pLink(n), c.matches, c.runs, c.strikeRate, c.average === null ? "-" : c.average];
        });
        const wicketRows = top(9, 25).map(function (n, i) {
            const c = careerNumbers(CF.players[n].career);
            return [i + 1, pLink(n), c.matches, c.wickets, c.economy, c.ballsPerWicket];
        });
        const teams = Object.keys(SD.squads).map(function (p) { return SD.squads[p]; })
            .filter(function (t, i, all) { return all.indexOf(t) === i; }).sort();
        byId("players-page").innerHTML = "<h1>Players</h1><p class='note'>Search any of the " + names.length
            + " players with the box at the top (short names like V Kohli, or nicknames like SKY), or pick from these lists.</p>"
            + "<div class='filters'><label>" + (LAST + 1) + " squad<select id='squad-team'>"
            + teams.map(function (t) { return "<option>" + safe(t) + "</option>"; }).join("") + "</select></label></div>"
            + "<div id='squad-list'></div>"
            + "<div class='two-columns'>" + panel("Most runs", "<div class='table-box'>" + linkTable(["#", "Player", "Matches", "Runs", "SR", "Avg"], runRows) + "</div>")
            + panel("Most wickets", "<div class='table-box'>" + linkTable(["#", "Player", "Matches", "Wkts", "Econ", "Balls/wkt"], wicketRows) + "</div>") + "</div>";
        function drawSquad() {
            const team = byId("squad-team").value;
            const players = Object.keys(SD.squads).filter(function (p) { return SD.squads[p] === team; }).sort();
            byId("squad-list").innerHTML = panel(safe(team) + ": " + players.length + " players (data/squads_" + (LAST + 1) + ".csv)",
                chips(players.map(function (p) {
                    const c = CF.players[p] ? careerNumbers(CF.players[p].career) : null;
                    return chip(playerHref(p), p, c ? c.runs + " runs · " + c.wickets + " wkts" : "");
                })));
        }
        byId("squad-team").addEventListener("change", drawSquad);
        drawSquad();
    }

    // ----- One player -------------------------------------------------------
    function renderPlayer(name) {
        const page = byId("players-page");
        if (!CF.players[name]) {
            page.innerHTML = "<h1>Player not found</h1><p class='note'>No player called \"" + safe(name)
                + "\" in the data. Try the search box (e.g. V Kohli, JJ Bumrah, SKY).</p>";
            return;
        }
        const player = CF.players[name];
        const p = AD.players.indexOf(name);
        const key = String(p);
        const c = careerNumbers(player.career);
        const field = SD.field[key] || [0, 0, 0];
        const seasons = Object.keys(player.seasons).sort();
        const teams = seasons.map(function (s) { return player.seasons[s][0]; }).filter(function (t, i, all) { return t && all.indexOf(t) === i; });
        // Show a role's sections only if it is a real part of his game: 120+ balls faced to show
        // batting, 300+ balls (50 overs) bowled to show bowling, unless it is the only thing he did.
        const batted = player.career[3] >= 120 || (player.career[3] > 0 && player.career[10] < 300);
        const bowls = player.career[10] >= 300 || (player.career[10] > 0 && player.career[3] < 120);
        let html = "<p class='crumbs'><a href='#/players'>Players</a> / " + safe(name) + "</p>"
            + "<div class='profile-head'><div><h1>" + safe(name) + "</h1><p><span class='badge'>" + playerRole(player.career, field[2])
            + "</span> IPL " + seasons[0] + "-" + seasons[seasons.length - 1] + " · " + teams.map(safe).join(", ") + "</p>"
            + (SD.squads[name] ? "<p class='note'>" + (LAST + 1) + " squad: <b>" + safe(SD.squads[name]) + "</b></p>" : "")
            + "</div><a class='button' href='#/ask?q=" + encodeURIComponent(name + " career stats") + "'>Ask about " + safe(name) + "</a></div>";

        const cards = [card("matches", c.matches)];
        if (batted) {
            cards.push(card("runs", c.runs), card("strike rate", c.strikeRate === null ? "-" : c.strikeRate),
                       card("average", c.average === null ? "-" : c.average),
                       card("highest / 50s / 100s", c.highest + " / " + c.fifties + " / " + c.hundreds), card("sixes", c.sixes));
        }
        if (bowls) {
            cards.push(card("wickets", c.wickets), card("economy", c.economy === null ? "-" : c.economy),
                       card("balls per wicket", c.ballsPerWicket === null ? "-" : c.ballsPerWicket));
        }
        cards.push(card("catches / run outs / stumpings", field.join(" / ")), card("Player of the Match", SD.potm[key] || 0));
        html += "<div class='numbers'>" + cards.join("") + "</div>";

        // Predictions that mention him
        if (CF.predictions) {
            const picks = [];
            [["Model A", CF.predictions.awards_a], ["Model B", CF.predictions.awards_b]].forEach(function (pair) {
                pair[1].forEach(function (r) {
                    if (r[2] === name && r[1] <= 3) { picks.push(pair[0] + ": " + safe(r[0]) + " #" + r[1]); }
                });
            });
            if (picks.length) {
                html += "<p class='callout'>In the " + CF.predictions.season + " predictions: " + picks.join("; ")
                      + ". <a href='#/predictions'>See the models &rarr;</a></p>";
            }
        }

        // Season by season
        const seasonCharts = [];
        if (batted) {
            seasonCharts.push(panel("Runs by season", svgBars(seasons.map(function (s) {
                const row = player.seasons[s];
                return { label: s.slice(2), value: row[1], title: s + " (" + row[0] + "): " + row[1] + " runs off " + row[2] + " balls" };
            }), { label: "runs by season" })));
            seasonCharts.push(panel("Strike rate by season", svgLine(seasons.map(function (s) {
                const row = player.seasons[s];
                return { label: s.slice(2), value: row[2] >= 30 ? round(row[1] / row[2] * 100, 1) : null,
                         title: s + ": strike rate " + (row[2] ? round(row[1] / row[2] * 100, 1) : "-") };
            }), { label: "strike rate by season" }), "Seasons with fewer than 30 balls faced are left out of the line."));
        }
        if (bowls) {
            seasonCharts.push(panel("Wickets by season", svgBars(seasons.map(function (s) {
                const row = player.seasons[s];
                return { label: s.slice(2), value: row[5], title: s + ": " + row[5] + " wickets in " + oversText(row[6]) + " overs" };
            }), { label: "wickets by season", whole: true })));
            seasonCharts.push(panel("Economy by season", svgLine(seasons.map(function (s) {
                const row = player.seasons[s];
                return { label: s.slice(2), value: row[6] >= 60 ? round(row[7] / (row[6] / 6), 2) : null,
                         title: s + ": economy " + (row[6] ? round(row[7] / (row[6] / 6), 2) : "-") };
            }), { label: "economy by season" }), "Seasons with fewer than 10 overs are left out of the line."));
        }
        html += "<h2>Season by season</h2><div class='two-columns'>" + seasonCharts.join("") + "</div>";

        // Recent form (click a bar to open the match)
        const form = [];
        const lastBat = SD.last_bat[key];
        if (lastBat && batted) {
            form.push(panel("Last " + lastBat.length + " innings (runs)", svgBars(lastBat.map(function (r) {
                return { label: r[0].slice(5), value: r[2], href: "match_centre.html#" + r[5],
                         title: r[0] + " v " + r[1] + ": " + r[2] + (r[4] ? "" : "*") + " off " + r[3] + " balls (click to open)" };
            }), { label: "last innings" }), "* = not out. Click a bar to open the scorecard."));
        }
        const lastBowl = SD.last_bowl[key];
        if (lastBowl && bowls) {
            form.push(panel("Last " + lastBowl.length + " bowling matches (wickets)", svgBars(lastBowl.map(function (r) {
                return { label: r[0].slice(5), value: r[4], href: "match_centre.html#" + r[5],
                         title: r[0] + " v " + r[1] + ": " + r[4] + "/" + r[3] + " in " + oversText(r[2]) + " overs (click to open)" };
            }), { label: "last bowling matches", whole: true })));
        }
        if (form.length) { html += "<h2>Recent form</h2><div class='two-columns'>" + form.join("") + "</div>"; }

        // Phases
        const byPhase = function (a, b) { return a[1] - b[1]; };      // Powerplay, Middle, Death
        const phaseBat = SD.bat_phase.filter(function (r) { return r[0] === p; }).sort(byPhase).map(function (r) {
            return [SD.phases[r[1]], r[2], r[3], r[3] ? round(r[2] / r[3] * 100, 1) : "-", r[4] ? round(r[2] / r[4], 1) : "-"];
        });
        const phaseBowl = SD.bowl_phase.filter(function (r) { return r[0] === p && r[2] > 0; }).sort(byPhase).map(function (r) {
            return [SD.phases[r[1]], oversText(r[2]), r[4], round(r[3] / (r[2] / 6), 2)];
        });
        const phasePanels = [];
        if (batted) { phasePanels.push(panel("Batting by phase", htmlTable(["Phase", "Runs", "Balls", "SR", "Avg"], phaseBat))); }
        if (phaseBowl.length && bowls) { phasePanels.push(panel("Bowling by phase", htmlTable(["Phase", "Overs", "Wkts", "Econ"], phaseBowl))); }
        html += "<h2>Powerplay, middle and death</h2><div class='two-columns'>" + phasePanels.join("") + "</div>";

        // Matchups
        const matchupPanels = [];
        if (batted) {
            const faced = AD.matchups.filter(function (r) { return r[0] === p && r[2] >= 24; });
            const toughest = faced.slice().sort(function (a, b) { return (a[3] / a[2]) - (b[3] / b[2]); }).slice(0, 6);
            const favourite = faced.slice().sort(function (a, b) { return (b[3] / b[2]) - (a[3] / a[2]); }).slice(0, 6);
            const row = function (r) { return [pLink(AD.players[r[1]]), r[2], r[3], round(r[3] / r[2] * 100, 1), r[4]]; };
            matchupPanels.push(panel("Toughest bowlers (lowest strike rate, 24+ balls)", linkTable(["Bowler", "Balls", "Runs", "SR", "Outs"], toughest.map(row))));
            matchupPanels.push(panel("Favourite bowlers (highest strike rate, 24+ balls)", linkTable(["Bowler", "Balls", "Runs", "SR", "Outs"], favourite.map(row))));
        }
        if (bowls) {
            const bowledAt = AD.matchups.filter(function (r) { return r[1] === p && r[2] >= 18; });
            const victims = bowledAt.slice().sort(function (a, b) { return b[4] - a[4] || a[3] - b[3]; }).slice(0, 6);
            matchupPanels.push(panel("Batters he dismissed most (18+ balls)", linkTable(["Batter", "Balls", "Runs", "SR", "Outs"],
                victims.map(function (r) { return [pLink(AD.players[r[0]]), r[2], r[3], round(r[3] / r[2] * 100, 1), r[4]]; }))));
        }
        if (matchupPanels.length) { html += "<h2>Matchups</h2><div class='two-columns'>" + matchupPanels.join("") + "</div>"; }

        // Against each team, and how he gets out
        const vsPanels = [];
        if (batted) {
            const vs = AD.bat_vs.filter(function (r) { return r[0] === p; }).sort(function (a, b) { return b[3] - a[3]; })
                .map(function (r) { return [AD.teams[r[1]], r[2], r[3], r[5] ? round(r[3] / r[5], 1) : "-", r[4] ? round(r[3] / r[4] * 100, 1) : "-"]; });
            vsPanels.push(panel("Batting against each team", "<div class='table-box scroll'>" + htmlTable(["Opponent", "Inns", "Runs", "Avg", "SR"], vs) + "</div>"));
            const outs = AD.outs.filter(function (r) { return r[0] === p; });
            const total = outs.reduce(function (sum, r) { return sum + r[2]; }, 0);
            if (total > 0) {
                vsPanels.push(panel("How he gets out (" + total + " dismissals)", htmlBars(outs.map(function (r) {
                    return { label: AD.out_kinds[r[1]], value: round(r[2] / total * 100, 1), text: r[2] + " (" + round(r[2] / total * 100, 1) + "%)" };
                }), 100, "")));
            }
        }
        if (bowls) {
            const vs = AD.bowl_vs.filter(function (r) { return r[0] === p; }).sort(function (a, b) { return b[3] - a[3]; })
                .map(function (r) { return [AD.teams[r[1]], r[2], r[3], oversText(r[4]), round(r[5] / (r[4] / 6), 2)]; });
            vsPanels.push(panel("Bowling against each team", "<div class='table-box scroll'>" + htmlTable(["Opponent", "Matches", "Wkts", "Overs", "Econ"], vs) + "</div>"));
        }
        html += "<h2>Against each team</h2><div class='two-columns'>" + vsPanels.join("") + "</div>";

        // Grounds
        const groundRows = [];
        AD.fit_bat.filter(function (r) { return batted && r[0] === p && r[3] >= 60 && r[9] > 0; }).forEach(function (r) {
            const here = round(r[4] / r[3] * 100, 1), elsewhere = round(r[10] / r[9] * 100, 1);
            groundRows.push({ sort: here - elsewhere, cells: [gLink(AD.venues[r[1]]), "Batting", r[3] + " balls, " + r[4] + " runs",
                              "SR " + here + " vs " + elsewhere, (here >= elsewhere ? "+" : "") + round(here - elsewhere, 1)] });
        });
        AD.fit_bowl.filter(function (r) { return bowls && r[0] === p && r[3] >= 60 && r[7] > 0; }).forEach(function (r) {
            const here = round(r[4] / (r[3] / 6), 2), elsewhere = round(r[8] / (r[7] / 6), 2);
            groundRows.push({ sort: elsewhere - here, cells: [gLink(AD.venues[r[1]]), "Bowling", oversText(r[3]) + " overs, " + r[5] + " wkts",
                              "Econ " + here + " vs " + elsewhere, (here <= elsewhere ? "" : "+") + round(here - elsewhere, 2)] });
        });
        groundRows.sort(function (a, b) { return b.sort - a.sort; });
        if (groundRows.length) {
            html += "<h2>Grounds</h2>" + panel("How each ground suits " + safe(name) + " (60+ balls there)",
                "<div class='table-box'>" + linkTable(["Ground", "Role", "Here", "Here vs other grounds, same seasons", "Difference"],
                                                      groundRows.map(function (r) { return r.cells; })) + "</div>",
                "Best fit first. Click a ground for its profile.");
        }
        page.innerHTML = html;
    }

    // ----- Ground directory -------------------------------------------------
    function renderGrounds() {
        const rows = AD.pitch["all"].slice().sort(function (a, b) { return b[1] - a[1]; });
        const cardsHtml = rows.map(function (r) {
            const g = AD.grounds.find(function (x) { return x[0] === r[0]; });
            const home = SD.home[AD.venues[r[0]]];
            return "<a class='ground-card' href='" + groundHref(AD.venues[r[0]]) + "'><b>" + safe(AD.venues[r[0]]) + "</b>"
                 + "<span>" + safe(g ? g[1] : "") + " · " + r[1] + " matches" + (home ? " · home of " + safe(home.join(", ")) : "") + "</span>"
                 + "<span class='index-chip " + (r[3] >= AD.pitch_thresholds[0] ? "up" : r[3] <= AD.pitch_thresholds[1] ? "down" : "") + "'>runs index "
                 + r[3] + "</span><small>" + safe(r[9]) + "</small></a>";
        });
        byId("grounds-page").innerHTML = "<h1>Grounds</h1><p class='note'>" + rows.length + " grounds. The runs index compares each "
            + "ground with the whole league in the same seasons (100 = average). There are no pitch reports in the data, so this is "
            + "how the ground has played: pitch, boundary size, outfield and weather together.</p>"
            + "<div class='ground-grid'>" + cardsHtml.join("") + "</div>";
    }

    // ----- One ground -------------------------------------------------------
    function groundPitchBlock(v, period) {
        const p = AD.pitch[period].find(function (r) { return r[0] === v; });
        if (!p) { return "<p class='note'>No matches here in this period.</p>"; }
        const phases = ["Powerplay", "Middle", "Death"].map(function (phase) {
            const row = AD.pitch_phase[period].find(function (r) { return r[0] === v && r[1] === phase; });
            return row ? indexBar(phase, row[3], "(" + row[2] + " runs an over)") : indexBar(phase, null, "");
        }).join("");
        const outs = AD.pitch_outs[period].filter(function (r) { return r[0] === v && (r[3] >= 1 || r[4] >= 1); })
            .sort(function (a, b) { return b[2] - a[2]; })
            .map(function (r) { return [AD.pitch_out_kinds[r[1]], r[2], r[3] + "%", r[4] + "%"]; });
        return "<p class='callout'><b>" + safe(p[9]) + "</b> (" + p[1] + " matches in this period)</p>"
            + "<div class='numbers'>" + card("run rate", p[2]) + card("avg 1st-innings score", show(p[7]))
            + card("chasing team won", p[8] === null ? "-" : p[8] + "%") + card("matches", p[1]) + "</div>"
            + "<div class='two-columns'>" + panel("Compared with the league (100 = average, same seasons)",
                  indexBar("Runs", p[3], "(" + moreOrFewer(p[3]) + " average)") + indexBar("Wickets per ball", p[4], "(" + moreOrFewer(p[4]) + " average)")
                  + indexBar("Fours and sixes", p[5], "(" + moreOrFewer(p[5]) + " average)") + indexBar("Dot balls", p[6], "(" + moreOrFewer(p[6]) + " average)"),
                  "Orange = above the league, blue = below.")
            + panel("Runs by phase (100 = league)", phases, "A low Middle-overs index often means help for spin or slower balls, but the data does not say why.")
            + "</div>" + panel("How batters got out here", htmlTable(["Dismissal", "Times", "% here", "% league"], outs),
                               "More bowled and lbw than the league can mean the ball keeps low, or just the bowlers who played here.");
    }

    function renderGround(name) {
        const page = byId("grounds-page");
        const v = AD.venues.indexOf(name);
        if (v < 0) {
            page.innerHTML = "<h1>Ground not found</h1><p class='note'>No ground called \"" + safe(name) + "\". <a href='#/grounds'>See all grounds</a>.</p>";
            return;
        }
        const g = AD.grounds.find(function (x) { return x[0] === v; });
        const home = SD.home[name];
        let html = "<p class='crumbs'><a href='#/grounds'>Grounds</a> / " + safe(name) + "</p>"
            + "<div class='profile-head'><div><h1>" + safe(name) + "</h1><p>" + safe(g[1]) + " · IPL " + g[3] + "-" + g[4] + " · "
            + g[2] + " matches" + (home ? " · home of <b>" + safe(home.join(", ")) + "</b>" : "") + "</p></div>"
            + "<a class='button' href='#/ask?q=" + encodeURIComponent("How does the pitch at " + name + " play?") + "'>Ask about this ground</a></div>"
            + "<div class='filters'><label>Period<select id='ground-period'></select></label></div><div id='ground-pitch'></div>";

        const seasons = AD.ground_seasons.filter(function (r) { return r[0] === v; });
        html += "<div class='two-columns'>" + panel("Average first-innings score by season", svgBars(seasons.map(function (r) {
                    return { label: String(r[1]).slice(2), value: r[3], title: r[1] + ": " + r[3] + " (" + r[2] + " matches)" };
                }), { label: "first innings by season" }), "Rain-shortened and no-result matches left out.")
            + panel("Toss and chasing", htmlTable(["", "Result"], [
                    ["Chasing team won", show(g[6]) + "%"],
                    ["Toss winner chose to bat, then won", show(g[8]) + "% (" + g[7] + " times)"],
                    ["Toss winner chose to field, then won", show(g[10]) + "% (" + g[9] + " times)"],
                    ["Highest total", show(g[11])]])) + "</div>";

        // Teams here
        const teamTotals = {};
        AD.team_ground.filter(function (r) { return r[1] === v; }).forEach(function (r) {
            const t = AD.teams[r[0]];
            if (!teamTotals[t]) { teamTotals[t] = { played: 0, wins: 0 }; }
            teamTotals[t].played += r[3];
            teamTotals[t].wins += r[4];
        });
        const teamBars = Object.keys(teamTotals).filter(function (t) { return teamTotals[t].played >= 3; })
            .sort(function (a, b) { return teamTotals[b].played - teamTotals[a].played; }).map(function (t) {
                const x = teamTotals[t];
                return { label: t, value: round(x.wins / x.played * 100, 1), text: round(x.wins / x.played * 100, 1) + "% (" + x.wins + "/" + x.played + ")" };
            });

        // Players here
        const topBat = AD.fit_bat.filter(function (r) { return r[1] === v; }).sort(function (a, b) { return b[4] - a[4]; }).slice(0, 8)
            .map(function (r) { return [pLink(AD.players[r[0]]), r[2], r[4], round(r[4] / r[3] * 100, 1)]; });
        const topBowl = AD.fit_bowl.filter(function (r) { return r[1] === v; }).sort(function (a, b) { return b[5] - a[5] || a[4] - b[4]; }).slice(0, 8)
            .map(function (r) { return [pLink(AD.players[r[0]]), r[2], r[5], round(r[4] / (r[3] / 6), 2)]; });
        const best = AD.fit_best[String(v)];
        html += "<h2>Teams and players here</h2><div class='two-columns'>"
            + panel("Win % here (3+ matches)", htmlBars(teamBars, 100, home ? home[0] : ""), "No-results not counted. Home team highlighted.")
            + panel("Top run-scorers here", linkTable(["Batter", "Inns", "Runs", "SR"], topBat))
            + panel("Top wicket-takers here", linkTable(["Bowler", "Matches", "Wkts", "Econ"], topBowl))
            + panel("Best fits: faster or cheaper here than elsewhere (120+ balls)",
                    linkTable(["Batter", "SR here", "SR elsewhere"], best.bat.map(function (r) { return [pLink(r[0]), r[2], r[3]]; }))
                    + linkTable(["Bowler", "Econ here", "Econ elsewhere"], best.bowl.map(function (r) { return [pLink(r[0]), r[2], r[3]]; })),
                    "Elsewhere = the same player at other grounds in the same seasons.")
            + "</div>";

        // Matches here
        const high = (AD.ground_high[String(v)] || []).map(function (r) { return [matchLink(r[5], r[0]), safe(r[1]), safe(r[2]), r[3]]; });
        const recent = CF.matches.filter(function (m) { return m[6] === name; }).slice(-8).reverse()
            .map(function (m) { return [matchLink(m[8], m[0]), safe(m[1] + " v " + m[2]), safe(m[5])]; });
        html += "<h2>Matches</h2><div class='two-columns'>" + panel("Highest totals", linkTable(["Score", "Team", "Against", "Season"], high))
              + panel("Most recent matches", linkTable(["Date", "Match", "Result"], recent)) + "</div>";
        page.innerHTML = html;

        const periods = AD.pitch_periods.filter(function (pr) { return AD.pitch[pr[0]].some(function (r) { return r[0] === v; }); });
        fillSelect(byId("ground-period"), periods, "all");
        const draw = function () { byId("ground-pitch").innerHTML = groundPitchBlock(v, byId("ground-period").value); };
        byId("ground-period").addEventListener("change", draw);
        draw();
    }

    // ----- Router -----------------------------------------------------------
    function showView(view) {
        document.querySelectorAll("[data-view]").forEach(function (el) { el.hidden = el.dataset.view !== view; });
        document.querySelectorAll(".site-nav a[data-nav]").forEach(function (a) {
            if (a.dataset.nav === view) { a.setAttribute("aria-current", "page"); } else { a.removeAttribute("aria-current"); }
        });
    }

    function route() {
        const r = parseRoute(location.hash);
        if (r.view === null) {
            // An old section link (#rivalry): show the view that holds it, then scroll to it.
            const target = byId(r.section);
            const holder = target ? target.closest("[data-view]") : null;
            showView(holder ? holder.dataset.view : "home");
            document.title = (target ? target.textContent : "Sports Arena") + " | Sports Arena";
            if (target) { target.scrollIntoView(); }
            return;
        }
        const known = ["home", "players", "grounds", "teams", "predictions", "ask", "analysis"];
        const view = known.indexOf(r.view) >= 0 ? r.view : "home";
        showView(view);
        const titles = { teams: "Teams", predictions: "Predictions", ask: "Ask Sports Arena", analysis: "More analysis" };
        if (titles[view]) { document.title = titles[view] + " | Sports Arena"; }
        if (view === "home") { renderHome(); document.title = "Sports Arena"; }
        if (view === "players") {
            if (r.player) { renderPlayer(r.player); document.title = r.player + " | Sports Arena"; }
            else { renderPlayers(); document.title = "Players | Sports Arena"; }
        }
        if (view === "grounds") {
            if (r.ground) { renderGround(r.ground); document.title = r.ground + " | Sports Arena"; }
            else { renderGrounds(); document.title = "Grounds | Sports Arena"; }
        }
        if (view === "ask" && r.question && byId("chat-input")) {
            byId("chat-input").value = r.question;
            byId("chat-form").dispatchEvent(new Event("submit", { cancelable: true }));
            history.replaceState(null, "", "#/ask");
        }
        window.scrollTo(0, 0);
    }

    // ----- Search, theme ----------------------------------------------------
    const list = byId("site-search-list");
    AD.players.concat(AD.venues, AD.teams).forEach(function (name) {
        const option = document.createElement("option");
        option.value = name;
        list.appendChild(option);
    });
    byId("site-search").addEventListener("submit", function (event) {
        event.preventDefault();
        const input = byId("site-search-input");
        const found = resolveSearch(input.value, NAMES, ALIASES);
        const hint = byId("site-search-hint");
        hint.innerHTML = "";
        if (!found) {
            hint.innerHTML = "No player, ground or team matches \"" + safe(input.value) + "\".";
            return;
        }
        if (found.kind === "choose") {
            hint.innerHTML = "Did you mean: " + found.options.map(function (n) { return "<a href='" + playerHref(n) + "'>" + safe(n) + "</a>"; }).join(", ");
            return;
        }
        input.value = "";
        if (found.kind === "player") { location.hash = playerHref(found.name); }
        if (found.kind === "ground") { location.hash = groundHref(found.name); }
        if (found.kind === "team") {
            byId("filter-team").value = found.name;
            byId("filter-team").dispatchEvent(new Event("change"));
            location.hash = "#/teams";
        }
    });
    byId("site-search-hint").addEventListener("click", function () { byId("site-search-hint").innerHTML = ""; });

    function setTheme(theme) {
        document.documentElement.dataset.theme = theme;
        try { localStorage.setItem("sports-arena-theme", theme); } catch (error) { /* storage blocked: fine */ }
    }
    let saved = null;
    try { saved = localStorage.getItem("sports-arena-theme"); } catch (error) { saved = null; }
    if (saved) { document.documentElement.dataset.theme = saved; }
    byId("theme-toggle").addEventListener("click", function () {
        const dark = document.documentElement.dataset.theme === "dark"
            || (!document.documentElement.dataset.theme && window.matchMedia("(prefers-color-scheme: dark)").matches);
        setTheme(dark ? "light" : "dark");
    });

    window.addEventListener("hashchange", route);
    route();
}

if (typeof document !== "undefined" && document.getElementById("site-data")) {
    setupSite();
}

// Let Node.js (tests/test_site.js) test the small functions.
if (typeof module !== "undefined") {
    module.exports = { parseRoute: parseRoute, playerRole: playerRole, careerNumbers: careerNumbers,
                       resolveSearch: resolveSearch, niceMax: niceMax, svgBars: svgBars, playerHref: playerHref };
}
