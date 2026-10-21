"""Smoke test for the language model: does Qwen3, running in Ollama on this computer,
ask for a tool when it needs one?

That request is the first move of every agent: instead of answering straight away, the
model replies "please run this tool with these arguments". This script checks only that
first move. Running the tool and handing the result back to the model is the agent loop,
which comes later.

It needs Ollama running on this computer, so it is not part of the tests on GitHub.
Run it with:
    python -m plantagent.smoke_ollama
"""

import time

import ollama

from plantagent.config import load_config

QUESTION = "What is the current reading of sensor TI-101?"


def read_sensor(tag: str) -> float:
    """Read the current value of one plant sensor.

    Args:
        tag: The sensor's tag name, for example TI-101.
    """
    toy_readings = {"TI-101": 87.5}  # made up: this sensor and its value don't exist
    return toy_readings[tag]


def show_reply(message) -> None:
    """Print what the model sent back: its text, and the tools it asked for."""
    print(f"  text: {message.content!r}")
    for call in message.tool_calls or []:
        print(f"  asks for tool: {call.function.name}, with arguments {dict(call.function.arguments)}")


def check(passed: bool, what: str) -> bool:
    """Print PASS or FAIL for one check, and give the result back."""
    print(f"{'PASS' if passed else 'FAIL'}: {what}")
    return passed


def main() -> None:
    llm = load_config()["llm"]
    print(f"Asking {llm['model']}: {QUESTION!r}")
    print("(the first call can take a minute: Ollama loads the model into memory)")

    start = time.perf_counter()
    response = ollama.chat(
        model=llm["model"],
        messages=[{"role": "user", "content": QUESTION}],
        tools=[read_sensor],
        think=llm["think"],
        options={
            "num_ctx": llm["num_ctx"],
            "temperature": llm["temperature"],
            "seed": llm["seed"],
        },
    )

    print(f"Answered in {time.perf_counter() - start:.1f} s")
    show_reply(response.message)
    tool_calls = response.message.tool_calls
    if tool_calls is None or len(tool_calls) == 0:
        print("No tool was asked for, so the other checks can't be done.")
        return
    check(tool_calls is not None and len(tool_calls) > 0, "model asked for at least one tool")
    check(tool_calls[0].function.name == "read_sensor", "first tool is read_sensor")
    check(tool_calls[0].function.arguments["tag"] == "TI-101", "asks for sensor TI-101")



if __name__ == "__main__":
    main()
