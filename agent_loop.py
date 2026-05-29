import argparse
import subprocess
import ollama
import re

from tracer import AgentTracer

MODEL = "qwen2.5:7b"

BASE_TASK = """
You are an autonomous coding agent.

Your task:
Write a Python function add(a, b)
that returns the sum of a and b.

IMPORTANT:
- Return ONLY valid Python code
- No markdown
- No explanations

For every attempt:
1. Explain your reasoning
2. Explain what may have failed
3. Explain your fix
4. Output corrected Python code

FORMAT:

THOUGHT:
...

PLAN:
...

CODE:
...
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
    help="Enable tracing"
)

args = parser.parse_args()


# =========================================================
# INITIALIZE TRACER
# =========================================================

tracer = AgentTracer(enabled=args.tracer)


# =========================================================
# TOKEN ESTIMATION FALLBACK
# =========================================================

def estimate_tokens(text):
    """
    Rough fallback token estimator.
    Useful if Ollama does not expose token metadata.
    """
    return int(len(text.split()) * 1.3)


# =========================================================
# CLEAN CODE BLOCKS (helper)
# =========================================================

def clean_code(code):

    code = re.sub(r"```python", "", code)
    code = re.sub(r"```", "", code)

    return code.strip()


# =========================================================
# RESPONSE PARSER (helper for tracer)
# =========================================================

def parse_response(response):

    thought = ""
    plan = ""
    code = response

    tracer.memory_access(
        operation="response_parsing",
        details={
            "response_length": len(response)
        }
    )

    try:

        # -------------------------------------------------
        # THOUGHT
        # -------------------------------------------------

        if "THOUGHT:" in response:

            thought_part = response.split("THOUGHT:", 1)[1]

            if "PLAN:" in thought_part:
                thought, remaining = thought_part.split("PLAN:", 1)
            else:
                thought = thought_part
                remaining = ""

            thought = thought.strip()

        # -------------------------------------------------
        # PLAN
        # -------------------------------------------------

        if "PLAN:" in response:

            plan_part = response.split("PLAN:", 1)[1]

            if "CODE:" in plan_part:
                plan, code = plan_part.split("CODE:", 1)
            else:
                plan = plan_part

            plan = plan.strip()

        # -------------------------------------------------
        # CODE
        # -------------------------------------------------

        if "CODE:" in response:
            code = response.split("CODE:", 1)[1]

        code = clean_code(code)

    except Exception as e:

        tracer.error_event(
            error_type="parse_error",
            message=str(e),
        )

    return {
        "thought": thought,
        "plan": plan,
        "code": code,
    }


# =========================================================
# ASK LLM
# =========================================================

def ask_llm(prompt, attempt):

    tracer.log(
        "llm_request",
        attempt=attempt,
        prompt=prompt,
    )

    tracer.memory_access(
        operation="prompt_read",
        details={
            "prompt_length": len(prompt)
        }
    )

    tracer.tool_call(
        tool_name="ollama.chat",
        input_data={
            "model": MODEL,
            "attempt": attempt,
        }
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

    # =====================================================
    # TOKEN USAGE
    # =====================================================

    prompt_tokens = response.get("prompt_eval_count")
    completion_tokens = response.get("eval_count")

    if prompt_tokens is None:
        prompt_tokens = estimate_tokens(prompt)

    if completion_tokens is None:
        completion_tokens = estimate_tokens(content)

    total_tokens = prompt_tokens + completion_tokens

    tracer.token_usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )

    tracer.evaluation_metric(
        "total_tokens",
        total_tokens,
    )

    tracer.tool_result(
        tool_name="ollama.chat",
        output_data={
            "response_length": len(content),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
    )

    tracer.log(
        "llm_response",
        attempt=attempt,
        response=content,
    )

    return content


# =========================================================
# WRITE SOLUTION
# =========================================================

def write_solution(code):

    tracer.memory_access(
        operation="solution_write",
        details={
            "code_lines": len(code.splitlines())
        }
    )

    with open("solution.py", "w") as f:
        f.write(code)

    tracer.log(
        "solution_written",
        lines=len(code.splitlines()),
        characters=len(code),
    )


# =========================================================
# RUN TESTS
# =========================================================

def run_tests():

    tracer.memory_access(
        operation="test_generation",
        details={
            "test_file": "test.py"
        }
    )

    with open("test.py", "w") as f:
        f.write(TEST_CODE)

    tracer.tool_call(
        tool_name="python_test_runner",
        input_data={
            "file": "test.py"
        }
    )

    with tracer.time_block("test_execution"):

        result = subprocess.run(
            ["python", "test.py"],
            capture_output=True,
            text=True,
        )

    tracer.tool_result(
        tool_name="python_test_runner",
        output_data={
            "returncode": result.returncode,
        }
    )

    tracer.log(
        "test_result",
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )

    return result


# =========================================================
# AGENT LOOP
# =========================================================

tracer.log(
    "agent_started",
    model=MODEL,
)

tracer.model_decision(
    decision="initialize_agent_loop",
    confidence="high",
)

attempt = 1
max_attempts = 5

task = BASE_TASK

success = False

while attempt <= max_attempts:

    print(f"\n========== Attempt {attempt} ==========")

    tracer.log(
        "attempt_started",
        attempt=attempt,
    )

    tracer.planning_step(
        f"Execute generation-test-repair loop for attempt {attempt}"
    )

    # =====================================================
    # MODEL GENERATION
    # =====================================================

    response = ask_llm(task, attempt)

    parsed = parse_response(response)

    tracer.reasoning_step(parsed["thought"])

    tracer.planning_step(parsed["plan"])

    code = parsed["code"]

    tracer.evaluation_metric(
        "generated_code_length",
        len(code)
    )

    # =====================================================
    # WRITE CODE
    # =====================================================

    write_solution(code)

    # =====================================================
    # RUN TESTS
    # =====================================================

    result = run_tests()

    # =====================================================
    # EVALUATION METRICS
    # =====================================================

    tracer.evaluation_metric(
        "tests_passed",
        result.returncode == 0,
    )

    tracer.evaluation_metric(
        "stderr_length",
        len(result.stderr),
    )

    tracer.evaluation_metric(
        "code_lines",
        len(code.splitlines()),
    )

    tracer.evaluation_metric(
        "attempt_number",
        attempt,
    )

    # =====================================================
    # SUCCESS
    # =====================================================

    if result.returncode == 0:

        success = True

        print(result.stdout)

        tracer.log(
            "attempt_success",
            attempt=attempt,
        )

        tracer.model_decision(
            decision="task_completed",
            confidence="high",
        )

        tracer.evaluation_metric(
            "final_success",
            True,
        )

        break

    # =====================================================
    # FAILURE
    # =====================================================

    else:

        print(result.stderr)

        tracer.log(
            "attempt_failed",
            attempt=attempt,
            error=result.stderr,
        )

        tracer.error_event(
            error_type="test_failure",
            message=result.stderr,
        )

        tracer.model_decision(
            decision="retry_generation",
            confidence="medium",
        )

        tracer.retry_event(
            reason=result.stderr,
            next_attempt=attempt + 1,
        )

        tracer.memory_access(
            operation="prompt_mutation",
            details={
                "previous_prompt_length": len(task)
            }
        )

        # -------------------------------------------------
        # PROMPT EVOLUTION
        # -------------------------------------------------

        task += f"""

The previous attempt failed.

ERROR:
{result.stderr}

Please fix the issue and try again.
"""

        tracer.log(
            "prompt_updated",
            attempt=attempt,
            new_prompt_length=len(task),
        )

        tracer.evaluation_metric(
            "prompt_length",
            len(task),
        )

        attempt += 1


# =========================================================
# FINALIZATION
# =========================================================

tracer.log(
    "agent_finished",
    success=success,
    attempts_used=attempt,
)

tracer.evaluation_metric(
    "overall_success",
    success,
)

tracer.evaluation_metric(
    "total_attempts",
    attempt,
)

tracer.model_decision(
    decision="shutdown_agent",
    confidence="high",
)

tracer.save()

print("\nAgent execution finished.")
