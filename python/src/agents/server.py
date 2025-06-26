"""
Agent Service FastAPI Server

This microservice handles all AI agent operations including document processing,
task analysis, and other CPU-intensive AI workloads. It's designed to scale
independently from the main API and MCP services.
"""

import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import agent modules
from .base_agent import BaseAgent
from .document_agent import DocumentAgent

# Import shared modules
from ..logfire_config import setup_logfire, api_logger
from ..credential_service import initialize_credentials
from ..utils import get_supabase_client
from ..config import ServiceDiscovery

# Request/Response models
class ProcessDocumentRequest(BaseModel):
    """Request model for document processing"""
    document_id: str
    operation: str = "analyze"  # analyze, summarize, extract
    options: Optional[Dict[str, Any]] = None

class ProcessDocumentResponse(BaseModel):
    """Response model for document processing"""
    document_id: str
    operation: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

class TaskAnalysisRequest(BaseModel):
    """Request model for task analysis"""
    task_id: str
    project_id: Optional[str] = None
    analysis_type: str = "full"  # full, quick, dependencies
    
class TaskAnalysisResponse(BaseModel):
    """Response model for task analysis"""
    task_id: str
    analysis_type: str
    status: str
    insights: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[str]] = None
    error: Optional[str] = None

class AgentHealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str = "archon-agents"
    version: str = "2.0.0"
    available_agents: List[str]
    active_tasks: int
    uptime_seconds: float

# Global variables
_startup_time: float = 0
_active_tasks: int = 0
_service_discovery: Optional[ServiceDiscovery] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global _startup_time, _service_discovery
    
    # Startup
    api_logger.info("🤖 Starting Archon Agent Service...")
    _startup_time = datetime.now().timestamp()
    
    try:
        # Initialize credentials
        await initialize_credentials()
        api_logger.info("✅ Credentials initialized")
        
        # Setup Logfire monitoring
        setup_logfire(service_name="archon-agents")
        api_logger.info("🔥 Logfire monitoring initialized")
        
        # Initialize service discovery
        _service_discovery = ServiceDiscovery()
        api_logger.info(f"🔍 Service discovery initialized: {_service_discovery.environment.value}")
        
        # Initialize Supabase client
        app.state.supabase = get_supabase_client()
        api_logger.info("✅ Database connection established")
        
        # Initialize agents
        app.state.document_agent = DocumentAgent()
        api_logger.info("✅ Document agent initialized")
        
        api_logger.info("🎉 Archon Agent Service started successfully!")
        
    except Exception as e:
        api_logger.error(f"❌ Failed to start agent service: {e}")
        raise
    
    yield
    
    # Shutdown
    api_logger.info("🛑 Shutting down Archon Agent Service...")
    # Cleanup tasks here if needed

# Create FastAPI application
app = FastAPI(
    title="Archon Agent Service",
    description="AI Agent microservice for document processing and task analysis",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "archon-agents",
        "version": "2.0.0",
        "description": "AI Agent microservice for Archon Knowledge Engine",
        "endpoints": {
            "health": "/health",
            "process_document": "/process-document",
            "analyze_task": "/analyze-task",
            "batch_process": "/batch-process"
        }
    }

# Health check endpoint
@app.get("/health", response_model=AgentHealthResponse)
async def health_check():
    """Health check endpoint"""
    global _startup_time, _active_tasks
    
    uptime = datetime.now().timestamp() - _startup_time
    
    return AgentHealthResponse(
        status="healthy",
        available_agents=["document", "task", "batch"],
        active_tasks=_active_tasks,
        uptime_seconds=uptime
    )

# Document processing endpoint
@app.post("/process-document", response_model=ProcessDocumentResponse)
async def process_document(
    request: ProcessDocumentRequest,
    background_tasks: BackgroundTasks
):
    """
    Process a document using AI agents.
    
    Operations:
    - analyze: Full document analysis
    - summarize: Generate document summary
    - extract: Extract specific information
    """
    global _active_tasks
    
    start_time = datetime.now()
    _active_tasks += 1
    
    try:
        # Get document agent
        document_agent: DocumentAgent = app.state.document_agent
        
        # Perform the requested operation
        if request.operation == "analyze":
            result = await document_agent.analyze_document(
                request.document_id,
                options=request.options
            )
        elif request.operation == "summarize":
            result = await document_agent.summarize_document(
                request.document_id,
                options=request.options
            )
        elif request.operation == "extract":
            result = await document_agent.extract_information(
                request.document_id,
                extraction_type=request.options.get("extraction_type", "entities")
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown operation: {request.operation}"
            )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ProcessDocumentResponse(
            document_id=request.document_id,
            operation=request.operation,
            status="completed",
            result=result,
            processing_time=processing_time
        )
        
    except Exception as e:
        api_logger.error(f"Document processing failed: {e}")
        return ProcessDocumentResponse(
            document_id=request.document_id,
            operation=request.operation,
            status="failed",
            error=str(e),
            processing_time=(datetime.now() - start_time).total_seconds()
        )
    finally:
        _active_tasks -= 1

