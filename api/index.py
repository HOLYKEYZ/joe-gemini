
import os
import json
import re
import requests
import hmac
import hashlib
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

# ... (imports remain) ...
# ... (config remain) ...

# ... (verify_signature helper remains) ...

# ... (get_github_client helper remains) ...

@app.route('/', methods=['GET'])
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
    elif event_type == 'pull_request' and payload.get('action') in ['opened', 'edited', 'synchronize']:
         # Simplified PR handling for now - just acknowledge
         pass

    return jsonify({'status': 'ok'})

def handle_issue_comment(payload):
    installation = payload.get('installation')
    if not installation:
        return

    # Authenticate as App Installation
    gh = get_github_client(installation['id'])
    
    repo_info = payload['repository']
    repo = gh.get_repo(repo_info['full_name'])
    comment = payload['comment']
    issue_number = payload['issue']['number']
    
    body = comment.get('body', '').lower()
    
    # Check mentions
    if "joe-gemini" not in body and f"@{repo_info['owner']['login']}" not in body:
         # TODO: Add robust reply check here if needed
         return

    # Logic from autonomous_bot.py adapted
    try:
        issue = repo.get_issue(number=issue_number)
        
        # Determine if PR
        pr_number = issue.number if issue.pull_request else None
        
        # Context
        context = f"User Comment: {comment['body']}\n\n"
        if pr_number:
             try:
                 pr = repo.get_pull(pr_number)
                 context += f"PR Title: {pr.title}\nPR Body: {pr.body}\n"
             except: pass

        # Gemini Query
        headers = {'Content-Type': 'application/json'}
        gemini_payload = {
            "contents": [{"parts": [{"text": f"You are @joe-gemini, a helpful GitHub bot. act as an agent. Context: {context}. User says: {comment['body']}"}]}],
             "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048}
        }
        
        r = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=gemini_payload, headers=headers)
        r.raise_for_status()
        response_text = r.json()['candidates'][0]['content']['parts'][0]['text']
        
        issue.create_comment(response_text)
        
    except Exception as e:
        print(f"Error processing comment: {e}")

if __name__ == '__main__':
    app.run(port=3000)

if __name__ == '__main__':
    app.run(port=3000)
