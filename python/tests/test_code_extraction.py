"""
Test code extraction functionality for various code editors and documentation frameworks.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from src.server.services.knowledge.code_extraction_service import CodeExtractionService
from src.server.services.rag.crawling_service import CrawlingService


class TestCodeExtraction:
    """Test code extraction from various HTML formats."""
    
    def test_extract_milkdown_code_blocks(self):
        """Test extraction of code blocks from Milkdown HTML format."""
        service = CodeExtractionService(supabase_client=Mock())
        
        # Sample Milkdown HTML
        html_content = '''
        <div class="milkdown-code-block">
            <div class="code-block-wrapper">
                <pre><code>npm install @milkdown/core @milkdown/preset-commonmark</code></pre>
            </div>
        </div>
        '''
        
        # Extract code blocks
        code_blocks = service._extract_html_code_blocks(html_content, min_length=10)
        
        # Verify extraction
        assert len(code_blocks) == 1
        assert "npm install @milkdown/core" in code_blocks[0]['code']
        assert code_blocks[0]['source_type'] == 'milkdown'
    
    def test_extract_monaco_editor_code(self):
        """Test extraction from Monaco Editor."""
        service = CodeExtractionService(supabase_client=Mock())
        
        html_content = '''
        <div class="monaco-editor">
            <div class="overflow-guard">
                <div class="view-lines">
                    <div>const hello = "world";</div>
                    <div>console.log(hello);</div>
                </div>
            </div>
        </div>
        '''
        
        code_blocks = service._extract_html_code_blocks(html_content, min_length=10)
        
        assert len(code_blocks) == 1
        assert "const hello" in code_blocks[0]['code']
        assert code_blocks[0]['source_type'] == 'monaco'
    
    def test_extract_codemirror_code(self):
        """Test extraction from CodeMirror."""
        service = CodeExtractionService(supabase_client=Mock())
        
        html_content = '''
        <div class="cm-editor">
            <div class="cm-content">
                <div class="cm-line">function add(a, b) {</div>
                <div class="cm-line">  return a + b;</div>
                <div class="cm-line">}</div>
            </div>
        </div>
        '''
        
        code_blocks = service._extract_html_code_blocks(html_content, min_length=10)
        
        assert len(code_blocks) == 1
        assert "function add" in code_blocks[0]['code']
        assert code_blocks[0]['source_type'] == 'codemirror'
    
    def test_extract_prism_code(self):
        """Test extraction from Prism.js."""
        service = CodeExtractionService(supabase_client=Mock())
        
        html_content = '''
        <pre class="language-python">
            <code>def hello():
    print("Hello, World!")
    
hello()</code>
        </pre>
        '''
        
        code_blocks = service._extract_html_code_blocks(html_content, min_length=10)
        
        assert len(code_blocks) == 1
        assert "def hello():" in code_blocks[0]['code']
        assert code_blocks[0]['language'] == 'python'
        assert code_blocks[0]['source_type'] == 'prism'
    
    def test_extract_highlight_js_code(self):
        """Test extraction from highlight.js."""
        service = CodeExtractionService(supabase_client=Mock())
        
        html_content = '''
        <pre><code class="hljs language-javascript">
const express = require('express');
const app = express();
app.listen(3000);
        </code></pre>
        '''
        
        code_blocks = service._extract_html_code_blocks(html_content, min_length=10)
        
        assert len(code_blocks) == 1
        assert "const express" in code_blocks[0]['code']
        assert code_blocks[0]['source_type'] == 'hljs'
    
    def test_extract_shiki_code(self):
        """Test extraction from Shiki (VitePress/Nextra)."""
        service = CodeExtractionService(supabase_client=Mock())
        
        html_content = '''
        <pre class="shiki">
            <code>
import { defineConfig } from 'vite'
export default defineConfig({
  plugins: []
})
            </code>
        </pre>
        '''
        
        code_blocks = service._extract_html_code_blocks(html_content, min_length=10)
        
        assert len(code_blocks) == 1
        assert "defineConfig" in code_blocks[0]['code']
        assert code_blocks[0]['source_type'] == 'shiki'
    
    def test_extract_multiple_code_blocks(self):
        """Test extraction of multiple code blocks from mixed sources."""
        service = CodeExtractionService(supabase_client=Mock())
        
        html_content = '''
        <h2>Installation</h2>
        <pre class="language-bash"><code>npm install mypackage</code></pre>
        
        <h2>Usage</h2>
        <div class="milkdown-code-block">
            <pre><code>import { MyComponent } from 'mypackage';
            
export default function App() {
  return <MyComponent />;
}</code></pre>
        </div>
        
        <h2>Configuration</h2>
        <pre><code class="hljs language-json">{
  "compilerOptions": {
    "target": "es5"
  }
}</code></pre>
        '''
        
        code_blocks = service._extract_html_code_blocks(html_content, min_length=10)
        
        # Should find 3 code blocks
        assert len(code_blocks) == 3
        
        # Check each was identified correctly
        source_types = [block['source_type'] for block in code_blocks]
        assert 'prism' in source_types
        assert 'milkdown' in source_types
        assert 'hljs' in source_types
    
    def test_html_entity_decoding(self):
        """Test that HTML entities are decoded properly."""
        service = CodeExtractionService(supabase_client=Mock())
        
        html_content = '''
        <pre><code>&lt;div class=&quot;test&quot;&gt;
  &amp;nbsp;&lt;p&gt;Hello&lt;/p&gt;
&lt;/div&gt;</code></pre>
        '''
        
        code_blocks = service._extract_html_code_blocks(html_content, min_length=10)
        
        assert len(code_blocks) == 1
        assert '<div class="test">' in code_blocks[0]['code']
        assert '&lt;' not in code_blocks[0]['code']
        assert '&quot;' not in code_blocks[0]['code']
    
    def test_min_length_filtering(self):
        """Test that code blocks below min length are filtered out."""
        service = CodeExtractionService(supabase_client=Mock())
        
        html_content = '''
        <pre><code>hi</code></pre>
        <pre><code>This is a longer code example that should be included</code></pre>
        '''
        
        code_blocks = service._extract_html_code_blocks(html_content, min_length=20)
        
        # Only the longer code block should be included
        assert len(code_blocks) == 1
        assert "longer code example" in code_blocks[0]['code']
    
    @pytest.mark.asyncio
    async def test_extract_and_store_code_examples(self):
        """Test the full extraction and storage flow."""
        mock_supabase = Mock()
        service = CodeExtractionService(mock_supabase)
        
        # Mock crawl results with HTML content
        crawl_results = [{
            'url': 'https://example.com/docs',
            'markdown': '# Docs\n\nSome content here',
            'html': '''
            <h1>Documentation</h1>
            <p>Here's how to use our API:</p>
            <pre class="language-javascript"><code>
const api = new API();
api.connect();
api.getData().then(console.log);
            </code></pre>
            '''
        }]
        
        url_to_full_document = {
            'https://example.com/docs': '# Docs\n\nSome content here'
        }
        
        # Mock the supabase operations
        mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock()
        
        # Run extraction
        count = await service.extract_and_store_code_examples(
            crawl_results,
            url_to_full_document
        )
        
        # Should have found and stored 1 code example
        assert count == 1


class TestCrawlingServiceCodeBlock:
    """Test the crawling service's code block detection."""
    
    def test_code_block_selectors(self):
        """Test that all major code block selectors are included."""
        service = CrawlingService()
        
        # Check that we have selectors for all major editors/frameworks
        selectors_str = ', '.join(service.CODE_BLOCK_SELECTORS)
        
        assert '.milkdown-code-block' in selectors_str
        assert '.monaco-editor' in selectors_str
        assert '.cm-editor' in selectors_str
        assert 'language-' in selectors_str
        assert '.hljs' in selectors_str
        assert '.shiki' in selectors_str
        assert '.code-block' in selectors_str
    
    @pytest.mark.asyncio
    async def test_crawl_with_code_block_wait(self):
        """Test that crawl configuration includes waiting for code blocks."""
        mock_crawler = AsyncMock()
        service = CrawlingService(crawler=mock_crawler)
        
        # Mock successful crawl
        mock_result = Mock(
            success=True,
            markdown='# Test',
            cleaned_html='<pre><code>test code</code></pre>',
            html='<pre><code>test code</code></pre>',
            title='Test Page',
            links={}
        )
        mock_crawler.arun.return_value = mock_result
        
        # Crawl a page
        result = await service.crawl_single_page('https://example.com')
        
        # Check that the crawl config included wait_for with code selectors
        call_args = mock_crawler.arun.call_args
        config = call_args.kwargs['config']
        
        assert hasattr(config, 'wait_for')
        assert 'css:' in config.wait_for
        assert '.milkdown-code-block' in config.wait_for


if __name__ == "__main__":
    pytest.main([__file__, "-v"])