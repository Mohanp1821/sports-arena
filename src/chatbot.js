// =============================================================================
// chatbot.js
// -----------------------------------------------------------------------------
// "Ask Sports Arena": a question-answering chatbot that uses ONLY the facts
// calculated from the data (outputs/chat_facts.json, made by src/chat_facts.py
// and put inside the dashboard page by build_report.py).
//
// It never makes up a number. How it works, step by step:
//   1. FIND THE NAMES in the question: teams ("CSK", "Kings XI Punjab"),
//      players ("Kohli", "SKY"), grounds ("Chepauk"), seasons (2016) and dates.
//      Short names and old names are in alias lists inside the facts file.
//   2. WORK OUT THE QUESTION TYPE from keywords and the names found
//      (e.g. "orange cap" + a season = a cap question; two players + "vs" = a matchup).
//   3. BUILD THE ANSWER from the facts only, and say where the numbers come from.
//   4. If the question is outside what the data covers, SAY SO and suggest
//      questions it can answer.
//
// The same file works in the browser (the chat panel) and in Node.js
// (tests/test_chatbot.js runs about 20 questions through it).
// Plain JavaScript, no libraries.
// =============================================================================


// ---------------------------------------------------------------------------
// 1. Small helpers
// ---------------------------------------------------------------------------
// Lower-case the question and turn punctuation into spaces, so "CSK's" -> "csk s".
function normalise(text) {
    return " " + text.toLowerCase().replace(/[’']/g, " ").replace(/[^a-z0-9\-\/ ]/g, " ").replace(/\s+/g, " ").trim() + " ";
}

function roundTo(value, places) {
    const factor = Math.pow(10, places);
    return Math.round(value * factor) / factor;
}

// 117 legal balls -> "19.3" overs.
function oversOf(legalBalls) {
    return Math.floor(legalBalls / 6) + "." + (legalBalls % 6);
}

// Format a number with commas: 10000 -> "10,000".
function withCommas(number) {
    return String(number).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Find every alias from aliasMap inside the text (whole words only).
// Longer aliases are tried first, and a part of the text can only be used once,
// so "royal challengers bangalore" is found as one team, not "bangalore" alone.
// Returns [{value, start}] in the order they appear in the question.
function findNames(text, aliasMap, used) {
    const aliases = Object.keys(aliasMap).sort(function (a, b) { return b.length - a.length; });
    const found = [];
    aliases.forEach(function (alias) {
        const needle = " " + alias + " ";
        let from = 0;
        while (true) {
            const at = text.indexOf(needle, from);
            if (at < 0) { break; }
            let free = true;
            for (let i = at + 1; i < at + needle.length - 1; i++) {
                if (used[i]) { free = false; break; }
            }
            if (free) {
                for (let i = at + 1; i < at + needle.length - 1; i++) { used[i] = true; }
                found.push({ value: aliasMap[alias], start: at, alias: alias });
            }
            from = at + 1;
        }
    });
    found.sort(function (a, b) { return a.start - b.start; });
    return found;
}

// Keep the first appearance of each value.
function unique(values) {
    return values.filter(function (value, i) { return values.indexOf(value) === i; });
}

const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };

// A date in the question, as "YYYY-MM-DD" (accepts 2026-05-31, 31/05/2026, 31 May 2026, May 31 2026).
function findDate(text) {
    let m = text.match(/(20\d\d)-(\d{1,2})-(\d{1,2})/);
    if (m) { return m[1] + "-" + pad(m[2]) + "-" + pad(m[3]); }
    m = text.match(/\b(\d{1,2})\/(\d{1,2})\/(20\d\d)\b/);
    if (m) { return m[3] + "-" + pad(m[2]) + "-" + pad(m[1]); }
    m = text.match(/\b(\d{1,2})(?:st|nd|rd|th)? (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* (20\d\d)\b/);
    if (m) { return m[3] + "-" + pad(MONTHS[m[2]]) + "-" + pad(m[1]); }
    m = text.match(/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* (\d{1,2})(?:st|nd|rd|th)? (20\d\d)\b/);
    if (m) { return m[3] + "-" + pad(MONTHS[m[1]]) + "-" + pad(m[2]); }
    return null;
}

function pad(number) {
    return String(number).length === 1 ? "0" + number : String(number);
}

function has(text, words) {
    return words.some(function (word) { return text.indexOf(word) >= 0; });
}


// ---------------------------------------------------------------------------
// 2. Reading the question
// ---------------------------------------------------------------------------
// A player's size of career, used to settle short names shared by several players.
function careerSize(facts, name) {
    const c = facts.players[name].career;
    return c[2] + 25 * c[9];          // runs + 25 x wickets
}

// Settle an alias that points to several players (e.g. "Sharma"):
// pick the clear leader if his career is 5 times bigger than the next, else ask.
function settlePlayer(facts, candidates) {
    if (candidates.length === 1) { return { name: candidates[0] }; }
    const sorted = candidates.slice().sort(function (a, b) { return careerSize(facts, b) - careerSize(facts, a); });
    if (careerSize(facts, sorted[0]) >= 5 * Math.max(1, careerSize(facts, sorted[1]))) {
        return { name: sorted[0], others: sorted.slice(1) };
    }
    return { ambiguous: sorted };
}

function readQuestion(question, facts) {
    const text = normalise(question);
    const used = {};
    const venues = unique(findNames(text, facts.venue_aliases, used).map(function (f) { return f.value; }));
    const teams = unique(findNames(text, facts.team_aliases, used).map(function (f) { return f.value; }));
    const playerHits = findNames(text, facts.player_aliases, used);
    const players = [];
    const ambiguous = [];
    const notes = [];
    playerHits.forEach(function (hit) {
        const settled = settlePlayer(facts, hit.value);
        if (settled.name) {
            if (players.indexOf(settled.name) < 0) { players.push(settled.name); }
            if (settled.others) {
                notes.push("I took \"" + hit.alias + "\" to mean " + settled.name + " (others with that name: "
                           + settled.others.slice(0, 4).join(", ") + ").");
            }
        } else {
            ambiguous.push({ alias: hit.alias, options: settled.ambiguous });
        }
    });
    const seasons = unique((text.match(/\b(19|20)\d\d\b/g) || []).map(Number));
    return { text: text, teams: teams, players: players, venues: venues, seasons: seasons,
             date: findDate(text), ambiguous: ambiguous, notes: notes };
}


// ---------------------------------------------------------------------------
// 3. Answers (each one uses only the facts)
// ---------------------------------------------------------------------------
const DATA_SOURCE = "Source: ball-by-ball data, Kaggle 2008-2019 + Cricsheet 2020-2026 (super overs not counted).";

function reply(text, source) {
    return { text: text, source: source };
}

function seasonOutside(facts, season) {
    return season < facts.meta.first_season || season > facts.meta.last_season;
}

function outOfRange(facts, season) {
    return reply("The data covers IPL " + facts.meta.season_range + ", so I have nothing for " + season
                 + ". Try a season from " + facts.meta.first_season + " to " + facts.meta.last_season
                 + (facts.predictions ? ", or ask about the " + facts.predictions.season + " predictions." : "."),
                 DATA_SOURCE);
}

function answerChampion(facts, q) {
    if (q.seasons.length > 0) {
        const season = q.seasons[0];
        if (facts.predictions && season === facts.predictions.season) { return answerPrediction(facts, q); }
        if (seasonOutside(facts, season)) { return outOfRange(facts, season); }
        const row = facts.champions[String(season)];
        return reply(row[1] + " won IPL " + season + ", beating " + row[2] + " in the final (" + row[3] + ") at "
                     + row[4] + "." + (row[0] !== row[1] ? " That franchise is now called " + row[0] + "." : ""),
                     "Source: the final (last match) of each season in the data.");
    }
    if (q.teams.length > 0) { return answerTitles(facts, q.teams[0]); }
    const lines = Object.keys(facts.champions).sort().map(function (season) {
        return season + ": " + facts.champions[season][1];
    });
    return reply("IPL champions " + facts.meta.season_range + ": " + lines.join("; ") + ".",
                 "Source: the final (last match) of each season in the data.");
}

function answerTitles(facts, team) {
    const won = Object.keys(facts.champions).sort().filter(function (season) { return facts.champions[season][0] === team; });
    if (won.length === 0) {
        return reply(team + " have not won the IPL in " + facts.meta.season_range + ".", "Source: the final of each season.");
    }
    return reply(team + " have won " + won.length + " IPL title" + (won.length > 1 ? "s" : "") + ": " + won.join(", ")
                 + " (franchise record, old team names included).", "Source: the final (last match) of each season.");
}

function answerCap(facts, q, orange) {
    const capName = orange ? "Orange Cap (most runs)" : "Purple Cap (most wickets)";
    if (q.seasons.length === 0) { return answerLeaders(facts, orange); }
    const season = q.seasons[0];
    if (facts.predictions && season === facts.predictions.season) { return answerAwardPrediction(facts, capName); }
    if (seasonOutside(facts, season)) { return outOfRange(facts, season); }
    const row = facts.caps[String(season)];
    const text = orange ? "The IPL " + season + " Orange Cap went to " + row[0] + " with " + row[1] + " runs."
                        : "The IPL " + season + " Purple Cap went to " + row[2] + " with " + row[3] + " wickets.";
    return reply(text, DATA_SOURCE + " Ties for wickets are broken by economy, like the official cap.");
}

function answerLeaders(facts, runs) {
    const names = Object.keys(facts.players);
    names.sort(function (a, b) {
        return runs ? facts.players[b].career[2] - facts.players[a].career[2] : facts.players[b].career[9] - facts.players[a].career[9];
    });
    const top = names.slice(0, 5).map(function (name, i) {
        const c = facts.players[name].career;
        return (i + 1) + ". " + name + " " + (runs ? c[2] + " runs" : c[9] + " wickets");
    });
    return reply("Most IPL " + (runs ? "runs" : "wickets") + " " + facts.meta.season_range + ": " + top.join("; ")
                 + ". Add a season (e.g. 2016) to get that year's cap.", DATA_SOURCE);
}

function answerPlayer(facts, name, season) {
    const player = facts.players[name];
    if (season) {
        if (seasonOutside(facts, season)) { return outOfRange(facts, season); }
        const s = player.seasons[String(season)];
        if (!s) { return reply(name + " did not bat or bowl in IPL " + season + " in the data.", DATA_SOURCE); }
        let text = name + " in IPL " + season + " (" + s[0] + "): ";
        const parts = [];
        if (s[2] > 0) {
            parts.push(s[1] + " runs off " + s[2] + " balls (strike rate " + roundTo(s[1] / s[2] * 100, 1)
                       + (s[3] > 0 ? ", average " + roundTo(s[1] / s[3], 2) : ", not out every time") + ", " + s[4] + " sixes)");
        }
        if (s[5] > 0 || s[6] >= 30) {      // leave out a part-time over or two with no wicket
            parts.push(s[5] + " wickets in " + oversOf(s[6]) + " overs (economy " + roundTo(s[7] / (s[6] / 6), 2) + ")");
        }
        return reply(text + parts.join("; ") + ".", DATA_SOURCE);
    }
    const c = player.career;
    const seasons = Object.keys(player.seasons).sort();
    let best = seasons[0];
    seasons.forEach(function (year) { if (player.seasons[year][1] > player.seasons[best][1]) { best = year; } });
    const parts = [c[0] + " matches (" + seasons[0] + "-" + seasons[seasons.length - 1] + ")"];
    if (c[3] > 0) {
        parts.push(c[2] + " runs at strike rate " + roundTo(c[2] / c[3] * 100, 1)
                   + (c[4] > 0 ? ", average " + roundTo(c[2] / c[4], 2) : "") + ", highest " + c[5] + ", "
                   + c[6] + " fifties, " + c[7] + " hundreds, " + c[8] + " sixes");
    }
    if (c[9] > 0 || c[10] >= 60) {     // leave out a few part-time overs with no wicket
        parts.push(c[9] + " wickets in " + oversOf(c[10]) + " overs (economy " + roundTo(c[11] / (c[10] / 6), 2) + ")");
    }
    let text = name + "'s IPL career: " + parts.join("; ") + ".";
    if (player.seasons[best][1] > 0) {
        text += " Best batting season: " + best + " (" + player.seasons[best][1] + " runs for " + player.seasons[best][0] + ").";
    }
    return reply(text, DATA_SOURCE);
}

function answerMatchup(facts, batter, bowler) {
    const b = facts.names.indexOf(batter);
    const w = facts.names.indexOf(bowler);
    let row = facts.matchups.find(function (r) { return r[0] === b && r[1] === w; });
    let swapped = false;
    if (!row) {
        row = facts.matchups.find(function (r) { return r[0] === w && r[1] === b; });
        swapped = true;
    }
    if (!row) {
        return reply(batter + " and " + bowler + " met in fewer than 6 balls (or never), so there is no matchup to report.",
                     DATA_SOURCE);
    }
    const bat = swapped ? bowler : batter;
    const bowl = swapped ? batter : bowler;
    const balls = row[2], runs = row[3], outs = row[4];
    return reply(bat + " (batting) against " + bowl + " (bowling): " + balls + " balls, " + runs + " runs, strike rate "
                 + roundTo(runs / balls * 100, 1) + ", out " + outs + " time" + (outs === 1 ? "" : "s")
                 + (outs > 0 ? " (" + roundTo(runs / outs, 1) + " runs per dismissal)" : "") + ", dot balls "
                 + roundTo(row[5] / balls * 100, 1) + "%, " + row[6] + " fours and " + row[7] + " sixes.",
                 DATA_SOURCE + " Balls faced leave out wides; dismissals are wickets credited to the bowler.");
}

function answerRivalry(facts, teamA, teamB) {
    const first = teamA < teamB ? teamA : teamB;
    const second = teamA < teamB ? teamB : teamA;
    const row = facts.rivalry[first + "|" + second];
    if (!row) { return reply(teamA + " and " + teamB + " never played each other in the data.", DATA_SOURCE); }
    return reply(first + " vs " + second + ", IPL " + facts.meta.season_range + ": " + row[0] + " matches. " + first
                 + " won " + row[1] + ", " + second + " won " + row[2] + (row[3] ? ", no result " + row[3] : "")
                 + ". Last meeting " + row[4] + ".", "Source: match results " + facts.meta.season_range
                 + " (franchise records, old team names included; super-over wins count as wins).");
}

function answerRivalryAtGround(facts, teamA, teamB, venue) {
    const first = teamA < teamB ? teamA : teamB;
    const second = teamA < teamB ? teamB : teamA;
    const grounds = facts.rivalry_ground[first + "|" + second] || {};
    const row = grounds[venue];
    const record = function (team) {
        const r = facts.ground[team + "|" + venue];
        return r ? team + " have won " + r[1] + " of " + r[0] + " there (" + roundTo(r[1] / r[0] * 100, 1) + "%)"
                 : team + " have not played there";
    };
    const text = (row ? first + " vs " + second + " at " + venue + ": " + row[0] + " matches, " + first + " won " + row[1] + ", "
                        + second + " won " + row[2] + (row[3] ? ", no result " + row[3] : "") + "."
                      : first + " and " + second + " have never played each other at " + venue + ".")
               + " Against anyone at this ground: " + record(teamA) + "; " + record(teamB) + ".";
    return reply(text, "Source: match results " + facts.meta.season_range + " (franchise records). "
                 + "The dashboard's compare page (Teams) has run rates and players at the ground side by side.");
}

function answerTeamAtGround(facts, team, venue) {
    const row = facts.ground[team + "|" + venue];
    if (!row) { return reply(team + " have no finished matches at " + venue + " in the data.", DATA_SOURCE); }
    return reply(team + " at " + venue + ": won " + row[1] + " of " + row[0] + " matches ("
                 + roundTo(row[1] / row[0] * 100, 1) + "%), " + row[2] + "-" + row[3] + ".",
                 "Source: match results (no-results not counted). The dashboard's Ground view has it season by season.");
}

const PITCH_NOTE = "Source: ball-by-ball data; indexes compare the ground with the whole league in the same seasons "
                 + "(100 = average). There are no pitch reports in the data, so this is how the ground has played "
                 + "(pitch, boundary size, outfield and weather together).";

function answerPitch(facts, venue) {
    const p = facts.pitch.all[venue];
    if (!p) { return reply("There are no matches at " + venue + " in the data.", DATA_SOURCE); }
    const describe = function (index, what) {
        const difference = roundTo(index - 100, 1);
        return what + " index " + index + " (" + (difference === 0 ? "the same as" : Math.abs(difference) + "% "
               + (difference > 0 ? "more than" : "fewer than")) + " the league)";
    };
    let text = venue + ", " + facts.meta.season_range + " (" + p[0] + " matches): " + p[8] + ". "
             + describe(p[2], "Runs") + ", " + describe(p[3], "wickets") + ", " + describe(p[4], "fours-and-sixes")
             + "; run rate " + p[1] + ", average first innings " + p[6] + ", chasing side won " + p[7] + "%.";
    const recent = facts.pitch.recent[venue];
    if (recent && recent[0] >= 5) {
        text += " Since 2023 (" + recent[0] + " matches): runs index " + recent[2] + ", wickets index " + recent[3] + ".";
    }
    return reply(text, PITCH_NOTE);
}

function answerPlayerAtGround(facts, name, venue) {
    const bat = facts.fit.bat[name + "|" + venue];
    const bowl = facts.fit.bowl[name + "|" + venue];
    if (!bat && !bowl) {
        return reply(name + " has fewer than 30 balls batting or bowling at " + venue + " in the data, so there is "
                     + "nothing reliable to compare.", DATA_SOURCE);
    }
    const parts = [];
    // A side with fewer than 60 balls (e.g. a batter's few overs) is left out, unless it is all there is.
    const showBat = bat && (bat[0] >= 60 || !bowl || bowl[0] < 60);
    const showBowl = bowl && (bowl[0] >= 60 || !bat || bat[0] < 60);
    if (showBat) {
        const here = roundTo(bat[1] / bat[0] * 100, 1);
        const elsewhere = bat[3] > 0 ? roundTo(bat[4] / bat[3] * 100, 1) : null;
        parts.push("batting: " + bat[1] + " runs off " + bat[0] + " balls, strike rate " + here
                   + (bat[2] > 0 ? ", average " + roundTo(bat[1] / bat[2], 1) : "")
                   + (elsewhere !== null ? " (vs strike rate " + elsewhere + " at other grounds in the same seasons, "
                      + (here >= elsewhere ? "+" : "") + roundTo(here - elsewhere, 1) + ")" : ""));
    }
    if (showBowl) {
        const here = roundTo(bowl[1] / (bowl[0] / 6), 2);
        const elsewhere = bowl[3] > 0 ? roundTo(bowl[4] / (bowl[3] / 6), 2) : null;
        parts.push("bowling: " + bowl[2] + (bowl[2] === 1 ? " wicket in " : " wickets in ") + oversOf(bowl[0]) + " overs, economy " + here
                   + (elsewhere !== null ? " (vs " + elsewhere + " elsewhere in the same seasons, "
                      + (here <= elsewhere ? "cheaper here" : "more expensive here") + ")" : ""));
    }
    return reply(name + " at " + venue + ": " + parts.join("; ") + ".",
                 DATA_SOURCE + " \"Elsewhere\" = the same player at other grounds in the seasons he played here.");
}

function answerImpact(facts) {
    const eras = facts.impact.eras;
    const choices = facts.impact.choices.map(function (c) { return c[0] + " " + c[1] + " times (won " + c[3] + "%)"; });
    const phase = function (era, name) {
        const row = facts.impact.phases.find(function (r) { return r[0] === era && r[1] === name; });
        return row ? row[2] : "-";
    };
    const label = function (era) { return era.split(" ")[0]; };     // "2020-22 (before ...)" -> "2020-22"
    return reply("Impact Player rule (from 2023): average first-innings score went from " + eras[0][2] + " in " + label(eras[0][0])
                 + " to " + eras[1][2] + " in " + label(eras[1][0]) + "; totals of 200+ from " + eras[0][4] + " to " + eras[1][4]
                 + " per match; chases won " + eras[0][5] + "% vs " + eras[1][5] + "%. Run rate: Powerplay "
                 + phase(eras[0][0], "Powerplay") + " to " + phase(eras[1][0], "Powerplay") + ", Death " + phase(eras[0][0], "Death")
                 + " to " + phase(eras[1][0], "Death") + ". What the " + facts.impact.substitutions
                 + " substitutes did: " + choices.join("; ") + ".",
                 "Source: ball-by-ball data 2020-2026 (rain-shortened and no-result matches left out) and the "
                 + "Cricsheet replacement records.");
}

function predictionRow(facts, team) {
    return facts.predictions.teams.find(function (t) { return t[0] === team; });
}

function answerPrediction(facts, q) {
    const p = facts.predictions;
    if (!p) { return reply("The predictions have not been made yet (run src/predict.py and src/predict_ml.py).", ""); }
    const source = "Source: Model A (form win %) and Model B (logistic regression + gradient boosting), "
                 + withCommas(p.simulations) + " simulated " + p.season + " seasons each.";
    if (q.teams.length > 0) {
        const t = predictionRow(facts, q.teams[0]);
        if (!t) { return reply(q.teams[0] + " is not in the " + p.season + " squads file.", source); }
        return reply(t[0] + " in IPL " + p.season + " (" + withCommas(p.simulations) + " simulated seasons per model): Model A gives a " + t[1] + "% title chance (" + t[2]
                     + "% to reach the playoffs; strength " + t[5] + " = form win %); Model B gives " + t[3] + "% ("
                     + t[4] + "% playoffs; squad strength " + t[6] + ", Elo " + t[7] + ").", source);
    }
    const byA = p.teams.slice().sort(function (x, y) { return y[1] - x[1]; });
    const byB = p.teams.slice().sort(function (x, y) { return y[3] - x[3]; });
    const top = function (rows, column) {
        return rows.slice(0, 3).map(function (t) { return t[0] + " " + t[column] + "%"; }).join(", ");
    };
    let text = (byA[0][0] === byB[0][0] ? "Both models make " + byA[0][0] + " the favourite for IPL " + p.season
                                         : "The models disagree for IPL " + p.season)
        + " (title chances from " + withCommas(p.simulations) + " simulated seasons per model). "
        + "Model A (strength = form win % of the last 3 seasons, weights 3-2-1): " + top(byA, 1) + ". Why: "
        + byA[0][0] + " has the best strength, " + byA[0][5] + ". Model B (Elo, form, head-to-head, ground, home, squad strength): "
        + top(byB, 3) + "; " + byB[0][0] + " has squad strength " + byB[0][6] + " and Elo " + byB[0][7] + ".";
    const modelA = p.backtest.find(function (r) { return r[0] === "Model A"; });
    if (modelA) {
        text += " Treat these as rough guides: in the 2021-2026 backtest Model A picked " + modelA[2]
              + "% of match winners, close to a coin flip.";
    }
    return reply(text, source);
}

function answerAwardPrediction(facts, award) {
    const p = facts.predictions;
    if (!p) { return reply("The predictions have not been made yet.", ""); }
    const a = p.awards_a.filter(function (r) { return r[0] === award; });
    const b = p.awards_b.filter(function (r) { return r[0] === award; });
    return reply(award + ", IPL " + p.season + ": Model A picks " + a[0][2] + " (" + a[0][3] + ", form " + a[0][4] + " "
                 + a[0][5] + " a season; next " + a.slice(1, 3).map(function (r) { return r[2]; }).join(", ")
                 + "). Model B picks " + b[0][2] + " (" + b[0][3] + ", predicted " + b[0][4] + " " + b[0][5] + "; next "
                 + b.slice(1, 3).map(function (r) { return r[2]; }).join(", ") + ").",
                 "Source: Model A form scores (last 3 seasons, weights 3-2-1) and Model B linear regression, "
                 + "players in data/squads_2027.csv only.");
}

function answerModels(facts) {
    const p = facts.predictions;
    if (!p) { return reply("The model comparison has not been run yet.", ""); }
    const rows = p.backtest.map(function (r) {
        return r[0] + ": accuracy " + r[2] + "%, log loss " + r[3] + ", Brier " + r[4];
    });
    const ranks = p.titles.map(function (t) { return t[0] + " " + t[2] + " (A #" + t[3] + ", B #" + t[4] + ")"; });
    return reply("Walk-forward backtest 2021-2026 (" + p.backtest[0][1] + " matches, each season predicted using only "
                 + "earlier seasons). " + rows.join("; ") + ". Lower log loss and Brier are better. Where the real "
                 + "champion ranked: " + ranks.join("; ") + ". Before a season starts, T20 results are close to a "
                 + "coin flip for both models.", "Source: outputs/model_comparison_matches.csv and model_comparison_titles.csv.");
}

function answerDate(facts, q) {
    let games = facts.matches.filter(function (m) { return m[0] === q.date; });
    if (q.teams.length > 0) {
        games = games.filter(function (m) { return q.teams.indexOf(m[3]) >= 0 || q.teams.indexOf(m[4]) >= 0; });
    }
    if (games.length === 0) {
        return reply("No IPL match in the data on " + q.date + ". (The data has every match from " + facts.matches[0][0]
                     + " to " + facts.matches[facts.matches.length - 1][0] + ".)", DATA_SOURCE);
    }
    const lines = games.map(function (m) {
        return m[1] + " v " + m[2] + " at " + m[6] + (m[9] !== "League" ? " (" + m[9] + ")" : "") + ": " + m[5]
             + ". Player of the match: " + (m[7] || "not awarded") + ". Open it in the match centre: match id " + m[8] + ".";
    });
    return reply("On " + q.date + ": " + lines.join(" "), DATA_SOURCE);
}

const SUGGESTIONS = ["Who will win IPL 2027?", "How does the pitch at Chepauk play?", "Kohli at Chinnaswamy",
                     "Who won the Orange Cap in 2016?", "Kohli vs Bumrah",
                     "CSK vs MI head to head", "How do CSK do at Chepauk?", "What changed with the Impact Player rule?",
                     "Which model is better, Model A or Model B?", "What happened on 31 May 2026?"];

function outOfScope(facts) {
    return reply("I can only answer from the IPL " + facts.meta.season_range + " data and the "
                 + (facts.predictions ? facts.predictions.season + " " : "") + "predictions, and I could not match that "
                 + "question. Try: " + SUGGESTIONS.slice(0, 5).join(" / "), "");
}


// ---------------------------------------------------------------------------
// 4. The main function: question in, answer out
// ---------------------------------------------------------------------------
function answerQuestion(question, facts) {
    const q = readQuestion(question, facts);
    const t = q.text;
    let result;

    if (q.ambiguous.length > 0 && q.players.length + q.teams.length === 0) {
        const a = q.ambiguous[0];
        return reply("Which \"" + a.alias + "\" do you mean? For example: " + a.options.slice(0, 8).join(", ")
                     + ". The data uses short names like V Kohli or RG Sharma.", "");
    }
    const wantsOrange = has(t, ["orange cap", "top scorer", "top run", "leading run", "highest run", "run scorer"])
                        || /most (ipl |career |total )?runs/.test(t);
    const wantsPurple = has(t, ["purple cap", "top wicket", "leading wicket", "highest wicket", "wicket taker"])
                        || /most (ipl |career |total )?wickets/.test(t);
    const wantsSixes = has(t, ["most sixes"]);
    const wantsPotm = has(t, ["player of the match awards", "most player of the match"]);
    const future = facts.predictions && (q.seasons.indexOf(facts.predictions.season) >= 0
                   || has(t, [" predict", " will win", "favourite", "favorite", " next season", " chance"]));

    if (has(t, ["test match", " tests ", " odi", "one day", "world cup", " t20i", "ranji", "international",
                " bbl ", " psl ", " cpl ", "county", "women", " wpl "])) {
        return reply("The data covers the men's IPL " + facts.meta.season_range + " only, so I cannot answer about other "
                     + "competitions. Try: " + SUGGESTIONS.slice(0, 3).join(" / "), "");
    }
    if (has(t, ["weather", " rain ", "forecast", "temperature", "humidity", " dew "])) {
        return reply("The data has no weather, dew or forecast information, so I cannot answer that. I can tell you how a "
                     + "ground has played, e.g. \"How does the pitch at Chepauk play?\"", "");
    }
    if (q.date) {
        result = answerDate(facts, q);
    } else if (has(t, ["impact player", "impact sub", "impact rule", "impact-player"])) {
        result = answerImpact(facts);
    } else if ((has(t, ["model a"]) && has(t, ["model b"])) || has(t, ["which model", "better model", "backtest",
               "compare the models", "models compare", "model comparison", "how accurate"])) {
        result = answerModels(facts);
    } else if (future && (wantsOrange || wantsPurple || wantsSixes || wantsPotm)) {
        result = answerAwardPrediction(facts, wantsOrange ? "Orange Cap (most runs)" : wantsPurple ? "Purple Cap (most wickets)"
                                              : wantsSixes ? "Most sixes" : "Most Player of the Match awards");
    } else if (future) {
        result = answerPrediction(facts, q);
    } else if (wantsOrange && q.players.length === 0) {
        result = answerCap(facts, q, true);
    } else if (wantsPurple && q.players.length === 0) {
        result = answerCap(facts, q, false);
    } else if (has(t, [" won ipl", " win ipl", " won the ipl", " win the ipl", "champion", " title", "winner of ipl",
                       "ipl winner", "won the final", "won the title"])) {
        result = answerChampion(facts, q);
    } else if (q.players.length >= 2) {
        result = answerMatchup(facts, q.players[0], q.players[1]);
    } else if (q.teams.length >= 2 && q.venues.length >= 1) {
        result = answerRivalryAtGround(facts, q.teams[0], q.teams[1], q.venues[0]);
    } else if (q.teams.length >= 2) {
        result = answerRivalry(facts, q.teams[0], q.teams[1]);
    } else if (q.teams.length === 1 && q.venues.length >= 1) {
        result = answerTeamAtGround(facts, q.teams[0], q.venues[0]);
    } else if (q.players.length === 1 && q.venues.length >= 1) {
        result = answerPlayerAtGround(facts, q.players[0], q.venues[0]);
    } else if (q.venues.length >= 1 && q.teams.length === 0
               && has(t, ["pitch", "conditions", "track", "surface", "wicket like", " play", "ground like", "venue",
                          "scoring", "batting", "bowling", "spin", "pace", "profile"])) {
        result = answerPitch(facts, q.venues[0]);
    } else if (q.players.length === 1) {
        result = answerPlayer(facts, q.players[0], q.seasons[0]);
    } else if (q.teams.length === 1) {
        result = answerTitles(facts, q.teams[0]);
    } else if (q.seasons.length > 0 && seasonOutside(facts, q.seasons[0])
               && !(facts.predictions && q.seasons[0] === facts.predictions.season)) {
        result = outOfRange(facts, q.seasons[0]);
    } else {
        result = outOfScope(facts);
    }
    if (q.notes.length > 0) { result.text = q.notes.join(" ") + " " + result.text; }
    return result;
}


// ---------------------------------------------------------------------------
// 5. The chat panel on the dashboard (only runs in a browser)
// ---------------------------------------------------------------------------
// The optional local-LLM server (src/chat_server.py). If it is not running,
// every answer comes from answerQuestion() above, with no internet needed.
const CHAT_SERVER = "http://localhost:8765";

function setupChatPanel() {
    const facts = JSON.parse(document.getElementById("chat-facts").textContent);
    const log = document.getElementById("chat-log");
    const input = document.getElementById("chat-input");
    let serverModel = null;          // set when the local-LLM server answers /health

    function escapeHtml(text) {
        return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    function addMessage(who, text, source) {
        const div = document.createElement("div");
        div.className = "chat-msg " + who;
        div.innerHTML = escapeHtml(text) + (source ? "<small>" + escapeHtml(source) + "</small>" : "");
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
    }
    function useServer() {
        return serverModel !== null && document.getElementById("chat-llm").checked;
    }

    function ask(question) {
        if (!question.trim()) { return; }
        addMessage("user", question, "");
        input.value = "";
        const offline = answerQuestion(question, facts);
        if (!useServer()) {
            addMessage("bot", offline.text, offline.source);
            return;
        }
        fetch(CHAT_SERVER + "/ask", { method: "POST", headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify({ question: question }) })
            .then(function (response) { return response.json(); })
            .then(function (data) { addMessage("bot", data.answer, data.source); })
            .catch(function () {
                addMessage("bot", offline.text, offline.source + " (Local model unreachable, so this is the offline answer.)");
            });
    }

    document.getElementById("chat-form").addEventListener("submit", function (event) {
        event.preventDefault();
        ask(input.value);
    });
    const chips = document.getElementById("chat-examples");
    SUGGESTIONS.forEach(function (text) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = text;
        button.addEventListener("click", function () { ask(text); });
        chips.appendChild(button);
    });
    addMessage("bot", "Ask me about IPL " + facts.meta.season_range + " (" + withCommas(facts.meta.matches) + " matches, "
               + withCommas(facts.meta.balls) + " balls) or the " + facts.predictions.season + " predictions. "
               + "Every number comes from the data.", "Offline mode: answers are worked out in this page.");

    // Is the optional local-LLM server running? Wait at most 1.5 seconds.
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    if (controller) { setTimeout(function () { controller.abort(); }, 1500); }
    fetch(CHAT_SERVER + "/health", controller ? { signal: controller.signal } : {})
        .then(function (response) { return response.json(); })
        .then(function (data) {
            serverModel = data.model;
            document.getElementById("chat-mode").innerHTML = "<label><input type='checkbox' id='chat-llm' checked> "
                + "Use the local model (" + escapeHtml(data.model) + " via Ollama), answering only from retrieved facts</label>";
        })
        .catch(function () { /* no server: stay in offline mode */ });
}

if (typeof document !== "undefined" && document.getElementById("chat-facts")) {
    setupChatPanel();
}

// Let Node.js (tests/test_chatbot.js) use the answer engine.
if (typeof module !== "undefined") {
    module.exports = { answerQuestion: answerQuestion, readQuestion: readQuestion };
}
