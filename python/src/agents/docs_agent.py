"""
DocsAgent for processing and validating project documentation.

This agent handles the creation, validation, and enhancement of project documentation
including PRDs, technical specs, feature plans, and other project documents.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from pydantic_ai.models import KnownModelName

from .base_agent import BaseAgent, ArchonDependencies
from ..modules.models import (
    ProjectRequirementsDocument, 
    GeneralDocument, 
    DocumentType,
    Goal,
    UserStory,
    TechnicalRequirement
)

class DocumentProcessingMode(str, Enum):
    """Different modes for document processing."""
    CREATE = "create"
    VALIDATE = "validate"
    ENHANCE = "enhance"
    REVIEW = "review"

@dataclass
class DocsDependencies(ArchonDependencies):
    """Dependencies for the DocsAgent."""
    project_title: Optional[str] = None
    existing_docs: Optional[List[Dict[str, Any]]] = None
    processing_mode: DocumentProcessingMode = DocumentProcessingMode.CREATE
    requirements: Optional[List[str]] = None
    context_data: Optional[Dict[str, Any]] = None

class DocumentOutput(BaseModel):
    """Structured output for document processing."""
    document_type: DocumentType
    title: str
    content: Dict[str, Any]
    validation_status: str = Field(description="Status of document validation")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in document quality")
    
class DocsAgent(BaseAgent[DocsDependencies, DocumentOutput]):
    """
    Specialized agent for processing project documentation.
    
    Capabilities:
    - Create comprehensive PRDs from basic requirements
    - Validate existing documentation for completeness
    - Enhance documentation with missing sections
    - Review and suggest improvements
    """
    
    def __init__(
        self,
        model: str = "openai:gpt-4o",
        name: str = "DocsAgent",
        retries: int = 3
    ):
        super().__init__(model=model, name=name, retries=retries)
        
    def _create_agent(self, **kwargs) -> Agent:
        """Create and configure the PydanticAI agent for document processing."""
        agent = Agent(
            model=self.model,
            deps_type=DocsDependencies,
            result_type=DocumentOutput,
            retries=self.retries,
            system_prompt=self.get_system_prompt(),
            **kwargs
        )
        
        # Register tools
        self._register_tools(agent)
        
        return agent
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for document processing."""
        return """
You are an expert technical writer and project analyst specializing in creating comprehensive project documentation.

Your responsibilities include:
1. **PRD Creation**: Transform basic project ideas into detailed Product Requirements Documents
2. **Documentation Validation**: Ensure all required sections are present and well-structured
3. **Content Enhancement**: Add missing details, improve clarity, and ensure completeness
4. **Quality Review**: Provide actionable suggestions for improvement

When processing documents:
- Follow industry best practices for technical documentation
- Ensure clarity, completeness, and actionability
- Structure content logically with proper hierarchy
- Include specific, measurable requirements when possible
- Consider technical feasibility and implementation complexity
- Maintain consistency in terminology and format

For PRDs specifically, ensure inclusion of:
- Clear project overview and objectives
- Detailed functional and non-functional requirements
- User stories with acceptance criteria
- Technical requirements and constraints
- Success metrics and KPIs
- Timeline and milestone considerations

Output Format: Always return a structured DocumentOutput with:
- Proper document type classification
- Clear, descriptive title
- Well-organized content in the specified schema
- Honest validation status
- Constructive suggestions for improvement
- Realistic confidence score
"""
    
    def _register_tools(self, agent: Agent):
        """Register tools for the docs agent."""
        
        @agent.tool
        async def analyze_existing_docs(
            ctx: RunContext[DocsDependencies],
            doc_type: str
        ) -> Dict[str, Any]:
            """Analyze existing project documents to understand current state."""
            if ctx.deps.existing_docs:
                matching_docs = [
                    doc for doc in ctx.deps.existing_docs 
                    if doc.get('document_type') == doc_type
                ]
                return {
                    "existing_count": len(matching_docs),
                    "docs": matching_docs,
                    "has_existing": len(matching_docs) > 0
                }
            return {"existing_count": 0, "docs": [], "has_existing": False}
        
        @agent.tool
        async def validate_document_structure(
            ctx: RunContext[DocsDependencies],
            content: Dict[str, Any],
            doc_type: str
        ) -> Dict[str, Any]:
            """Validate that a document has the required structure for its type."""
            validation_results = {
                "missing_sections": [],
                "incomplete_sections": [],
                "score": 0.0
            }
            
            if doc_type == "prd":
                required_sections = [
                    "overview", "goals", "user_stories", "functional_requirements",
                    "non_functional_requirements", "technical_requirements"
                ]
                
                total_sections = len(required_sections)
                present_sections = 0
                
                for section in required_sections:
                    if section not in content:
                        validation_results["missing_sections"].append(section)
                    elif not content.get(section):
                        validation_results["incomplete_sections"].append(section)
                    else:
                        present_sections += 1
                
                validation_results["score"] = present_sections / total_sections
            
            return validation_results
        
        @agent.tool
        async def generate_user_stories(
            ctx: RunContext[DocsDependencies],
            project_description: str,
            target_users: List[str]
        ) -> List[Dict[str, Any]]:
            """Generate user stories based on project description and target users."""
            # This would typically use the LLM to generate stories
            # For now, return a structured format
            stories = []
            for user_type in target_users:
                stories.append({
                    "user_type": user_type,
                    "story": f"As a {user_type}, I want to {project_description.lower()}",
                    "acceptance_criteria": [
                        "Feature is accessible and functional",
                        "User can complete the task successfully",
                        "Appropriate feedback is provided"
                    ]
                })
            return stories
        
        @agent.tool
        async def suggest_technical_requirements(
            ctx: RunContext[DocsDependencies],
            functional_requirements: List[str],
            project_type: str = "web_application"
        ) -> List[Dict[str, Any]]:
            """Suggest technical requirements based on functional requirements."""
            tech_requirements = []
            
            # Common technical requirements based on project type
            if project_type == "web_application":
                tech_requirements.extend([
                    {
                        "category": "Performance",
                        "requirement": "Page load time under 3 seconds",
                        "priority": "high"
                    },
                    {
                        "category": "Security",
                        "requirement": "HTTPS encryption for all data transmission",
                        "priority": "high"
                    },
                    {
                        "category": "Scalability",
                        "requirement": "Support for concurrent users",
                        "priority": "medium"
                    }
                ])
            
            return tech_requirements
    
    async def create_prd(
        self,
        project_title: str,
        project_description: str,
        requirements: List[str] = None,
        context: Dict[str, Any] = None
    ) -> DocumentOutput:
        """
        Create a comprehensive PRD from basic project information.
        
        Args:
            project_title: Title of the project
            project_description: Basic description of what the project should do
            requirements: List of specific requirements (optional)
            context: Additional context information (optional)
            
        Returns:
            DocumentOutput with the generated PRD
        """
        deps = DocsDependencies(
            project_title=project_title,
            processing_mode=DocumentProcessingMode.CREATE,
            requirements=requirements or [],
            context_data=context or {}
        )
        
        prompt = f"""
Create a comprehensive Product Requirements Document for the following project:

**Project Title**: {project_title}
**Description**: {project_description}

Additional Requirements:
{chr(10).join(f"- {req}" for req in (requirements or []))}

Please create a detailed PRD that includes:
1. Project overview and objectives
2. Specific goals with success metrics
3. User stories with acceptance criteria
4. Detailed functional requirements
5. Non-functional requirements (performance, security, etc.)
6. Technical requirements and constraints
7. Implementation considerations

Structure the output according to the ProjectRequirementsDocument schema.
"""
        
        return await self.run(prompt, deps)
    
    async def validate_document(
        self,
        document: Dict[str, Any],
        document_type: DocumentType
    ) -> DocumentOutput:
        """
        Validate an existing document for completeness and quality.
        
        Args:
            document: The document content to validate
            document_type: Type of document being validated
            
        Returns:
            DocumentOutput with validation results and suggestions
        """
        deps = DocsDependencies(
            processing_mode=DocumentProcessingMode.VALIDATE,
            existing_docs=[{"content": document, "document_type": document_type}]
        )
        
        prompt = f"""
Validate the following {document_type} document for completeness and quality:

{document}

Please analyze:
1. Structural completeness - are all required sections present?
2. Content quality - is the information clear and actionable?
3. Consistency - is terminology and format consistent throughout?
4. Technical feasibility - are requirements realistic and implementable?

Provide:
- Validation status (pass/fail/needs_improvement)
- Specific suggestions for improvement
- Confidence score for overall document quality
"""
        
        return await self.run(prompt, deps)
    
    async def enhance_document(
        self,
        document: Dict[str, Any],
        enhancement_areas: List[str]
    ) -> DocumentOutput:
        """
        Enhance an existing document by adding missing content or improving existing sections.
        
        Args:
            document: The document to enhance
            enhancement_areas: Specific areas to focus on for enhancement
            
        Returns:
            DocumentOutput with enhanced document content
        """
        deps = DocsDependencies(
            processing_mode=DocumentProcessingMode.ENHANCE,
            existing_docs=[{"content": document}],
            context_data={"enhancement_areas": enhancement_areas}
        )
        
        prompt = f"""
Enhance the following document by focusing on these areas:
{chr(10).join(f"- {area}" for area in enhancement_areas)}

Current document:
{document}

Please:
1. Add missing content in the specified areas
2. Improve clarity and detail where needed
3. Ensure consistency with existing content
4. Maintain the document's original structure and intent

Return the enhanced document with improvements clearly integrated.
"""
        
        return await self.run(prompt, deps) 