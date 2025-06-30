"""
Agents Service - Lightweight FastAPI server for PydanticAI agents

This service ONLY hosts PydanticAI agents. It does NOT contain:
- ML models or embeddings (those are in Server)
- Direct database access (use MCP tools)
- Business logic (that's in Server)

The agents use MCP tools for all data operations.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Import our PydanticAI agents
from .base_agent import BaseAgent
from .document_agent import DocumentAgent
from .rag_agent import RagAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Request/Response models
class AgentRequest(BaseModel):
    """Request model for agent interactions"""
    agent_type: str  # "document", "rag", etc.
    prompt: str
    context: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    """Response model for agent interactions"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# Agent registry
AVAILABLE_AGENTS = {
    "document": DocumentAgent,
    "rag": RagAgent,
}

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    logger.info("Starting Agents service...")
    
    # Initialize agents
    app.state.agents = {}
    for name, agent_class in AVAILABLE_AGENTS.items():
        try:
            app.state.agents[name] = agent_class()
            logger.info(f"Initialized {name} agent")
        except Exception as e:
            logger.error(f"Failed to initialize {name} agent: {e}")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Agents service...")

# Create FastAPI app
app = FastAPI(
    title="Archon Agents Service",
    description="Lightweight service hosting PydanticAI agents",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "agents",
        "agents_available": list(AVAILABLE_AGENTS.keys()),
        "note": "This service only hosts PydanticAI agents"
    }

@app.post("/agents/run", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """
    Run a specific agent with the given prompt.
    
    The agent will use MCP tools for any data operations.
    """
    try:
        # Get the requested agent
        if request.agent_type not in app.state.agents:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent type: {request.agent_type}"
            )
        
        agent = app.state.agents[request.agent_type]
        
        # Prepare dependencies for the agent
        deps = {
            "context": request.context or {},
            "options": request.options or {},
            "mcp_endpoint": os.getenv("MCP_SERVICE_URL", "http://archon-mcp:8051")
        }
        
        # Run the agent
        result = await agent.run(request.prompt, deps)
        
        return AgentResponse(
            success=True,
            result=result,
            metadata={
                "agent_type": request.agent_type,
                "model": agent.model
            }
        )
        
    except Exception as e:
        logger.error(f"Error running {request.agent_type} agent: {e}")
        return AgentResponse(
            success=False,
            error=str(e)
        )

@app.get("/agents/list")
async def list_agents():
    """List all available agents and their capabilities"""
    agents_info = {}
    
    for name, agent in app.state.agents.items():
        agents_info[name] = {
            "name": agent.name,
            "model": agent.model,
            "description": agent.__class__.__doc__ or "No description available",
            "available": True
        }
    
    return {
        "agents": agents_info,
        "total": len(agents_info)
    }

@app.post("/agents/{agent_type}/stream")
async def stream_agent(agent_type: str, request: AgentRequest):
    """
    Stream responses from an agent (for real-time interactions).
    
    Note: This is a placeholder for streaming functionality.
    """
    raise HTTPException(
        status_code=501,
        detail="Streaming not yet implemented"
    )

# Main entry point
if __name__ == "__main__":
    port = int(os.getenv("AGENTS_PORT", "8052"))
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False  # Disable reload in production
    )