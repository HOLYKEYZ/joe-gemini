
import os
import json
import sys

# 1. Ask for keys if not set
if "GEMINI_API_KEY" not in os.environ:
    print("❌ GEMINI_API_KEY not found in environment variables.")
    print("   Run: $env:GEMINI_API_KEY='your_key'")
    sys.exit(1)

if "GITHUB_TOKEN" not in os.environ:
    print("❌ GITHUB_TOKEN not found in environment variables.")
    print("   Run: $env:GITHUB_TOKEN='your_token'")
    sys.exit(1)

# 2. Create a mock event file
mock_event = {
    "repository": {
        "full_name": "HOLYKEYZ/joe-gemini"  # Replace with your actual repo
    },
    "issue": {
        "number": 1,  # Replace with a real issue number from your repo
        "title": "Test Issue",
        "body": "Can you help me fix the typo in README?"
    },
    "comment": {
        "body": "@joe-gemini please fix the typo in the readme file"
    },
    "sender": {
        "login": "HOLYKEYZ"
    }
}

event_path = os.path.abspath("mock_event.json")
with open(event_path, "w") as f:
    json.dump(mock_event, f)

# 3. Set the event path env var
os.environ["GITHUB_EVENT_PATH"] = event_path

print(f"✅ Mock event created at {event_path}")
print("🚀 Running autonomous_bot.py locally...")

# 4. Run the bot
exit_code = os.system("python autonomous_bot.py")

if exit_code == 0:
    print("\n✅ Bot finished successfully!")
else:
    print(f"\n❌ Bot failed with exit code {exit_code}")
