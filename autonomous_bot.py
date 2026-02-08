import os
import json
import re
import requests
from github import Github
from git import Repo

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

gh = Github(GITHUB_TOKEN)
with open(os.environ['GITHUB_EVENT_PATH']) as f:
    event = json.load(f)

repo_name = event['repository']['full_name']
repo = gh.get_repo(repo_name)
local_path = "/tmp/repo"

# Clone repo to local workspace
Repo.clone_from(repo.clone_url.replace("https://", f"https://{GITHUB_TOKEN}@"), local_path)

BOT_TAG = "@joe-gemini"
# gemini-2.5-flash since it's my base model
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Detect mention (allow @joe-gemini, joe-gemini, or replies to bot)
def is_mentioned(comment, bot_user_login):
    text = comment.get('body', '').lower()
    
    # Check for text mentions
    if "@joe-gemini" in text or "joe-gemini" in text:
        return True
    
    # Check if it's a direct reply to the bot (GitHub UI reply)
    # Note: GitHub webhooks provide 'in_reply_to_id' for PR review comments, 
    # but for issue comments, we might need to check if we are the parent.
    # However, a simpler heuristic for "quoting" is checking if the body contains the bot's previous text
    # or if the user is replying to a thread started by the bot.
    # Since we can't easily check threading for every event without more API calls,
    # we'll stick to text matching + maybe checking if the comment starts with > (quote) 
    # and we were the last commenter? No, that's too active.
    
    # Actually, for PR review comments, 'in_reply_to_id' exists. 
    # For issue comments, effective "replying" usually involves quoting or tagging.
    # If the user quotes the bot but doesn't tag, the text usually contains ">"
    
    return False # Placeholder - logic moved to main for context access

# ... (fetch_memory and other functions remain same) ...



# Read PR diff to understand code changes
def get_pr_diff(pr_number):
    try:
        pr = repo.get_pull(pr_number)
        files_changed = []
        for file in pr.get_files():
            files_changed.append({
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "patch": file.patch[:2000] if file.patch else ""  # Limit patch size
            })
        return {
            "title": pr.title,
            "body": pr.body or "",
            "files": files_changed[:10]  # Limit to 10 files
        }
    except Exception as e:
        print(f"PR diff error: {e}")
        return None

# Read file content from repo
def read_file_content(file_path):
    try:
        content = repo.get_contents(file_path)
        return content.decoded_content.decode('utf-8')[:5000]  # Limit size
    except Exception as e:
        print(f"File read error for {file_path}: {e}")
        return None

# Query Gemini API (correct endpoint and auth)
def query_gemini(prompt, context="", max_retries=2):
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"""You are an autonomous GitHub bot called @joe-gemini.
You help maintain this repository by analyzing issues, reviewing PRs, and generating code fixes.

Context:
{context}

Request:
{prompt}

Instructions:
1. Be concise but partial to technical detail.
2. If writing code, include full file context where necessary or clearly marked complete replacements.
3. Think step-by-step."""
            }]
        }],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 16384
        }
    }
    
    for attempt in range(max_retries + 1):
        try:
            r = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json=payload,
                headers=headers,
                timeout=30
            )
            r.raise_for_status()
            result = r.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            if attempt == max_retries:
                print(f"Gemini API error after {max_retries + 1} attempts: {e}")
                return None
            print(f"Gemini API attempt {attempt + 1} failed, retrying...")
    return None

# Ask Gemini for code changes in structured format
def query_gemini_for_code(prompt, context=""):
    code_prompt = f"""{prompt}

IMPORTANT: If you need to suggest file changes, respond with a JSON block like this:
```json
{{
  "explanation": "Brief explanation of changes",
  "files": {{
    "path/to/file.py": "full file content here",
    "another/file.js": "full file content here"
  }}
}}
```

If no code changes are needed, just respond normally without JSON."""
    
    return query_gemini(code_prompt, context)

# Extract JSON from LLM response (handles markdown code blocks)
def extract_json_from_response(text):
    if not text:
        return None
    
    # Try to find JSON in code blocks
    json_patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
        r'\{[\s\S]*"files"[\s\S]*\}'
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    return None

