import subprocess
import ollama

MODEL = "qwen2.5:7b"

TASK = """
You are an expert software engineer. You are asked to deliver valid, professional and robust source code.
Write a Python function add(a, b) that returns the sum of a and b.
Save it in a file called solution.py.
Return ONLY valid Python code.
No markdown.
No explanation.
As an example, a valid output could be:
import os
print("hello")
"""

TEST_CODE = """
from solution import add

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

test_add()
print("TESTS PASSED")
"""

def ask_llm(prompt):
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]

def write_solution(code):
    with open("solution.py", "w") as f:
        f.write(code)

def run_tests():
    with open("test.py", "w") as f:
        f.write(TEST_CODE)

    return subprocess.run(
        ["python", "test.py"],
        capture_output=True,
        text=True
    )

# =========================================================  
# AGENT LOOP # 
# =========================================================

attempt = 1
while attempt <= 5:
    print(f"\nAttempt {attempt}")

    code = ask_llm(TASK)
    write_solution(code)

    result = run_tests()

    if result.returncode == 0:
        print(result.stdout)
        break
    else:
        TASK += f"\nThe code failed with this error:\n{result.stderr}"
        attempt += 1