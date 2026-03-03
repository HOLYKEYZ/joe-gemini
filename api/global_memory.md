# Joe-Gemini Global Memory & Experience

This file tracks the bot's successful improvements, technical patterns learned, and mistakes avoided across all repositories.

## 🧠 Master Lessons
- **DX Matters**: Proactive documentation additions (Build/Run guides) are highly valued by maintainers.
- **Surgical Precision**: Avoid full-file rewrites. Precise search/replace blocks are safer and cleaner.
- **Technical Depth**: Focus on Security, Performance, and Logic rather than formatting.
- **Size Guard**: Never propose a replacement that deletes more than 50% of the matched search block.

## 📝 Recent Experience (PR Log)
- **Repo: temple-sysinfo**: Added a comprehensive build/run guide to the README. (Ref: PR #1) - *Status: APPROVED - Joseph liked this!*
- **Repo: unfetter_proxy**: [DX] Make Groq web session test script prompt configurable. (Ref: PR #1) - *Status: APPROVED - Joseph liked this!*
- **Repo: joe-gemini**: [LOGIC] Complete parse_diff_files for accurate diff analysis. (Ref: PR #4) - *Status: REJECTED - Deleted 678 lines of core code. Lesson: NEVER propose a search block larger than 10 lines.*

## 🚫 Mistakes to Avoid
- **Massive Deletions**: Do not gut files to "clean up".
- **Placeholders**: Never use `...` or `// code remains the same` in replace blocks.
- **Triviality**: Do not change whitespace or single typos as a standalone PR.
- **Large Search Blocks**: Keep search blocks under 10 lines. Smaller, targeted edits are safer.
- **Own Repo Caution**: When editing joe-gemini itself, be EXTRA careful. One bad edit can brick the entire bot.
- **Repo: micro-edit**: [LOGIC] Complete editorPrompt return statement. (Ref: https://github.com/HOLYKEYZ/micro-edit/pull/1) - *Status: PENDING REVIEW*
- **Repo: Jo-ayanda-real-estate**: [LOGIC] Complete inquiries array definition. (Ref: https://github.com/HOLYKEYZ/Jo-ayanda-real-estate/pull/1) - *Status: PENDING REVIEW*
- **Repo: micro-edit**: [LOGIC] Complete editorPrompt functionality and robustness. (Ref: https://github.com/HOLYKEYZ/micro-edit/pull/2) - *Status: PENDING REVIEW*
- **Repo: unfetter_proxy**: [DX] Improve Web Session Test Prompts for Clarity. (Ref: https://github.com/HOLYKEYZ/unfetter_proxy/pull/2) - *Status: PENDING REVIEW*