import os
from fastapi import Body, FastAPI, HTTPException
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

app = FastAPI()

endpoint = os.environ["AIFOUNDRY_PROJECT_ENDPOINT"]
triage_agent_id = os.environ.get("TRIAGE_AGENT_ID")

cred = DefaultAzureCredential()
project_client = AIProjectClient(endpoint=endpoint, credential=cred)
agents_client = project_client.agents

@app.get("/")
def health():
    return {"status": "ok", "endpoint": endpoint, "triage_agent_id": triage_agent_id}

@app.post("/triage")
def triage(ticket: str = Body(..., embed=True)):
    if not triage_agent_id:
        raise HTTPException(status_code=500, detail="No triage agent configured. Set TRIAGE_AGENT_ID.")

    try:
        thread = agents_client.threads.create()
        agents_client.threads.messages.create(thread_id=thread.id, role="user", content=ticket)
        run = agents_client.threads.runs.create(thread_id=thread.id, agent_id=triage_agent_id)
    except Exception as exc:  # broad except to translate SDK failures into HTTP errors
        raise HTTPException(status_code=502, detail=f"Failed to triage ticket: {exc}") from exc

    return {"thread_id": thread.id, "run_id": run.id}
