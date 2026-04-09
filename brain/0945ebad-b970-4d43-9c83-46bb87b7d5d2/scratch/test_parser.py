import re

def parse_incremental_files(raw_text):
    if not raw_text or not isinstance(raw_text, str):
        return []

    marker_pattern = (
        r"(?:\n|^)[-=#*]{3,}\s*([\w./\-\\]+\.[a-zA-Z0-9]{1,10})\s*(?:[-=#*]{3,})?"
    )
    
    matches = list(re.finditer(marker_pattern, raw_text, re.IGNORECASE))
    if not matches:
        return []

    files = []
    for i, match in enumerate(matches):
        filename = match.group(1).lower().strip()
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        content = raw_text[start_pos:end_pos].strip()
        if filename and (len(content) > 0 or i < len(matches) - 1):
            files.append({"name": filename, "content": content})
    return files

# Test cases
buffer = """
--- index.jsx ---
import React from 'react';
export default function App() {
  return <div>Hello</div>;
}
--- style.css ---
body { background: 
"""

files = parse_incremental_files(buffer)
print(f"Detected {len(files)} files")
for f in files:
    print(f"File: {f['name']}")
    print(f"Content: {f['content']}")
    print("-" * 20)

assert len(files) == 2
assert files[0]['name'] == 'index.jsx'
assert 'Hello' in files[0]['content']
assert files[1]['name'] == 'style.css'
assert 'background:' in files[1]['content']
print("TEST PASSED")
