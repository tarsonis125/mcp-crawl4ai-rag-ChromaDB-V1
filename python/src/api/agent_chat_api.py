"""
Agent Chat API
Handles real-time chat conversations with AI agents using WebSocket streaming.
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..agents.docs_agent import DocsAgent
from ..utils import get_supabase_client

# Import logfire for comprehensive API logging  
from ..logfire_config import logfire
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Get the global crawling context from main.py (same pattern as knowledge_api)
def get_crawling_context():
    """Get the global crawling context from the app state."""
    from fastapi import Request
    import inspect
    
    # Try to get the context from the current request
    frame = inspect.currentframe()
    try:
        # Walk up the call stack to find the app instance
        while frame:
            if 'app' in frame.f_locals and hasattr(frame.f_locals['app'], 'state'):
                app = frame.f_locals['app']
                if hasattr(app.state, 'crawling_context'):
                    return app.state.crawling_context
            frame = frame.f_back
    finally:
        del frame
    
    # Fallback - import directly from main
    try:
        from ..main import crawling_context
        return crawling_context
    except ImportError:
        # Create a minimal context if we can't get the global one
        class MinimalContext:
            def __init__(self):
                self._initialized = False
                self.supabase_client = get_supabase_client()
            
            def create_context(self):
                """Create a context object that matches what MCP functions expect."""
                lifespan_context = type('LifespanContext', (), {
                    'supabase_client': self.supabase_client
                })()
                
                request_context = type('RequestContext', (), {
                    'lifespan_context': lifespan_context
                })()
                
                context = type('Context', (), {
                    'request_context': request_context
                })()
                
                return context
        return MinimalContext()

# Pydantic models for chat
class ChatMessage(BaseModel):
    id: str
    content: str
    sender: str  # 'user' or 'agent'
    timestamp: datetime
    agent_type: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    project_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ChatSession(BaseModel):
    session_id: str
    project_id: Optional[str]
    messages: List[ChatMessage]
    agent_type: str = "docs"
    created_at: datetime

# Chat Session Manager
class ChatSessionManager:
    """Manages chat sessions and WebSocket connections."""
    
    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.websockets: Dict[str, List[WebSocket]] = {}
        self._docs_agent = None
        
        # Add request queuing to prevent rate limit overload
        self._processing_lock = asyncio.Lock()
        self._request_queue = asyncio.Queue(maxsize=100)  # Limit queue size
        self._processing_requests = 0
        self._max_concurrent_requests = 3  # Limit concurrent OpenAI calls
        
        # Simple response cache to avoid repeat API calls
        self._response_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._max_cache_size = 100
    
    @property
    def docs_agent(self):
        """Lazy initialization of docs agent to avoid OpenAI key requirement at startup."""
        if self._docs_agent is None:
            print("DEBUG: Initializing DocsAgent...")
            # Set OpenAI API key from credential service before initializing agent
            import os
            from ..utils import get_openai_api_key_sync
            
            print("DEBUG: Getting OpenAI API key...")
            api_key = get_openai_api_key_sync()
            if api_key:
                print(f"DEBUG: Got API key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 8 else '***'}")
                os.environ['OPENAI_API_KEY'] = api_key
            else:
                print("DEBUG: No API key found!")
            
            print("DEBUG: Creating DocsAgent instance...")
            self._docs_agent = DocsAgent()
            print("DEBUG: DocsAgent created successfully")
        return self._docs_agent
    
    async def create_session(
        self, 
        project_id: Optional[str] = None,
        agent_type: str = "docs"
    ) -> str:
        """Create a new chat session."""
        session_id = str(uuid.uuid4())
        
        # Create welcome message
        welcome_message = ChatMessage(
            id=str(uuid.uuid4()),
            content="Hello! I'm your Documentation Assistant. I can help you create, review, and enhance project documents. What would you like to work on?",
            sender="agent",
            timestamp=datetime.now(),
            agent_type=agent_type
        )
        
        session = ChatSession(
            session_id=session_id,
            project_id=project_id,
            messages=[welcome_message],
            agent_type=agent_type,
            created_at=datetime.now()
        )
        
        self.sessions[session_id] = session
        return session_id
    
    async def add_websocket(self, session_id: str, websocket: WebSocket) -> None:
        """Add a WebSocket connection to a chat session."""
        if session_id not in self.websockets:
            self.websockets[session_id] = []
        
        self.websockets[session_id].append(websocket)
        print(f"DEBUG: WebSocket added. Total connections for {session_id}: {len(self.websockets[session_id])}")
        
        # Only send session history if this is a reconnection (not the first connection)
        # The frontend loads initial messages via getSession(), so we don't need to duplicate them
        if len(self.websockets[session_id]) > 1 and session_id in self.sessions:
            session = self.sessions[session_id]
            print(f"DEBUG: Sending session history for reconnection - {len(session.messages)} messages")
            for message in session.messages:
                message_data = message.model_dump()
                # Convert datetime objects to ISO format strings for JSON serialization
                for key, value in message_data.items():
                    if hasattr(value, 'isoformat'):
                        message_data[key] = value.isoformat()
                
                await websocket.send_json({
                    "type": "message",
                    "data": message_data
                })
        else:
            print(f"DEBUG: First WebSocket connection - not sending session history to avoid duplication")
    
    def remove_websocket(self, session_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if session_id in self.websockets:
            try:
                self.websockets[session_id].remove(websocket)
                if not self.websockets[session_id]:
                    del self.websockets[session_id]
            except ValueError:
                pass  # WebSocket not in list
    
    async def broadcast_message(self, session_id: str, message: ChatMessage) -> None:
        """Broadcast a message to all connected WebSockets for a session."""
        if session_id not in self.websockets:
            return
        
        # Convert message to dict and handle datetime serialization
        message_dict = message.model_dump()
        # Convert datetime objects to ISO format strings for JSON serialization
        for key, value in message_dict.items():
            if hasattr(value, 'isoformat'):
                message_dict[key] = value.isoformat()
        
        message_data = {
            "type": "message",
            "data": message_dict
        }
        
        disconnected = []
        for websocket in self.websockets[session_id]:
            try:
                await websocket.send_json(message_data)
            except:
                disconnected.append(websocket)
        
        # Clean up disconnected WebSockets
        for ws in disconnected:
            self.remove_websocket(session_id, ws)
    
    async def broadcast_typing(self, session_id: str, is_typing: bool = True) -> None:
        """Broadcast typing indicator to all connected WebSockets."""
        if session_id not in self.websockets:
            return
        
        typing_data = {
            "type": "typing",
            "data": {"is_typing": is_typing}
        }
        
        disconnected = []
        for websocket in self.websockets[session_id]:
            try:
                await websocket.send_json(typing_data)
            except:
                disconnected.append(websocket)
        
        # Clean up disconnected WebSockets
        for ws in disconnected:
            self.remove_websocket(session_id, ws)
    
    async def process_user_message(
        self, 
        session_id: str, 
        message_content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Process a user message and generate agent response."""
        print(f"DEBUG: Processing message '{message_content}' for session {session_id}")
        
        if session_id not in self.sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = self.sessions[session_id]
        print(f"DEBUG: Found session with agent_type: {session.agent_type}")
        
        # Add user message to session
        user_message = ChatMessage(
            id=str(uuid.uuid4()),
            content=message_content,
            sender="user",
            timestamp=datetime.now()
        )
        
        session.messages.append(user_message)
        await self.broadcast_message(session_id, user_message)
        
        # Check if we're at capacity and queue the request
        async with self._processing_lock:
            if self._processing_requests >= self._max_concurrent_requests:
                print(f"DEBUG: Rate limiting - queuing request for session {session_id}")
                await self.broadcast_typing(session_id, True)
                # Queue the request
                try:
                    await asyncio.wait_for(
                        self._request_queue.put((session_id, message_content, context)),
                        timeout=30.0  # Don't wait more than 30 seconds to queue
                    )
                    # Process queued requests
                    asyncio.create_task(self._process_queued_requests())
                    return
                except asyncio.TimeoutError:
                    error_message = ChatMessage(
                        id=str(uuid.uuid4()),
                        content="I'm currently handling many requests. Please try again in a moment.",
                        sender="agent",
                        timestamp=datetime.now(),
                        agent_type=session.agent_type
                    )
                    session.messages.append(error_message)
                    await self.broadcast_message(session_id, error_message)
                    return
            else:
                self._processing_requests += 1
        
        # Show typing indicator
        await self.broadcast_typing(session_id, True)
        
        try:
            await self._process_single_request(session_id, message_content, context)
        finally:
            # Always decrement the processing counter
            async with self._processing_lock:
                self._processing_requests = max(0, self._processing_requests - 1)
            
            # Process any queued requests
            if not self._request_queue.empty():
                asyncio.create_task(self._process_queued_requests())
    
    async def _process_queued_requests(self):
        """Process queued requests when capacity becomes available."""
        try:
            while not self._request_queue.empty():
                async with self._processing_lock:
                    if self._processing_requests >= self._max_concurrent_requests:
                        break  # Still at capacity
                    
                    try:
                        session_id, message_content, context = self._request_queue.get_nowait()
                        self._processing_requests += 1
                    except asyncio.QueueEmpty:
                        break
                
                # Process the queued request
                try:
                    print(f"DEBUG: Processing queued request for session {session_id}")
                    await self._process_single_request(session_id, message_content, context)
                except Exception as e:
                    print(f"Error processing queued request: {e}")
                finally:
                    async with self._processing_lock:
                        self._processing_requests = max(0, self._processing_requests - 1)
                        
        except Exception as e:
            print(f"Error in _process_queued_requests: {e}")
    
    async def _process_single_request(self, session_id: str, message_content: str, context: Optional[Dict[str, Any]] = None):
        """Process a single request (used for both immediate and queued requests)."""
        if session_id not in self.sessions:
            return
            
        session = self.sessions[session_id]
        
        try:
            # Process with agent
            if session.agent_type == "docs":
                print(f"DEBUG: Calling docs agent for message: {message_content}")
                response_content = await self._process_with_docs_agent(
                    message_content, 
                    session, 
                    context
                )
                print(f"DEBUG: Docs agent responded with: {response_content[:100]}...")
            else:
                response_content = "I'm not sure how to help with that. I'm currently specialized in documentation tasks."
            
            # Create agent response message
            agent_message = ChatMessage(
                id=str(uuid.uuid4()),
                content=response_content,
                sender="agent",
                timestamp=datetime.now(),
                agent_type=session.agent_type
            )
            
            session.messages.append(agent_message)
            
            # Stop typing indicator
            await self.broadcast_typing(session_id, False)
            
            # Send agent response
            await self.broadcast_message(session_id, agent_message)
            
        except Exception as e:
            # Stop typing indicator
            await self.broadcast_typing(session_id, False)
            
            # Send error message
            error_message = ChatMessage(
                id=str(uuid.uuid4()),
                content=f"I encountered an error processing your request: {str(e)}. Let me know how else I can help with your documentation needs.",
                sender="agent",
                timestamp=datetime.now(),
                agent_type=session.agent_type
            )
            
            session.messages.append(error_message)
            await self.broadcast_message(session_id, error_message)
    
    def _get_cache_key(self, message: str, session_id: str) -> str:
        """Generate cache key for message."""
        import hashlib
        key_data = f"{message.lower().strip()}:{session_id}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """Get cached response if available and not expired."""
        import time
        if cache_key in self._response_cache:
            cached_time, response = self._response_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                print(f"DEBUG: Using cached response for key: {cache_key[:8]}...")
                return response
            else:
                # Remove expired cache entry
                del self._response_cache[cache_key]
        return None
    
    def _cache_response(self, cache_key: str, response: str):
        """Cache a response with timestamp."""
        import time
        # Clean cache if too large
        if len(self._response_cache) >= self._max_cache_size:
            # Remove oldest entries (simple LRU-like behavior)
            oldest_keys = sorted(self._response_cache.keys(), 
                               key=lambda k: self._response_cache[k][0])[:10]
            for key in oldest_keys:
                del self._response_cache[key]
        
        self._response_cache[cache_key] = (time.time(), response)
        print(f"DEBUG: Cached response for key: {cache_key[:8]}...")

    async def _process_with_docs_agent(
        self,
        message: str,
        session: ChatSession,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process message with the simplified DocsAgent."""
        print(f"DEBUG: _process_with_docs_agent called with message: {message}")
        
        # Check cache first
        cache_key = self._get_cache_key(message, session.session_id)
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            return cached_response
        
        try:
            # Use the simplified DocsAgent - just run the message
            print(f"DEBUG: Using simplified DocsAgent for message: {message}")
            
            # First check if we should use streaming or regular response
            should_stream = session.session_id in self.websockets and len(self.websockets[session.session_id]) > 0
            
            if should_stream:
                print(f"DEBUG: Using streaming response for session {session.session_id}")
                accumulated_response = ""
                
                try:
                    async with self.docs_agent.run_stream(message, project_id=session.session_id) as response_stream:
                        async for chunk in response_stream:
                            if hasattr(chunk, 'delta') and chunk.delta:
                                accumulated_response += chunk.delta
                                # Send stream chunk via WebSocket
                                if session.session_id in self.websockets:
                                    for websocket in self.websockets[session.session_id]:
                                        try:
                                            await websocket.send_json({
                                                "type": "stream_chunk",
                                                "content": chunk.delta,
                                                "session_id": session.session_id
                                            })
                                        except:
                                            pass  # Handle disconnected websockets
                    
                    # Send completion signal
                    if session.session_id in self.websockets:
                        for websocket in self.websockets[session.session_id]:
                            try:
                                await websocket.send_json({
                                    "type": "stream_complete",
                                    "session_id": session.session_id
                                })
                            except:
                                pass
                    
                    response = accumulated_response
                    
                except Exception as stream_error:
                    print(f"DEBUG: Streaming failed, using regular response: {stream_error}")
                    response = await self.docs_agent.run(message, project_id=session.session_id)
            else:
                print(f"DEBUG: Using regular response (no active WebSocket)")
                response = await self.docs_agent.run(message, project_id=session.session_id)
            
            print(f"DEBUG: DocsAgent response: {response[:100]}...")
            
            # Cache the successful response
            self._cache_response(cache_key, response)
            return response
                           
        except Exception as e:
            print(f"Error in docs agent processing: {e}")
            import traceback
            traceback.print_exc()
            
            # Check if it's a rate limit error and provide appropriate message
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str or "request_limit" in error_str:
                return "I'm currently experiencing high demand. Please try again in a moment."
            else:
                return f"I encountered an error processing your request: {str(e)}. Let me know how else I can help with your documentation needs."

