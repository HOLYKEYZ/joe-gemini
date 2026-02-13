
import os
import json
import re
import requests
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
from github import Github, GithubIntegration

app = Flask(__name__)

# Config
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
APP_ID = os.environ.get('APP_ID')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '').replace('\\n', '\n')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')
# GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Helper: Verify Webhook Signature
def verify_signature(req):
    signature = req.headers.get('X-Hub-Signature-256')
    if not signature or not WEBHOOK_SECRET:
        return False
    
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    
    mac = hmac.new(WEBHOOK_SECRET.encode(), req.data, hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

# Helper: Get GitHub Client for Installation
def get_github_client(installation_id):
    integration = GithubIntegration(APP_ID, PRIVATE_KEY)
    token = integration.get_access_token(installation_id).token
    return Github(token)

# Helper: Get Bot Login
BOT_LOGIN_CACHE = None
def get_bot_login():
    global BOT_LOGIN_CACHE
    if BOT_LOGIN_CACHE:
        return BOT_LOGIN_CACHE
    try:
        integration = GithubIntegration(APP_ID, PRIVATE_KEY)
        BOT_LOGIN_CACHE = f"{integration.get_app().slug}[bot]"
        return BOT_LOGIN_CACHE
    except Exception as e:
        print(f"Error getting bot login: {e}")
        return "joe-gemini-bot[bot]"

# ... (imports remain) ...
# ... (config remain) ...

# ... (verify_signature helper remains) ...

# ... (imports) ...

# ... (config) ...

# ... (verify_signature) ...

# ... (get_github_client) ...

# ... (get_github_client helper remains) ...

def fetch_memory(repo, issue_number, bot_login):
    """Read bot's previous comments and extract [MEMORY] blocks."""
    try:
        issue = repo.get_issue(number=issue_number)
        memory_data = {
            "files_read": [],
            "context_summary": ""
        }
        
        for comment in issue.get_comments():
            if comment.user.login.lower() == bot_login.lower():
                body = comment.body
                # Look for hidden memory block
                memory_match = re.search(r'<!-- \[MEMORY\]([\s\S]*?)\[/MEMORY\] -->', body)
                if memory_match:
                    try:
                        mem = json.loads(memory_match.group(1).strip())
                        if 'files_read' in mem:
                            memory_data['files_read'].extend(mem['files_read'])
                        if 'context_summary' in mem:
                            memory_data['context_summary'] = mem['context_summary']
                    except json.JSONDecodeError:
                        pass
        
        # Deduplicate files
        memory_data['files_read'] = list(set(memory_data['files_read']))
        return memory_data
    except Exception as e:
        print(f"Memory fetch error: {e}")
        return {"files_read": [], "context_summary": ""}

def format_memory_block(data):
    """Format memory data as a hidden HTML comment."""
    return f"\n\n<!-- [MEMORY]{json.dumps(data)}[/MEMORY] -->"

def get_repo_structure(repo, path="", max_depth=1, current_depth=0):
    """Get repository file structure via GitHub API (single level to avoid timeout)."""
    if current_depth > max_depth:
        return ""
    
    structure = ""
    try:
        contents = repo.get_contents(path)
        # Sort: dirs first, then files
        items = sorted(contents, key=lambda x: (x.type != 'dir', x.name))
        
        for item in items[:30]:  # Limit to 30 items to avoid timeout
            if item.name.startswith('.'):
                continue
            
            indent = "  " * current_depth
            marker = "📁 " if item.type == 'dir' else "📄 "
            structure += f"{indent}{marker}{item.name}\n"
            
            # Only go 1 level deep to avoid timeout
            if item.type == 'dir' and current_depth < max_depth:
                structure += get_repo_structure(repo, item.path, max_depth, current_depth + 1)
    except Exception as e:
        print(f"Repo structure error: {e}")
        structure = f"Error: {e}\n"
    
    return structure

def read_file_content(repo, file_path):
    """Read file content from repo."""
    try:
        content = repo.get_contents(file_path)
        return content.decoded_content.decode('utf-8')[:5000]  # Limit size
    except Exception as e:
        print(f"File read error for {file_path}: {e}")
        return None

def get_context_expansion_files(prompt, initial_context):
    """Ask Gemini what files it needs to read."""
    analysis_prompt = f"""You are an expert developer.

User Request: {prompt}

Current Context:
{initial_context}

Task: Determine if you need to read any specific files from the repository to answer accurately or verify syntax/conventions.
If you need files, list them as a JSON array. If you have enough info, return [].

Response Format:
```json
["path/to/file1.ext", "path/to/file2.ext"]
```
Do not explain. Just return the JSON.
"""
    response = query_gemini(analysis_prompt, initial_context)
    return extract_json_from_response(response)


def extract_json_from_response(text):
    if not text: return None
    json_patterns = [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```', r'\{[\s\S]*"files"[\s\S]*\}']
    for pattern in json_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                return json.loads(json_str)
            except: continue
    return None

def commit_changes_via_api(repo, branch_name, file_changes, commit_message):
    try:
        sb = repo.get_branch(repo.default_branch)
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=sb.commit.sha)
        for path, content in file_changes.items():
            try:
                contents = repo.get_contents(path, ref=branch_name)
                repo.update_file(path, commit_message, content, contents.sha, branch=branch_name)
            except:
                repo.create_file(path, commit_message, content, branch=branch_name)
        return True
    except Exception as e:
        print(f"API Commit Error: {e}")
        return False

def query_gemini(prompt, context="", temperature=0.4):
    headers = {'Content-Type': 'application/json'}
    final_prompt = f"""You are an autonomous GitHub bot called @joe-gemini.
Context: {context}
Request: {prompt}
Instructions:
1. Be concise and summarize your thoughts into ONE comment if possible.
2. Do not reply to yourself unless absolutely necessary.
3. If writing code, return full files.
4. Focus on responding to other users if they reply to you."""
    
    payload = {
        "contents": [{"parts": [{"text": final_prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 16000}
    }
    try:
        r = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload, headers=headers)
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

def query_gemini_for_code(prompt, context=""):
    code_prompt = f"""{prompt}
IMPORTANT: If suggestions involve file changes, respond options:
1. Normal text.
2. JSON for auto-apply:
```json
{{ "explanation": "...", "files": {{ "path/to/file": "content" }} }}
```"""
    return query_gemini(code_prompt, context)

@app.route('/', methods=['GET'])
# ...
def home():
    return "Joe-Gemini Vercel Bot is Active! 🚀", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if not verify_signature(request):
        return jsonify({'error': 'Invalid signature'}), 401
    
    event_type = request.headers.get('X-GitHub-Event')
    payload = request.json
    
    if event_type == 'issue_comment' and payload.get('action') == 'created':
        handle_issue_comment(payload)
    elif event_type == 'pull_request' and payload.get('action') in ['opened', 'synchronize']:
         handle_pr(payload)

    return jsonify({'status': 'ok'})

def handle_pr(payload):
    """Handle PR opened/synchronized events."""
    bot_login = get_bot_login()
    # Don't review own PRs (if we ever create them)
    if payload.get('pull_request', {}).get('user', {}).get('login') == bot_login:
        return

    try:
        installation = payload.get('installation')
        if not installation:
            print("No installation in payload")
            return
        

        gh = get_github_client(installation['id'])
        repo_info = payload['repository']
        repo = gh.get_repo(repo_info['full_name'])
        pr_number = payload['pull_request']['number']
        pr = repo.get_pull(pr_number)
        bot_login = get_bot_login()
        
        # DEBUG: Verify we reached here
        print(f"DEBUG: Processing PR #{pr_number}")
        
        # Fetch memory
        try:
            memory = fetch_memory(repo, pr_number, bot_login)
            files_already_read = memory.get('files_read', [])
        except Exception as e:
            print(f"Memory fetch failed: {e}")
            files_already_read = []
        
        # Get repo structure
        try:
            repo_structure = get_repo_structure(repo)
        except Exception as e:
            print(f"Structure fetch failed: {e}")
            repo_structure = "(Structure fetch failed)"
        
        # Get the Diff
        diff_url = pr.diff_url
        diff_content = requests.get(diff_url).text
        
        if len(diff_content) > 60000:
            diff_content = diff_content[:60000] + "\n...(truncated)..."
        
        base_context = f"""
Repository Structure:
{repo_structure}

Files already read (from memory):
{', '.join(files_already_read) if files_already_read else 'None'}

PR Title: {pr.title}
PR Description: {pr.body}

Diff:
{diff_content}
"""
        
        # Step 1: Ask what files to read
        needed_files = get_context_expansion_files(f"Review this PR: {pr.title}", base_context)
        
        expanded_context = base_context
        new_files_read = []
        
        if needed_files and isinstance(needed_files, list):
            files_to_read = [f for f in needed_files if f not in files_already_read][:5]
            
            if files_to_read:
                file_contents = ""
                for file_path in files_to_read:
                    if ".." in file_path or file_path.startswith("/"):
                        continue
                    content = read_file_content(repo, file_path)
                    if content:
                        file_contents += f"\n--- {file_path} ---\n{content}\n"
                        new_files_read.append(file_path)
                
                expanded_context += f"\n\nFile Contents:\n{file_contents}"
        
        # Step 2: Generate review
        prompt = f"""You are an expert code reviewer. Review this PR.
Identify bugs, security issues, or improvements. Be concise.

Context:
{expanded_context}
"""
        review = query_gemini(prompt)
        
        if review:
            all_files = files_already_read + new_files_read
            memory_block = format_memory_block({"files_read": all_files})
            pr.create_issue_comment(f"🤖 **Automated Code Review**\n\n{review}{memory_block}")
            
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"Error reviewing PR: {err_msg}")
        try:
            # Try to report error to user if possible
            if 'pr' in locals():
                pr.create_issue_comment(f"⚠️ **Bot Error**: Something went wrong.\n\n```\n{err_msg}\n```")
        except:
            pass

def handle_issue_comment(payload):
    installation = payload.get('installation')
    if not installation: return

    gh = get_github_client(installation['id'])
    repo_info = payload['repository']
    repo = gh.get_repo(repo_info['full_name'])
    comment = payload['comment']
    issue_number = payload['issue']['number']
    
    bot_login = get_bot_login()
    
    # CRITICAL: Do not reply to self!
    if comment.get('user', {}).get('login') == bot_login:
        return

    body = comment.get('body', '').lower()
    
    # Check mentions & replies
    mentioned = False
    if "joe-gemini" in body:
        # Only set mentioned=True if it's NOT the bot talking to itself
        mentioned = True
    else:
        try:
            issue = repo.get_issue(number=issue_number)
            comments = list(issue.get_comments())
            if len(comments) > 1:
                last_comment = comments[-1]
                prev_comment = comments[-2]
                
                # If this comment replies to a bot comment
                if str(last_comment.id) == str(comment.get('id')):
                    if prev_comment.user.login == bot_login:
                         mentioned = True
        except: pass
    
    if not mentioned: return

    try:
        issue = repo.get_issue(number=issue_number)
        
        # 1. Fetch Memory with [MEMORY] blocks
        memory = fetch_memory(repo, issue_number, bot_login)
        files_already_read = memory.get('files_read', [])
        
        # 2. Get repo structure
        repo_structure = get_repo_structure(repo)
        
        # 3. PR Context if applicable
        pr_context = ""
        if issue.pull_request:
            try:
                pr = repo.get_pull(issue_number)
                diff_content = requests.get(pr.diff_url).text[:20000]
                pr_context = f"PR Title: {pr.title}\nDiff:\n{diff_content}"
            except: pass
    
        base_context = f"""
Repository Structure:
{repo_structure}

Files already read (from memory):
{', '.join(files_already_read) if files_already_read else 'None'}

{pr_context}
"""
        
        # 4. Ask Gemini what files it needs
        needed_files = get_context_expansion_files(comment['body'], base_context)
        
        expanded_context = base_context
        new_files_read = []
        
        if needed_files and isinstance(needed_files, list):
            files_to_read = [f for f in needed_files if f not in files_already_read][:5]
            
            if files_to_read:
                issue.create_comment(f"👀 Checking: `{', '.join(files_to_read)}`...")
                
                file_contents = ""
                for file_path in files_to_read:
                    if ".." in file_path or file_path.startswith("/"):
                        continue
                    content = read_file_content(repo, file_path)
                    if content:
                        file_contents += f"\n--- {file_path} ---\n{content}\n"
                        new_files_read.append(file_path)
                
                expanded_context += f"\n\nFile Contents:\n{file_contents}"
        
        # 5. Generate response
        plan = query_gemini(f"User Request: {comment['body']}\n\nRespond using the context provided.", expanded_context)
        if not plan: return
        
        all_files = files_already_read + new_files_read
        memory_block = format_memory_block({"files_read": all_files})
        
        issue.create_comment(f"🤖 **Response:**\n{plan}{memory_block}")
        
        # 6. Code changes?
        if any(k in body for k in ['fix', 'code', 'implement', 'change']):
            code = query_gemini_for_code(f"Generate code for: {plan}", expanded_context)
            parsed = extract_json_from_response(code)
            
            if parsed and 'files' in parsed:
                branch = f"joe-gemini/fix-{issue_number}-{int(time.time())}"
                if commit_changes_via_api(repo, branch, parsed['files'], f"Fix: {parsed.get('explanation', 'Automated fix')}"):
                    msg = f"✅ Committed to branch `{branch}`.\n\nChanges: {parsed.get('explanation')}"
                    issue.create_comment(msg)
                    try:
                        repo.create_pull(title=f"Fix for #{issue_number}", body=f"Automated fix.\n{parsed.get('explanation')}", head=branch, base=repo.default_branch)
                        issue.create_comment(f"🚀 Created PR for `{branch}`")
                    except Exception as e:
                        print(f"PR Creation error: {e}")
            else:
                issue.create_comment(f"💡 **Thoughts:**\n{code}")
    except Exception as e:
        print(f"Error processing comment: {e}")

if __name__ == '__main__':
    app.run(port=3000)


