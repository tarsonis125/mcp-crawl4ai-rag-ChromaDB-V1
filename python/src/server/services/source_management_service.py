"""
Source Management Service

Handles source metadata, summaries, and management.
"""
import os
from typing import List, Dict, Any, Tuple, Optional
import openai
from supabase import Client

from ..config.logfire_config import search_logger


def extract_source_summary(source_id: str, content: str, max_length: int = 500) -> str:
    """
    Extract a summary for a source from its content using an LLM.
    
    This function uses the OpenAI API to generate a concise summary of the source content.
    
    Args:
        source_id: The source ID (domain)
        content: The content to extract a summary from
        max_length: Maximum length of the summary
        
    Returns:
        A summary string
    """
    # Default summary if we can't extract anything meaningful
    default_summary = f"Content from {source_id}"
    
    if not content or len(content.strip()) == 0:
        return default_summary
    
    # Get the model choice from environment variables
    model_choice = os.getenv("MODEL_CHOICE")
    
    # Limit content length to avoid token limits
    truncated_content = content[:25000] if len(content) > 25000 else content
    
    # Create the prompt for generating the summary
    prompt = f"""<source_content>
{truncated_content}
</source_content>

The above content is from the documentation for '{source_id}'. Please provide a concise summary (3-5 sentences) that describes what this library/tool/framework is about. The summary should help understand what the library/tool/framework accomplishes and the purpose.
"""
    
    try:
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return default_summary
        
        client = openai.OpenAI(api_key=api_key)
        
        # Call the OpenAI API to generate the summary
        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise library/tool/framework summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        # Extract the generated summary
        summary = response.choices[0].message.content.strip()
        
        # Ensure the summary is not too long
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
            
        return summary
    
    except Exception as e:
        search_logger.error(f"Error generating summary with LLM for {source_id}: {e}. Using default summary.")
        return default_summary


def generate_source_title_and_metadata(
    source_id: str, 
    content: str, 
    knowledge_type: str = "technical", 
    tags: Optional[List[str]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate a user-friendly title and metadata for a source based on its content.
    
    Args:
        source_id: The source ID (domain)
        content: Sample content from the source
        knowledge_type: Type of knowledge (default: "technical")
        tags: Optional list of tags
        
    Returns:
        Tuple of (title, metadata)
    """
    # Default title is the source ID
    title = source_id
    
    # Try to generate a better title from content
    if content and len(content.strip()) > 100:
        try:
            # Get API key
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                client = openai.OpenAI(api_key=api_key)
                model_choice = os.getenv("MODEL_CHOICE", "gpt-4.1-nano")
                
                # Limit content for prompt
                sample_content = content[:3000] if len(content) > 3000 else content
                
                prompt = f"""Based on this content from {source_id}, generate a concise, descriptive title (3-6 words) that captures what this source is about:

{sample_content}

Provide only the title, nothing else."""
                
                response = client.chat.completions.create(
                    model=model_choice,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates concise titles."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=20
                )
                
                generated_title = response.choices[0].message.content.strip()
                # Clean up the title
                generated_title = generated_title.strip('"\'')
                if len(generated_title) < 50:  # Sanity check
                    title = generated_title
                    
        except Exception as e:
            search_logger.error(f"Error generating title for {source_id}: {e}")
    
    # Build metadata
    metadata = {
        "knowledge_type": knowledge_type,
        "tags": tags or [],
        "auto_generated": True
    }
    
    return title, metadata


def update_source_info(
    client: Client, 
    source_id: str, 
    summary: str, 
    word_count: int, 
    content: str = "", 
    knowledge_type: str = "technical", 
    tags: Optional[List[str]] = None, 
    update_frequency: int = 7
):
    """
    Update or insert source information in the sources table.
    
    Args:
        client: Supabase client
        source_id: The source ID (domain)
        summary: Summary of the source
        word_count: Total word count for the source
        content: Sample content for title generation
        knowledge_type: Type of knowledge
        tags: List of tags
        update_frequency: Update frequency in days
    """
    try:
        # Generate title and metadata
        title, metadata = generate_source_title_and_metadata(
            source_id, content, knowledge_type, tags
        )
        
        # Add update_frequency to metadata
        metadata["update_frequency"] = update_frequency
        
        # Try to update existing source
        result = client.table('sources').update({
            'title': title,
            'summary': summary,
            'total_word_count': word_count,
            'metadata': metadata,
            'updated_at': 'now()'
        }).eq('source_id', source_id).execute()
        
        # If no rows were updated, insert new source
        if not result.data:
            client.table('sources').insert({
                'source_id': source_id,
                'title': title,
                'summary': summary,
                'total_word_count': word_count,
                'metadata': metadata
            }).execute()
            search_logger.info(f"Created new source: {source_id}")
        else:
            search_logger.info(f"Updated source: {source_id}")
            
    except Exception as e:
        search_logger.error(f"Error updating source {source_id}: {e}")