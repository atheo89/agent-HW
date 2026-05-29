import argparse
import subprocess
import ollama

from tracer import AgentTracer

MODEL = "qwen2.5:7b"

BASE_TASK = """
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


# =========================================================
# ARGUMENTS
# =========================================================

parser = argparse.ArgumentParser()
parser.add_argument(
    "--tracer",
    action="store_true",
    help="Enable agent tracing"
)

args = parser.parse_args()

# =========================================================
# INITIALIZE TRACER
# =========================================================

tracer = AgentTracer(enabled=args.tracer)

# =========================================================
# LLM
# =========================================================

def ask_llm(prompt, attempt):

    tracer.log(
        "llm_request",
        attempt=attempt,
        prompt=prompt,
    )

    with tracer.time_block("ollama_generation"):

        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

    content = response["message"]["content"]

    tracer.log(
        "llm_response",
        attempt=attempt,
        response=content,
    )

    return content

# =========================================================
# FILE WRITING
# =========================================================


def write_solution(code):

    with open("solution.py", "w") as f:
        f.write(code)

    tracer.log(
        "solution_written",
        lines=len(code.splitlines()),
        characters=len(code),
    )

# =========================================================
# TESTS
# =========================================================


def run_tests():

    with open("test.py", "w") as f:
        f.write(TEST_CODE)

    with tracer.time_block("test_execution"):

        result = subprocess.run(
            ["python", "test.py"],
            capture_output=True,
            text=True,
        )

    tracer.log(
        "test_result",
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )

    return result

# =========================================================  
# AGENT LOOP # 
# =========================================================

# =========================================================
# AGENT LOOP
# =========================================================

tracer.log(
    "agent_started",
    model=MODEL,
)

attempt = 1
max_attempts = 5

task = BASE_TASK

while attempt <= max_attempts:

    print(f"\nAttempt {attempt}")

    tracer.log(
        "attempt_started",
        attempt=attempt,
    )

    code = ask_llm(task, attempt)

    write_solution(code)

    result = run_tests()

    if result.returncode == 0:

        print(result.stdout)

        tracer.log(
            "attempt_success",
            attempt=attempt,
        )

        break

    else:

        print(result.stderr)

        tracer.log(
            "attempt_failed",
            attempt=attempt,
            error=result.stderr,
        )

        task += f"""

The code failed with this error:

{result.stderr}

Please fix it.
"""

        tracer.log(
            "prompt_updated",
            attempt=attempt,
            new_prompt_length=len(task),
        )

        attempt += 1


# =========================================================
# FINALIZE TRACE
# =========================================================

tracer.log(
    "agent_finished",
    success=result.returncode == 0,
    attempts_used=attempt,
)

tracer.save()
