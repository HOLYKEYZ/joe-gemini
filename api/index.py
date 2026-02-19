
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
def get_installation_token(installation_id):
    integration = GithubIntegration(APP_ID, PRIVATE_KEY)
    return integration.get_access_token(installation_id).token

def get_github_client(installation_id):
    token = get_installation_token(installation_id)
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

def parse_diff_files(diff_text):
    """Parse unified diff to extract changed files with their line ranges."""
    files = []
    current_file = None
    current_lines = []
    
    for line in diff_text.split('\n'):
        # New file in diff
        if line.startswith('+++ b/'):
            if current_file:
                files.append({'path': current_file, 'lines': current_lines})
            current_file = line[6:]  # Remove '+++ b/'
            current_lines = []
        # Hunk header: @@ -old,count +new,count @@
        elif line.startswith('@@') and current_file:
            import re as _re
            match = _re.search(r'\+(\d+)(?:,(\d+))?', line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) else 1
                current_lines.append({'start': start, 'end': start + count - 1})
    
    if current_file:
        files.append({'path': current_file, 'lines': current_lines})
    
    return files

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
def home():
    return "Joe-Gemini Vercel Bot is Active! 🚀", 200

@app.route('/api/cron', methods=['GET'])
def cron_job():
    """Hourly autonomous improvement job."""
    # Security: Verify Vercel Cron header
    if request.headers.get('Authorization') != f"Bearer {os.environ.get('CRON_SECRET')}" and \
       request.headers.get('x-vercel-cron') != '1':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Initialize GitHub client
        # Note: We need an installation ID. For simplicity, we'll try to get the first available installation.
        # Ideally, this should iterate all installations or be configured.
        integration = GithubIntegration(APP_ID, PRIVATE_KEY)
        start_installations = integration.get_installations()
        
        # Pick the first installation (or random one)
        if start_installations.totalCount == 0:
            return jsonify({'status': 'No installations found'}), 200
             
        installation = start_installations[0] # Just grab first one for now
        gh = Github(integration.get_access_token(installation.id).token)
        
        # Get all repos accessible
        repos = list(gh.get_installation(installation.id).get_repos())
        if not repos:
            return jsonify({'status': 'No repos found'}), 200
        
        # Pick a random repo
        import random
        target_repo = random.choice(repos)
        print(f"Targeting repo: {target_repo.full_name}")
        
        # Don't touch forked repos or archived ones unless specified (autonomy rule: focus on user's own code)
        if target_repo.fork or target_repo.archived:
            return jsonify({'status': f'Skipped {target_repo.full_name} (fork/archived)'}), 200

        # Analysis Phase: Get file structure and key files
        structure = get_repo_structure(target_repo, max_depth=2)
        readme = read_file_content(target_repo, "README.md") or ""
        
        # Ask Gemini for an improvement
        prompt = f"""You are an autonomous maintainer for this repo: {target_repo.full_name}.
Goal: Find ONE small, safe, high-value improvement.
Codebase Structure:
{structure}

README:
{readme[:2000]}

Task: Suggest a specific file to read to find a concrete improvement (refactor, doc fix, bug fix).
Return only the file path in JSON: ["path/to/file.ext"]
"""
        initial_files = get_context_expansion_files("Find improvement", prompt)
        file_content = ""
        target_path = ""
        
        if initial_files and len(initial_files) > 0:
            target_path = initial_files[0]
            file_content = read_file_content(target_repo, target_path)
        
        if not file_content:
            return jsonify({'status': 'Could not identify target file'}), 200

        # Generate Improvement
        improvement_prompt = f"""Repository: {target_repo.full_name}
File: {target_path}
Content:
{file_content}

Task: Propose a meaningful, safe code improvement.
Examples: formatting fixes, adding types, improving docstrings, fixing potential bugs.
Do NOT break existing logic.

Respond with strict JSON:
{{
  "title": "Short PR Title",
  "body": "Detailed PR description explaining the change.",
  "branch_name": "bot/improvement-{int(time.time())}",
  "files": {{
      "{target_path}": "FULL NEW CONTENT OF THE FILE"
  }}
}}
"""
        raw_response = query_gemini(improvement_prompt, temperature=0.2)
        improvement_data = extract_json_from_response(raw_response)
        
        if improvement_data and 'files' in improvement_data:
            # Create Branch & PR
            branch = improvement_data.get('branch_name', f'bot/fix-{int(time.time())}')
            title = improvement_data.get('title', 'Automated improvement')
            body = improvement_data.get('body', 'Automated changes by Joe-Gemini.')
            
            # Commit
            success = commit_changes_via_api(target_repo, branch, improvement_data['files'], title)
            
            if success:
                # Open PR
                pr = target_repo.create_pull(
                    title=title,
                    body=f"{body}\n\nGenerated autonomously by Joe-Gemini 🤖",
                    head=branch,
                    base=target_repo.default_branch
                )
                return jsonify({'status': 'PR Created', 'url': pr.html_url}), 200
            else:
                return jsonify({'error': 'Commit failed'}), 500
        
        return jsonify({'status': 'No improvement generated'}), 200
        
    except Exception as e:
        print(f"Cron error: {e}")
        return jsonify({'error': str(e)}), 500

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
        
        # Parse diff for file/line info
        diff_files = parse_diff_files(diff_content)
        file_line_info = ""
        for df in diff_files:
            ranges = ", ".join([f"L{r['start']}-{r['end']}" for r in df['lines']])
            file_line_info += f"  {df['path']}: {ranges}\n"
        
        # Step 2: Generate review with committable suggestions
        prompt = f"""You are an expert Principal Software Engineer. 
Perform a RIGOROUS technical review of this PR.

Changed files and line ranges:
{file_line_info}

Context:
{expanded_context}

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{{
  "summary": "Full technical report (Markdown). Analyze architecture, security, performance, race conditions, and error handling. Be critical and thorough.",
  "suggestions": [
    {{
      "file": "path/to/file.ext",
      "line": 42,
      "original": "the exact original line(s) from the diff",
      "replacement": "your suggested replacement code",
      "reason": "Detailed justification (e.g. complexity reduction, security fix)"
    }}
  ]
}}

Rules:
1. SUMMARY MUST BE DEEP. Not just "looks good". Analyze impact.
2. SUGGESTIONS are OPTIONAL. Only provide if necessary/high-value.
3. "line" must be the END line number in the new file (right side of diff)
4. "original" must be the EXACT code currently at that line
5. "replacement" is your suggested fix
6. Do NOT suggest formatting/style changes unless critical.
7. Do NOT wrap in markdown code blocks, return raw JSON only
"""
        review_raw = query_gemini(prompt, temperature=0.2)
        
        all_files = files_already_read + new_files_read
        memory_block = format_memory_block({"files_read": all_files})
        
        # Try to parse as structured suggestions
        suggestions_data = None
        if review_raw:
            try:
                # Try direct JSON parse first
                suggestions_data = json.loads(review_raw)
            except json.JSONDecodeError:
                # Try extracting from markdown code block
                suggestions_data = extract_json_from_response(review_raw)
        
        if suggestions_data and isinstance(suggestions_data, dict) and 'suggestions' in suggestions_data:
            summary = suggestions_data.get('summary', 'Code review complete.')
            suggestions = suggestions_data['suggestions'] or []
            
            # Build inline review comments
            review_comments = []
            for s in suggestions[:5]:  # Max 5
                file_path = s.get('file', '')
                line_num = s.get('line', 0)
                original = s.get('original', '')
                replacement = s.get('replacement', '')
                reason = s.get('reason', '')
                
                if not file_path or not line_num or not replacement:
                    continue
                
                # Build committable suggestion body
                body = f"{reason}\n\n```suggestion\n{replacement}\n```"
                
                review_comments.append({
                    'path': file_path,
                    'line': int(line_num),
                    'body': body
                })
            
            if review_comments:
                try:
                    # Use GitHub REST API directly for line+side support
                    token = get_installation_token(installation['id'])
                    api_url = f"https://api.github.com/repos/{repo_info['full_name']}/pulls/{pr_number}/reviews"
                    review_payload = {
                        'body': f"🤖 **Automated Code Review**\n\n{summary}{memory_block}",
                        'event': 'COMMENT',
                        'comments': [{
                            'path': c['path'],
                            'line': c['line'],
                            'side': 'RIGHT',
                            'body': c['body']
                        } for c in review_comments]
                    }
                    api_headers = {
                        'Authorization': f'token {token}',
                        'Accept': 'application/vnd.github.v3+json'
                    }
                    resp = requests.post(api_url, json=review_payload, headers=api_headers)
                    if resp.status_code in [200, 201]:
                        print(f"Posted review with {len(review_comments)} inline suggestions")
                    else:
                        print(f"Review API failed: {resp.status_code} {resp.text}")
                        raise Exception(f"API {resp.status_code}")
                except Exception as review_err:
                    print(f"Review API exception: {review_err}")
                    # Fallback: post as regular comment with suggestion blocks
                    fallback = f"🤖 **Automated Code Review**\n\n{summary}\n\n"
                    for s in suggestions[:5]:
                        fallback += f"**{s.get('file', '')}** (L{s.get('line', '?')}): {s.get('reason', '')}\n"
                        fallback += f"```suggestion\n{s.get('replacement', '')}\n```\n\n"
                    pr.create_issue_comment(f"{fallback}{memory_block}")
            else:
                # No inline suggestions, just post summary
                pr.create_issue_comment(f"🤖 **Automated Code Review**\n\n{summary}{memory_block}")
        elif review_raw:
            # Gemini didn't return structured JSON, post as plain review
            pr.create_issue_comment(f"🤖 **Automated Code Review**\n\n{review_raw}{memory_block}")
            
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
    
    # CRITICAL SECURITY: Ignore own comments (Double Check)
    # 1. Login check
    if comment.get('user', {}).get('login') == bot_login:
        return
    # 2. Type check (Ignore ALL bots, including gemini-code-assist)
    if comment.get('user', {}).get('type') == 'Bot':
        return
    # 3. Content check (Our bot ALWAYS adds [MEMORY] blocks)
    if '<!-- [memory]' in body or '<!-- [memory]' in comment.get('body', ''):
        return

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

            # Do NOT post 'Thoughts'. If code gen fails or is just text, it's usually duplicate of the plan.
            # else:
            #     issue.create_comment(f"💡 **Thoughts:**\n{code}")
    except Exception as e:
        print(f"Error processing comment: {e}")

if __name__ == '__main__':
    app.run(port=3000)