# Global session manager
chat_manager = ChatSessionManager()

# Create router
router = APIRouter(prefix="/api/agent-chat", tags=["agent-chat"])

@router.post("/sessions")
async def create_chat_session(
    project_id: Optional[str] = None,
    agent_type: str = "docs"
):
    """Create a new chat session with an agent."""
    with logfire.span("api_create_chat_session") as span:
        span.set_attribute("endpoint", "/api/agent-chat/sessions")
        span.set_attribute("method", "POST")
        span.set_attribute("agent_type", agent_type)
        if project_id:
            span.set_attribute("project_id", project_id)
        
        try:
            logfire.info("Creating new chat session", agent_type=agent_type, project_id=project_id)
            session_id = await chat_manager.create_session(project_id, agent_type)
            
            logfire.info("Chat session created successfully", session_id=session_id, agent_type=agent_type)
            span.set_attribute("session_id", session_id)
            
            return {
                "success": True,
                "session_id": session_id,
                "message": "Chat session created successfully"
            }
        except Exception as e:
            logfire.error("Failed to create chat session", error=str(e), agent_type=agent_type)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str):
    """Get chat session details."""
    if session_id not in chat_manager.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = chat_manager.sessions[session_id]
    return {
        "success": True,
        "session": session.model_dump()
    }

