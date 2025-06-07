"""
Simple DocsAgent using PydanticAI properly.
Lazy initialization to avoid OpenAI key issues at import time.
"""

import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

logger = logging.getLogger(__name__)

@dataclass
class DocsDependencies:
    """Simple dependencies for the DocsAgent."""
    project_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None

class DocsAgent:
    """Simple wrapper around PydanticAI agent with lazy initialization."""
    
    def __init__(self):
        self._agent = None
        
    def _ensure_agent(self):
        """Ensure the PydanticAI agent is initialized with proper OpenAI key."""
        if self._agent is None:
            # Set OpenAI API key from credential service before initializing agent
            try:
                from ..utils import get_openai_api_key_sync
                
                print("DEBUG: Getting OpenAI API key for DocsAgent...")
                api_key = get_openai_api_key_sync()
                if api_key:
                    print(f"DEBUG: Got API key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 8 else '***'}")
                    os.environ['OPENAI_API_KEY'] = api_key
                else:
                    print("DEBUG: No API key found!")
                    # Try fallback to environment
                    cached_openai_key = os.getenv("OPENAI_API_KEY")
                    if cached_openai_key:
                        print("DEBUG: Using cached OPENAI_API_KEY from environment")
                    else:
                        print("WARNING: No OpenAI API key available - DocsAgent will fail")
            except Exception as e:
                print(f"DEBUG: Error getting OpenAI API key: {e}")
                # Try fallback to environment
                cached_openai_key = os.getenv("OPENAI_API_KEY")
                if cached_openai_key:
                    print("DEBUG: Using cached OPENAI_API_KEY from environment")
                else:
                    print("WARNING: No OpenAI API key available - DocsAgent will fail")
            
            # Create the actual PydanticAI agent
            self._agent = Agent(
                model="openai:gpt-4o-mini",
                deps_type=DocsDependencies,
                system_prompt="""You are a helpful documentation assistant.

You help users with project documentation tasks including:
- Creating and reviewing documentation 
- Answering questions about documentation
- Providing guidance on best practices
- General conversation about documentation needs

Keep responses concise and helpful. For simple greetings like "hi", just respond naturally."""
            )
            
            # Add tools
            @self._agent.tool
            async def get_project_documents(ctx: RunContext[DocsDependencies], project_id: str) -> str:
                """Get existing project documents."""
                logger.info(f"Getting documents for project {project_id}")
                return f"Retrieved documents for project {project_id}"

            @self._agent.tool  
            async def create_document(ctx: RunContext[DocsDependencies], title: str, content: str) -> str:
                """Create a new document."""
                logger.info(f"Creating document: {title}")
                return f"Created document '{title}' with content length {len(content)}"
            
            print("DEBUG: DocsAgent PydanticAI agent initialized successfully")
        
        return self._agent
        
    async def run(self, message: str, project_id: Optional[str] = None, **kwargs) -> str:
        """Run the agent with a message."""
        agent = self._ensure_agent()
        
        deps = DocsDependencies(
            project_id=project_id,
            context=kwargs.get('context'),
            request_id=kwargs.get('request_id'),
            user_id=kwargs.get('user_id')
        )
        
        try:
            result = await agent.run(message, deps=deps)
            # Extract the actual data from PydanticAI result
            if hasattr(result, 'data'):
                return str(result.data)
            else:
                return str(result)
        except Exception as e:
            logger.error(f"DocsAgent error: {e}")
            if "request_limit" in str(e).lower():
                return "I'm experiencing high demand right now. Please try again in a moment."
            raise e
    
    async def run_stream(self, message: str, project_id: Optional[str] = None, **kwargs):
        """Run the agent with streaming."""
        agent = self._ensure_agent()
        
        deps = DocsDependencies(
            project_id=project_id,
            context=kwargs.get('context'),
            request_id=kwargs.get('request_id'),
            user_id=kwargs.get('user_id')
        )
        
        try:
            # PydanticAI streaming should work directly
            return agent.run_stream(message, deps=deps)
        except Exception as e:
            logger.error(f"DocsAgent stream error: {e}")
            if "request_limit" in str(e).lower():
                # For streaming errors, we need to handle differently
                raise Exception("I'm experiencing high demand right now. Please try again in a moment.")
            raise e 
