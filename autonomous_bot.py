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

# Detect mention (allow @joe-gemini or just joe-gemini)
def is_mentioned(text):
    text_lower = text.lower()
    return "@joe-gemini" in text_lower or "joe-gemini" in text_lower

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
    
    # Build context
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
    
    full_context = f"""Memory from previous interactions:
{memory}

{pr_context}"""
    
    # Step 1: Generate plan
    plan_prompt = f"User request: {comment_body}\n\nAnalyze this request and create a plan to address it."
    plan = query_gemini(plan_prompt, full_context)
    
    if not plan:
        post_comment(target_number, "❌ Sorry, I couldn't process your request. Please try again.")
        return
    
    post_comment(target_number, f"🤖 **Agent Plan:**\n\n{plan}")
    
    # Step 2: Check if code changes are needed
    if any(keyword in comment_body.lower() for keyword in ['fix', 'change', 'update', 'add', 'remove', 'refactor', 'implement']):
        code_prompt = f"Based on the plan above, generate the necessary code changes.\n\nPlan: {plan}"
        code_response = query_gemini_for_code(code_prompt, full_context)
        
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
