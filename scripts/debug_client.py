from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

endpoint = "https://mafmbsqhfm5yfmu4ewmfky26tkhuksub.services.ai.azure.com/api/projects/mafmbsqhfm5yfmu4ewmfky26tkhukproj"

client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
print("client created")
print("agents:", list(client.agents.list_agents()))
thread = client.agents.threads.create()
print("thread created", thread.id)
