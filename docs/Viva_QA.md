# Viva Questions and Answers

Short answers to the questions most likely to come up in the Q&A (2 marks).
Each answer points to the file you can open to show it.

**Q1. How can someone else get exactly your results?** (reproducibility)
Four things: (1) the raw data is committed and `verify_data.py` checks its SHA-256 checksums;
(2) `requirements.txt` pins exact library versions; (3) `prepare_data.py` is deterministic;
(4) Docker gives an identical environment on any computer. Then `tests/test_facts.py` confirms the results.

**Q2. Why don't wides count as balls faced, and why are byes not in economy?**
Cricket rules: a wide is out of the batter's reach, so they didn't "face" it; it isn't a legal ball either.
Byes and leg-byes are runs the bowler didn't give away off the bat, so the ICC excludes them from bowling figures.

**Q3. What was the most important cleaning step?**
The 2018–19 double-counted extras. Without it, Warner's 2019 total was 727 instead of the official 692,
and every run rate and strike rate for those seasons was inflated. We found it by comparing our Orange Cap
numbers with the official records, which shows why fact-checking matters.

**Q4. Why did you rename teams but keep Deccan Chargers separate from Sunrisers Hyderabad?**
Delhi Daredevils → Delhi Capitals is the same franchise with a new name. Deccan Chargers were terminated
and Sunrisers is a new franchise with different owners, so merging them would be wrong.

**Q5. Why use a feature branch and merge instead of committing everything to main?**
Branches isolate unfinished work: main always runs. Merging with `--no-ff` keeps a record in
`git log --graph` of what was developed separately. It's the same workflow teams use with pull requests.

**Q6. Why these metrics? Why not just total runs?**
Totals reward playing more matches. **Average** measures consistency, **strike rate** measures speed.
In T20 speed matters as much as runs, which is why the quadrant chart plots both. For bowlers,
**economy** matters most in T20, because stopping runs is often more valuable than taking wickets.

**Q7. Why is there a minimum number of balls in the top-10 charts?**
Without it, a player who hit 2 sixes off 2 balls would have a strike rate of 600 and top the list.
Minimums (200 balls, 30 overs) make the ranking fair.

**Q8. What does the rolling average show that a normal average doesn't?**
A season average is one number. A 5-innings rolling average shows how form **changes during** the season:
a run of low scores is visible as a dip even if the season average is high.

**Q9. What are the limitations?**
The data ends in 2019 (no Gujarat Titans or Lucknow). There are small differences from official scorecards.
Short player names. Home advantage uses one fixed home ground per team.

**Q10. Why is the dataset license separate from your MIT license?**
We wrote the code, so we can license it as MIT. We did not create the data; it keeps the license its
publisher chose, which is recorded in `data/README.md`.

**Q11. What does each service in your `docker-compose.yml` do?**
`pipeline` builds the image and runs the analysis once (verify → prepare → analysis → tests → predictions → dashboard page),
writing results into the shared `./outputs` folder. `dashboard` reuses the same image and serves `./outputs`
as a website on port 8080. It starts only if `pipeline` finished successfully.

**Q12. What is the difference between an image and a container?**
An **image** is the read-only recipe result (Python + libraries + our code), built from the `Dockerfile`.
A **container** is a running copy of an image. Our two containers, `pipeline` and `dashboard`, both come from the image `sports-arena:1.0`.

**Q13. Why is the dashboard's volume mounted read-only (`:ro`)?**
The web server only needs to read the charts. Read-only means it cannot change or delete results, even by mistake.
This is the principle of least privilege.

**Q14. What is the difference between `git merge --no-ff` and a normal merge?**
A normal (fast-forward) merge just moves `main` forward, so the branch disappears from the history.
`--no-ff` always creates a merge commit, so `git log --graph` shows the work was done on a separate branch.

**Q15. What does `git tag v1.0` do, and why use it?**
A tag is a permanent name for one commit. `v1.0` marks the version that was submitted, so anyone can return to
exactly that code with `git checkout v1.0`, even after later changes.

**Q16. Which open-source tools does the project use, and what are their licences?**
Python (PSF licence), pandas (BSD-3), matplotlib (PSF-based), seaborn (BSD-3), Git (GPL-2), Docker Engine (Apache-2.0).
Our code is MIT; the dataset is CC BY-NC-SA 4.0.

**Q17. How do you predict the 2020 champion?** (`src/predict.py`)
Each team gets a strength = its win % over the last 3 seasons, weighted 3-2-1 so recent form counts most.
Then we play the whole season 10,000 times on the computer: in each match team A wins with chance A ÷ (A + B),
the top 4 go into the IPL playoffs, and we count how often each team wins the final. Chennai won 23.7% of the
simulated seasons, Mumbai 21.2%.

**Q18. Why is the favourite's chance only 23.7%, not 60% or more?**
Even a strong team must first finish in the top 4 and then win two knock-out matches. Every match has some luck,
so the chances multiply down. That is realistic: in 2011–2019 the team with the best form won only 2 of 9 titles.

**Q19. How do you know the predictions are any good?** (the backtest)
For each season 2011–2019 we predicted using only earlier seasons, then compared with the real result.
The champion was picked exactly 2 times out of 9 (random guessing: about 1 in 8) and was in our top 5 in 7 of 9.
Award picks were right less often (Orange Cap 0 of 9), which we report honestly: form does not capture injuries,
auctions or a player changing team role.

**Q20. Why not use machine learning, e.g. scikit-learn?**
With only 12 seasons there are very few examples of "who won the title", so a complex model would overfit.
A weighted average and a simulation are transparent (every number can be checked on paper), need no extra
library, and the fixed random seed (42) makes the results identical on every run.

**Q21. How is your dashboard interactive?** (`src/dashboard_explorer.js`)
In the **Explore** section you choose a season and a team, and the summary cards, the win % chart, the top 10
batters and bowlers, and the match results all update at once. Clicking a bar drills down into that team or
season, and the player search shows any player's season-by-season career. Python (`build_report.py`) writes
the data into the page as JSON; JavaScript filters it, adds it up and redraws the page when a filter changes.

**Q22. Why did you write the interactivity in plain JavaScript instead of Streamlit, Dash or Plotly?**
Those need a running Python server or an internet connection for their libraries. Our page is one HTML file
that works offline, opens by double-click, and is served by the simple `http.server` in Docker without any
change to the architecture. It also keeps the project small and every line explainable.
