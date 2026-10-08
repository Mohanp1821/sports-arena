#!/bin/bash
# =============================================================================
# git_commands.sh: every Git command used to build this repository, in order
# =============================================================================
# This file documents how the Git history of Sports Arena was created.
# Read it as a guide; each command has a comment explaining what it does.
#
# To practise, copy-paste ONE STEP at a time into Git Bash / Terminal,
# inside the project folder.
# =============================================================================


# -----------------------------------------------------------------------------
# STEP 1: create the repository and say who you are
# -----------------------------------------------------------------------------
git init -b main                       # make this folder a Git repository; first branch = "main"
git config user.name "Mohanp1821"      # name recorded on every commit
git config user.email "you@example.com"   # use your GitHub email
git status                             # show new/changed files (all "untracked" now)


# -----------------------------------------------------------------------------
# STEP 2: build the core project on main, one small commit at a time
# -----------------------------------------------------------------------------
# git add    = put files in the "staging area" (the list for the next commit)
# git commit = save a snapshot of the staged files, with a message saying WHY

git add .gitignore LICENSE requirements.txt
git commit -m "Add project setup: gitignore, licence and pinned requirements"

git add data/raw/ data/README.md src/verify_data.py
git commit -m "Add raw IPL dataset, data README and checksum script"

git add src/prepare_data.py data/processed/
git commit -m "Add data cleaning script"

git add src/metrics.py
git commit -m "Add batting, bowling and team metrics"

git add tests/test_facts.py
git commit -m "Add fact-check tests against official IPL records"


# -----------------------------------------------------------------------------
# STEP 3: charts and dashboard on a FEATURE BRANCH
# -----------------------------------------------------------------------------
# A branch is a separate line of work, so experiments never break main.
git branch feature/visualizations      # create the branch
git branch                             # list branches (* = current)
git checkout feature/visualizations    # switch to it

git add src/analysis.py
git commit -m "Add player form, team comparison and top performer charts"