# Commit changes to new branch
def commit_changes(branch_name, file_changes, commit_message):
    try:
        repo_local = Repo(local_path)
        
        # Configure Git Identity (Uses the account associated with the token)
        try:
            user = gh.get_user()
            # Use authenticated user's details, fallback to generic if missing
            name = user.name or user.login
            email = user.email or f"{user.id}+{user.login}@users.noreply.github.com"
            
            repo_local.config_writer().set_value("user", "name", name).release()
            repo_local.config_writer().set_value("user", "email", email).release()
        except Exception as e:
            print(f"Warning: Could not set custom git identity: {e}")
            # Fallback is standard git config or Actions bot
            
        repo_local.git.checkout('-b', branch_name)
        
        for path, content in file_changes.items():
            full_path = os.path.join(local_path, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            repo_local.git.add(path)
        
        repo_local.index.commit(commit_message)
        origin = repo_local.remote(name='origin')
        origin.push(refspec=f"{branch_name}:{branch_name}")
        return True
    except Exception as e:
        print(f"Commit error: {e}")
        return False

# Post comment to issue/PR
def post_comment(issue_number, body):
    try:
        issue = repo.get_issue(number=issue_number)
        issue.create_comment(body)
        return True
    except Exception as e:
        print(f"Comment error: {e}")
        return False

# Helper: Estimate token count (very rough approximation)
def get_token_count(text):
    return len(text) // 4

# Get repository structure as a tree string
def get_repo_structure(path, max_depth=2, current_depth=0):
    if current_depth > max_depth:
        return ""
    
    structure = ""
    try:
        # Sort so directories come first, then files
        items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x))
        
        for item in items:
            if item.startswith('.'): # Skip hidden files/dirs
                continue
                
            full_path = os.path.join(path, item)
            is_dir = os.path.isdir(full_path)
            
            indent = "  " * current_depth
            marker = "📁 " if is_dir else "📄 "
            structure += f"{indent}{marker}{item}\n"
            
            if is_dir:
                structure += get_repo_structure(full_path, max_depth, current_depth + 1)
    except Exception as e:
        structure += f"Error listing {path}: {e}\n"
        
    return structure

# Read relevant configuration files
def read_relevant_configs():
    config_files = [
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "package-lock.json",
        "requirements.txt",
        "pyproject.toml",
        "vercel.json",
        "next.config.js",
        "vite.config.ts",
        "vite.config.js",
        "tsconfig.json"
    ]
    
    context = "Configuration Files:\n"
    found = False
    
    for relative_path in config_files:
        full_path = os.path.join(local_path, relative_path)
        if os.path.exists(full_path):
            found = True
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Truncate large config files (especially lockfiles)
                    if len(content) > 5000:
                         context += f"\n--- {relative_path} (Truncated first 5000 chars) ---\n{content[:5000]}\n...\n"
                    else:
                        context += f"\n--- {relative_path} ---\n{content}\n"
            except Exception as e:
                context += f"\n--- {relative_path} (Error reading) ---\n{e}\n"
    
    if not found:
        return ""
    return context

# Step 1: Analyze Context and Request More Files
def get_context_expansion_files(prompt, initial_context):
    analysis_prompt = f"""You are an expert developer.
    
User Request: {prompt}

Current Context:
{initial_context}

Task: Determine if you need to read any specific files from the repository to answer the request accurately or to check syntax/conventions (e.g. checking for pnpm vs npm, verify existing patterns).
If you need to read files, list them as a JSON array of file paths.
If you have enough information, return an empty array [].

Response Format:
```json
[
  "path/to/file1.ext",
  "path/to/file2.ext"
]
```
Do not explain. Just return the JSON.
"""
    response = query_gemini(analysis_prompt, initial_context)
    return extract_json_from_response(response)

