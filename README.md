# Joe-Gemini 🤖

Joe-Gemini is an autonomous GitHub bot powered by **Google Gemini 2.5 Flash**. It lives in your repository, reviews code, fixes bugs, and improves your project autonomously.

## ✨ Features
- **Smart Reviews**: Analyzes PRs and Issues using advanced AI.
- **Autonomous Fixes**: Can write code, create branches, and open PRs for you.
- **Context Aware**: Remembers previous interactions in the thread.
- **Conversation Capable**: Chat with it by tagging `@joe-gemini` (or just mentioning `joe-gemini`).
- **Custom Identity**: Uses your own avatar/account for commits (if configured).

## 🚀 Deployment (Vercel)
This bot is designed to be deployed as a **GitHub App** hosted on **Vercel**.

1.  **Create GitHub App**: Point Webhook URL to `https://your-vercel-app.vercel.app/webhook`.
2.  **Deploy to Vercel**: `vercel --prod`.
3.  **Environment Variables**:
    *   `GEMINI_API_KEY`: Google Gemini API Key.
    *   `APP_ID`: GitHub App ID.
    *   `PRIVATE_KEY`: GitHub App Private Key.
    *   `WEBHOOK_SECRET`: GitHub App Webhook Secret.
4.  **Install**: Click "Install" on your GitHub App page to add it to any repository.

## �️ Tech Stack
-   **Python 3.9+**
-   **Flask**: Web server for webhooks.
-   **Google Gemini 2.5 Flash**: AI Intelligence.
-   **PyGithub**: GitHub API interaction.
-   **Vercel**: Serverless hosting.

## ⚠️ Note
This bot was built for my own personal usage to automate my workflows, but anyone is welcome to use it, deploy it, or fork it for their own projects! Happy coding! 🚀
