import os
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


load_dotenv()

OPENFDA_BASE_URL = "https://api.fda.gov"
OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY")


app = FastAPI(
    title="OpenFDA MCP Server",
    description=(
        "MCP-compatible HTTP server exposing selected openFDA functionality as "
        "structured tools for use by agents (e.g., LangChain)."
    ),
    version="0.1.0",
)


class DrugAdverseEventsRequest(BaseModel):
    drug_name: str = Field(..., description="Name of the drug to search adverse events for.")
    limit: int = Field(5, ge=1, le=100, description="Maximum number of records to return.")
    skip: int = Field(0, ge=0, description="Number of records to skip (for pagination).")


class DrugLabelRequest(BaseModel):
    drug_name: str = Field(..., description="Name of the drug to look up label information for.")
    limit: int = Field(5, ge=1, le=100, description="Maximum number of records to return.")
    skip: int = Field(0, ge=0, description="Number of records to skip (for pagination).")


class DrugRecallsRequest(BaseModel):
    search_term: str = Field(..., description="Drug product name or keyword to search recall reports.")
    limit: int = Field(5, ge=1, le=100, description="Maximum number of records to return.")
    skip: int = Field(0, ge=0, description="Number of records to skip (for pagination).")


class FoodRecallsRequest(BaseModel):
    search_term: str = Field(..., description="Food product name or keyword to search recall reports.")
    limit: int = Field(5, ge=1, le=100, description="Maximum number of records to return.")
    skip: int = Field(0, ge=0, description="Number of records to skip (for pagination).")


async def call_openfda(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Helper to call the openFDA API with the configured API key.
    """
    if not OPENFDA_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENFDA_API_KEY is not configured. Set it in the .env file or environment.",
        )

    params = dict(params or {})
    params["api_key"] = OPENFDA_API_KEY

    url = f"{OPENFDA_BASE_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error connecting to openFDA: {exc}",
        ) from exc

    if response.status_code != 200:
        # Handle "no results" from openFDA gracefully so agents can react
        # without treating this as an error.
        if response.status_code == 404:
            return {
                "results": [],
                "message": "No matches found for your search query.",
            }

        # Pass through other openFDA error messages when available.
        try:
            error_body = response.json()
        except ValueError:
            error_body = response.text

        raise HTTPException(
            status_code=response.status_code,
            detail={"message": "openFDA returned an error", "body": error_body},
        )

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Invalid JSON received from openFDA.",
        ) from exc


@app.get("/health")
async def health() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    """
    return {
        "status": "ok",
        "openfda_api_key_loaded": bool(OPENFDA_API_KEY),
    }


@app.get("/tools")
async def list_tools() -> List[Dict[str, Any]]:
    """
    Returns a list of available tool definitions for MCP discovery.
    Each tool is described with a JSON Schema-like parameters object.
    """
    return [
        {
            "name": "drug_adverse_events",
            "description": "Searches drug adverse events by drug name using openFDA drug/event.",
            "method": "POST",
            "path": "/drug/adverse-events",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {
                        "type": "string",
                        "description": "Name of the drug to search adverse events for.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 5,
                        "description": "Maximum number of records to return.",
                    },
                    "skip": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Number of records to skip (for pagination).",
                    },
                },
                "required": ["drug_name"],
            },
        },
        {
            "name": "drug_label",
            "description": "Looks up drug label information including warnings, dosage, and interactions using openFDA drug/label.",
            "method": "POST",
            "path": "/drug/label",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {
                        "type": "string",
                        "description": "Name of the drug to look up label information for.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 5,
                        "description": "Maximum number of records to return.",
                    },
                    "skip": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Number of records to skip (for pagination).",
                    },
                },
                "required": ["drug_name"],
            },
        },
        {
            "name": "drug_recalls",
            "description": "Searches for drug recall enforcement reports using openFDA drug/enforcement.",
            "method": "POST",
            "path": "/drug/recalls",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Drug product name or keyword to search recall reports.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 5,
                        "description": "Maximum number of records to return.",
                    },
                    "skip": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Number of records to skip (for pagination).",
                    },
                },
                "required": ["search_term"],
            },
        },
        {
            "name": "food_recalls",
            "description": "Searches for food recall enforcement reports using openFDA food/enforcement.",
            "method": "POST",
            "path": "/food/recalls",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Food product name or keyword to search recall reports.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 5,
                        "description": "Maximum number of records to return.",
                    },
                    "skip": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Number of records to skip (for pagination).",
                    },
                },
                "required": ["search_term"],
            },
        },
    ]