git add outputs/*.png
git commit -m "Add generated chart images"

git add notebooks/ipl_analysis.ipynb
git commit -m "Add Colab analysis notebook"

git add src/build_report.py outputs/index.html
git commit -m "Add HTML dashboard of results"

# Bring the finished feature into main.
# --no-ff keeps a merge commit, so the branch stays visible in the history graph.
git checkout main
git merge --no-ff feature/visualizations -m "Merge feature/visualizations into main"


# -----------------------------------------------------------------------------
# STEP 4: containerisation on a second FEATURE BRANCH
# -----------------------------------------------------------------------------
git checkout -b feature/docker         # create AND switch in one command

git add Dockerfile docker-compose.yml .dockerignore
git commit -m "Add Dockerfile and two-service Compose architecture"

git checkout main
git merge --no-ff feature/docker -m "Merge feature/docker into main"


# -----------------------------------------------------------------------------
# STEP 5: run script, documentation, release
# -----------------------------------------------------------------------------
git add run_all.sh
git commit -m "Add one-command run script"

git add README.md CONTRIBUTING.md docs/
git commit -m "Add README, documentation and contributing guide"

git add git_commands.sh
git commit -m "Add Git command walkthrough"

git log --oneline --graph --all        # show the history as a graph (both branches visible)

git tag -a v1.0 -m "Sports Arena v1.0"   # label this version as release 1.0


# -----------------------------------------------------------------------------
# STEP 6: publish to GitHub
# -----------------------------------------------------------------------------
# First create an EMPTY repository called "sports-arena" on github.com.
git remote add origin git@github.com:Mohanp1821/sports-arena.git   # link to GitHub, named "origin"
git push -u origin main                          # upload main; -u remembers the link
git push origin feature/visualizations feature/docker   # upload the feature branches
git push origin --tags                           # upload the v1.0 tag


# -----------------------------------------------------------------------------
# STEP 7: a new feature after release: 2020 predictions (third FEATURE BRANCH)
# -----------------------------------------------------------------------------
git checkout -b feature/predictions

git add src/predict.py
git commit -m "Add 2020 champion and award predictions with backtest"

git add tests/test_facts.py
git commit -m "Add fact checks for champions and prediction maths"

git add run_all.sh Dockerfile src/build_report.py outputs/
git commit -m "Add predictions to the pipeline and dashboard"

git add notebooks/ipl_analysis.ipynb README.md docs/ git_commands.sh
git commit -m "Document the prediction method in the notebook and docs"

git checkout main
git merge --no-ff feature/predictions -m "Merge feature/predictions into main"
git tag -a v1.1 -m "Sports Arena v1.1: 2020 predictions"

git push origin main feature/predictions   # upload main and the new branch
git push origin v1.1                       # upload the new tag

# A small fix straight on main (no branch needed for a one-file change):
git add src/build_report.py outputs/index.html
git commit -m "Show prediction charts at the top of the dashboard with a section menu"
git push


# -----------------------------------------------------------------------------
# STEP 8: make the dashboard interactive (fourth FEATURE BRANCH)
# -----------------------------------------------------------------------------
git checkout -b feature/interactive-dashboard

git add src/dashboard_explorer.js src/build_report.py outputs/index.html
git commit -m "Add interactive season, team and player filters to the dashboard"

git add tests/test_facts.py
git commit -m "Check the interactive dashboard data against metrics"

git add README.md docs/ git_commands.sh
git commit -m "Document the interactive dashboard"

git checkout main
git merge --no-ff feature/interactive-dashboard -m "Merge feature/interactive-dashboard into main"
git tag -a v1.2 -m "Sports Arena v1.2: interactive dashboard"
git push origin main feature/interactive-dashboard
git push origin v1.2


# -----------------------------------------------------------------------------
# STEP 9: check the 2020 prediction against the real results (on main)
# -----------------------------------------------------------------------------
git add src/predict.py src/build_report.py outputs/
git commit -m "Compare the 2020 prediction with the official results"

git add README.md docs/ git_commands.sh
git commit -m "Document the 2020 check and the tested Docker setup"

git push


# -----------------------------------------------------------------------------
# STEP 10: the 2008-2026 version, one commit per phase on a feature branch
# -----------------------------------------------------------------------------
git checkout -b feature/ipl-2008-2026 origin/main     # start from the latest GitHub version

git add -A
git commit -m "Switch the pipeline to the merged 2008-2026 dataset"          # phase 1: data layer
git add -A
git commit -m "Add analyst views, charts and a match centre to the dashboard" # phase 2
git add -A
git commit -m "Add Model B and compare both 2027 prediction models"          # phase 3
git add -A
git commit -m "Add the Ask Sports Arena chatbot with an optional local-LLM mode"   # phase 4
git add -A
git commit -m "Update the docs, notebook and guide for 2008-2026"            # phase 5

# Phases 6-10 (pitch and player fit, the redesigned site with player, ground and
# team pages, and name links) were committed the same way.

# After review (all fact checks passed): merge into main and mark the release.
git fetch origin                                     # get the latest GitHub version
git checkout -B main origin/main                     # make local main match GitHub's main
git merge --no-ff feature/ipl-2008-2026 -m "Merge feature/ipl-2008-2026 into main"
git tag -a v2.0 -m "Sports Arena v2.0: IPL 2008-2026, two 2027 models, chatbot"
git push origin main feature/ipl-2008-2026 v2.0      # upload main, the branch and the tag


# -----------------------------------------------------------------------------
# EVERYDAY COMMANDS (after the project is on GitHub)
# -----------------------------------------------------------------------------
# git status                          what changed?
# git diff                            exactly which lines changed
# git add -A                          stage everything
# git commit -m "Describe the change" save a snapshot
# git push                            upload to GitHub
# git pull                            download the latest from GitHub
# git checkout -b feature/new-idea    start a new feature branch
