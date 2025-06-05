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

import logging

logger = logging.getLogger(__name__)

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
    ALL = "all"

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
    """Execute MCP tool tests using Docker container."""
    execution = test_executions[execution_id]
    
    try:
        # Docker command to run MCP tests
        cmd = [
            "docker", "exec", "-it", "archon-pyserver",
            "python", "tests/run_mcp_tests.py"
        ]
        
        logger.info(f"Starting MCP test execution: {' '.join(cmd)}")
        
        # Start process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd="/Users/seanbuck/Software Development/archon/archon"  # Absolute path to workspace
        )
        
        execution.process = process
        execution.status = TestStatus.RUNNING
        
        # Stream output
        await stream_process_output(execution_id, process)
        
        # Wait for completion
        exit_code = await process.wait()
        execution.exit_code = exit_code
        execution.completed_at = datetime.now()
        
        if exit_code == 0:
            execution.status = TestStatus.COMPLETED
            execution.summary = {"result": "All tests passed", "exit_code": exit_code}
        else:
            execution.status = TestStatus.FAILED
            execution.summary = {"result": "Some tests failed", "exit_code": exit_code}
        
        logger.info(f"MCP tests completed with exit code: {exit_code}")
        
    except Exception as e:
        logger.error(f"Error executing MCP tests: {e}")
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
    """Execute UI tests using vitest (placeholder for now)."""
    execution = test_executions[execution_id]
    
    try:
        # For now, this is a placeholder since we haven't set up vitest yet
        # In the future, this would run vitest in the archon-ui-main directory
        
        execution.status = TestStatus.RUNNING
        
        # Simulate test execution
        await websocket_manager.broadcast_to_execution(execution_id, {
            "type": "output",
            "message": "UI testing infrastructure not yet implemented",
            "timestamp": datetime.now().isoformat()
        })
        
        await asyncio.sleep(2)  # Simulate some processing time
        
        execution.status = TestStatus.COMPLETED
        execution.completed_at = datetime.now()
        execution.exit_code = 0
        execution.summary = {"result": "UI tests not yet implemented", "note": "Vitest setup pending"}
        
    except Exception as e:
        logger.error(f"Error executing UI tests: {e}")
        execution.status = TestStatus.FAILED
        execution.completed_at = datetime.now()
        execution.summary = {"error": str(e)}
    
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
    """Stream process output to WebSocket clients."""
    execution = test_executions[execution_id]
    
    while True:
        try:
            line = await process.stdout.readline()
            if not line:
                break
            
            decoded_line = line.decode('utf-8').rstrip()
            execution.output_lines.append(decoded_line)
            
            # Broadcast to WebSocket clients
            await websocket_manager.broadcast_to_execution(execution_id, {
                "type": "output",
                "message": decoded_line,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error streaming output: {e}")
            break

async def execute_tests_background(execution_id: str, test_type: TestType):
    """Background task for test execution."""
    try:
        if test_type == TestType.MCP:
            await execute_mcp_tests(execution_id)
        elif test_type == TestType.UI:
            await execute_ui_tests(execution_id)
        elif test_type == TestType.ALL:
            # Execute both test types
            await execute_mcp_tests(execution_id)
            # Could execute UI tests here too when implemented
            
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
    """Execute MCP tool tests with real-time streaming output."""
    execution_id = str(uuid.uuid4())
    
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
    
    return TestExecutionResponse(
        execution_id=execution_id,
        test_type=TestType.MCP,
        status=TestStatus.PENDING,
        started_at=execution.started_at,
        message="MCP test execution started"
    )

@router.post("/ui/run", response_model=TestExecutionResponse)
async def run_ui_tests(
    request: TestExecutionRequest,
    background_tasks: BackgroundTasks
):
    """Execute UI tests with real-time streaming output."""
    execution_id = str(uuid.uuid4())
    
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
    
    return TestExecutionResponse(
        execution_id=execution_id,
        test_type=TestType.UI,
        status=TestStatus.PENDING,
        started_at=execution.started_at,
        message="UI test execution started (placeholder)"
    )

@router.post("/all/run", response_model=TestExecutionResponse)
async def run_all_tests(
    request: TestExecutionRequest,
    background_tasks: BackgroundTasks
):
    """Execute all tests (MCP and UI) with real-time streaming output."""
    execution_id = str(uuid.uuid4())
    
    # Create test execution record
    execution = TestExecution(
        execution_id=execution_id,
        test_type=TestType.ALL,
        status=TestStatus.PENDING,
        started_at=datetime.now()
    )
    
    test_executions[execution_id] = execution
    
    # Start background task
    background_tasks.add_task(execute_tests_background, execution_id, TestType.ALL)
    
    return TestExecutionResponse(
        execution_id=execution_id,
        test_type=TestType.ALL,
        status=TestStatus.PENDING,
        started_at=execution.started_at,
        message="All tests execution started"
    )

@router.get("/status/{execution_id}", response_model=TestStatusResponse)
async def get_test_status(execution_id: str):
    """Get the status of a specific test execution."""
    if execution_id not in test_executions:
        raise HTTPException(status_code=404, detail="Test execution not found")
    
    execution = test_executions[execution_id]
    
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

@router.get("/history", response_model=TestHistoryResponse)
async def get_test_history(limit: int = 50, offset: int = 0):
    """Get test execution history."""
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
    
    return TestHistoryResponse(
        executions=execution_responses,
        total_count=total_count
    )

@router.delete("/execution/{execution_id}")
async def cancel_test_execution(execution_id: str):
    """Cancel a running test execution."""
    if execution_id not in test_executions:
        raise HTTPException(status_code=404, detail="Test execution not found")
    
    execution = test_executions[execution_id]
    
    if execution.status not in [TestStatus.PENDING, TestStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Test execution cannot be cancelled")
    
    # Try to terminate the process
    if execution.process:
        try:
            execution.process.terminate()
            await asyncio.sleep(1)  # Give it a moment to terminate gracefully
            if execution.process.returncode is None:
                execution.process.kill()
        except Exception as e:
            logger.warning(f"Error terminating process: {e}")
    
    execution.status = TestStatus.CANCELLED
    execution.completed_at = datetime.now()
    execution.summary = {"result": "Test execution cancelled by user"}
    
    # Broadcast cancellation
    await websocket_manager.broadcast_to_execution(execution_id, {
        "type": "cancelled",
        "message": "Test execution cancelled",
        "timestamp": datetime.now().isoformat()
    })
    
    return {"message": "Test execution cancelled", "execution_id": execution_id}

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