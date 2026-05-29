import subprocess
import ollama

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    ConsoleSpanExporter,
)

# =========================================================
# OPEN TELEMETRY SETUP
# =========================================================

provider = TracerProvider()

processor = SimpleSpanProcessor(ConsoleSpanExporter())

provider.add_span_processor(processor)

trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# =========================================================
# AGENT CONFIG
# =========================================================

MODEL = "qwen2.5:7b"

TASK = """
You are an expert software engineer.

Write a Python function add(a, b)
that returns the sum of a and b.

Save it in a file called solution.py.

Return ONLY valid Python code.
No markdown.
No explanation.
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
# LLM
# =========================================================

def ask_llm(prompt):

    with tracer.start_as_current_span("llm_call") as span:

        span.set_attribute("model", MODEL)
        span.set_attribute("prompt.length", len(prompt))

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

        span.set_attribute("response.length", len(content))

        # Token tracking if available
        prompt_tokens = response.get("prompt_eval_count")
        completion_tokens = response.get("eval_count")

        if prompt_tokens:
            span.set_attribute(
                "prompt_tokens",
                prompt_tokens
            )

        if completion_tokens:
            span.set_attribute(
                "completion_tokens",
                completion_tokens
            )

        return content


# =========================================================
# FILE WRITE
# =========================================================

def write_solution(code):

    with tracer.start_as_current_span("write_solution") as span:

        span.set_attribute(
            "code.length",
            len(code)
        )

        with open("solution.py", "w") as f:
            f.write(code)


# =========================================================
# TEST EXECUTION
# =========================================================

def run_tests():

    with tracer.start_as_current_span("run_tests") as span:

        with open("test.py", "w") as f:
            f.write(TEST_CODE)

        result = subprocess.run(
            ["python", "test.py"],
            capture_output=True,
            text=True
        )

        span.set_attribute(
            "returncode",
            result.returncode
        )

        span.set_attribute(
            "stderr.length",
            len(result.stderr)
        )

        if result.returncode != 0:
            span.record_exception(
                Exception(result.stderr)
            )

        return result


# =========================================================
# AGENT LOOP
# =========================================================

with tracer.start_as_current_span("agent_loop") as agent_span:

    attempt = 1

    while attempt <= 5:

        with tracer.start_as_current_span(
            f"attempt_{attempt}"
        ) as attempt_span:

            print(f"\nAttempt {attempt}")

            attempt_span.set_attribute(
                "attempt.number",
                attempt
            )

            code = ask_llm(TASK)

            write_solution(code)

            result = run_tests()

            if result.returncode == 0:

                print(result.stdout)

                attempt_span.set_attribute(
                    "attempt.success",
                    True
                )

                break

            else:

                attempt_span.set_attribute(
                    "attempt.success",
                    False
                )

                attempt_span.set_attribute(
                    "attempt.error",
                    result.stderr
                )

                TASK += f"\nThe code failed with this error:\n\n{result.stderr}\n"

                attempt += 1
