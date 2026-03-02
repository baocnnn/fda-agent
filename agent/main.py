import json
import os
from typing import Any, Dict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    # Preferred modern imports (LangChain 0.3+ / 1.x)
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except ImportError:  # pragma: no cover - fallback for older layouts
    # Fallback: AgentExecutor still exposed from langchain.agents,
    # create_tool_calling_agent lives in the tool_calling_agent submodule.
    from langchain.agents import AgentExecutor  # type: ignore
    from langchain.agents.tool_calling_agent.base import (  # type: ignore
        create_tool_calling_agent,
    )

from langchain.tools import StructuredTool
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


load_dotenv()

MCP_SERVER_BASE_URL = os.getenv("MCP_SERVER_BASE_URL", "http://localhost:8000").rstrip("/")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


app = FastAPI(
    title="OpenFDA LangChain Agent",
    description=(
        "FastAPI service exposing a LangChain-powered agent using Claude. "
        "The agent has tools that call the OpenFDA MCP server."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., description="User's natural language question or instruction.")


def _call_mcp(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper to call the MCP server with the given path and JSON payload.
    """
    url = f"{MCP_SERVER_BASE_URL}{path}"
    try:
        response = httpx.post(url, json=payload, timeout=30.0)
    except httpx.RequestError as exc:
        raise RuntimeError(f"Error calling MCP server at {url}: {exc}") from exc

    if response.status_code != 200:
        try:
            body = response.json()
        except ValueError:
            body = response.text
        raise RuntimeError(
            f"MCP server returned status {response.status_code}: {body}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Invalid JSON response from MCP server") from exc


def _extract_text(output: Any) -> str:
    """
    Normalize various LangChain / LLM output shapes into a plain string.

    Handles cases where the output is already a string, a list of message-like
    dicts with 'text' or 'content' fields, or other JSON-serializable forms.
    """
    # Already a plain string
    if isinstance(output, str):
        return output

    # List of items (e.g., messages)
    if isinstance(output, list):
        parts = []
        for item in output:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n\n".join(parts)
        return ""

    # Single dict with text/content
    if isinstance(output, dict):
        text = output.get("text") or output.get("content")
        if isinstance(text, str):
            return text

    # Fallback: best-effort string conversion
    return str(output)


def tool_drug_adverse_events(drug_name: str, limit: int = 10, skip: int = 0) -> str:
    """
    Look up adverse events (side effects, safety reports) for a specific drug
    using the MCP server's /drug/adverse-events tool.
    """
    data = {
        "drug_name": drug_name,
        "limit": limit,
        "skip": skip,
    }
    result = _call_mcp("/drug/adverse-events", data)
    return json.dumps(result)


def tool_drug_label(drug_name: str, limit: int = 10, skip: int = 0) -> str:
    """
    Retrieve drug label information (warnings, dosage, interactions) for a
    specific drug using the MCP server's /drug/label tool.
    """
    data = {
        "drug_name": drug_name,
        "limit": limit,
        "skip": skip,
    }
    result = _call_mcp("/drug/label", data)
    return json.dumps(result)


def tool_drug_recalls(search_term: str, limit: int = 10, skip: int = 0) -> str:
    """
    Search for drug recall enforcement reports using the MCP server's
    /drug/recalls tool.
    """
    data = {
        "search_term": search_term,
        "limit": limit,
        "skip": skip,
    }
    result = _call_mcp("/drug/recalls", data)
    return json.dumps(result)


def tool_food_recalls(search_term: str, limit: int = 10, skip: int = 0) -> str:
    """
    Search for food recall enforcement reports using the MCP server's
    /food/recalls tool.
    """
    data = {
        "search_term": search_term,
        "limit": limit,
        "skip": skip,
    }
    result = _call_mcp("/food/recalls", data)
    return json.dumps(result)


tools = [
    StructuredTool.from_function(
        name="drug_adverse_events",
        func=tool_drug_adverse_events,
        description=(
            "Use this tool to look up adverse events and safety reports for a "
            "specific drug name via the OpenFDA MCP server."
        ),
    ),
    StructuredTool.from_function(
        name="drug_label",
        func=tool_drug_label,
        description=(
            "Use this tool to retrieve drug label information including "
            "warnings, dosage, and interactions for a given drug name via the "
            "OpenFDA MCP server."
        ),
    ),
    StructuredTool.from_function(
        name="drug_recalls",
        func=tool_drug_recalls,
        description=(
            "Use this tool to search for drug recall enforcement reports using "
            "a product name or keyword via the OpenFDA MCP server."
        ),
    ),
    StructuredTool.from_function(
        name="food_recalls",
        func=tool_food_recalls,
        description=(
            "Use this tool to search for food recall enforcement reports using "
            "a product name or keyword via the OpenFDA MCP server."
        ),
    ),
]


llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    temperature=0.0,
)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are an assistant that helps users explore FDA safety, label, "
                "and recall information. When helpful, call the provided tools to "
                "retrieve precise data from the OpenFDA MCP server before answering. "
                "Response formatting: never use headers (##, ###, or any heading levels) "
                "in your responses. Use only simple bullet points or numbered lists—"
                "never nested lists. Keep responses concise and flat in structure. "
                "Bold key terms with **term** when helpful, but avoid all heading levels. "
                "Always explain your answers in clear, concise language."
            ),
        ),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)


@app.get("/health")
def health() -> Dict[str, Any]:
    """
    Basic health endpoint for the agent service.
    """
    return {
        "status": "ok",
        "mcp_server_base_url": MCP_SERVER_BASE_URL,
        "anthropic_api_key_loaded": bool(ANTHROPIC_API_KEY),
        "tools": [tool.name for tool in tools],
    }


@app.post("/chat")
def chat(request: ChatRequest) -> Dict[str, Any]:
    """
    Chat endpoint that sends the user's message to a LangChain agent
    powered by Claude with tools that call the OpenFDA MCP server.

    The response is always returned as a plain string, even if the
    underlying agent output is a list of message objects.
    """
    try:
        result = agent_executor.invoke({"input": request.message})
        raw_output = result.get("output", "")
        response_text = _extract_text(raw_output)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"response": response_text}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)

