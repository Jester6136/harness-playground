---
name: find_secrets
description: Scan a codebase for hardcoded secrets, API keys, and credentials. Reports a triaged list with severity.
---

# Find hardcoded secrets

1. Use `run_bash` to grep for common secret patterns. Run these from the project root:
   - `grep -rEn "(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}" --include='*.py' --include='*.js' --include='*.ts' --include='*.env*' .`
   - `grep -rEn "(AKIA|AIza|ghp_|sk-)[A-Za-z0-9]{16,}" .`
   - Skip noisy dirs: append ` --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=__pycache__`.
2. For each hit, use `read_file` and look at 5-10 lines around the match for context.
3. Triage each finding into one of:
   - **Real secret**: hardcoded value that looks random and high-entropy.
   - **Placeholder**: things like `password = "CHANGEME"`, example docs values, test fixtures.
   - **Variable reference only**: `api_key = os.getenv("API_KEY")` — not a leak.
4. Report findings as a markdown list:
   - `file:line` — short description — **severity** (HIGH / MEDIUM / LOW) — recommendation.

Always include a one-line summary at the top: how many real findings vs. placeholders vs. references.