# Task analysis endpoint
@app.post("/analyze-task", response_model=TaskAnalysisResponse)
async def analyze_task(request: TaskAnalysisRequest):
    """
    Analyze a task using AI to provide insights and recommendations.
    
    Analysis types:
    - full: Complete task analysis with dependencies and recommendations
    - quick: Quick analysis for immediate insights
    - dependencies: Focus on task dependencies and blockers
    """
    global _active_tasks
    _active_tasks += 1
    
    try:
        # This would integrate with your task analysis agent
        # For now, return a mock response
        
        insights = {
            "complexity": "medium",
            "estimated_hours": 8,
            "required_skills": ["python", "fastapi", "docker"],
            "potential_blockers": ["database schema changes", "API integration"],
            "dependencies": ["task-123", "task-456"]
        }
        
        recommendations = [
            "Break down into smaller subtasks",
            "Consider pair programming for complex sections",
            "Add integration tests for API endpoints"
        ]
        
        return TaskAnalysisResponse(
            task_id=request.task_id,
            analysis_type=request.analysis_type,
            status="completed",
            insights=insights,
            recommendations=recommendations
        )
        
    except Exception as e:
        api_logger.error(f"Task analysis failed: {e}")
        return TaskAnalysisResponse(
            task_id=request.task_id,
            analysis_type=request.analysis_type,
            status="failed",
            error=str(e)
        )
    finally:
        _active_tasks -= 1

# Batch processing endpoint
@app.post("/batch-process")
async def batch_process(
    documents: List[ProcessDocumentRequest],
    background_tasks: BackgroundTasks
):
    """
    Process multiple documents in batch for better efficiency.
    Returns a job ID for tracking progress.
    """
    job_id = f"batch-{datetime.now().timestamp()}"
    
    # Add batch processing to background tasks
    background_tasks.add_task(
        process_batch,
        job_id=job_id,
        documents=documents
    )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "document_count": len(documents),
        "message": "Batch processing started"
    }

async def process_batch(job_id: str, documents: List[ProcessDocumentRequest]):
    """Background task for batch processing"""
    api_logger.info(f"Starting batch processing job: {job_id}")
    
    # Process documents with controlled concurrency
    semaphore = asyncio.Semaphore(3)  # Process 3 documents at a time
    
    async def process_with_semaphore(doc: ProcessDocumentRequest):
        async with semaphore:
            return await process_document(doc, BackgroundTasks())
    
    tasks = [process_with_semaphore(doc) for doc in documents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    api_logger.info(f"Batch processing job completed: {job_id}")
    # Store results in database or cache for retrieval

# Inter-service communication endpoints
@app.get("/internal/status")
async def internal_status():
    """Internal status endpoint for service mesh health checks"""
    return {
        "service": "agents",
        "status": "ready",
        "connections": {
            "database": bool(app.state.supabase),
            "api_service": await _service_discovery.health_check("api"),
            "mcp_service": await _service_discovery.health_check("mcp")
        }
    }

# Metrics endpoint for Prometheus
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    global _active_tasks, _startup_time
    
    uptime = datetime.now().timestamp() - _startup_time
    
    # Return Prometheus format metrics
    return f"""# HELP archon_agents_active_tasks Number of active agent tasks
# TYPE archon_agents_active_tasks gauge
archon_agents_active_tasks {_active_tasks}

# HELP archon_agents_uptime_seconds Agent service uptime in seconds
# TYPE archon_agents_uptime_seconds counter
archon_agents_uptime_seconds {uptime}

# HELP archon_agents_info Agent service information
# TYPE archon_agents_info gauge
archon_agents_info{{version="2.0.0",service="archon-agents"}} 1
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8052,
        log_level="info"
    )