"""
Base Agent class for all PydanticAI agents in the Archon system.

This provides common functionality and dependency injection for all agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
import asyncio
import logging

# Type variables for generic agent typing
DepsT = TypeVar('DepsT')
OutputT = TypeVar('OutputT')

logger = logging.getLogger(__name__)

@dataclass
class ArchonDependencies:
    """Base dependencies available to all Archon agents."""
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: datetime = None
    context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.context is None:
            self.context = {}

class BaseAgentOutput(BaseModel):
    """Base output model for all agent responses."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[list[str]] = None
    
class BaseAgent(ABC, Generic[DepsT, OutputT]):
    """
    Base class for all PydanticAI agents in the Archon system.
    
    Provides common functionality like:
    - Error handling and retries
    - Logging and monitoring
    - Standard dependency injection
    - Common tools and utilities
    """
    
    def __init__(
        self,
        model: str = "openai:gpt-4o",
        name: str = None,
        retries: int = 3,
        **agent_kwargs
    ):
        self.model = model
        self.name = name or self.__class__.__name__
        self.retries = retries
        
        # Initialize the PydanticAI agent
        self._agent = self._create_agent(**agent_kwargs)
        
        # Setup logging
        self.logger = logging.getLogger(f"agents.{self.name}")
        
    @abstractmethod
    def _create_agent(self, **kwargs) -> Agent:
        """Create and configure the PydanticAI agent. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent. Must be implemented by subclasses."""
        pass
    
    async def run(
        self, 
        user_prompt: str, 
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> OutputT:
        """
        Run the agent with the given prompt and dependencies.
        
        Args:
            user_prompt: The user's input prompt
            deps: Dependencies to inject into the agent
            **kwargs: Additional arguments to pass to the agent
            
        Returns:
            The structured output from the agent
        """
        try:
            self.logger.info(f"Running {self.name} agent with prompt: {user_prompt[:100]}...")
            
            result = await self._agent.run(
                user_prompt=user_prompt,
                deps=deps,
                **kwargs
            )
            
            self.logger.info(f"{self.name} agent completed successfully")
            return result.data
            
        except Exception as e:
            self.logger.error(f"Error in {self.name} agent: {str(e)}")
            raise
    
    def run_sync(
        self, 
        user_prompt: str, 
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> OutputT:
        """
        Synchronous wrapper for run method.
        
        Args:
            user_prompt: The user's input prompt
            deps: Dependencies to inject into the agent
            **kwargs: Additional arguments to pass to the agent
            
        Returns:
            The structured output from the agent
        """
        return asyncio.run(self.run(user_prompt, deps, **kwargs))
    
    def add_tool(self, func, **tool_kwargs):
        """
        Add a tool function to the agent.
        
        Args:
            func: The function to register as a tool
            **tool_kwargs: Additional arguments for the tool decorator
        """
        return self._agent.tool(**tool_kwargs)(func)
    
    def add_system_prompt_function(self, func):
        """
        Add a dynamic system prompt function to the agent.
        
        Args:
            func: The function to register as a system prompt
        """
        return self._agent.system_prompt(func)
    
    @property
    def agent(self) -> Agent:
        """Get the underlying PydanticAI agent instance."""
        return self._agent 
