"""
Agents module for PydanticAI-powered agents in the Archon system.

This module contains various specialized agents for different tasks:
- DocsAgent: Processes and validates project documentation
- PlanningAgent: Generates feature plans and technical specifications 
- ERDAgent: Creates entity relationship diagrams
- TaskAgent: Generates and manages project tasks

All agents are built using PydanticAI for type safety and structured outputs.
"""

from .docs_agent import DocsAgent
from .base_agent import BaseAgent

__all__ = ['BaseAgent', 'DocsAgent'] 
