"""
Code Storage Service

Handles extraction and storage of code examples from documents.
"""
import os
import re
import json
import asyncio
import time
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urlparse
from supabase import Client

from ...config.logfire_config import search_logger
from ..embeddings.embedding_service import create_embeddings_batch, create_embedding, create_embeddings_batch_async, create_embedding_async
from ..embeddings.contextual_embedding_service import generate_contextual_embeddings_batch
from ..llm_provider_service import get_llm_client_sync
from ..credential_service import credential_service


def _get_model_choice() -> str:
    """Get MODEL_CHOICE from credential service using proper methods (sync version)."""
    try:
        # Import the sync helper from llm_provider_service
        from ..llm_provider_service import _get_active_provider_sync
        
        provider_config = _get_active_provider_sync()
        model = provider_config["chat_model"]
        provider = provider_config["provider"]
        
        search_logger.debug(f"Using model from provider config: {model} with provider: {provider}")
        return model
    except Exception as e:
        search_logger.warning(f"Error getting provider config: {e}, using default")
        return "gpt-4.1-nano"


def _get_max_workers() -> int:
    """Get max workers from environment, defaulting to 3."""
    return int(os.getenv("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "3"))




def extract_code_blocks(markdown_content: str, min_length: int = None) -> List[Dict[str, Any]]:
    """
    Extract code blocks from markdown content along with context.
    
    Args:
        markdown_content: The markdown content to extract code blocks from
        min_length: Minimum length of code blocks to extract (default: 250 characters)
        
    Returns:
        List of dictionaries containing code blocks and their context
    """
    if min_length is None:
        # Try to get from settings, but fall back to 250 if not available
        try:
            from ...services.credential_service import get_credential_sync
            min_length = int(get_credential_sync('MIN_CODE_BLOCK_LENGTH', 250))
        except:
            min_length = 250  # Default to 250 for better code coverage
    
    search_logger.debug(f"Extracting code blocks with minimum length: {min_length} characters")
    code_blocks = []
    
    # Skip if content starts with triple backticks (edge case for files wrapped in backticks)
    content = markdown_content.strip()
    start_offset = 0
    
    # Check for corrupted markdown (entire content wrapped in code block)
    if content.startswith('```'):
        first_line = content.split('\n')[0] if '\n' in content else content[:10]
        # If it's ```K` or similar single-letter "language" followed by backtick, it's corrupted
        # This pattern specifically looks for ```K` or ```K` (with extra backtick)
        if re.match(r'^```[A-Z]`$', first_line):
            search_logger.warning(f"Detected corrupted markdown with fake language: {first_line}")
            # Try to find actual code blocks within the corrupted content
            # Look for nested triple backticks
            # Skip the outer ```K` and closing ```
            inner_content = content[5:-3] if content.endswith('```') else content[5:]
            # Now extract normally from inner content
            search_logger.info(f"Attempting to extract from inner content (length: {len(inner_content)})")
            return extract_code_blocks(inner_content, min_length)
        # For normal language identifiers (e.g., ```python, ```javascript), process normally
        # No need to skip anything - the extraction logic will handle it correctly
        start_offset = 0
    
    # Find all occurrences of triple backticks
    backtick_positions = []
    pos = start_offset
    while True:
        pos = markdown_content.find('```', pos)
        if pos == -1:
            break
        backtick_positions.append(pos)
        pos += 3
    
    # Process pairs of backticks
    i = 0
    while i < len(backtick_positions) - 1:
        start_pos = backtick_positions[i]
        end_pos = backtick_positions[i + 1]
        
        # Extract the content between backticks
        code_section = markdown_content[start_pos+3:end_pos]
        
        # Check if there's a language specifier on the first line
        lines = code_section.split('\n', 1)
        if len(lines) > 1:
            # Check if first line is a language specifier (no spaces, common language names)
            first_line = lines[0].strip()
            if first_line and not ' ' in first_line and len(first_line) < 20:
                language = first_line.lower()
                # Keep the code content with its original formatting (don't strip)
                code_content = lines[1] if len(lines) > 1 else ""
            else:
                language = ""
                # No language identifier, so the entire section is code
                code_content = code_section
        else:
            language = ""
            # Single line code block - keep as is
            code_content = code_section
        
        # Skip if code block is too short
        if len(code_content) < min_length:
            i += 2  # Move to next pair
            continue
        
        # Check if this is actually code or just documentation text
        # If no language specified, check content to determine if it's code
        if not language or language in ['text', 'plaintext', 'txt']:
            # Check if content looks like prose/documentation rather than code
            code_lower = code_content.lower()
            
            # Common indicators this is documentation, not code
            doc_indicators = [
                # Prose patterns
                ('this ', 'that ', 'these ', 'those ', 'the '),  # Articles
                ('is ', 'are ', 'was ', 'were ', 'will ', 'would '),  # Verbs
                ('to ', 'from ', 'with ', 'for ', 'and ', 'or '),  # Prepositions/conjunctions
                
                # Documentation specific
                'for example:', 'note:', 'warning:', 'important:',
                'description:', 'usage:', 'parameters:', 'returns:',
                
                # Sentence endings
                '. ', '? ', '! ',
            ]
            
            # Count documentation indicators
            doc_score = 0
            for indicator in doc_indicators:
                if isinstance(indicator, tuple):
                    # Check if multiple words from tuple appear
                    doc_score += sum(1 for word in indicator if word in code_lower)
                else:
                    if indicator in code_lower:
                        doc_score += 2
            
            # Calculate lines and check structure
            content_lines = code_content.split('\n')
            non_empty_lines = [line for line in content_lines if line.strip()]
            
            # If high documentation score relative to content size, skip
            words = code_content.split()
            if len(words) > 0:
                doc_ratio = doc_score / len(words)
                # If more than 10% of words are documentation indicators, likely not code
                if doc_ratio > 0.1:
                    search_logger.debug(f"Skipping documentation text disguised as code | doc_ratio={doc_ratio:.2f} | first_50_chars={repr(code_content[:50])}")
                    i += 2
                    continue
            
            # Additional check: if no typical code patterns found
            code_patterns = [
                '=', '(', ')', '{', '}', '[', ']', ';', 
                'function', 'def', 'class', 'import', 'export',
                'const', 'let', 'var', 'return', 'if', 'for',
                '->', '=>', '==', '!=', '<=', '>='
            ]
            
            code_pattern_count = sum(1 for pattern in code_patterns if pattern in code_content)
            if code_pattern_count < 3 and len(non_empty_lines) > 5:
                # Looks more like prose than code
                search_logger.debug(f"Skipping prose text | code_patterns={code_pattern_count} | lines={len(non_empty_lines)}")
                i += 2
                continue
        
        # Extract context before (1000 chars)
        context_start = max(0, start_pos - 1000)
        context_before = markdown_content[context_start:start_pos].strip()
        
        # Extract context after (1000 chars)
        context_end = min(len(markdown_content), end_pos + 3 + 1000)
        context_after = markdown_content[end_pos + 3:context_end].strip()
        
        # Add the extracted code block
        stripped_code = code_content.strip()
        code_blocks.append({
            'code': stripped_code,
            'language': language,
            'context_before': context_before,
            'context_after': context_after,
            'full_context': f"{context_before}\n\n{stripped_code}\n\n{context_after}"
        })
        
        # Move to next pair (skip the closing backtick we just processed)
        i += 2
    
    return code_blocks


def generate_code_example_summary(code: str, context_before: str, context_after: str, language: str = "", provider: str = None) -> Dict[str, str]:
    """
    Generate a summary and name for a code example using its surrounding context.
    
    Args:
        code: The code example
        context_before: Context before the code
        context_after: Context after the code
        language: The code language (if known)
        provider: Optional provider override
        
    Returns:
        A dictionary with 'summary' and 'example_name'
    """
    # Get model choice from credential service (RAG setting)
    model_choice = _get_model_choice()
    
    # Create the prompt
    prompt = f"""<context_before>
{context_before[-500:] if len(context_before) > 500 else context_before}
</context_before>

<code_example language="{language}">
{code[:1500] if len(code) > 1500 else code}
</code_example>

<context_after>
{context_after[:500] if len(context_after) > 500 else context_after}
</context_after>

Based on the code example and its surrounding context, provide:
1. A concise, action-oriented name (1-4 words) that describes what this code DOES, not what it is. Focus on the action or purpose.
   Good examples: "Parse JSON Response", "Validate Email Format", "Connect PostgreSQL", "Handle File Upload", "Sort Array Items", "Fetch User Data"
   Bad examples: "Function Example", "Code Snippet", "JavaScript Code", "API Code"
2. A summary (2-3 sentences) that describes what this code example demonstrates and its purpose

Format your response as JSON:
{{
  "example_name": "Action-oriented name (1-4 words)",
  "summary": "2-3 sentence description of what the code demonstrates"
}}
"""
    
    try:
        # Get LLM client using the provider service
        # Note: Sync version has limited provider support
        try:
            client = get_llm_client_sync()
        except Exception as e:
            search_logger.error(f"Failed to create LLM client: {e} - returning default values")
            return {
                "example_name": f"Code Example{f' ({language})' if language else ''}",
                "summary": "Code example for demonstration purposes."
            }
        
        search_logger.debug(f"Calling OpenAI API with model: {model_choice}, language: {language}, code length: {len(code)}")
        
        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes code examples and provides JSON responses with example names and summaries."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        response_content = response.choices[0].message.content.strip()
        search_logger.debug(f"OpenAI API response: {repr(response_content[:200])}...")
        
        result = json.loads(response_content)
        
        # Validate the response has the required fields
        if not result.get("example_name") or not result.get("summary"):
            search_logger.warning(f"Incomplete response from OpenAI: {result}")
        
        final_result = {
            "example_name": result.get("example_name", f"Code Example{f' ({language})' if language else ''}"),
            "summary": result.get("summary", "Code example for demonstration purposes.")
        }
        
        search_logger.info(f"Generated code example summary - Name: '{final_result['example_name']}', Summary length: {len(final_result['summary'])}")
        return final_result
    
    except json.JSONDecodeError as e:
        search_logger.error(f"Failed to parse JSON response from OpenAI: {e}, Response: {repr(response_content) if 'response_content' in locals() else 'No response'}")
        return {
            "example_name": f"Code Example{f' ({language})' if language else ''}",
            "summary": "Code example for demonstration purposes."
        }
    except Exception as e:
        search_logger.error(f"Error generating code example summary: {e}, Model: {model_choice}")
        return {
            "example_name": f"Code Example{f' ({language})' if language else ''}",
            "summary": "Code example for demonstration purposes."
        }


async def generate_code_summaries_batch(code_blocks: List[Dict[str, Any]], max_workers: int = 3, progress_callback = None) -> List[Dict[str, str]]:
    """
    Generate summaries for multiple code blocks with rate limiting and proper worker management.
    
    Args:
        code_blocks: List of code block dictionaries
        max_workers: Maximum number of concurrent API requests
        progress_callback: Optional callback for progress updates (async function)
        
    Returns:
        List of summary dictionaries
    """
    if not code_blocks:
        return []
    
    search_logger.info(f"Generating summaries for {len(code_blocks)} code blocks with max_workers={max_workers}")
    
    # Semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_workers)
    completed_count = 0
    lock = asyncio.Lock()
    
    async def generate_single_summary_with_limit(block: Dict[str, Any]) -> Dict[str, str]:
        nonlocal completed_count
        async with semaphore:
            # Add delay between requests to avoid rate limiting
            await asyncio.sleep(0.5)  # 500ms delay between requests
            
            # Run the synchronous function in a thread
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                generate_code_example_summary,
                block['code'],
                block['context_before'],
                block['context_after'],
                block.get('language', '')
            )
            
            # Update progress
            async with lock:
                completed_count += 1
                if progress_callback:
                    # Simple progress based on summaries completed
                    progress_percentage = int((completed_count / len(code_blocks)) * 100)
                    await progress_callback({
                        'status': 'code_extraction', 
                        'percentage': progress_percentage,
                        'log': f'Generated {completed_count}/{len(code_blocks)} code summaries',
                        'completed_summaries': completed_count,
                        'total_summaries': len(code_blocks)
                    })
            
            return result
    
    # Process all blocks concurrently but with rate limiting
    try:
        summaries = await asyncio.gather(
            *[generate_single_summary_with_limit(block) for block in code_blocks],
            return_exceptions=True
        )
        
        # Handle any exceptions in the results
        final_summaries = []
        for i, summary in enumerate(summaries):
            if isinstance(summary, Exception):
                search_logger.error(f"Error generating summary for code block {i}: {summary}")
                # Use fallback summary
                language = code_blocks[i].get('language', '')
                fallback = {
                    "example_name": f"Code Example{f' ({language})' if language else ''}",
                    "summary": "Code example for demonstration purposes."
                }
                final_summaries.append(fallback)
            else:
                final_summaries.append(summary)
        
        search_logger.info(f"Successfully generated {len(final_summaries)} code summaries")
        return final_summaries
    
    except Exception as e:
        search_logger.error(f"Error in batch summary generation: {e}")
        # Return fallback summaries for all blocks
        fallback_summaries = []
        for block in code_blocks:
            language = block.get('language', '')
            fallback = {
                "example_name": f"Code Example{f' ({language})' if language else ''}",
                "summary": "Code example for demonstration purposes."
            }
            fallback_summaries.append(fallback)
        return fallback_summaries


async def add_code_examples_to_supabase(
    client: Client,
    urls: List[str],
    chunk_numbers: List[int],
    code_examples: List[str],
    summaries: List[str],
    metadatas: List[Dict[str, Any]],
    batch_size: int = 20,
    url_to_full_document: Optional[Dict[str, str]] = None,
    progress_callback: Optional[Callable] = None,
    provider: Optional[str] = None
):
    """
    Add code examples to the Supabase code_examples table in batches.
    
    Args:
        client: Supabase client
        urls: List of URLs
        chunk_numbers: List of chunk numbers
        code_examples: List of code example contents
        summaries: List of code example summaries
        metadatas: List of metadata dictionaries
        batch_size: Size of each batch for insertion
        url_to_full_document: Optional mapping of URLs to full document content
        progress_callback: Optional async callback for progress updates
    """
    if not urls:
        return
        
    # Delete existing records for these URLs
    unique_urls = list(set(urls))
    for url in unique_urls:
        try:
            client.table('code_examples').delete().eq('url', url).execute()
        except Exception as e:
            search_logger.error(f"Error deleting existing code examples for {url}: {e}")
    
    # Check if contextual embeddings are enabled
    try:
        from ..credential_service import credential_service
        use_contextual_embeddings = credential_service._cache.get("USE_CONTEXTUAL_EMBEDDINGS")
        if isinstance(use_contextual_embeddings, str):
            use_contextual_embeddings = use_contextual_embeddings.lower() == "true"
        elif isinstance(use_contextual_embeddings, dict) and use_contextual_embeddings.get("is_encrypted"):
            # Handle encrypted value
            encrypted_value = use_contextual_embeddings.get("encrypted_value")
            if encrypted_value:
                try:
                    decrypted = credential_service._decrypt_value(encrypted_value)
                    use_contextual_embeddings = decrypted.lower() == "true"
                except:
                    use_contextual_embeddings = False
            else:
                use_contextual_embeddings = False
        else:
            use_contextual_embeddings = bool(use_contextual_embeddings)
    except:
        # Fallback to environment variable
        use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false").lower() == "true"
    
    search_logger.info(f"Using contextual embeddings for code examples: {use_contextual_embeddings}")
    
    # Process in batches
    total_items = len(urls)
    for i in range(0, total_items, batch_size):
        batch_end = min(i + batch_size, total_items)
        batch_texts = []
        batch_metadatas_for_batch = metadatas[i:batch_end]
        
        # Create combined texts for embedding (code + summary)
        combined_texts = []
        for j in range(i, batch_end):
            # Validate inputs
            code = code_examples[j] if isinstance(code_examples[j], str) else str(code_examples[j])
            summary = summaries[j] if isinstance(summaries[j], str) else str(summaries[j])
            
            if not code:
                search_logger.warning(f"Empty code at index {j}, skipping...")
                continue
                
            combined_text = f"{code}\n\nSummary: {summary}"
            combined_texts.append(combined_text)
        
        # Apply contextual embeddings if enabled
        if use_contextual_embeddings and url_to_full_document:
            # Get full documents for context
            full_documents = []
            for j in range(i, batch_end):
                url = urls[j]
                full_doc = url_to_full_document.get(url, "")
                full_documents.append(full_doc)
            
            # Generate contextual embeddings
            contextual_results = generate_contextual_embeddings_batch(full_documents, combined_texts)
            
            # Process results
            for j, (contextual_text, success) in enumerate(contextual_results):
                batch_texts.append(contextual_text)
                if success and j < len(batch_metadatas_for_batch):
                    batch_metadatas_for_batch[j]["contextual_embedding"] = True
        else:
            # Use original combined texts
            batch_texts = combined_texts
        
        # Create embeddings for the batch
        embeddings = await create_embeddings_batch_async(batch_texts, provider=provider)
        
        # Check if embeddings are valid (not all zeros)
        valid_embeddings = []
        for idx, embedding in enumerate(embeddings):
            if embedding and not all(v == 0.0 for v in embedding):
                valid_embeddings.append(embedding)
            else:
                search_logger.warning("Zero or invalid embedding detected, creating new one...")
                # Try to create a single embedding as fallback using async version
                single_embedding = await create_embedding_async(batch_texts[idx], provider=provider)
                valid_embeddings.append(single_embedding)
        
        # Prepare batch data
        batch_data = []
        for j, embedding in enumerate(valid_embeddings):
            idx = i + j
            
            # Extract source_id from URL
            parsed_url = urlparse(urls[idx])
            source_id = parsed_url.netloc or parsed_url.path
            
            batch_data.append({
                'url': urls[idx],
                'chunk_number': chunk_numbers[idx],
                'content': code_examples[idx],
                'summary': summaries[idx],
                'metadata': metadatas[idx],  # Store as JSON object, not string
                'source_id': source_id,
                'embedding': embedding
            })
        
        # Insert batch into Supabase with retry logic
        max_retries = 3
        retry_delay = 1.0
        
        for retry in range(max_retries):
            try:
                client.table('code_examples').insert(batch_data).execute()
                # Success - break out of retry loop
                break
            except Exception as e:
                if retry < max_retries - 1:
                    search_logger.warning(f"Error inserting batch into Supabase (attempt {retry + 1}/{max_retries}): {e}")
                    search_logger.info(f"Retrying in {retry_delay} seconds...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed
                    search_logger.error(f"Failed to insert batch after {max_retries} attempts: {e}")
                    # Optionally, try inserting records one by one as a last resort
                    search_logger.info("Attempting to insert records individually...")
                    successful_inserts = 0
                    for record in batch_data:
                        try:
                            client.table('code_examples').insert(record).execute()
                            successful_inserts += 1
                        except Exception as individual_error:
                            search_logger.error(f"Failed to insert individual record for URL {record['url']}: {individual_error}")
                    
                    if successful_inserts > 0:
                        search_logger.info(f"Successfully inserted {successful_inserts}/{len(batch_data)} records individually")

        search_logger.info(f"Inserted batch {i//batch_size + 1} of {(total_items + batch_size - 1)//batch_size} code examples")
        
        # Report progress if callback provided
        if progress_callback:
            batch_num = i//batch_size + 1
            total_batches = (total_items + batch_size - 1)//batch_size
            progress_percentage = int((batch_num / total_batches) * 100)
            await progress_callback({
                'status': 'code_storage',
                'percentage': progress_percentage,
                'log': f'Stored batch {batch_num}/{total_batches} of code examples',
                'batch_number': batch_num,
                'total_batches': total_batches
            })
    
    # Report final completion at 100% after all batches are done
    if progress_callback and total_items > 0:
        await progress_callback({
            'status': 'code_storage',
            'percentage': 100,
            'log': f'Code storage completed. Stored {total_items} code examples.',
            'total_items': total_items
        })