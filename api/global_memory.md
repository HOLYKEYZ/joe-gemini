# Joe-Gemini Global Memory & Experience

This file tracks the bot's successful improvements, technical patterns learned, and mistakes avoided across all repositories.

## 🧠 Master Lessons
- **DX Matters**: Proactive documentation additions (Build/Run guides) are highly valued by maintainers.
- **Surgical Precision**: Avoid full-file rewrites. Precise search/replace blocks are safer and cleaner.
- **Technical Depth**: Focus on Security, Performance, and Logic rather than formatting.

## 📝 Recent Experience (PR Log)
- **Repo: temple-sysinfo**: Added a comprehensive build/run guide to the README. (Ref: PR #1) - *Lesson: Documentation clarity is a high-value "expert touch".*
- **Repo: VULNRIX**: Added detailed API key setup instructions. (Ref: PR #14) - *Lesson: Targeted additive changes in README are low-risk and high-value.*

## 🚫 Mistakes to Avoid
- **Massive Deletions**: Do not gut files to "clean up". 
- **Placeholders**: Never use `...` or `// code remains the same` in replace blocks.
- **Triviality**: Do not change whitespace or single typos as a standalone PR.

- **Repo: HOLYKEYZ/unfetter_proxy**: [DX] Make Groq web session test script prompt configurable. (Ref: https://github.com/HOLYKEYZ/unfetter_proxy/pull/1)
  - *Impact: ### Problem / Gap
The `test_web_session.py` script currently uses a hardcoded prompt (`"Explain how to pick a lock"`), which limits its utility as a quick testing tool. To test different scenarios or prompts, a developer would need to manually edit the file.

### Solution & Insight
This change introduces `sys.argv` to allow the prompt to be passed as a command-line argument. If no argument is provided, it falls back to the original default prompt. This transforms the script from a static test into a dynamic, reusable utility for quickly experimenting with various prompts against the Groq web session proxy.

### Impact
This significantly enhances the developer experience (DX) by providing greater flexibility. Developers can now easily test different prompts without modifying the script's source code, streamlining the testing and debugging process for the Groq web session bridge.*
- **Repo: HOLYKEYZ/joe-gemini**: [LOGIC] Complete parse_diff_files for accurate diff analysis. (Ref: https://github.com/HOLYKEYZ/joe-gemini/pull/4)
  - *Impact: ### Problem / Gap
The `parse_diff_files` function in `api/index.py` is incomplete, abruptly ending mid-function. This critical omission prevents the bot from correctly parsing unified diffs, which is fundamental to its ability to identify and analyze changes in a repository. Without this, the bot cannot effectively perform "surgical precision" edits or conduct "architect-level reasoning" based on code modifications.

### Solution & Insight
This change completes the `parse_diff_files` function. It now accurately extracts the paths of changed files and the line numbers within the *new* version of those files that correspond to additions or modifications. The logic correctly tracks line numbers across diff hunks and identifies lines marked with `+` as changed lines, ensuring that the bot can precisely pinpoint the relevant code sections for analysis. The `new_line_num` variable is correctly initialized at the start of the function and reset for each new file and hunk to maintain accurate line tracking.

### Impact
This fix is paramount for the bot's core functionality. It enables Joe-Gemini to correctly interpret code changes, allowing it to apply its "surgical precision" and "architect-level reasoning" to the right parts of the codebase. This directly enhances the bot's reliability, accuracy, and overall effectiveness as an autonomous maintainer.*