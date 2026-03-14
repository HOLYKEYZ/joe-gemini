import re
import json

def extract_json_from_response(text):
    if not text: return None
    json_patterns = [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```', r'\{[\s\S]*"edits"[\s\S]*\}']
    
    for pattern in json_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                return json.loads(json_str)
            except Exception as e:
                # Attempt to fix the string before failing completely
                try:
                    import ast
                    parsed = ast.literal_eval(json_str.strip())
                    if isinstance(parsed, dict):
                         return parsed
                except Exception:
                    pass
                
                # Fix unescaped newlines in strings
                try:
                    # Replace actual newlines with \\n, but only inside string values.
                    # A robust way is to just escape all single unescaped newlines, but keeping structural JSON intact is hard.
                    # Another way: since the Executor is meant to output structural JSON, we can assume lines ending with `,` or `{` or `[` or `}` or `]` are structural.
                    # Lines ending in other characters inside the string block are literal newlines.
                    lines = json_str.split('\n')
                    fixed_lines = []
                    in_string = False
                    
                    # Safer method: Python's json parser actually has an issue strictly with \n inside double quotes.
                    # We can use a regex to find all text inside "...", and replace \n with \\n inside those matches.
                    # However, regex matching balanced quotes with arbitrary escaped quotes inside is notoriously fragile.
                    
                    # Let's try the simple heuristic: if a line does NOT end with a structural JSON character, it's likely a continued string.
                    # Note: this fails if string values end with those chars, but it's a good fallback.
                    import ast
                    def escape_newlines_in_json_strings(s):
                        result = []
                        in_string = False
                        escaped = False
                        for char in s:
                            if char == '"' and not escaped:
                                in_string = not in_string
                            elif char == '\\' and not escaped:
                                escaped = True
                            else:
                                escaped = False
                                
                            if in_string and char == '\n':
                                result.append('\\n')
                            elif in_string and char == '\r':
                                result.append('\\r')
                            elif in_string and char == '\t':
                                result.append('\\t')
                            else:
                                result.append(char)
                        return "".join(result)
                    
                    fixed_str = escape_newlines_in_json_strings(json_str)
                    return json.loads(fixed_str)
                except Exception as final_e:
                    print(f"Final parse error: {final_e}")
                    pass
                continue
    return None

test_text = """Here are the requested surgical edits for your file:

```json
{
  "title": "[CI] Fix backend workflow",
  "body": "Replaced missing run command",
  "edits": [
    {
      "file": ".github/workflows/backend_ci.yml",
      "search": "",
      "replace": "name: Backend CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npm test"
    }
  ]
}
```
"""

result = extract_json_from_response(test_text)
if result:
    print("\nSUCCESS! Parsed JSON:")
    print(json.dumps(result, indent=2))
else:
    print("\nFAILED TO PARSE JSON.")
