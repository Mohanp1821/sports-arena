# Viva Questions and Answers

Short answers to the questions most likely to come up in the Q&A. Each answer points to the file you can open to
show it. Numbers quoted here come from the pipeline's outputs (`outputs/` and the dashboard).

## A. Data and reproducibility

**Q1. How can someone else get exactly your results?**
(1) The data is committed and `src/verify_data.py` checks SHA-256 checksums; (2) `requirements.txt` pins exact
library versions; (3) `prepare_data.py` is deterministic (fixed sort order; gzip without a time stamp); (4) every
random step uses a fixed seed (42); (5) Docker gives the same environment everywhere. `tests/test_facts.py` and
`tests/test_chatbot.js` then confirm the results.

**Q2. Where does the 2008-2026 data come from?**
Kaggle's IPL 2008-2019 files (CC BY-NC-SA 4.0) and Cricsheet's ball-by-ball JSON for 2020-2026 (data version 1.2.0),
merged into one set with the Kaggle column names: 1,243 matches, 295,729 balls, 19 seasons. `data/README.md`.

**Q3. Why are the merged files "never edited"?**
So there is one source of truth that anyone can verify by checksum. All fixes happen in `prepare_data.py`, which
writes `data/processed/`, so every change is written in code with a reason, and can be undone.

**Q4. How did you get the merged CSV files?** (`src/recover_merged_data.py`)
They were published as an interactive explorer page that stores every ball as compact JSON. The script rebuilds
the CSV rows exactly as the page's "Raw CSV rows" tab does. We checked the result: 2008-2017 is identical to the
original Kaggle files, and all 38 official Orange and Purple Caps match.

**Q5. Why does the data keep "Delhi Daredevils" for 2015 but your team stats say "Delhi Capitals"?**
Team names stay as they were that season, for display. A `franchise` column gives today's name, so team records
run across renames (Daredevils → Capitals, Kings XI Punjab → Punjab Kings, RCB Bangalore → Bengaluru).
Deccan Chargers is a different franchise from Sunrisers Hyderabad (different owners), so it is not merged.

**Q6. What is the player-name map, and why was it needed?** (`src/build_name_map.py`)
Kaggle wrote some 2018-19 debutants differently from Cricsheet: "S Gill" vs "Shubman Gill", "J Archer" vs "JC Archer".
Without a fix, Shubman Gill's career would be split. We paired each Kaggle match with the Cricsheet match (same date
and teams), lined up the balls of each over, and took a majority vote of **Cricsheet player IDs**, keyed by
(season, team, name). Result: 71 fixes, each winning 99.7-100% of its votes.

