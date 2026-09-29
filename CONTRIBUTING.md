# Contributing to Sports Arena

Thank you for helping! Please keep all code **simple and commented**: this is a learning project.

## Steps

1. **Fork** the repository on GitHub and **clone** your fork.
2. Create a branch for your change:
   ```bash
   git checkout -b feature/my-new-chart
   ```
3. Make your change, then run the full pipeline (it includes the fact checks):
   ```bash
   ./run_all.sh
   ```
4. Commit with a clear message, e.g. `Add head-to-head chart`, and push your branch.
5. Open a **Pull Request** that explains what you changed and why.

## Code style

- One function = one job, with a docstring.
- Prefer clear step-by-step pandas (`groupby`, `merge`) over clever one-liners.
- Every chart has a title, axis labels and a legend (when there are 2+ series), and is saved to `outputs/`.
- Explain every cricket formula in a comment.
- Never edit files in `data/raw/`. Put cleaning steps in `src/prepare_data.py`.
- If you change a function in `src/`, update the matching cell in `notebooks/ipl_analysis.ipynb`.

## Reporting problems

Open a GitHub Issue with what you ran, what you expected, and what happened.
