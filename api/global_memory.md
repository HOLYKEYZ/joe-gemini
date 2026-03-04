# mayo Global Memory & Experience

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
- **Repo: micro-edit**: [LOGIC] Complete editorPrompt return statement. (Ref: https://github.com/HOLYKEYZ/micro-edit/pull/1) - *Status: REJECTED - Joseph closed this*
- **Repo: Jo-ayanda-real-estate**: [LOGIC] Complete inquiries array definition. (Ref: https://github.com/HOLYKEYZ/Jo-ayanda-real-estate/pull/1) - *Status: REJECTED - Joseph closed this Comment: '### <span aria-hidden="true">✅</span> Deploy Preview for *nextphaserealestate* r'*
- **Repo: micro-edit**: [LOGIC] Complete editorPrompt functionality and robustness. (Ref: https://github.com/HOLYKEYZ/micro-edit/pull/2) - *Status: REJECTED - Joseph closed this Comment: 'joe-gemini, this is flop'*
- **Repo: unfetter_proxy**: [DX] Improve Web Session Test Prompts for Clarity. (Ref: https://github.com/HOLYKEYZ/unfetter_proxy/pull/2) - *Status: REJECTED - Joseph closed this Comment: 'joe-gemini , u keep doing shits after shits 
this is rubbish!!! 
u wanna delete '*
- **Repo: unfetter_proxy**: [DX] Improve Groq Web Session Test Feedback. (Ref: https://github.com/HOLYKEYZ/unfetter_proxy/pull/3) - *Status: MERGED - Joseph approved!*
- **Repo: Alexcathe**: [DX] Update TypeScript target to ES2020. (Ref: https://github.com/HOLYKEYZ/Alexcathe/pull/2) - *Status: MERGED - Joseph approved! Comment: '[vc]: #Cr0NuEf70RwI3UY1RhYbEJNkhdscHr6JuNUY3lvEsLg=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0'*
- **Repo: ecom-stor**: [DX] Add inline documentation to postcss.config.js plugins. (Ref: https://github.com/HOLYKEYZ/ecom-stor/pull/1) - *Status: MERGED - Joseph approved! Comment: '[vc]: #rnr+551YjaA07lQABHGDprQFSGuQg1w6hrbr4705j20=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0'*
- **Repo: Jo-ayanda-real-estate**: [LOGIC] Complete and expand sample inquiries data. (Ref: https://github.com/HOLYKEYZ/Jo-ayanda-real-estate/pull/2) - *Status: REJECTED - Joseph closed this Comment: '### <span aria-hidden="true">✅</span> Deploy Preview for *nextphaserealestate* r'*
- **Repo: HOLYKEYZ**: [LOGIC] Fix truncated URL for GitHub top languages statistics image. (Ref: https://github.com/HOLYKEYZ/HOLYKEYZ/pull/1) - *Status: PENDING REVIEW*