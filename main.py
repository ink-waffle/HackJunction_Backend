from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
from services.openai_service import *

app = FastAPI()

# Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
openai_service = OpenAIService()

class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 100

@app.get("/")
async def root():
    return {"message": "API is running"}

@app.post("/api/completion")
async def get_completion(request: CompletionRequest):
    try:
        response = await openai_service.get_completion_structured(request.prompt)
        return {"result": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # This allows access from local network
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)