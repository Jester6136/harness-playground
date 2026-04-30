---
name: summarize_codebase
description: Walk through a project directory and produce a structured summary covering purpose, architecture, and key files.
---

# Summarize a codebase

Follow these steps in order:

1. **List the top-level directory** with `ls` using the absolute path from your working directory (e.g. if working directory is `/home/user/project`, call `ls` with path `/home/user/project`).
2. **Read the README** if one exists (README.md, README.rst, etc.).
3. **Identify the entry point**: look for `main.py`, `index.ts`, `cmd/main.go`, `package.json` scripts, etc.
4. **Read the entry point** to understand how the app starts.
5. **Identify the main package/module directory** (often named after the project) and list it.
6. **Read 2-3 key files** that look most central based on naming and the README's mention.
7. **Produce a summary** with these sections:
   - **Purpose**: one sentence on what this project does.
   - **Architecture**: bullet list of the main modules and what each owns.
   - **Entry point**: how to run it.
   - **Notable design decisions**: anything surprising or non-obvious.

Stop calling tools once you have enough to fill those sections — do not try to read every file.
Keep the final summary under 300 words.
