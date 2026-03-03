# Mayo 🦾🤖
### The Autonomous Triple-AI Maintainer

Mayo is a **Self-Improving Autonomous Maintenance Engine** integrated directly into your GitHub ecosystem. It uses a **Triple-AI Pipeline** — three specialized AI models working in concert — to produce high-value, validated code improvements across all your repositories.

---

## 🧬 Triple-AI Pipeline

Every improvement goes through 3 AI models before it becomes a PR:

```mermaid
flowchart TD
    A["⏰ Hourly Cron Trigger"] --> R0["🛡️ REVIEWER: Audit pending PR statuses"]
    R0 --> B["🔭 SCANNER: Deep codebase analysis"]
    B -->|"Text-only summary + plan"| C["⚡ EXECUTOR: Generate surgical edits"]
    C -->|"Proposed search/replace JSON"| D["🛡️ REVIEWER: Validate edits"]
    D -->|"✅ APPROVE"| E["📦 Create PR"]
    D -->|"🔧 CORRECT"| F["Apply corrected edits → Create PR"]
    D -->|"❌ REJECT + feedback"| C2["⚡ EXECUTOR: Retry with feedback"]
    C2 --> D2["🛡️ REVIEWER: Validate retry"]
    D2 -->|"✅ APPROVE"| E
    D2 -->|"❌ REJECT"| SKIP["⏭️ Skip, save failure to memory"]
    E --> MEM["🧠 All 3 AIs save lessons to Global Memory"]
    F --> MEM
```

| Role | Model | Purpose |
|---|---|---|
| 🔭 **Scanner** | Gemini 2.5 Flash | Reads full codebase → text-only analysis (zero compaction risk) |
| ⚡ **Executor** | Kimi K2 (Groq) | Receives plan → produces surgical search/replace edits |
| 🛡️ **Reviewer** | Gemini 2.5 Flash | Validates edits, corrects mistakes, audits PR review history |

---

## 🧠 Cross-Repo Global Memory

Unlike standard AI bots, Mayo has **persistent memory**:
- Tracks successes, failures, and "lessons learned" across all repositories.
- Insights from Repo A directly improve work on Repo B.
- The Reviewer audits real PR states (merged/closed/commented) and updates memory automatically.

---

## 🩺 Surgical Precision

The Executor uses a **Search/Replace block system** (max 10 lines per block). This guarantees:
- **100% preservation** of your original code structure.
- **Zero hallucination** of unrelated code.
- **Validated PRs** — every edit is reviewed by the Reviewer before creation.

---

## 🏗️ Analysis Depth

The Scanner performs a rigorous multi-layered analysis:
1. **Security**: Injections, hardcoded secrets, missing validation
2. **Logic**: Edge cases, null checks, error handling
3. **DX**: Missing READMEs, build guides, setup docs
4. **Performance**: Redundant calls, memory leaks
5. **Consistency**: Naming, patterns, style
6. **Creative**: Proactive "expert touches"

---

## ⚙️ Setup & Deployment

### Environment Variables
| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Scanner (Gemini A) |
| `GEMINI2_API_KEY` | Reviewer (Gemini B) |
| `GROK_API_KEY` | Executor (Kimi K2 via Groq) |
| `APP_ID` / `PRIVATE_KEY` | GitHub App authentication |
| `CRON_SECRET` | Hourly trigger authorization |

### Deployment
1. Deploy as a **GitHub App** on **Vercel**.
2. Point webhook to `https://your-app.vercel.app/webhook`.
3. Install on your repositories.
4. The hourly cron (`.github/workflows/cron.yml`) handles the rest.

---

## ℹ️ Author
Created by **Joseph (@HOLYKEYZ)**. Advanced agentic engineering for autonomous codebase maintenance.

Happy coding! 🚀 (v3.0 — Triple-AI)