# Main logic
def main():
    comment_body = event.get('comment', {}).get('body', '')
    issue_number = event.get('issue', {}).get('number')
    pr_number = event.get('pull_request', {}).get('number') or event.get('issue', {}).get('pull_request', {}).get('number') if event.get('issue', {}).get('pull_request') else None
    
    # Only respond if mentioned
    if not (issue_number or pr_number) or not is_mentioned(comment_body):
        print("Bot not mentioned or no issue/PR context. Exiting.")
        return
    
    target_number = issue_number or pr_number
    
    # Identify bot user
    bot_user = gh.get_user()
    bot_login = bot_user.login.lower()
    
    # Check if mentioned or replying
    mentioned = False
    if "@joe-gemini" in comment_body.lower() or "joe-gemini" in comment_body.lower():
        mentioned = True
    else:
        # Check if replying to bot's last comment (heuristic: last comment on issue was from bot)
        try:
            issue = repo.get_issue(number=target_number)
            comments = list(issue.get_comments())
            # If there are comments and the one before this (last one excluding current webhook payload usually) was bot
            # Note: The webhook payload comment is already created on GitHub usually.
            # Let's check the last comment in the thread.
            if comments:
                last_comment = comments[-1]
                # If the current comment is the last one, check the one before it
                if str(last_comment.id) == str(event.get('comment', {}).get('id')):
                    if len(comments) > 1 and comments[-2].user.login.lower() == bot_login:
                        mentioned = True
                elif last_comment.user.login.lower() == bot_login:
                     # This case handles race conditions or if webhook fires before list update
                    mentioned = True
        except Exception as e:
            print(f"Error checking thread history: {e}")

    if not (issue_number or pr_number) or not mentioned:
        print("Bot not mentioned and not complying to reply logic. Exiting.")
        return

    # Build initial context with Repo Structure and Configs
    print("Building repository context...")
    repo_structure = get_repo_structure(local_path)
    config_context = read_relevant_configs()
    
    memory = fetch_memory(target_number)
    pr_context = ""
    
    if pr_number:
        pr_diff = get_pr_diff(pr_number)
        if pr_diff:
            pr_context = f"""
PR Title: {pr_diff['title']}
PR Description: {pr_diff['body']}
Files Changed:
{json.dumps(pr_diff['files'], indent=2)[:3000]}
"""
    
    base_context = f"""
Repository Structure (Root):
{repo_structure}

{config_context}

Memory from previous interactions:
{memory}

{pr_context}
"""

    # Step 1: Context Expansion - Check if we need more files
    print("Step 1: Analyzing request for missing context...")
    needed_files = get_context_expansion_files(comment_body, base_context)
    
    expanded_context = base_context
    if needed_files and isinstance(needed_files, list) and len(needed_files) > 0:
        print(f"Bot requested to read: {needed_files}")
        post_comment(target_number, f"👀 I need to check some files to be sure: `{', '.join(needed_files[:5])}`...")
        
        file_contents = ""
        for file_path in needed_files[:5]: # Limit to 5 files to save tokens/time
             # Secure path check to prevent traversing up
             if ".." in file_path or file_path.startswith("/"):
                 continue
                 
             content = read_file_content(file_path)
             if content:
                 file_contents += f"\n--- {file_path} ---\n{content}\n"
        
        expanded_context += f"\n\nRequested File Contents:\n{file_contents}"
    
    # Step 2: Generate plan with full context
    print("Step 2: Generating plan...")
    plan_prompt = f"User request: {comment_body}\n\nAnalyze this request and create a plan to address it. \nIMPORTANT: Verify your plan against the 'Configuration Files' and 'Repository Structure' provided."
    plan = query_gemini(plan_prompt, expanded_context)
    
    if not plan:
        post_comment(target_number, "❌ Sorry, I couldn't process your request. Please try again.")
        return
    
    post_comment(target_number, f"🤖 **Agent Plan:**\n\n{plan}")
    
    # Step 3: Check if code changes are needed
    if any(keyword in comment_body.lower() for keyword in ['fix', 'change', 'update', 'add', 'remove', 'refactor', 'implement']):
        code_prompt = f"Based on the plan above, generate the necessary code changes.\n\nPlan: {plan}\n\nEnsure you use the correct syntax and dependencies found in the context."
        code_response = query_gemini_for_code(code_prompt, expanded_context)
        
        if code_response:
            parsed = extract_json_from_response(code_response)
            
            if parsed and 'files' in parsed:
                branch_name = f"joe-gemini/fix-{target_number}-{int(__import__('time').time())}"
                
                if commit_changes(branch_name, parsed['files'], f"[joe-gemini] {parsed.get('explanation', 'Automated fix')}"):
                    post_comment(target_number, f"✅ Committed changes to branch `{branch_name}`\n\n**Changes:**\n{parsed.get('explanation', 'See branch for details')}")
                else:
                    post_comment(target_number, f"⚠️ Generated changes but failed to commit. Here's what I planned:\n\n{code_response[:2000]}")
            else:
                # No structured changes, just post the response
                post_comment(target_number, f"💡 **Analysis:**\n\n{code_response[:2000]}")

if __name__ == "__main__":
    main()