**Q7. How did you avoid merging two different people with the same name?**
Three ways: the vote key includes the team ("Ankit Sharma" at Delhi 2018 is Abhishek Sharma, but at Rajasthan 2018
he is a real Ankit Sharma); we use Cricsheet's unique IDs, not names; and we never rename to a name that two IDs
share (two players are called "Harmeet Singh", so Kaggle's "Harmeet Singh (2)" is kept). `tests/test_facts.py` checks these traps.

**Q8. How did you standardise grounds?**
Remove a ", City" ending (Cricsheet's "Wankhede Stadium, Mumbai" → "Wankhede Stadium"), then rename grounds that changed
name (Feroz Shah Kotla → Arun Jaitley Stadium, Motera → Narendra Modi Stadium, Sheikh Zayed → Zayed Cricket Stadium,
Mullanpur/New Chandigarh → Maharaja Yadavindra Singh Stadium, the long Lucknow name → Ekana). One city per ground.
Result: 36 grounds; Wankhede spans 2008-2026 under one name (tested).

**Q9. How do you know which matches were playoffs?**
The last 3 matches of 2008-2009 and the last 4 of every later season. We checked this rule against the stage written
in the Cricsheet files: 74 of 74 playoff matches matched.

## B. Cricket formulas and analysis

**Q10. Why don't wides count as balls faced, and why are byes not in economy?**
A wide is out of the batter's reach, so they did not "face" it, and it is not a legal ball. Byes and leg-byes did not
come off the bat, so the bowler is not charged for them.

**Q11. How do you calculate net run rate in the rebuilt points table?** (`metrics.points_table`)
Runs scored per over minus runs conceded per over, over the league matches. A team bowled out counts its full 20 overs
(the official rule). The rebuilt tables put the 4 real playoff teams in the top 4 in every season from 2009 to 2026.

**Q12. Why does your 2008 points table differ from the official one?**
A Delhi v Kolkata match was abandoned without a ball being bowled, so it is not in the ball-by-ball data: Delhi has
1 point fewer than officially. The dashboard notes this automatically (it sees those teams played 13 games, not 14).

**Q13. How are partnerships built, and how do you know they are right?**
Group the balls by the two batters at the crease (written alphabetically so A&B = B&A); the wicket number is the
wickets that fell before + 1. Check: in every one of the innings, the partnership runs add up exactly to the team total.

**Q14. What is the home fortress index?**
Home win % minus away win %, in percentage points. Sunrisers Hyderabad is highest (+19.7). Punjab Kings has two home
grounds in the list because they moved from Mohali to Mullanpur in 2024.

**Q15. What did the Impact Player rule change?**
Comparing 2020-22 with 2023-26: the average first-innings score rose from 167.0 to 189.7, totals of 200+ from 0.21 to
0.67 per match, and the Powerplay run rate from 7.76 to 9.47; chase success hardly moved (53.6% vs 52.5%).
The 557 substitutions come from Cricsheet's replacement records.

**Q16. How does the chase win-probability model work?**
For every ball of every normal chase we know the runs needed, balls left and wickets left, and whether the chase was
won. Logistic regression learns how these turn into a chance. Example: 60 needed off 60 balls is about 86% with
7 wickets left. The dashboard calculator uses the same learned weights.

**Q17. Why are pace vs spin splits missing?**
The data does not record bowling styles. Guessing them would break the rule that every number is calculated from the
data, so we left them out and said so.

## C. The two prediction models

**Q18. How does Model A predict 2027?** (`src/predict.py`)
Strength = form win % over the last 3 seasons (weights 3, 2, 1). Team A beats team B with chance A ÷ (A + B). The 2027
season is played 10,000 times in the real format, and title chance = seasons won ÷ 10,000.
Result: RCB 22.5%, then Gujarat Titans 13.9% and Sunrisers 13.5%.

**Q19. What is "the real format" with 10 teams?**
Two groups of 5, seeded by titles (then finals reached). A team plays its group twice, the other group once, and its
"row-mate" in the other group a second time: 8 + 5 + 1 = 14 games. Then Qualifier 1 (1st v 2nd), Eliminator (3rd v 4th),
Qualifier 2 and the Final. The test checks 70 league games and 14 per team.

**Q20. How does Model B work?** (`src/predict_ml.py`)
It describes each match with pre-season numbers: Elo difference, last-10 form, head-to-head, ground record, home flag,
squad strength and an Impact Player era flag. Logistic regression and gradient boosting learn from past seasons; their
chances are averaged and fed into the same 10,000-season simulator. Result: RCB 20.7%, Rajasthan 17.0%, Sunrisers 13.0%.

**Q21. What is an Elo rating?**
A rating where every team starts at 1500; after a match the winner gains points and the loser loses them, more for
beating a stronger team (new = old + 20 × (result − expected)). Before each season ratings move a third of the way back
to 1500, because squads change.

**Q22. What is "squad strength", and why does it use last season?**
The sum of the best 11 previous-season impact scores among the players in a squad. Last season, because during a season
we cannot know this season's form yet. For 2027 the squad comes from `data/squads_2027.csv`.

**Q23. Why did you leave the toss out?**
The toss is only known minutes before a match, never before the season. Using it would let the model "see" information
the 2027 prediction cannot have.

**Q24. Why is each match used twice in training?**
As "A v B, did A win?" and "B v A, did B win?". Otherwise the model could learn that "team 1" wins more often. We also
ask the model both ways round and average, so P(A beats B) + P(B beats A) = 1 (tested).

**Q25. What is a walk-forward backtest?**
For each season 2021-2026 we pretend it has not happened: train only on earlier seasons, predict every match and the
title, then compare with what happened. This is how the model would have been used in real life, so it is a fair test.

**Q26. What are accuracy, log loss, Brier score and calibration?**
Accuracy: % of matches where the side given more than 50% won (coin flip 50%). Log loss: average of −log(chance given
to what happened), which punishes confident mistakes (coin flip 0.693). Brier: average of (chance − result)², coin flip
0.25. Calibration: when the model says 60%, does that side win about 60% of the time?

**Q27. Which model was better?**
Model A: 51.2% accuracy, log loss 0.700; Model B: 50.7%, 0.704; coin flip: 50%, 0.693. Neither beat the coin flip's log
loss, and both were over-confident. Model A ranked the real champion 1st in 2026; across 2021-2026 the champion's rank
varied from 1st to 9th for both. The honest conclusion: before a season, T20 matches are close to a coin flip, and the
simpler model was at least as good.

**Q28. Why didn't you tune the models to score better on the backtest?**
Because then the backtest would no longer be a fair test: we would be fitting the test seasons (overfitting), and the
scores would look better than the model really is on 2027.

**Q29. What can't the models know?**
Auctions, trades and releases (edit `data/squads_2027.csv`), injuries, and breakout players: V Suryavanshi scored 252 runs
in 2025 and 776 in 2026 to win the Orange Cap; neither model had him as its top pick before 2026.

## D. Dashboard and chatbot

**Q30. How is the dashboard interactive without a server?**
Python calculates every table and writes it into the page as JSON. Plain JavaScript only looks rows up when a drop-down
changes (any team pair, batter and bowler, ground, phase, season). The page works offline as a file and in Docker.

**Q31. How does "Ask Sports Arena" answer without an AI model?** (`src/chatbot.js`)
It finds the names in the question using alias lists (e.g. "SKY" → SA Yadav, "Kings XI Punjab" → Punjab Kings), decides
the question type from keywords, and fills in an answer **only** from the facts file, adding its source. If a name is
ambiguous ("Sharma") it asks which one; if the question is out of scope it says so and suggests questions.

**Q32. How do you stop the chatbot inventing numbers?**
It has no numbers of its own: every number comes from `outputs/chat_facts.json`, which Python calculated from the data.
`tests/test_chatbot.js` checks 21 questions against the expected facts (e.g. 2016 Orange Cap = V Kohli, 973) and that
every numeric answer names its source.

**Q33. What does the optional local-LLM mode add, and what is RAG?**
`src/chat_server.py` uses retrieval-augmented generation: it picks the 25 fact lines that best match the question and
gives only those to an open-weights model running locally in Ollama, with the instruction to answer only from them.
It phrases answers more naturally, but the facts still come from our data. It is in a Docker Compose profile (`llm`),
so the default setup is unchanged, and the page falls back to offline mode if it is not running.

**Q34. What is the match centre?**
`outputs/match_centre.html`: every match with its scorecard (how each batter got out, the bowling card), an
over-by-over strip and the raw ball rows, using the cleaned names. Rivalry and ground tables link straight to a match.

## E. Tools, Git and Docker

**Q35. What does each Docker Compose service do?**
`pipeline` runs the 8 steps once and writes `./outputs`; `dashboard` serves `./outputs` on port 8080 (read-only) and
starts only if the pipeline succeeded. With the `llm` profile, `ollama` runs the local model and `chat` runs the chat server.

**Q36. Image vs container?**
An image is the built recipe (Python, libraries, Node.js, our code); a container is a running copy of it. All our services
use the image `sports-arena:1.0` (except Ollama's own image).

**Q37. Why `git merge --no-ff` and feature branches?**
Branches keep unfinished work away from `main`. `--no-ff` keeps a merge commit, so the history graph shows each branch.
This version was built on `feature/ipl-2008-2026`, with one commit per phase.

**Q38. Which open-source tools and licences?**
Python (PSF), pandas (BSD-3), NumPy (BSD-3), matplotlib (PSF-based), seaborn (BSD-3), scikit-learn (BSD-3), Node.js (MIT),
Git (GPL-2), Docker Engine (Apache-2.0), Ollama (MIT). Our code is MIT. Kaggle data: CC BY-NC-SA 4.0; Cricsheet's register:
ODC-By 1.0 (and we credit Cricsheet for the match data).

**Q39. Why is the dataset licence separate from your MIT licence?**
We wrote the code, so we choose its licence. We did not create the data; it keeps its publishers' licences, recorded in
`data/README.md`.

**Q40. How did you run Docker on a Mac?**
With Colima (`brew install colima docker docker-compose`, then `colima start`); Docker Desktop works the same way.
