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
# EVERYDAY COMMANDS (after the project is on GitHub)
# -----------------------------------------------------------------------------
# git status                          what changed?
# git diff                            exactly which lines changed
# git add -A                          stage everything
# git commit -m "Describe the change" save a snapshot
# git push                            upload to GitHub
# git pull                            download the latest from GitHub
# git checkout -b feature/new-idea    start a new feature branch
