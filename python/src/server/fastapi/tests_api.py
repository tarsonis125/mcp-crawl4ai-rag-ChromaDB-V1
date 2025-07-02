"""
Test Execution API for Archon

Provides FastAPI endpoints for executing tests (pytest, vitest) with real-time streaming output.
Includes WebSocket streaming, background task management, and test result tracking.
"""
import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Removed direct logging import - using unified config

# Import logfire for comprehensive API logging
from ..config.logfire_config import logfire

from ..config.logfire_config import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/tests", tags=["tests"])

# Test execution status enum
class TestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Test type enum
class TestType(str, Enum):
    MCP = "mcp"
    UI = "ui"

# Pydantic models for API requests/responses
class TestExecutionRequest(BaseModel):
    test_type: TestType
    options: Optional[Dict[str, Any]] = {}

class TestExecutionResponse(BaseModel):
    execution_id: str
    test_type: TestType
    status: TestStatus
    started_at: datetime
    message: str

class TestStatusResponse(BaseModel):
    execution_id: str
    test_type: TestType
    status: TestStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    exit_code: Optional[int] = None
    summary: Optional[Dict[str, Any]] = None

class TestHistoryResponse(BaseModel):
    executions: List[TestStatusResponse]
    total_count: int

# Data classes for test execution tracking
@dataclass
class TestExecution:
    execution_id: str
    test_type: TestType
    status: TestStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    output_lines: List[str] = None
    summary: Optional[Dict[str, Any]] = None
    process: Optional[asyncio.subprocess.Process] = None
    
    def __post_init__(self):
        if self.output_lines is None:
            self.output_lines = []
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

# Global state for test executions
test_executions: Dict[str, TestExecution] = {}
active_websockets: Dict[str, List[WebSocket]] = {}

# WebSocket connection manager
class TestWebSocketManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, execution_id: str):
        await websocket.accept()
        if execution_id not in self.connections:
            self.connections[execution_id] = []
        self.connections[execution_id].append(websocket)
        logger.info(f"WebSocket connected for execution {execution_id}")
    
    def disconnect(self, websocket: WebSocket, execution_id: str):
        if execution_id in self.connections:
            self.connections[execution_id].remove(websocket)
            if not self.connections[execution_id]:
                del self.connections[execution_id]
        logger.info(f"WebSocket disconnected for execution {execution_id}")
    
    async def broadcast_to_execution(self, execution_id: str, message: dict):
        if execution_id in self.connections:
            disconnected = []
            for websocket in self.connections[execution_id]:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.append(websocket)
            
            # Remove disconnected websockets
            for ws in disconnected:
                self.disconnect(ws, execution_id)

websocket_manager = TestWebSocketManager()

