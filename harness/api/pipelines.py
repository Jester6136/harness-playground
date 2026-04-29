"""Pipeline endpoints — /pipelines list + auto-registered POST /api/{name}."""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from harness.extensions.pipelines import PIPELINES, run_pipeline

router = APIRouter()


@router.get("/pipelines")
async def get_pipelines():
    """List registered pipelines and their input/output schemas."""
    return {
        "pipelines": [
            {
                "name": p.name,
                "description": p.description,
                "input_schema": p.input_model.model_json_schema(),
                "output_schema": p.output_model.model_json_schema(),
            }
            for p in PIPELINES.values()
        ]
    }


def register_pipeline_routes(app: FastAPI) -> None:
    """Mount POST /api/{pipeline_name} for every registered pipeline."""
    for pipeline_name in list(PIPELINES.keys()):
        name = pipeline_name  # capture by value

        async def pipeline_endpoint(request: Request, _name: str = name):
            body = await request.json()
            try:
                result = await run_pipeline(_name, body)
                return JSONResponse(content=result)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))

        app.add_api_route(
            f"/api/{name}",
            pipeline_endpoint,
            methods=["POST"],
            name=f"pipeline_{name}",
            summary=PIPELINES[name].description,
        )
