"""
Verifier for task 3: runs the completed main.py on sample.txt
and checks that output has exactly 10 lines, each matching "<count> <word>".
Exit 0 = pass, Exit 1 = fail.
"""
import subprocess, sys, re, os

script = os.path.join(os.path.dirname(__file__), 'main.py')
sample = os.path.join(os.path.dirname(__file__), 'sample.txt')

result = subprocess.run(
    [sys.executable, script, sample],
    capture_output=True, text=True
)

if result.returncode != 0:
    print(f"FAIL: script exited {result.returncode}\n{result.stderr}")
    sys.exit(1)

lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
if len(lines) != 10:
    print(f"FAIL: expected 10 output lines, got {len(lines)}")
    sys.exit(1)

pattern = re.compile(r'^\d+ \w+$')
for line in lines:
    if not pattern.match(line):
        print(f"FAIL: line does not match '<count> <word>': {line!r}")
        sys.exit(1)

# Top word should be 'the' (appears most)
top_word = lines[0].split()[1]
if top_word != 'the':
    print(f"WARN: expected top word 'the', got '{top_word}' — may still be correct")

print(f"PASS: 10 lines, correct format, top word='{top_word}'")
sys.exit(0)
