# Agent Loop

This project is a very small Hello World Python Agent that write code, saves the result to `solution.py`, and runs a test file against it.

## What It Does

`agent_loop.py`:

- sends a coding task to an Ollama model
- writes the returned code to `solution.py`
- writes tests to `test.py`
- runs the tests
- retries up to 5 times if the tests fail

## How To Run

Make sure you have:

- Python
- Ollama running locally
- the model from `agent_loop.py` available locally

Then run:

```bash
python agent_loop.py
```

Files created during execution:

- `solution.py`
- `test.py`

## Flow

```mermaid
flowchart TD
    A[Start agent_loop.py] --> B[Send task to LLM]
    B --> C[Receive generated code]
    C --> D[Write solution.py]
    D --> E[Write test.py]
    E --> F[Run tests]
    F --> G{Tests passed?}
    G -- Yes --> H[Print success output and stop]
    G -- No --> I[Append test error to prompt]
    I --> J{Attempts left?}
    J -- Yes --> B
    J -- No --> K[Stop after 5 attempts]
```
