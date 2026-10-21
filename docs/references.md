# References

The sources this project relies on, and what each one was used for.

## Setting up the project

- [venv: creation of virtual environments](https://docs.python.org/3/library/venv.html) (Python documentation). What a virtual environment is, and the note on Windows that explains why PowerShell may refuse to run `Activate.ps1` and which setting allows it.
- [tomllib: parse TOML files](https://docs.python.org/3/library/tomllib.html) (Python documentation). The built-in reader for our settings file, `config.toml`, and why the file must be opened in binary mode.
- [Building and testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) (GitHub documentation). How a workflow file makes GitHub install the project and run its tests after every push; the basis of `.github/workflows/tests.yml`.

## MCP (how the agent reaches its tools)

- [First steps](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/) (MCP Python SDK documentation, version 2). Host, client and server; tools; how one decorator turns a Python function into a tool, with its description and argument form read from the function itself.
- [Testing](https://py.sdk.modelcontextprotocol.io/get-started/testing/) (MCP Python SDK documentation). Connecting a client to a server object directly, in memory, which is how `tests/test_smoke_mcp.py` works.

## The language model (Ollama)

- [Tool calling](https://docs.ollama.com/capabilities/tool-calling) (Ollama documentation). How a model is offered tools and how it replies with a request to run one; the basis of `src/plantagent/smoke_ollama.py`.
- [FAQ: how can I specify the context window size?](https://docs.ollama.com/faq) (Ollama documentation). Ollama's default context is 4,096 tokens, which is why we always set `num_ctx` ourselves.

## The plant data

- [Additional Tennessee Eastman Process Simulation Data for Anomaly Detection Evaluation](https://doi.org/10.7910/DVN/6C3JR1) (Rieth, Amsel, Tran and Cook, 2017, Harvard Dataverse). The recorded plant runs this project works on: normal runs and runs with each of 20 faults. Used to download the four data files and to check the facts we rely on (one sample every 3 minutes, run lengths, when each fault starts).