@app.post("/drug/adverse-events")
async def drug_adverse_events(payload: DrugAdverseEventsRequest) -> Dict[str, Any]:
    """
    Searches drug adverse events by drug name via openFDA drug/event.
    """
    search = f"patient.drug.medicinalproduct:{payload.drug_name}"
    params = {"search": search, "limit": payload.limit, "skip": payload.skip}
    raw = await call_openfda("/drug/event.json", params=params)

    events = []
    for item in raw.get("results", []):
        patient = item.get("patient", {}) or {}
        drugs = patient.get("drug", []) or []
        reactions = patient.get("reaction", []) or []

        medicinal_products = sorted(
            {
                d.get("medicinalproduct")
                for d in drugs
                if isinstance(d, dict) and d.get("medicinalproduct")
            }
        )
        reaction_terms = sorted(
            {
                r.get("reactionmeddrapt")
                for r in reactions
                if isinstance(r, dict) and r.get("reactionmeddrapt")
            }
        )

        events.append(
            {
                "safetyreportid": item.get("safetyreportid"),
                "serious": item.get("serious"),
                "medicinal_products": medicinal_products,
                "reactions": reaction_terms,
            }
        )

    return {"results": events}


@app.post("/drug/label")
async def drug_label(payload: DrugLabelRequest) -> Dict[str, Any]:
    """
    Looks up drug label information including warnings, dosage and interactions via openFDA drug/label.
    """
    # Search both brand and generic names so queries like "Advil" and "ibuprofen" return results.
    search = f"(openfda.brand_name:{payload.drug_name} OR openfda.generic_name:{payload.drug_name})"
    params = {"search": search, "limit": payload.limit, "skip": payload.skip}
    raw = await call_openfda("/drug/label.json", params=params)

    labels = []
    for item in raw.get("results", []):
        openfda = item.get("openfda", {}) or {}
        labels.append(
            {
                "brand_name": openfda.get("brand_name"),
                "generic_name": openfda.get("generic_name"),
                "warnings": item.get("warnings"),
                "dosage_and_administration": item.get("dosage_and_administration"),
                "drug_interactions": item.get("drug_interactions"),
                "contraindications": item.get("contraindications"),
            }
        )

    return {"results": labels}


@app.post("/drug/recalls")
async def drug_recalls(payload: DrugRecallsRequest) -> Dict[str, Any]:
    """
    Searches for drug recall enforcement reports via openFDA drug/enforcement.
    """
    search = f"product_description:{payload.search_term}"
    params = {"search": search, "limit": payload.limit, "skip": payload.skip}
    raw = await call_openfda("/drug/enforcement.json", params=params)

    recalls = []
    for item in raw.get("results", []):
        recalls.append(
            {
                "recall_number": item.get("recall_number"),
                "recalling_firm": item.get("recalling_firm"),
                "product_description": item.get("product_description"),
                "reason_for_recall": item.get("reason_for_recall"),
                "status": item.get("status"),
                "recall_initiation_date": item.get("recall_initiation_date"),
            }
        )

    return {"results": recalls}


@app.post("/food/recalls")
async def food_recalls(payload: FoodRecallsRequest) -> Dict[str, Any]:
    """
    Searches for food recall enforcement reports via openFDA food/enforcement.
    """
    search = f"product_description:{payload.search_term}"
    params = {"search": search, "limit": payload.limit, "skip": payload.skip}
    raw = await call_openfda("/food/enforcement.json", params=params)

    recalls = []
    for item in raw.get("results", []):
        recalls.append(
            {
                "recall_number": item.get("recall_number"),
                "recalling_firm": item.get("recalling_firm"),
                "product_description": item.get("product_description"),
                "reason_for_recall": item.get("reason_for_recall"),
                "status": item.get("status"),
                "recall_initiation_date": item.get("recall_initiation_date"),
            }
        )

    return {"results": recalls}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