# Test execution functions
async def execute_mcp_tests(execution_id: str) -> TestExecution:
    """Execute Python tests using pytest with real-time streaming."""
    execution = test_executions[execution_id]
    
    try:
        # Use pytest directly for all Python tests with verbose output and real-time streaming
        cmd = [
            "python", "-m", "pytest", 
            "-v",  # verbose output
            "-s",  # don't capture stdout, allows real-time output
            "--tb=short",  # shorter traceback format
            "tests/server/",  # run server tests specifically
            "--no-header",  # cleaner output
            "--disable-warnings"  # cleaner output
        ]
        
        logger.info(f"Starting Python test execution: {' '.join(cmd)}")
        
        # Start process with line buffering for real-time output
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd="/app",  # Use the app directory inside the container
            env={**os.environ, "PYTHONUNBUFFERED": "1"}  # Ensure unbuffered output
        )
        
        execution.process = process
        execution.status = TestStatus.RUNNING
        
        # Stream output in real-time
        await stream_process_output(execution_id, process)
        
        # Wait for completion
        exit_code = await process.wait()
        execution.exit_code = exit_code
        execution.completed_at = datetime.now()
        
        if exit_code == 0:
            execution.status = TestStatus.COMPLETED
            execution.summary = {"result": "All Python tests passed", "exit_code": exit_code}
        else:
            execution.status = TestStatus.FAILED
            execution.summary = {"result": "Some Python tests failed", "exit_code": exit_code}
        
        logger.info(f"Python tests completed with exit code: {exit_code}")
        
    except Exception as e:
        logger.error(f"Error executing Python tests: {e}")
        execution.status = TestStatus.FAILED
        execution.completed_at = datetime.now()
        execution.summary = {"error": str(e)}
        
        # Broadcast error
        await websocket_manager.broadcast_to_execution(execution_id, {
            "type": "error",
            "message": f"Test execution failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })
    
    # Broadcast completion
    await websocket_manager.broadcast_to_execution(execution_id, {
        "type": "completed",
        "status": execution.status.value,
        "exit_code": execution.exit_code,
        "summary": execution.summary,
        "timestamp": datetime.now().isoformat()
    })
    
    return execution

async def execute_ui_tests(execution_id: str) -> TestExecution:
    """Execute React UI tests using vitest in the frontend container."""
    execution = test_executions[execution_id]
    
    try:
        # Execute React tests inside the frontend container using docker exec
        # The frontend container has Node.js and all dependencies installed
        cmd = [
            "docker", "exec", "archon-frontend-1",
            "npm", "run", "test", 
            "--", 
            "--reporter=verbose",  # verbose output
            "--run"  # run once, don't watch
        ]
        
        logger.info(f"Starting React UI test execution: {' '.join(cmd)}")
        
        # Start process with line buffering for real-time output
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "DOCKER_HOST": "unix:///var/run/docker.sock"}
        )
        
        execution.process = process
        execution.status = TestStatus.RUNNING
        
        # Stream output in real-time
        await stream_process_output(execution_id, process)
        
        # Wait for completion
        exit_code = await process.wait()
        execution.exit_code = exit_code
        execution.completed_at = datetime.now()
        
        if exit_code == 0:
            execution.status = TestStatus.COMPLETED
            execution.summary = {"result": "All React UI tests passed", "exit_code": exit_code}
        else:
            execution.status = TestStatus.FAILED
            execution.summary = {"result": "Some React UI tests failed", "exit_code": exit_code}
        
        logger.info(f"React UI tests completed with exit code: {exit_code}")
        
    except Exception as e:
        logger.error(f"Error executing React UI tests: {e}")
        execution.status = TestStatus.FAILED
        execution.completed_at = datetime.now()
        execution.summary = {"error": str(e)}
        
        # Broadcast error
        await websocket_manager.broadcast_to_execution(execution_id, {
            "type": "error",
            "message": f"Test execution failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })
    
    # Broadcast completion
    await websocket_manager.broadcast_to_execution(execution_id, {
        "type": "completed",
        "status": execution.status.value,
        "exit_code": execution.exit_code,
        "summary": execution.summary,
        "timestamp": datetime.now().isoformat()
    })
    
    return execution

async def stream_process_output(execution_id: str, process: asyncio.subprocess.Process):
    """Stream process output to WebSocket clients with improved real-time handling."""
    execution = test_executions[execution_id]
    
    # Send initial status update
    await websocket_manager.broadcast_to_execution(execution_id, {
        "type": "status",
        "data": {"status": "running"},
        "message": "Test execution started",
        "timestamp": datetime.now().isoformat()
    })
    
    while True:
        try:
            # Use a timeout to prevent hanging
            line = await asyncio.wait_for(process.stdout.readline(), timeout=30.0)
            if not line:
                break
            
            decoded_line = line.decode('utf-8').rstrip()
            if decoded_line:  # Only add non-empty lines
                execution.output_lines.append(decoded_line)
                
                # Broadcast to WebSocket clients immediately
                await websocket_manager.broadcast_to_execution(execution_id, {
                    "type": "output",
                    "message": decoded_line,
                    "timestamp": datetime.now().isoformat()
                })
            
        except asyncio.TimeoutError:
            # Check if process is still alive
            if process.returncode is not None:
                break
            # Send heartbeat to keep connection alive
            await websocket_manager.broadcast_to_execution(execution_id, {
                "type": "status",
                "data": {"status": "running"},
                "message": "Tests still running...",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error streaming output: {e}")
            break

async def execute_tests_background(execution_id: str, test_type: TestType):
    """Background task for test execution - removed ALL type."""
    try:
        if test_type == TestType.MCP:
            await execute_mcp_tests(execution_id)
        elif test_type == TestType.UI:
            await execute_ui_tests(execution_id)
        else:
            raise ValueError(f"Unknown test type: {test_type}")
            
    except Exception as e:
        logger.error(f"Background test execution failed: {e}")
        execution = test_executions[execution_id]
        execution.status = TestStatus.FAILED
        execution.completed_at = datetime.now()
        execution.summary = {"error": str(e)}

# API Endpoints

@router.post("/mcp/run", response_model=TestExecutionResponse)
async def run_mcp_tests(
    request: TestExecutionRequest,
    background_tasks: BackgroundTasks
):
    """Execute Python tests using pytest with real-time streaming output."""
    execution_id = str(uuid.uuid4())
    
    logfire.info(f"Starting MCP test execution | execution_id={execution_id} | test_type=mcp")
    
    # Create test execution record
    execution = TestExecution(
        execution_id=execution_id,
        test_type=TestType.MCP,
        status=TestStatus.PENDING,
        started_at=datetime.now()
    )
    
    test_executions[execution_id] = execution
    
    # Start background task
    background_tasks.add_task(execute_tests_background, execution_id, TestType.MCP)
    
    logfire.info(f"MCP test execution queued successfully | execution_id={execution_id}")
    
    return TestExecutionResponse(
        execution_id=execution_id,
        test_type=TestType.MCP,
        status=TestStatus.PENDING,
        started_at=execution.started_at,
        message="Python test execution started"
    )

@router.post("/ui/run", response_model=TestExecutionResponse)
async def run_ui_tests(
    request: TestExecutionRequest,
    background_tasks: BackgroundTasks
):
    """Execute React UI tests using vitest with real-time streaming output."""
    execution_id = str(uuid.uuid4())
    
    logfire.info(f"Starting UI test execution | execution_id={execution_id} | test_type=ui")
    
    # Create test execution record
    execution = TestExecution(
        execution_id=execution_id,
        test_type=TestType.UI,
        status=TestStatus.PENDING,
        started_at=datetime.now()
    )
    
    test_executions[execution_id] = execution
    
    # Start background task
    background_tasks.add_task(execute_tests_background, execution_id, TestType.UI)
    
    logfire.info(f"UI test execution queued successfully | execution_id={execution_id}")
    
    return TestExecutionResponse(
        execution_id=execution_id,
        test_type=TestType.UI,
        status=TestStatus.PENDING,
        started_at=execution.started_at,
        message="React UI test execution started"
    )

@router.get("/status/{execution_id}", response_model=TestStatusResponse)
async def get_test_status(execution_id: str):
    """Get the status of a specific test execution."""
    try:
        logfire.info(f"Getting test execution status | execution_id={execution_id}")
        
        if execution_id not in test_executions:
            logfire.warning(f"Test execution not found | execution_id={execution_id}")
            raise HTTPException(status_code=404, detail="Test execution not found")
        
        execution = test_executions[execution_id]
        
        logfire.info(f"Test execution status retrieved | execution_id={execution_id} | status={execution.status} | test_type={execution.test_type}")
        
        return TestStatusResponse(
            execution_id=execution.execution_id,
            test_type=execution.test_type,
            status=execution.status,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            duration_seconds=execution.duration_seconds,
            exit_code=execution.exit_code,
            summary=execution.summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get test status | error={str(e)} | execution_id={execution_id}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=TestHistoryResponse)
async def get_test_history(limit: int = 50, offset: int = 0):
    """Get test execution history."""
    try:
        logfire.info(f"Getting test execution history | limit={limit} | offset={offset}")
        
        executions = list(test_executions.values())
        
        # Sort by started_at descending
        executions.sort(key=lambda x: x.started_at, reverse=True)
        
        # Apply pagination
        total_count = len(executions)
        paginated_executions = executions[offset:offset + limit]
        
        # Convert to response models
        execution_responses = [
            TestStatusResponse(
                execution_id=exec.execution_id,
                test_type=exec.test_type,
                status=exec.status,
                started_at=exec.started_at,
                completed_at=exec.completed_at,
                duration_seconds=exec.duration_seconds,
                exit_code=exec.exit_code,
                summary=exec.summary
            )
            for exec in paginated_executions
        ]
        
        logfire.info(f"Test execution history retrieved | total_count={total_count} | returned_count={len(execution_responses)}")
        
        return TestHistoryResponse(
            executions=execution_responses,
            total_count=total_count
        )
        
    except Exception as e:
        logfire.error(f"Failed to get test history | error={str(e)} | limit={limit} | offset={offset}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/execution/{execution_id}")
async def cancel_test_execution(execution_id: str):
    """Cancel a running test execution."""
    try:
        logfire.info(f"Cancelling test execution | execution_id={execution_id}")
        
        if execution_id not in test_executions:
            logfire.warning(f"Test execution not found for cancellation | execution_id={execution_id}")
            raise HTTPException(status_code=404, detail="Test execution not found")
        
        execution = test_executions[execution_id]
        
        if execution.status not in [TestStatus.PENDING, TestStatus.RUNNING]:
            logfire.warning(f"Test execution cannot be cancelled | execution_id={execution_id} | status={execution.status}")
            raise HTTPException(status_code=400, detail="Test execution cannot be cancelled")
        
        # Try to terminate the process
        if execution.process:
            try:
                execution.process.terminate()
                await asyncio.sleep(1)  # Give it a moment to terminate gracefully
                if execution.process.returncode is None:
                    execution.process.kill()
            except Exception as e:
                logfire.warning(f"Error terminating test process | error={str(e)} | execution_id={execution_id}")
        
        execution.status = TestStatus.CANCELLED
        execution.completed_at = datetime.now()
        execution.summary = {"result": "Test execution cancelled by user"}
        
        # Broadcast cancellation
        await websocket_manager.broadcast_to_execution(execution_id, {
            "type": "cancelled",
            "message": "Test execution cancelled",
            "timestamp": datetime.now().isoformat()
        })
        
        logfire.info(f"Test execution cancelled successfully | execution_id={execution_id}")
        
        return {"message": "Test execution cancelled", "execution_id": execution_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to cancel test execution | error={str(e)} | execution_id={execution_id}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint for real-time test output
@router.websocket("/stream/{execution_id}")
async def test_output_websocket(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for streaming test output in real-time."""
    await websocket_manager.connect(websocket, execution_id)
    
    try:
        # Send existing output if execution exists
        if execution_id in test_executions:
            execution = test_executions[execution_id]
            
            # Send current status
            await websocket.send_json({
                "type": "status",
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat(),
                "timestamp": datetime.now().isoformat()
            })
            
            # Send existing output lines
            for line in execution.output_lines:
                await websocket.send_json({
                    "type": "output",
                    "message": line,
                    "timestamp": datetime.now().isoformat()
                })
            
            # If execution is already completed, send completion message
            if execution.status in [TestStatus.COMPLETED, TestStatus.FAILED, TestStatus.CANCELLED]:
                await websocket.send_json({
                    "type": "completed",
                    "status": execution.status.value,
                    "exit_code": execution.exit_code,
                    "summary": execution.summary,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Keep connection alive until client disconnects
        while True:
            try:
                # Just wait for client messages (we don't expect any, but this keeps the connection alive)
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            
    except WebSocketDisconnect:
        pass
    finally:
        websocket_manager.disconnect(websocket, execution_id) 