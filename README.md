## Project overview

This project is an end‑to‑end AI assistant that uses the FDA database to answer questions about **food and drug recalls**, **medication risks and adverse events**, and **drug labels**.  
It combines:

- **MCP server**: wraps the openFDA REST API and exposes clean, discoverable tools.
- **Agent service**: a LangChain + Claude agent that calls those tools and synthesizes answers.
- **Frontend**: a React + Vite chat UI so users can ask FDA‑related questions in natural language.

## Architecture

- **MCP server (`mcp-server`)**
  - **Purpose**: Wraps the public openFDA API (`https://api.fda.gov`) and exposes a small set of **MCP-style tools**.
  - **Behavior**:
    - Adds the `api_key` query parameter from `OPENFDA_API_KEY`.
    - Trims the raw openFDA JSON down to **only the most relevant fields** for:
      - Drug adverse events
      - Drug labels
      - Drug recalls
      - Food recalls
    - Handles openFDA `404` responses gracefully by returning an empty `results` array with a friendly message.

- **Agent service (`agent`)**
  - **Purpose**: Receives natural language questions, chooses which MCP tools to call, and writes clear responses.
  - **Implementation**:
    - Uses **LangChain** with **Claude (Anthropic)** via `ChatAnthropic`.
    - Tools are defined as `StructuredTool` wrappers that call the MCP server’s HTTP endpoints.
    - Uses a **tool-calling agent** (`create_tool_calling_agent` + `AgentExecutor`) so the model can:
      - Decide *when* to call tools.
      - Decide *which* tool and parameters to call.
      - Combine tool outputs into final answers (often including markdown lists and headings).
    - Exposes a simple `POST /chat` endpoint that accepts:
      - `{"message": "user text here"}`
      - And returns `{"response": "agent reply here"}` as a plain string.

- **Frontend (`frontend`)**
  - **Purpose**: Browser-based chat interface for users.
  - **Implementation**:
    - Built with **React + Vite**.
    - Talks directly to the agent at `http://localhost:8001/chat`.
    - Renders agent responses as **markdown** (using `react-markdown`) for headings, bold text, and bullet/numbered lists.
    - Includes:
      - A modern dark-themed UI.
      - Typing indicator (three bouncing dots).
      - Tight, readable markdown list formatting inside the chat bubbles.

## API keys

- **openFDA API key**
  - **Where to get it**: `https://open.fda.gov/apis/authentication`
  - **Steps**:
    - Sign up / log in on the openFDA site.
    - Request an API key (free).
    - Copy the key into your `.env` file as `OPENFDA_API_KEY`.

- **Anthropic API key (Claude)**
  - **Where to get it**: `https://console.anthropic.com`
  - **Steps**:
    - Sign in to the Anthropic console.
    - Create an API key under the API keys section.
    - Copy the key into your `.env` file as `ANTHROPIC_API_KEY`.

There is a template at the project root:

- **`.env.example`** – copy this to `.env` and fill in the two keys.

## Local setup instructions (without Docker)

You can run the three services separately in development: **MCP server**, **agent**, and **frontend**.

### 1. MCP server (FastAPI + openFDA tools)

- **Windows (PowerShell)**:

```powershell
cd /path/to/fda-agent/mcp-server
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

- **macOS / Linux**:

```bash
cd /path/to/fda-agent/mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

This starts the MCP server at `http://localhost:8000`.

### 2. Agent service (FastAPI + LangChain + Claude)

Make sure your root `.env` (or `agent/.env` for local dev) has `ANTHROPIC_API_KEY` and that the MCP server is reachable (default `http://localhost:8000`).

- **Windows (PowerShell)**:

  **Note for Windows:** Run `pip install "numpy>=2.0.0"` before `pip install -r requirements.txt` to avoid a build error (e.g. missing C compiler for numpy wheels).

```powershell
cd /path/to/fda-agent/agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install "numpy>=2.0.0"
pip install -r requirements.txt
python main.py
```

- **macOS / Linux**:

```bash
cd /path/to/fda-agent/agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

This starts the agent at `http://localhost:8001` with a `POST /chat` endpoint.

### 3. Frontend (React + Vite)

Ensure the agent is running on `http://localhost:8001`.

- **Windows / macOS / Linux**:

```bash
cd /path/to/fda-agent/frontend
npm install
npm run dev
```

This starts the Vite dev server at `http://localhost:5173`.  
The frontend is already configured to call `http://localhost:8001/chat` by default.

## Docker instructions

You can run all three services together via **Docker Compose**.

- **Prerequisites**:
  - **Docker** and **Docker Compose** must be installed and running.
  - The root `.env` file must exist and contain:
    - `OPENFDA_API_KEY=...`
    - `ANTHROPIC_API_KEY=...`

- **Build and run all services**:

```bash
cd /path/to/fda-agent
docker compose up --build
```

This will:

- Build and run:
  - **`mcp-server`** on host port `8000`.
  - **`agent`** on host port `8001`.
  - **`frontend`** on host port `8080`.
- Wire the internal URLs so the agent talks to `mcp-server` via `http://mcp-server:8000`.

Once running:

- Open the UI at `http://localhost:8080`.
- The UI will call the agent at `http://localhost:8001/chat`, which in turn calls `mcp-server` for FDA data.

## Folder structure

High‑level structure of the project (excluding `node_modules` and build artifacts):

```text
fda-agent/
├─ .env.example             # Template for OPENFDA_API_KEY and ANTHROPIC_API_KEY
├─ docker-compose.yml       # Orchestrates mcp-server, agent, and frontend
├─ README.md                # This file
├─ .gitignore
├─ mcp-server/
│  ├─ main.py               # FastAPI MCP server wrapping openFDA
│  ├─ requirements.txt      # Python dependencies for MCP server
│  └─ Dockerfile            # Container for MCP server
├─ agent/
│  ├─ main.py               # FastAPI + LangChain + Claude agent
│  ├─ requirements.txt      # Python dependencies for agent
│  └─ Dockerfile            # Container for agent service
└─ frontend/
   ├─ package.json          # Frontend dependencies and scripts
   ├─ package-lock.json
   ├─ vite.config.js        # Vite config for React app
   ├─ index.html            # HTML entry for Vite
   ├─ Dockerfile            # Builds static bundle and serves via nginx
   ├─ nginx.conf            # nginx config for serving the SPA
   └─ src/
      ├─ main.jsx           # React entry point
      ├─ App.jsx            # Chat UI component
      └─ styles.css         # Styling for the chat interface
```

From this setup you can either:

- Run all three services locally via Python + Node, or
- Use `docker compose up --build` for a full containerized stack.

