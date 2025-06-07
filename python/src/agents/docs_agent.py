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
                system_prompt="""You are a proactive Documentation Assistant that helps users with their project documentation.

**Your approach:**
- When users ask about documents, projects, or what they have, IMMEDIATELY use your tools to look them up
- Don't ask for project IDs - use project names and search with your tools
- If someone mentions a project name (like "Archon Projects" or "The Archon Projects"), search for it right away
- Be helpful and actually retrieve information instead of asking for more details

**Available tools:**
- get_project_documents: Search for projects by name and list their documents
- show_project_document_details: Show detailed content of specific documents

**Examples:**
- User: "What docs do I have?" → Use get_project_documents() to show all projects
- User: "Docs for Archon Projects" → Use get_project_documents("Archon Projects") 
- User: "Show me the PRD" → Use show_project_document_details() to find PRD documents

Always try to be helpful by actually looking up information rather than asking for clarification."""
            )
            
            # Add tools that actually work with your system
            @self._agent.tool
            async def get_project_documents(ctx: RunContext[DocsDependencies], project_name: str = None) -> str:
                """Get existing project documents. Can search by project name or ID."""
                try:
                    from ..utils import get_supabase_client
                    supabase = get_supabase_client()
                    
                    if project_name:
                        # First try to find project by name
                        logger.info(f"Searching for project with name: {project_name}")
                        response = supabase.table("projects").select("*").ilike("title", f"%{project_name}%").execute()
                        
                        if response.data:
                            project = response.data[0]
                            docs = project.get("docs", [])
                            
                            if docs:
                                doc_list = []
                                for doc in docs:
                                    doc_list.append(f"- {doc.get('title', 'Untitled')} ({doc.get('document_type', 'unknown type')})")
                                
                                return f"Found project '{project['title']}' with {len(docs)} documents:\n" + "\n".join(doc_list)
                            else:
                                return f"Found project '{project['title']}' but it has no documents yet."
                        else:
                            # Try to list all projects
                            all_projects = supabase.table("projects").select("id, title").execute()
                            if all_projects.data:
                                project_list = [f"- {p['title']}" for p in all_projects.data[:10]]
                                return f"No project found matching '{project_name}'. Available projects:\n" + "\n".join(project_list)
                            else:
                                return "No projects found in the system."
                    else:
                        # List all projects if no specific name given
                        response = supabase.table("projects").select("id, title, docs").execute()
                        if response.data:
                            project_list = []
                            for project in response.data[:10]:  # Limit to first 10
                                doc_count = len(project.get("docs", []))
                                project_list.append(f"- {project['title']} ({doc_count} documents)")
                            
                            return f"Found {len(response.data)} projects:\n" + "\n".join(project_list)
                        else:
                            return "No projects found in the system."
                            
                except Exception as e:
                    logger.error(f"Error getting project documents: {e}")
                    return f"I encountered an error retrieving project documents: {str(e)}"

            @self._agent.tool  
            async def show_project_document_details(ctx: RunContext[DocsDependencies], project_name: str, document_title: str = None) -> str:
                """Show detailed content of a specific document in a project."""
                try:
                    from ..utils import get_supabase_client
                    supabase = get_supabase_client()
                    
                    # Find project by name
                    response = supabase.table("projects").select("*").ilike("title", f"%{project_name}%").execute()
                    
                    if not response.data:
                        return f"No project found matching '{project_name}'"
                    
                    project = response.data[0]
                    docs = project.get("docs", [])
                    
                    if not docs:
                        return f"Project '{project['title']}' has no documents."
                    
                    if document_title:
                        # Find specific document
                        matching_docs = [doc for doc in docs if document_title.lower() in doc.get('title', '').lower()]
                        if matching_docs:
                            doc = matching_docs[0]
                            content = doc.get('content', {})
                            return f"Document: {doc.get('title', 'Untitled')}\nType: {doc.get('document_type', 'unknown')}\nContent: {str(content)[:500]}..."
                        else:
                            return f"No document found matching '{document_title}' in project '{project['title']}'"
                    else:
                        # Show summary of all documents
                        doc_summaries = []
                        for doc in docs[:5]:  # Limit to first 5
                            title = doc.get('title', 'Untitled')
                            doc_type = doc.get('document_type', 'unknown')
                            doc_summaries.append(f"- {title} ({doc_type})")
                        
                        return f"Documents in '{project['title']}':\n" + "\n".join(doc_summaries)
                        
                except Exception as e:
                    logger.error(f"Error showing document details: {e}")
                    return f"I encountered an error retrieving document details: {str(e)}"
            
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
