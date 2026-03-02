import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: clean_blanklines.py <file>")
    sys.exit(1)

p = Path(sys.argv[1])
if not p.exists():
    print(f"File not found: {p}")
    sys.exit(2)

text = p.read_text(encoding='utf-8')

out_lines = []
empty_count = 0
for line in text.splitlines(True):
    if line.strip() == "":
        empty_count += 1
    else:
        if empty_count > 0:
            out_lines.append("\n")
            empty_count = 0
        out_lines.append(line)
# if file ends with blank lines, ensure single trailing newline
if empty_count > 0:
    out_lines.append("\n")

new_text = "".join(out_lines)
# avoid modifying if identical
if new_text == text:
    print("No changes needed")
else:
    p.write_text(new_text, encoding='utf-8')
    print(f"Cleaned blank lines in {p}")
