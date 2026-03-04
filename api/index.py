
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
GEMINI2_API_KEY = os.environ.get('GEMINI2_API_KEY')
GROK_API_KEY = os.environ.get('GROK_API_KEY')
APP_ID = os.environ.get('APP_ID')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '').replace('\\n', '\n')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

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

def apply_surgical_edits(content, edits):
    """Apply search/replace blocks to content with safety guards."""
    new_content = content
    for edit in edits:
        search = edit.get('search')
        replace = edit.get('replace')
        if search and search in new_content:
            # SAFETY GUARD: Reject edits that delete more than 50% of the search block
            search_lines = len(search.strip().splitlines())
            replace_lines = len(replace.strip().splitlines()) if replace else 0
            if search_lines > 5 and replace_lines < search_lines * 0.5:
                print(f"DEBUG: BLOCKED destructive edit - would delete {search_lines - replace_lines} lines ({search[:60]}...)")
                continue
            new_content = new_content.replace(search, replace, 1)
        else:
            print(f"DEBUG: Search block not found in file: {search[:50]}...")
    return new_content


def query_gemini(prompt, context="", temperature=0.4):
    headers = {'Content-Type': 'application/json'}
    final_prompt = f"""You are an autonomous GitHub bot called @mayo.
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

# === TRIPLE-AI FUNCTIONS ===

def query_gemini_scanner(prompt, temperature=0.2):
    """Scanner AI (Gemini A) — reads codebase, outputs text-only analysis."""
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 8000}
    }
    try:
        r = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload, headers=headers, timeout=25)
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Scanner Error: {e}")
        return None

def query_groq(prompt, temperature=0.1):
    """Executor AI (Kimi K2) — produces surgical code edits via Groq."""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROK_API_KEY}'
    }
    payload = {
        "model": "moonshotai/kimi-k2-instruct-0905",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 8000
    }
    try:
        r = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=25)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Groq/Kimi Error: {e}")
        return None

def query_gemini_reviewer(prompt, temperature=0.1):
    """Reviewer AI (Gemini B) — validates edits, returns verdict JSON."""
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 8000}
    }
    try:
        api_key = GEMINI2_API_KEY or GEMINI_API_KEY
        r = requests.post(f"{GEMINI_API_URL}?key={api_key}", json=payload, headers=headers, timeout=25)
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Reviewer Error: {e}")
        return None

def audit_pending_reviews(gh):
    """Reviewer checks PENDING REVIEW entries in memory and updates with actual PR status."""
    try:
        bot_repo = gh.get_repo(os.environ.get('BOT_REPO_NAME', 'HOLYKEYZ/mayo'))
        memory_file = bot_repo.get_contents("api/global_memory.md")
        memory = memory_file.decoded_content.decode('utf-8')
        
        if 'PENDING REVIEW' not in memory:
            print("DEBUG: No pending reviews to audit")
            return
        
        import re as re_mod
        pending_entries = re_mod.findall(r'\(Ref: (https://github\.com/[^\)]+/pull/\d+)\) - \*Status: PENDING REVIEW\*', memory)
        
        updated_memory = memory
        for pr_url in pending_entries:
            try:
                parts = pr_url.replace('https://github.com/', '').split('/pull/')
                repo_name = parts[0]
                pr_number = int(parts[1])
                
                repo = gh.get_repo(repo_name)
                pr = repo.get_pull(pr_number)
                
                if pr.merged:
                    status = "MERGED - Joseph approved!"
                elif pr.state == 'closed':
                    status = "REJECTED - Joseph closed this"
                elif pr.state == 'open':
                    continue  # Still open, skip
                else:
                    continue
                
                # Check for Joseph's comments
                comments = list(pr.get_issue_comments())
                joseph_comment = ""
                for c in comments:
                    if c.user.login != 'joe-gemini-bot[bot]':
                        joseph_comment = f" Comment: '{c.body[:80]}'"
                        break
                
                updated_memory = updated_memory.replace(
                    f"(Ref: {pr_url}) - *Status: PENDING REVIEW*",
                    f"(Ref: {pr_url}) - *Status: {status}{joseph_comment}*"
                )
                print(f"DEBUG: Updated review status for {pr_url}: {status}")
            except Exception as e:
                print(f"DEBUG: Failed to audit PR {pr_url}: {e}")
        
        # Memory Decay: Keep only the 30 most recent entries. Archive older ones.
        mem_lines = updated_memory.split('\n')
        repo_entries = [i for i, line in enumerate(mem_lines) if line.startswith('- **Repo:')]
        
        if len(repo_entries) > 30:
            cutoff_idx = repo_entries[-30]
            header = mem_lines[0]
            archived_count = len(repo_entries) - 30
            summary_msg = f"\n- *[ARCHIVED] {archived_count} older lessons were archived to preserve focus.*"
            new_lines = [header, summary_msg] + mem_lines[cutoff_idx:]
            updated_memory = '\n'.join(new_lines)

        if updated_memory != memory:
            bot_repo.update_file(
                "api/global_memory.md",
                "feat(memory): audit pending reviews and decay memory",
                updated_memory,
                memory_file.sha
            )
            print("DEBUG: Memory updated with review audits and decay")
    except Exception as e:
        print(f"DEBUG: Failed to audit pending reviews: {e}")

def update_ai_communication_log(gh, ts, scanner_summary, executor_proposal, reviewer_verdict):
    """Append a cycle entry to ai_communication.md and truncate to last 5 cycles."""
    try:
        bot_repo = gh.get_repo("HOLYKEYZ/joe-gemini")
        comm_file = bot_repo.get_contents("api/ai_communication.md")
        old_log = comm_file.decoded_content.decode('utf-8')
        
        entry = (
            f"\n## Cycle {ts}\n"
            f"**Scanner**: {scanner_summary[:300]}\n\n"
            f"**Executor**: {executor_proposal[:200]}\n\n"
            f"**Reviewer**: {reviewer_verdict[:200]}\n\n---\n"
        )
        
        new_log = old_log + entry
        
        # Truncate to last 5 cycles
        cycles = new_log.split('## Cycle ')
        if len(cycles) > 6:  # header + 5 cycles
            new_log = cycles[0] + '## Cycle '.join(cycles[-5:])
        
        bot_repo.update_file(
            "api/ai_communication.md",
            f"feat(comms): log cycle {ts}",
            new_log,
            comm_file.sha
        )
        print("DEBUG: AI communication log updated")
    except Exception as e:
        print(f"DEBUG: Failed to update communication log: {e}")

@app.route('/', methods=['GET'])
def home():
    return "Mayo Vercel Bot is Active! 🚀", 200
@app.route('/status', methods=['GET'])
def get_status():
    """Simple dashboard endpoint to check Mayo's health and memory."""
    try:
        integration = GithubIntegration(APP_ID, PRIVATE_KEY)
        installations = integration.get_installations()
        if not installations or installations.totalCount == 0:
            return jsonify({'error': 'No installations found'})
            
        token = integration.get_access_token(installations[0].id).token
        gh = Github(token)
        bot_repo = gh.get_repo("HOLYKEYZ/joe-gemini")
        
        # Get memory length
        mem_file = bot_repo.get_contents("api/global_memory.md")
        mem_content = mem_file.decoded_content.decode('utf-8')
        mem_lines = len(mem_content.split('\n'))
        
        # Get comms length
        comms_file = bot_repo.get_contents("api/ai_communication.md")
        comms_content = comms_file.decoded_content.decode('utf-8')
        cycles = len(comms_content.split('## Cycle ')) - 1
        
        return jsonify({
            'status': 'Online',
            'bot_name': 'Mayo 🤖',
            'memory_lines': mem_lines,
            'recent_cycles_logged': cycles,
            'uptime_seconds': int(time.time()),
            'excluded_repos': ['Square-farms', 'Jo-ayanda-real-estate', 'Backend-images-app', 'ecom-stor']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cron', methods=['GET'])
def cron_job():
    """Hourly autonomous improvement job — Triple-AI Pipeline."""
    print("DEBUG: Cron triggered — Triple-AI Pipeline")
    # Security: Verify Authorization header
    if request.headers.get('Authorization') != f"Bearer {os.environ.get('CRON_SECRET')}":
        print("DEBUG: Auth failed")
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Initialize GitHub App
        integration = GithubIntegration(APP_ID, PRIVATE_KEY)
        installations = integration.get_installations()
        
        if not installations or installations.totalCount == 0:
            print("DEBUG: No installations found")
            return jsonify({'status': 'No installations found'}), 200
        
        installation = installations[0]
        token = integration.get_access_token(installation.id).token
        gh = Github(token)
        
        # === PHASE 0: REVIEWER AUDITS PENDING REVIEWS ===
        print("DEBUG: Phase 0 — Auditing pending reviews")
        audit_pending_reviews(gh)
        
        # Get all repos via REST API
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        repos_response = requests.get('https://api.github.com/installation/repositories', headers=headers)
        repos_data = repos_response.json()
        repo_names = [r['full_name'] for r in repos_data.get('repositories', [])]
        print(f"DEBUG: Found {len(repo_names)} repos: {repo_names}")
        
        if not repo_names:
            return jsonify({'status': 'No repos found'}), 200
        
        # Fetch Global Memory first for priority/cooldown analysis
        try:
            bot_repo = gh.get_repo(os.environ.get('BOT_REPO_NAME', 'HOLYKEYZ/mayo'))
            memory_file_obj = bot_repo.get_contents("api/global_memory.md")
            global_memory = memory_file_obj.decoded_content.decode('utf-8')
            print(f"DEBUG: Global memory fetched (len: {len(global_memory)})")
        except Exception as e:
            print(f"DEBUG: Failed to fetch global memory: {e}")
            global_memory = "No global memory found. Start with fresh excellence."

        # === REPO SELECTION: Exclusions, Cooldown, Priority ===
        EXCLUDED_REPOS = ['Square-farms', 'Jo-ayanda-real-estate', 'Backend-images-app', 'ecom-stor']
        
        candidates = [r for r in repos_data.get('repositories', []) 
                      if not r.get('fork') and not r.get('archived') 
                      and r.get('name') not in EXCLUDED_REPOS]
        
        if not candidates:
            return jsonify({'status': 'No eligible repos found'}), 200
            
        # Parse last 3 repos from memory for cooldown
        recent_repos = []
        import re as re_mod
        for line in reversed(global_memory.split('\n')):
            match = re_mod.search(r'\*\*Repo: ([^\*]+)\*\*', line)
            if match:
                r_name = match.group(1).strip()
                if r_name not in recent_repos:
                    recent_repos.append(r_name)
                if len(recent_repos) >= 3:
                    break
                    
        # Filter out cooldown repos
        available = [r for r in candidates if r.get('name') not in recent_repos]
        if not available:
            print("DEBUG: All candidates in cooldown. Ignoring cooldown.")
            available = candidates
            
        # Priority Queue: rank by oldest occurrence in memory
        def repo_score(repo):
            return global_memory.rfind(f"**Repo: {repo.get('name')}**")
            
        available.sort(key=repo_score)
        
        # Pick randomly from the top 30% most-needing repos
        import random
        top_k = max(1, len(available) // 3)
        chosen = random.choice(available[:top_k])
        target_repo = gh.get_repo(chosen['full_name'])
        print(f"DEBUG: Targeting repo {target_repo.full_name} (cooldown/priority applied)")

        # Gather codebase context
        structure = get_repo_structure(target_repo, max_depth=2)
        readme_content = read_file_content(target_repo, "README.md") or "(No README found)"
        
        # List source files
        source_files = []
        try:
            contents = target_repo.get_contents("")
            for item in contents:
                if item.type == 'file' and any(item.name.endswith(ext) for ext in ['.py', '.js', '.ts', '.go', '.c', '.cpp', '.h', '.md', '.json']):
                    source_files.append(item.path)
            for dirname in ['src', 'api', 'lib', 'app', 'pages']:
                try:
                    dir_contents = target_repo.get_contents(dirname)
                    for item in dir_contents:
                        if item.type == 'file' and any(item.name.endswith(ext) for ext in ['.py', '.js', '.ts', '.go', '.jsx', '.tsx', '.c', '.cpp', '.h']):
                            source_files.append(item.path)
                except:
                    pass
        except Exception as e:
            print(f"DEBUG: Error listing files: {e}")
        
        if not source_files:
            if readme_content != "(No README found)":
                source_files = ["README.md"]
            else:
                return jsonify({'status': 'No source files found'}), 200
        
        # Multi-file support: Pick up to 3 files
        import random
        random.shuffle(source_files)
        target_paths = [sf.path if hasattr(sf, 'path') else sf for sf in source_files[:3]]
        
        file_contents = ""
        for tp in target_paths:
            content = read_file_content(target_repo, tp)
            if content:
                file_contents += f"\n--- {tp} ---\n{content}\n"
        
        if not file_contents:
            print("DEBUG: Could not read target files")
            return jsonify({'status': 'Could not identify target files'}), 200

        ts = int(time.time())
        target_path_display = ", ".join(target_paths)

        # === PHASE 1: SCANNER (Gemini A) ===
        print(f"DEBUG: Phase 1 — Scanner analyzing {target_path_display}")
        try:
            scanner_path = os.path.join(os.path.dirname(__file__), 'scanner_prompt.txt')
            with open(scanner_path, 'r') as f:
                scanner_template = f.read()
            
            scanner_prompt = scanner_template.replace('{{REPO_NAME}}', target_repo.full_name)\
                                             .replace('{{FILE_PATH}}', target_path_display)\
                                             .replace('{{REPO_STRUCTURE}}', structure)\
                                             .replace('{{README_CONTENT}}', readme_content)\
                                             .replace('{{FILE_CONTENT}}', file_contents)\
                                             .replace('{{GLOBAL_MEMORY}}', global_memory)
        except Exception as e:
            print(f"DEBUG: Failed to load scanner prompt: {e}")
            scanner_prompt = f"Analyze {target_repo.full_name} ({target_path_display}) and recommend one improvement. Text only, no code."
        
        scanner_plan = query_gemini_scanner(scanner_prompt)
        if not scanner_plan:
            print("DEBUG: Scanner returned nothing")
            return jsonify({'status': 'Scanner failed'}), 200
        
        print(f"DEBUG: Scanner plan length: {len(scanner_plan)}")

        # === PHASE 2 & 3: EXECUTOR + REVIEWER (with retry) ===
        max_attempts = 2
        reviewer_feedback = ""
        final_edits = None
        final_title = ""
        final_body = ""
        final_branch = ""
        reviewer_verdict_text = ""

        for attempt in range(1, max_attempts + 1):
            print(f"DEBUG: Phase 2 — Executor attempt {attempt}")
            
            # Load executor prompt
            try:
                executor_path = os.path.join(os.path.dirname(__file__), 'executor_prompt.txt')
                with open(executor_path, 'r') as f:
                    executor_template = f.read()
                
                executor_prompt = executor_template.replace('{{REPO_NAME}}', target_repo.full_name)\
                                                   .replace('{{FILE_PATH}}', target_path_display)\
                                                   .replace('{{REPO_STRUCTURE}}', structure)\
                                                   .replace('{{SCANNER_PLAN}}', scanner_plan)\
                                                   .replace('{{FILE_CONTENT}}', file_contents)\
                                                   .replace('{{GLOBAL_MEMORY}}', global_memory)\
                                                   .replace('{{TIMESTAMP}}', str(ts))\
                                                   .replace('{{REVIEWER_FEEDBACK}}', reviewer_feedback)
            except Exception as e:
                print(f"DEBUG: Failed to load executor prompt: {e}")
                break
            
            # Kimi K2 executes via Groq
            executor_response = query_groq(executor_prompt)
            if not executor_response:
                print("DEBUG: Executor returned nothing")
                break
            
            print(f"DEBUG: Executor response length: {len(executor_response)}")
            improvement_data = extract_json_from_response(executor_response)
            
            if not improvement_data or 'edits' not in improvement_data:
                print("DEBUG: No valid improvement JSON from Executor")
                break

            # === PHASE 3: REVIEWER (Gemini B) ===
            print(f"DEBUG: Phase 3 — Reviewer validating attempt {attempt}")
            try:
                reviewer_path = os.path.join(os.path.dirname(__file__), 'reviewer_prompt.txt')
                with open(reviewer_path, 'r') as f:
                    reviewer_template = f.read()
                
                reviewer_prompt = reviewer_template.replace('{{REPO_NAME}}', target_repo.full_name)\
                                                   .replace('{{FILE_PATH}}', target_path)\
                                                   .replace('{{FILE_CONTENT}}', file_content)\
                                                   .replace('{{PROPOSED_EDITS}}', json.dumps(improvement_data.get('edits', [])))\
                                                   .replace('{{SCANNER_PLAN}}', scanner_plan)\
                                                   .replace('{{GLOBAL_MEMORY}}', global_memory)
            except Exception as e:
                print(f"DEBUG: Failed to load reviewer prompt: {e}")
                final_edits = improvement_data.get('edits', [])
                final_title = improvement_data.get('title', 'Automated improvement')
                final_body = improvement_data.get('body', '')
                final_branch = improvement_data.get('branch_name', f'bot/fix-{ts}')
                break
            
            reviewer_response = query_gemini_reviewer(reviewer_prompt)
            if not reviewer_response:
                print("DEBUG: Reviewer returned nothing, using Executor's edits as-is")
                final_edits = improvement_data.get('edits', [])
                final_title = improvement_data.get('title', 'Automated improvement')
                final_body = improvement_data.get('body', '')
                final_branch = improvement_data.get('branch_name', f'bot/fix-{ts}')
                reviewer_verdict_text = "Reviewer unavailable — used Executor's edits directly"
                break
            
            reviewer_data = extract_json_from_response(reviewer_response)
            
            if not reviewer_data:
                print("DEBUG: Could not parse Reviewer JSON, using Executor's edits")
                final_edits = improvement_data.get('edits', [])
                final_title = improvement_data.get('title', 'Automated improvement')
                final_body = improvement_data.get('body', '')
                final_branch = improvement_data.get('branch_name', f'bot/fix-{ts}')
                reviewer_verdict_text = "Reviewer response unparseable"
                break
            
            verdict = reviewer_data.get('verdict', 'REJECT').upper()
            reviewer_verdict_text = f"{verdict}: {reviewer_data.get('reason', 'No reason given')}"
            print(f"DEBUG: Reviewer verdict: {verdict}")
            
            if verdict == 'APPROVE':
                final_edits = improvement_data.get('edits', [])
                final_title = improvement_data.get('title', 'Automated improvement')
                final_body = improvement_data.get('body', '')
                final_branch = improvement_data.get('branch_name', f'bot/fix-{ts}')
                break
            elif verdict == 'CORRECT':
                final_edits = reviewer_data.get('corrected_edits', improvement_data.get('edits', []))
                final_title = improvement_data.get('title', 'Automated improvement')
                final_body = improvement_data.get('body', '')
                final_branch = improvement_data.get('branch_name', f'bot/fix-{ts}')
                break
            elif verdict == 'REJECT':
                reviewer_feedback = reviewer_data.get('feedback_for_executor', 'Your edits were rejected. Try smaller, safer changes.')
                # Save rejection to memory
                memory_note = reviewer_data.get('memory_note', f'Rejected edit on {target_repo.name}')
                try:
                    bot_repo = gh.get_repo(os.environ.get('BOT_REPO_NAME', 'HOLYKEYZ/mayo'))
                    mem_file = bot_repo.get_contents("api/global_memory.md")
                    mem_content = mem_file.decoded_content.decode('utf-8')
                    mem_content += f"\n- **REJECTED by Reviewer**: {memory_note}"
                    bot_repo.update_file("api/global_memory.md", f"feat(memory): reviewer rejected edit on {target_repo.name}", mem_content, mem_file.sha)
                except Exception as e:
                    print(f"DEBUG: Failed to save rejection to memory: {e}")
                
                if attempt == max_attempts:
                    print("DEBUG: Max attempts reached, skipping PR")
                    # Log the failed cycle
                    update_ai_communication_log(gh, ts, scanner_plan or "", executor_response or "", f"REJECTED x{max_attempts}: {reviewer_feedback}")
                    return jsonify({'status': 'Rejected after max attempts'}), 200
                continue

        if not final_edits:
            print("DEBUG: No valid edits after pipeline")
            return jsonify({'status': 'No improvement generated'}), 200

        # Group edits by file
        file_edits = {}
        for edit in final_edits:
            # Fallback to the first target path if the AI forgot the file field
            fpath = edit.get('file') or target_paths[0]
            if fpath not in file_edits:
                file_edits[fpath] = []
            file_edits[fpath].append(edit)
            
        file_changes = {}
        for fpath, edits in file_edits.items():
            content = read_file_content(target_repo, fpath)
            if not content:
                print(f"DEBUG: Could not read {fpath} for edits")
                continue
            new_content = apply_surgical_edits(content, edits)
            if new_content != content:
                file_changes[fpath] = new_content
        
        if not file_changes:
            print("DEBUG: No changes applied after surgical edits (search failed or no valid files)")
            return jsonify({'status': 'No changes applied'}), 200

        # Create PR
        print(f"DEBUG: Creating branch {final_branch} with validated edits for {list(file_changes.keys())}")
        success = commit_changes_via_api(target_repo, final_branch, file_changes, final_title)
        
        if success:
            owner_login = target_repo.owner.login
            pr = target_repo.create_pull(
                title=f"[VALIDATED] {final_title}",
                body=f"Hey @{owner_login}! Joseph, I've found an improvement for you.\n\n{final_body}\n\n---\n*Validated by Triple-AI: Scanner (Gemini) → Executor (Kimi K2) → Reviewer (Gemini)*\n\nGenerated autonomously by Mayo 🤖",
                head=final_branch,
                base=target_repo.default_branch
            )
            
            try:
                pr.add_to_assignees(owner_login)
                pr.create_review_request(reviewers=[owner_login])
            except Exception as e:
                print(f"DEBUG: Failed to assign/request review: {e}")

            print(f"DEBUG: PR created: {pr.html_url}")
            
            # Save to memory
            try:
                bot_repo = gh.get_repo(os.environ.get('BOT_REPO_NAME', 'HOLYKEYZ/mayo'))
                old_memory_file = bot_repo.get_contents("api/global_memory.md")
                old_memory = old_memory_file.decoded_content.decode('utf-8')
                lesson = f"\n- **Repo: {target_repo.name}**: {final_title}. (Ref: {pr.html_url}) - *Status: PENDING REVIEW*"
                bot_repo.update_file(
                    "api/global_memory.md",
                    f"feat(memory): record lesson from {target_repo.name}",
                    old_memory + lesson,
                    old_memory_file.sha
                )
            except Exception as e:
                print(f"DEBUG: Failed to update memory: {e}")
            
            # Log the successful cycle
            update_ai_communication_log(gh, ts, scanner_plan or "", executor_response or "", reviewer_verdict_text)

            return jsonify({'status': 'PR Created', 'url': pr.html_url}), 200
        else:
            print("DEBUG: Commit failed")
            return jsonify({'error': 'Commit failed'}), 500
        
    except Exception as e:
        print(f"Cron error: {e}")
        import traceback
        traceback.print_exc()
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
    elif event_type == 'pull_request_review' and payload.get('action') == 'submitted':
        handle_pr_review_feedback(payload)

    return jsonify({'status': 'ok'})

def handle_pr_review_feedback(payload):
    """Record Joseph's review outcome in global memory."""
    try:
        pr_data = payload.get('pull_request', {})
        review = payload.get('review', {})
        pr_url = pr_data.get('html_url', '')
        review_state = review.get('state', 'commented').upper()  # APPROVED, CHANGES_REQUESTED, COMMENTED
        reviewer = review.get('user', {}).get('login', 'unknown')
        
        # Only process reviews from the repo owner, not the bot itself
        bot_login = get_bot_login()
        if reviewer == bot_login:
            return
        
        # Map review states to memory-friendly labels
        state_map = {
            'APPROVED': 'APPROVED - Joseph liked this!',
            'CHANGES_REQUESTED': 'REJECTED - Needs improvement',
            'COMMENTED': 'COMMENTED - Joseph had feedback',
            'DISMISSED': 'DISMISSED'
        }
        memory_status = state_map.get(review_state, review_state)
        
        installation = payload.get('installation')
        if not installation:
            return
        
        gh = get_github_client(installation['id'])
        bot_repo = gh.get_repo(os.environ.get('BOT_REPO_NAME', 'HOLYKEYZ/mayo'))
        
        memory_file = bot_repo.get_contents("api/global_memory.md")
        old_memory = memory_file.decoded_content.decode('utf-8')
        
        # Update the PENDING REVIEW status for this PR
        if pr_url in old_memory:
            new_memory = old_memory.replace(
                f"(Ref: {pr_url}) - *Status: PENDING REVIEW*",
                f"(Ref: {pr_url}) - *Status: {memory_status}*"
            )
            if new_memory != old_memory:
                bot_repo.update_file(
                    "api/global_memory.md",
                    f"feat(memory): record review outcome ({review_state})",
                    new_memory,
                    memory_file.sha
                )
                print(f"DEBUG: Memory updated with review: {review_state} for {pr_url}")
        else:
            print(f"DEBUG: PR {pr_url} not found in memory, skipping review update")
    except Exception as e:
        print(f"DEBUG: Failed to record review feedback: {e}")

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
    if "mayo" in body.lower() or "joe-gemini" in body.lower():
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
        
        # 5. Generate response (Reviewer)
        reviewer_prompt = f"""You are Mayo, the Senior Quality Assurance & Reviewer AI.
Joseph (the human owner) has made a comment: "{comment['body']}"

Context:
{expanded_context}

Instructions:
1. Address Joseph's comment clearly and concisely.
2. If Joseph is providing feedback, rejecting something, or explaining a preferred pattern, state clearly how you understand his instruction.
3. If Joseph's request requires code changes, explain the technical plan for the fix and end your ENTIRE response with the exact marker: [REQUIRES_EXECUTION]
"""
        plan = query_gemini_reviewer(reviewer_prompt)
        if not plan: return
        
        all_files = files_already_read + new_files_read
        memory_block = format_memory_block({"files_read": all_files})
        
        issue.create_comment(f"🛡️ **Reviewer (Mayo):**\n{plan}{memory_block}")
        
        # 6. Execute Code Changes (Executor)
        if "[REQUIRES_EXECUTION]" in plan:
            issue.create_comment("⚡ *Executor (Kimi K2) is now writing the code changes...*")
            
            executor_prompt = f"""You are Mayo, the Executor AI (Code Engineer).
The Reviewer AI has established this plan based on Joseph's feedback:
{plan}

Based on this plan, look at the files provided in the context below:
{expanded_context}

Generate the exact surgical search/replace JSON edits needed to fulfill this fix.
IMPORTANT RULES:
1. MAX 10 lines per search block.
2. Return strict JSON.
3. Include the "file" field in each edit block so I know which file to modify!
"""
            code_response = query_groq(executor_prompt)
            parsed = extract_json_from_response(code_response)
            
            if parsed and 'edits' in parsed:
                # Group edits by file
                file_edits = {}
                for edit in parsed['edits']:
                    fpath = edit.get('file')
                    if not fpath: continue
                    if fpath not in file_edits:
                        file_edits[fpath] = []
                    file_edits[fpath].append(edit)
                
                # Apply edits
                file_changes = {}
                for fpath, edits in file_edits.items():
                    content = read_file_content(repo, fpath)
                    if not content: continue
                    new_content = apply_surgical_edits(content, edits)
                    if new_content != content:
                        file_changes[fpath] = new_content
                
                if file_changes:
                    # Decide branch
                    if issue.pull_request:
                        try:
                            pr = repo.get_pull(issue_number)
                            branch = pr.head.ref
                        except:
                            branch = f"mayo/fix-{issue_number}-{int(time.time())}"
                    else:
                        branch = f"mayo/fix-{issue_number}-{int(time.time())}"
                    
                    commit_title = parsed.get('title', f"Fix: Addressed feedback in #{issue_number}")
                    if commit_changes_via_api(repo, branch, file_changes, commit_title):
                        msg = f"✅ Committed changes to `{branch}`.\n\nDescription: {parsed.get('body', commit_title)}"
                        issue.create_comment(msg)
                        
                        if not issue.pull_request:
                            try:
                                repo.create_pull(title=commit_title, body=f"Automated fix.\n{parsed.get('body', '')}", head=branch, base=repo.default_branch)
                                issue.create_comment(f"🚀 Created new PR for `{branch}`")
                            except Exception as e:
                                print(f"PR Creation error: {e}")
                    else:
                        issue.create_comment("⚠️ Executor generated edits, but the commit failed. Check logs.")
                else:
                    issue.create_comment("⚠️ Executor generated edits, but they did not match the file contents (search blocks failed).")
            else:
                 issue.create_comment("⚠️ Executor failed to generate valid JSON edits.")
    except Exception as e:
        print(f"Error processing comment: {e}")

if __name__ == '__main__':
    app.run(port=3000)


