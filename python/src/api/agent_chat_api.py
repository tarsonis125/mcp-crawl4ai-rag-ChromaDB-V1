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

from ..agents.docs_agent import DocsAgent, DocsDependencies, DocumentProcessingMode
from ..utils import get_supabase_client

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
        
        # Show typing indicator
        await self.broadcast_typing(session_id, True)
        
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
                content=f"I encountered an error processing your request: {str(e)}",
                sender="agent",
                timestamp=datetime.now(),
                agent_type=session.agent_type
            )
            
            session.messages.append(error_message)
            await self.broadcast_message(session_id, error_message)
    
    async def _process_with_docs_agent(
        self,
        message: str,
        session: ChatSession,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process message with the DocsAgent using actual LLM conversation."""
        print(f"DEBUG: _process_with_docs_agent called with message: {message}")
        try:
            # Get project documents for context
            existing_docs = []
            if session.project_id:
                try:
                    # Get project documents directly from Supabase
                    supabase_client = get_supabase_client()
                    response = supabase_client.table("projects").select("docs").eq("id", session.project_id).execute()
                    if response.data:
                        existing_docs = response.data[0].get("docs", [])
                        print(f"DEBUG: Found {len(existing_docs)} existing documents in project")
                except Exception as e:
                    print(f"Could not fetch project documents: {e}")
            
            # Create dependencies with project context
            from ..agents.docs_agent import DocsDependencies, DocumentProcessingMode
            
            # Determine processing mode based on user intent
            message_lower = message.lower()
            if any(word in message_lower for word in ['create', 'generate', 'write', 'new']):
                mode = DocumentProcessingMode.CREATE
            elif any(word in message_lower for word in ['review', 'validate', 'check', 'analyze']):
                mode = DocumentProcessingMode.REVIEW
            elif any(word in message_lower for word in ['see', 'show', 'find', 'look', 'view', 'read']):
                mode = DocumentProcessingMode.REVIEW  # Reading is reviewing
            else:
                mode = DocumentProcessingMode.REVIEW  # Default to review for conversational queries
            
            deps = DocsDependencies(
                project_title=context.get('project_title', 'Archon Project') if context else 'Archon Project',
                existing_docs=existing_docs,
                processing_mode=mode,
                requirements=[message] if context else None,
                context_data=context or {}
            )
            
            print(f"DEBUG: Created dependencies with {len(existing_docs)} docs")
            print(f"DEBUG: Calling DocsAgent.run() with user message...")
            
            # Use the DocsAgent as an actual conversational LLM with streaming
            try:
                # First check if we should use streaming or regular response
                should_stream = session.id in self.websocket_connections and len(self.websocket_connections[session.id]) > 0
                
                if should_stream:
                    print(f"DEBUG: Using streaming response for session {session.id}")
                    # Use streaming with PydanticAI
                    accumulated_response = ""
                    
                    async with self.docs_agent.run_stream(user_prompt=message, deps=deps) as response_stream:
                        async for chunk in response_stream:
                            if hasattr(chunk, 'delta') and chunk.delta:
                                # Stream the delta to WebSocket clients
                                accumulated_response += chunk.delta
                                await self.broadcast_message(
                                    session.id,
                                    {
                                        "type": "stream_chunk",
                                        "content": chunk.delta,
                                        "session_id": session.id
                                    }
                                )
                        
                        # Get the final result
                        final_result = response_stream.get_result()
                        print(f"DEBUG: Streaming completed. Final result type: {type(final_result)}")
                        
                        # Send completion signal
                        await self.broadcast_message(
                            session.id,
                            {
                                "type": "stream_complete",
                                "session_id": session.id
                            }
                        )
                        
                        return accumulated_response or str(final_result)
                else:
                    print(f"DEBUG: Using regular response (no active WebSocket)")
                    result = await self.docs_agent.run(
                        user_prompt=message,
                        deps=deps
                    )
                    
                    print(f"DEBUG: DocsAgent returned result type: {type(result)}")
                    
                    # Handle the result based on its type
                    if hasattr(result, 'content') and isinstance(result.content, str):
                        response = result.content
                    elif hasattr(result, 'content') and isinstance(result.content, dict):
                        # If it's a document output, format it nicely
                        doc_type = result.document_type if hasattr(result, 'document_type') else 'document'
                        title = result.title if hasattr(result, 'title') else 'Generated Document'
                        confidence = result.confidence_score if hasattr(result, 'confidence_score') else 0.0
                        
                        response = f"I've created a {doc_type} titled '{title}' based on your request.\n\n"
                        response += f"Confidence Score: {confidence:.1%}\n\n"
                        
                        if hasattr(result, 'suggestions') and result.suggestions:
                            response += "Key insights:\n" + "\n".join([f"• {s}" for s in result.suggestions[:5]])
                    else:
                        response = str(result)
                    
                    print(f"DEBUG: Formatted response: {response[:100]}...")
                    return response
                    
            except Exception as stream_error:
                print(f"DEBUG: Streaming failed, falling back to regular response: {stream_error}")
                # Fallback to regular response
                result = await self.docs_agent.run(
                    user_prompt=message,
                    deps=deps
                )
                return str(result)
                           
        except Exception as e:
            print(f"Error in docs agent processing: {e}")
            import traceback
            traceback.print_exc()
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
    try:
        session_id = await chat_manager.create_session(project_id, agent_type)
        return {
            "success": True,
            "session_id": session_id,
            "message": "Chat session created successfully"
        }
    except Exception as e:
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
    try:
        print(f"DEBUG: WebSocket connecting for session {session_id}")
        
        # CRITICAL: Accept WebSocket connection FIRST
        await websocket.accept()
        print(f"DEBUG: WebSocket accepted for session {session_id}")
        
        # Add to manager after accepting
        await chat_manager.add_websocket(session_id, websocket)
        print(f"DEBUG: WebSocket registered for session {session_id}")
        
        # Keep connection alive
        while True:
            try:
                # Wait for messages from client (like ping)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if message == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send heartbeat every 30 seconds
                await websocket.send_json({"type": "heartbeat"})
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        print(f"DEBUG: WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"DEBUG: WebSocket error for session {session_id}: {e}")
    finally:
        chat_manager.remove_websocket(session_id, websocket) 