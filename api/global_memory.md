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
- **Own Repo Caution**: When editing mayo itself, be EXTRA careful. One bad edit can brick the entire bot.
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
- **Repo: HOLYKEYZ**: [LOGIC] Fix truncated URL for GitHub top languages statistics image. (Ref: https://github.com/HOLYKEYZ/HOLYKEYZ/pull/1) - *Status: REJECTED - Joseph closed this Comment: 'why are u deleting unnecessary thingssss, this is rubbish, mayo'*
- **Repo: Joseph-Portfolio**: [DOCS] Enhance README for Better Developer Experience. (Ref: https://github.com/HOLYKEYZ/Joseph-Portfolio/pull/1) - *Status: MERGED - Joseph approved! Comment: '[vc]: #zikQGlJc/WxuUecN8PvZvhQ7hcZzWrfVTtbv4ER1C5k=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0'*
- **Joseph's Feedback on Joseph-Portfolio#1**: "mayo , this one is good" — Mayo acknowledged and responded.
- **Repo: HADNX**: [DX] Complete EXTERNAL TOOLS Section in README. (Ref: https://github.com/HOLYKEYZ/HADNX/pull/11) - *Status: REJECTED - Joseph closed this Comment: '[vc]: #O/X/frOObjos0mhcL1Dk8j0d2ozL5adveGe+cnH3Ixs=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0'*
- **Joseph's Feedback on HADNX#11**: "hii, mayo, reviewer, executor is deleting everything, i cant merge this shii
u gotta review diff, wth is this man" — Mayo acknowledged and responded.
- **Repo: IntellectSafe**: [DX] Correct Getting Started Instructions in README.md. (Ref: https://github.com/HOLYKEYZ/IntellectSafe/pull/8) - *Status: REJECTED - Joseph closed this Comment: '[vc]: #QM0n6H8iRitDxiBScpaI/q2vk1RKFK7I73TXWOefFG8=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0'*
- **Joseph's Feedback on IntellectSafe#8**: "mayo , I am currently investigating exactly why the Executor caused this mass deletion, and how it bypassed my recent li" — Mayo acknowledged and responded.
- **Repo: VULNRIX**: [DX] Clarify .env Setup in README. (Ref: https://github.com/HOLYKEYZ/VULNRIX/pull/15) - *Status: MERGED - Joseph approved!*
- **Repo: ModelFang**: [DX] Standardize Google Gemini API Key Environment Variable. (Ref: https://github.com/HOLYKEYZ/ModelFang/pull/4) - *Status: REJECTED - Joseph closed this Comment: '[vc]: #uSvL7PbT/r+1DmrsC/87GM0skuPWK1gPtYsG2pKRxnQ=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0'*
- **Repo: model-unfetter**: [DX] Enhance README with Development Environment Setup. (Ref: https://github.com/HOLYKEYZ/model-unfetter/pull/1) - *Status: MERGED - Joseph approved!*
- **REJECTED by Reviewer**: Executor attempted a full README rewrite via a single search/replace, violating the 50% deletion rule by replacing 100% of the search block.
- **REJECTED by Reviewer**: Executor attempted full README rewrite (100% deletion of search block) which violates Size Guard, and search block also had mismatch.
- **REJECTED by Reviewer**: Executor's search block did not exactly match original content due to missing blank lines between items.
- **Repo: private-storage**: [DOCS] Enhance README for Private Storage Repository. (Ref: https://github.com/HOLYKEYZ/private-storage/pull/1) - *Status: MERGED - Joseph approved! Comment: 'good'*
- **REJECTED by Reviewer**: Executor's proposed edits for package.json dependencies were rejected because the diff preview showed 'NO CHANGES', indicating search blocks were not found despite appearing correct.
- **REJECTED by Reviewer**: Executor's seemingly correct search blocks failed to produce a diff, indicating a deeper system mismatch or an issue with the diff preview generation.
- **REJECTED by Reviewer**: Executor's search block failed to match due to missing indentation, resulting in 'NO CHANGES' in the diff preview. Emphasize exact match including whitespace.
- **Repo: temple-sysinfo**: [LOGIC] Upgrade Memory Info Retrieval for Accuracy. (Ref: https://github.com/HOLYKEYZ/temple-sysinfo/pull/2) - *Status: MERGED - Joseph approved! Comment: 'good , mayo'*
- **Joseph's Feedback on temple-sysinfo#2**: "good , mayo" — Mayo acknowledged and responded.
- **Repo: micro-edit**: [LOGIC] Implement Missing Navigation Key Functionality. (Ref: https://github.com/HOLYKEYZ/micro-edit/pull/3) - *Status: MERGED - Joseph approved!*
- **REJECTED by Reviewer**: Executor's search block was 16 lines, exceeding the 15-line limit. Rejected for splitting.
- **Repo: unfetter_proxy**: [DX] Enhance test_web_session.py with Configurable Groq Model. (Ref: https://github.com/HOLYKEYZ/unfetter_proxy/pull/4) - *Status: MERGED - Joseph approved!*
- **REJECTED by Reviewer**: Executor's search blocks appeared correct but failed to match according to the diff preview, indicating subtle mismatch.
- **REJECTED by Reviewer**: Executor's search blocks for README.md updates failed to match due to heading level and missing blank line, leading to 'NO CHANGES'. Emphasize exact match including whitespace.
- **Repo: Alexcathe**: [DX] Update README.md for accurate gradient description. (Ref: https://github.com/HOLYKEYZ/Alexcathe/pull/3) - *Status: MERGED - Joseph approved! Comment: '[vc]: #O/DILtdHUpxvgJQQEtAOpptlAAUZOddoVfKcAgNr1iY=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0'*
- **REJECTED by Reviewer**: Executor's search block for README.md image replacement failed to match, resulting in 'NO CHANGES' in diff preview. Emphasize exact match.
- **Repo: HOLYKEYZ**: [DX] Standardize Supabase Badge in Tech Arsenal. (Ref: https://github.com/HOLYKEYZ/HOLYKEYZ/pull/2) - *Status: PENDING REVIEW*
- **REJECTED by Reviewer**: Executor attempted full README rewrite via single search/replace, violating 50% deletion rule by replacing 100% of the search block.
- **Repo: Joseph-Portfolio**: [DOCS] Enhance README for Better Developer Experience. (Ref: https://github.com/HOLYKEYZ/Joseph-Portfolio/pull/2) - *Status: PENDING REVIEW*
- **Joseph's Feedback on Joseph-Portfolio#2**: "hi , mayo 
did the reviewer not tell the executor to edit real code files? " — Mayo acknowledged and responded.