@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, request: ChatRequest):
    """Send a message to an agent in a chat session."""
    try:
        await chat_manager.process_user_message(
            session_id=session_id,
            message_content=request.message,
            context=request.context
        )
        return {
            "success": True,
            "message": "Message sent successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/sessions/{session_id}/ws")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat communication."""
    print(f"🔌 DEBUG: WebSocket connection attempt for session {session_id}")
    print(f"DEBUG: WebSocket headers: {websocket.headers}")
    
    try:
        print(f"DEBUG: About to accept WebSocket for session {session_id}")
        
        # CRITICAL: Accept WebSocket connection FIRST
        await websocket.accept()
        print(f"🚀 DEBUG: WebSocket accepted for session {session_id}")
        
        # Add to manager after accepting
        await chat_manager.add_websocket(session_id, websocket)
        print(f"✅ DEBUG: WebSocket registered for session {session_id}")
        
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection_confirmed",
            "data": {"session_id": session_id, "status": "connected"}
        })
        
        # Keep connection alive
        while True:
            try:
                # Wait for messages from client (like ping)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                print(f"📨 DEBUG: Received message from client: {message}")
                if message == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send heartbeat every 30 seconds
                print(f"💓 DEBUG: Sending heartbeat for session {session_id}")
                await websocket.send_json({"type": "heartbeat"})
            except WebSocketDisconnect:
                print(f"🔌 DEBUG: WebSocket disconnect received for session {session_id}")
                break
                
    except WebSocketDisconnect:
        print(f"❌ DEBUG: WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"💥 DEBUG: WebSocket error for session {session_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"🧹 DEBUG: Cleaning up WebSocket for session {session_id}")
        chat_manager.remove_websocket(session_id, websocket)

# Add new endpoint to monitor rate limiting status
@router.get("/status")
async def get_chat_status():
    """Get current chat system status including rate limiting info."""
    return {
        "success": True,
        "status": {
            "active_sessions": len(chat_manager.sessions),
            "active_websockets": sum(len(ws_list) for ws_list in chat_manager.websockets.values()),
            "processing_requests": chat_manager._processing_requests,
            "max_concurrent_requests": chat_manager._max_concurrent_requests,
            "queued_requests": chat_manager._request_queue.qsize(),
            "cached_responses": len(chat_manager._response_cache)
        }
    }

@router.get("/debug/token-usage")
async def debug_token_usage():
    """Debug endpoint to show simplified agent info."""
    return {
        "success": True,
        "info": {
            "agent_type": "simplified_pydantic_ai",
            "model": "openai:gpt-4o-mini",
            "features": [
                "Single agent instance",
                "No complex inheritance",
                "Direct PydanticAI usage",
                "Built-in rate limit handling"
            ]
        },
        "estimated_tokens": {
            "simple_chat": "~100 tokens (system prompt + message + tools)",
            "document_tasks": "~200-500 tokens (depending on complexity)",
            "previous_broken_version": "~900+ tokens (with complex schemas and inheritance)"
        }
    } 