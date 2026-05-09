import asyncio

import typer
from fastapi import FastAPI, HTTPException
from loguru import logger

from app.graph.workflow import compliance_engine
from app.models.state import AuditState, SystemMetadata, new_audit_state
from app.services.ingestion import get_ingestion_service

app = FastAPI(
    title="LexGuardBE API",
    description="Automated EU AI Act Compliance Engine",
    version="1.0.0",
)

cli = typer.Typer()


@app.get("/")
async def root():
    return {"message": "LexGuardBE Engine Active", "target_deadline": "August 2026"}


@app.post("/audit")
async def run_audit(metadata: SystemMetadata):
    """
    Triggers the agentic compliance audit for a given AI system.
    """
    try:
        initial_state: AuditState = new_audit_state(
            description=metadata.description,
            system_metadata=metadata,
            is_ai_generated=metadata.is_ai_generated,
        )
        result = await compliance_engine.ainvoke(initial_state)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@cli.command()
def ingest(file_path: str, jurisdiction: str = "EU"):
    """
    Ingest a legal PDF into the Qdrant vector store.
    """
    logger.info(f"Starting ingestion for: {file_path} ({jurisdiction})")

    async def run():
        service = get_ingestion_service()
        chunks = await service.process_pdf(file_path, jurisdiction)
        await service.upload_to_qdrant(chunks)

    asyncio.run(run())


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] != "run":
        cli()
    else:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000)
