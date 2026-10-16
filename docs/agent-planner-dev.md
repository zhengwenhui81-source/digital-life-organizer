# Agent Planner configuration for Real Mode

The Agent HTTP API is available without a model, but a new task needs a planner.
Set these variables before starting `fileforge server` (or restart the server
after changing them).

## Team E2E mode without an LLM

In PowerShell:

```powershell
$env:FILEFORGE_AGENT_PLANNER_MODE = "demo"
fileforge server
```

Demo mode generates the same contract-shaped plan for each task: list the chosen
workspace, then propose creating `Agent_Dev_Demo_<task-id>` inside it. The task
pauses for approval and shows a `preview_id`. Approving creates only that empty
folder; rejecting leaves the workspace unchanged. This mode is for testing the
frontend, HTTP lifecycle, approval, and report flow. It does not interpret the
user's goal or build a materials package.

## OpenAI-compatible model endpoint

```powershell
$env:FILEFORGE_AGENT_PLANNER_MODE = "llm"
$env:FILEFORGE_AGENT_PLANNER_BASE_URL = "http://127.0.0.1:11434/v1"
$env:FILEFORGE_AGENT_PLANNER_MODEL = "qwen3-coder"
# Set only if the configured endpoint requires a key:
$env:FILEFORGE_AGENT_PLANNER_API_KEY = "your-key"
fileforge server
```

`llm` is the default mode. Its default endpoint is
`http://localhost:11434/v1`, with model `qwen3-coder`. Local loopback requests
bypass HTTP proxy environment settings; remote endpoints retain normal proxy
behavior. If the endpoint cannot be reached or returns an API error, the task
becomes `failed` and `TaskSnapshot.error` explains which model and base URL to
configure, or suggests demo mode. Task creation still returns `202`.
