# References

The sources this project relies on, and what each one was used for.

## Setting up the project

- [venv: creation of virtual environments](https://docs.python.org/3/library/venv.html) (Python documentation). What a virtual environment is, and the note on Windows that explains why PowerShell may refuse to run `Activate.ps1` and which setting allows it.
- [tomllib: parse TOML files](https://docs.python.org/3/library/tomllib.html) (Python documentation). The built-in reader for our settings file, `config.toml`, and why the file must be opened in binary mode.
- [Building and testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) (GitHub documentation). How a workflow file makes GitHub install the project and run its tests after every push; the basis of `.github/workflows/tests.yml`.

## MCP (how the agent reaches its tools)

- [First steps](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/) (MCP Python SDK documentation, version 2). Host, client and server; tools; how one decorator turns a Python function into a tool, with its description and argument form read from the function itself.
- [Testing](https://py.sdk.modelcontextprotocol.io/get-started/testing/) (MCP Python SDK documentation). Connecting a client to a server object directly, in memory, which is how `tests/test_smoke_mcp.py` works.
- [What's new in v2](https://py.sdk.modelcontextprotocol.io/whats-new/) (MCP Python SDK documentation). The names that changed since version 1 (`MCPServer`, `Client`, `is_error`), checked before writing the plant server so it uses the current ones.
- [Tools](https://py.sdk.modelcontextprotocol.io/servers/tools/) (MCP Python SDK documentation). How each argument gets a description and limits the model can read, and how a tool is marked as read-only; used in `src/plantagent/mcp_server/server.py`.
- [Structured Output](https://py.sdk.modelcontextprotocol.io/servers/structured-output/) (MCP Python SDK documentation). How a tool that returns a fixed form (a Pydantic model) sends its fields as named data as well as text; the basis of `src/plantagent/mcp_server/models.py`.
- [Handling errors](https://py.sdk.modelcontextprotocol.io/servers/handling-errors/) (MCP Python SDK documentation). Why our tools raise `ToolError`: its message reaches the model, which can correct its request, while other crashes only show a generic message.
- [Transports](https://py.sdk.modelcontextprotocol.io/client/transports/) (MCP Python SDK documentation). How a client starts a server as a separate program and talks to it over standard input and output (stdio); used in `src/plantagent/mcp_server/demo.py`.

## The language model (Ollama)

- [Tool calling](https://docs.ollama.com/capabilities/tool-calling) (Ollama documentation). How a model is offered tools and how it replies with a request to run one; the basis of `src/plantagent/smoke_ollama.py`.
- [FAQ: how can I specify the context window size?](https://docs.ollama.com/faq) (Ollama documentation). Ollama's default context is 4,096 tokens, which is why we always set `num_ctx` ourselves.

## The plant itself

- [Tennessee Eastman Challenge Archive](https://depts.washington.edu/control/LARRY/TE/download.html) (N. L. Ricker, University of Washington). Home of the plant's simulation code, including the 2015 revision by Bathelt, Ricker and Jelali, whose header lists every measurement and valve with its unit. Used to build and check `knowledge/tags.csv`.
- [PCA for fault detection in Tennessee Eastman Process](https://bibmon.readthedocs.io/en/stable/tutorial_tep.html) (BibMon documentation). A clear table of the 41 measurements and 12 valves, with units and analyser timing, in the correct valve order, and a short description of the plant's units. A source for `tags.csv` and `process_overview.md`.
- [FaultExplainer: Leveraging Large Language Models for Interpretable Fault Detection and Diagnosis](https://arxiv.org/abs/2412.14492) (Khan, Nahar, Chen, Constante Flores and Li, 2024) and its [code](https://github.com/li-group/FaultExplainer). The published work closest to this project: a language model explains faults of the same plant from a single prompt. Its prompt file (`backend/prompts.py`) holds a detailed description of the plant, used as a source for `process_overview.md`.

## The monitor and the baseline

- [Random forests](https://scikit-learn.org/stable/modules/ensemble.html#random-forests) (scikit-learn user guide) and the [`RandomForestClassifier` page](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html). What a random forest is (many decision trees grown on random parts of the examples, which vote) and its settings; the basis of baseline B2 in `src/plantagent/baseline/classifier.py`.
- [Analysis and generalization of fault diagnosis methods for process monitoring](https://doi.org/10.1016/j.jprocont.2010.10.005) (Alcala and Qin, 2011, Journal of Process Control). Gives the name "complete decomposition" to the way we split T² into one non-negative part per signal (`src/plantagent/monitor/contributions.py`). Only the abstract was read; that the parts add up to T² is checked by our own test.

## The plant data

- [Additional Tennessee Eastman Process Simulation Data for Anomaly Detection Evaluation](https://doi.org/10.7910/DVN/6C3JR1) (Rieth, Amsel, Tran and Cook, 2017, Harvard Dataverse). The recorded plant runs this project works on: normal runs and runs with each of 20 faults. Used to download the four data files and to check the facts we rely on (one sample every 3 minutes, run lengths, when each fault starts).
