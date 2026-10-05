// =============================================================================
// test_chatbot.js
// -----------------------------------------------------------------------------
// Question -> expected-answer checks for the "Ask Sports Arena" chatbot.
// Each check asks src/chatbot.js a question, using the facts file made by
// build_report.py (outputs/chat_facts.json), and checks that the answer
// CONTAINS the expected words and numbers.
//
// Official records (caps, champions) are written here; numbers that come from
// the ball data (e.g. a batter-vs-bowler matchup) are looked up in the facts
// file, so the test checks the chatbot repeats the data exactly.
//
// Run it from the project folder (after build_report.py) with:
//     node tests/test_chatbot.js
// =============================================================================

const path = require("path");
const projectFolder = path.join(__dirname, "..");
const facts = require(path.join(projectFolder, "outputs", "chat_facts.json")).facts;
const chatbot = require(path.join(projectFolder, "src", "chatbot.js"));

// Numbers from the facts file, for the data-dependent checks.
const kohli = facts.names.indexOf("V Kohli");
const bumrah = facts.names.indexOf("JJ Bumrah");
const matchup = facts.matchups.find(function (r) { return r[0] === kohli && r[1] === bumrah; });
const cskMi = facts.rivalry["Chennai Super Kings|Mumbai Indians"];
const cskChepauk = facts.ground["Chennai Super Kings|MA Chidambaram Stadium, Chepauk"];
const favourite = facts.predictions.teams.slice().sort(function (a, b) { return b[1] - a[1]; })[0];
const orange2027 = facts.predictions.awards_a.find(function (r) { return r[0] === "Orange Cap (most runs)" && r[1] === 1; });
const eras = facts.impact.eras;
const chepauk = facts.pitch.all["MA Chidambaram Stadium, Chepauk"];
const kohliChinnaswamy = facts.fit.bat["V Kohli|M Chinnaswamy Stadium"];
const topRuns = Object.keys(facts.players).sort(function (a, b) {
    return facts.players[b].career[2] - facts.players[a].career[2];
})[0];

const CHECKS = [
    ["Who won the Orange Cap in 2016?", ["V Kohli", "973"]],
    ["Who won IPL 2026?", ["Royal Challengers Bengaluru"]],
    ["Who won the Purple Cap in 2023?", ["Mohammed Shami", "28"]],
    ["Who won IPL 2009?", ["Deccan Chargers"]],
    ["Who won the Orange Cap in 2026?", ["V Suryavanshi", "776"]],
    ["How did Kohli do in 2016?", ["V Kohli", "973 runs"]],
    ["Kohli vs Bumrah", ["V Kohli", "JJ Bumrah", matchup[2] + " balls", matchup[3] + " runs"]],
    ["CSK vs MI head to head", ["Chennai Super Kings", "Mumbai Indians", cskMi[0] + " matches"]],
    ["How do CSK do at Chepauk?", ["MA Chidambaram Stadium", "won " + cskChepauk[1] + " of " + cskChepauk[0]]],
    ["Who will win IPL 2027?", ["Model A", "Model B", favourite[0], "10,000"]],
    ["Which model is better, Model A or Model B?", ["log loss", "Model A", "Model B", "Random guess"]],
    ["What changed with the Impact Player rule?", [String(eras[0][2]), String(eras[1][2])]],
    ["What happened on 31 May 2026?", ["Royal Challengers Bengaluru won by 5 wickets", "Final"]],
    ["How many titles have Royal Challengers Bangalore won?", ["Royal Challengers Bengaluru", "2025", "2026"]],
    ["How many titles have CSK won?", ["5 IPL titles", "2010", "2023"]],
    ["SKY career stats", ["SA Yadav"]],
    ["Who will win the Orange Cap in 2027?", [orange2027[2], "Model A", "Model B"]],
    ["Who has the most IPL runs?", [topRuns]],
    ["Who won the Orange Cap in 2007?", ["2008-2026", "nothing for 2007"]],
    ["What is the weather in Mumbai tomorrow?", ["no weather"]],
    ["Who scored the most runs in a test match?", ["men's IPL", "only"]],
    ["Sharma stats", ["Which", "RG Sharma"]],
    ["How does the pitch at Chepauk play?", ["MA Chidambaram Stadium, Chepauk", "Runs index " + chepauk[2]]],
    ["Kohli at Chinnaswamy", ["V Kohli", "M Chinnaswamy Stadium", kohliChinnaswamy[1] + " runs off " + kohliChinnaswamy[0] + " balls"]],
];

let failed = 0;
CHECKS.forEach(function (check) {
    const question = check[0];
    const expected = check[1];
    const answer = chatbot.answerQuestion(question, facts);
    const missing = expected.filter(function (text) { return answer.text.indexOf(text) < 0; });
    if (missing.length === 0) {
        console.log("PASS  " + question);
    } else {
        failed += 1;
        console.log("FAIL  " + question + "\n      missing: " + JSON.stringify(missing) + "\n      answer : " + answer.text);
    }
});

// Every answer that gives numbers must say where they come from
// (the out-of-scope and "which one?" answers give no numbers, so they need no source).
const NO_NUMBERS = ["Who won the Orange Cap in 2007?", "What is the weather in Mumbai tomorrow?",
                    "Who scored the most runs in a test match?", "Sharma stats"];
CHECKS.filter(function (check) { return NO_NUMBERS.indexOf(check[0]) < 0; }).forEach(function (check) {
    const answer = chatbot.answerQuestion(check[0], facts);
    if (!answer.source) {
        failed += 1;
        console.log("FAIL  no source given for: " + check[0]);
    }
});

// The pitch answer must say the data has no pitch reports (in its source line).
if (chatbot.answerQuestion("How does the pitch at Chepauk play?", facts).source.indexOf("no pitch reports") < 0) {
    failed += 1;
    console.log("FAIL  the pitch answer must say there are no pitch reports in the data");
}

if (failed > 0) {
    console.log("\n" + failed + " chatbot check(s) failed.");
    process.exit(1);
}
console.log("\nAll " + CHECKS.length + " chatbot checks passed (and every numeric answer names its source).");
