// =============================================================================
// test_site.js
// -----------------------------------------------------------------------------
// Checks for the new site design (src/site.js): the address router, the search
// that understands nicknames, player roles and career numbers, and the charts.
// The numbers are compared with the chatbot facts (outputs/chat_facts.json),
// which Python calculated from the data.
//
// Run it from the project folder (after build_report.py) with:
//     node tests/test_site.js
// =============================================================================

const path = require("path");
const projectFolder = path.join(__dirname, "..");
const facts = require(path.join(projectFolder, "outputs", "chat_facts.json")).facts;
const site = require(path.join(projectFolder, "src", "site.js"));

let failed = 0;
function check(name, condition) {
    if (condition) {
        console.log("PASS  " + name);
    } else {
        failed += 1;
        console.log("FAIL  " + name);
    }
}

// 1. The router reads every kind of address.
const player = site.parseRoute("#/player/V%20Kohli");
check("route to a player page", player.view === "players" && player.player === "V Kohli");
const ground = site.parseRoute("#/ground/MA%20Chidambaram%20Stadium%2C%20Chepauk");
check("route to a ground page (comma in the name)", ground.view === "grounds" && ground.ground === "MA Chidambaram Stadium, Chepauk");
check("route to home", site.parseRoute("").view === "home" && site.parseRoute("#/home").view === "home");
check("old section link", site.parseRoute("#rivalry").view === null && site.parseRoute("#rivalry").section === "rivalry");
check("ask with a question", site.parseRoute("#/ask?q=Kohli%20vs%20Bumrah").question === "Kohli vs Bumrah");
check("links round-trip", site.parseRoute(site.playerHref("AB de Villiers")).player === "AB de Villiers");
check("route to a team page", site.parseRoute(site.teamHref("Mumbai Indians")).team === "Mumbai Indians");
const compare = site.parseRoute(site.compareHref("Chennai Super Kings", "Mumbai Indians", "MA Chidambaram Stadium, Chepauk"));
check("route to a two-team comparison at a ground", compare.view === "compare" && compare.teamA === "Chennai Super Kings"
      && compare.teamB === "Mumbai Indians" && compare.ground === "MA Chidambaram Stadium, Chepauk");
check("route to a rivalry", site.parseRoute("#/rivalry/Royal%20Challengers%20Bengaluru/Kolkata%20Knight%20Riders").teamB === "Kolkata Knight Riders");
check("edge text names the leader", site.edgeText("A", 60, "B", 50, true, "win %", "%") === "A lead on win %: 60% vs 50%."
      && site.edgeText("A", 8.6, "B", 8.2, false, "runs conceded", "") === "B lead on runs conceded: 8.2 vs 8.6.");

// 2. Search understands names, nicknames and grounds (using the chatbot's alias lists).
const names = { players: facts.names, venues: Object.values(facts.venue_aliases).filter(function (v, i, all) { return all.indexOf(v) === i; }),
                teams: Object.values(facts.team_aliases).filter(function (v, i, all) { return all.indexOf(v) === i; }) };
const aliases = { players: facts.player_aliases, venues: facts.venue_aliases, teams: facts.team_aliases };
check("search 'sky' -> SA Yadav", site.resolveSearch("sky", names, aliases).name === "SA Yadav");
check("search 'chepauk' -> the ground", site.resolveSearch("Chepauk", names, aliases).name === "MA Chidambaram Stadium, Chepauk");
check("search 'kings xi punjab' -> Punjab Kings", site.resolveSearch("Kings XI Punjab", names, aliases).name === "Punjab Kings");
check("search 'csk' -> a team", site.resolveSearch("csk", names, aliases).kind === "team");
check("search 'sharma' asks which one", site.resolveSearch("sharma", names, aliases).kind === "choose");
check("search nonsense finds nothing", site.resolveSearch("zzzz", names, aliases) === null);

// 3. Career numbers equal the facts (worked out the same way as metrics.py).
const kohli = facts.players["V Kohli"].career;
const numbers = site.careerNumbers(kohli);
check("Kohli runs = facts", numbers.runs === kohli[2]);
check("Kohli strike rate = runs / balls x 100", numbers.strikeRate === Math.round(kohli[2] / kohli[3] * 1000) / 10);
check("Kohli is a batter, Bumrah a bowler", site.playerRole(kohli, 0) === "Batter"
      && site.playerRole(facts.players["JJ Bumrah"].career, 0) === "Bowler");
check("a keeper is marked as wicket-keeper", site.playerRole(facts.players["MS Dhoni"].career, 5).indexOf("wicket-keeper") > 0);

// 4. Charts: round axis tops, and one bar per item with its hover text.
check("nice axis tops", site.niceMax(973) === 1000 && site.niceMax(7.4) === 10 && site.niceMax(0.25) === 0.25);
const svg = site.svgBars([{ label: "a", value: 3, title: "A: 3" }, { label: "b", value: 5, title: "B: 5", href: "#x" }], {});
check("bar chart has 2 bars, hover text and a link", (svg.match(/<rect/g) || []).length === 2 && svg.indexOf("<title>B: 5</title>") > 0
      && svg.indexOf("href='#x'") > 0);

if (failed > 0) {
    console.log("\n" + failed + " site check(s) failed.");
    process.exit(1);
}
console.log("\nAll site checks passed.");
