---
title: Testing
sidebar_position: 8
---

# Testing Guide

Archon employs a comprehensive testing strategy covering unit tests, integration tests, end-to-end tests, and performance testing across all components of the system.

## 🧪 Testing Philosophy

Our testing approach follows the testing pyramid:

```mermaid
graph TB
    subgraph "Testing Pyramid"
        E2E["E2E Tests<br/>🔍 User Journeys<br/>Selenium/Playwright"]
        Integration["Integration Tests<br/>🔗 API & Database<br/>FastAPI TestClient"]
        Unit["Unit Tests<br/>⚡ Functions & Classes<br/>pytest + mocks"]
    end

    Unit --> Integration
    Integration --> E2E

    style Unit fill:#e1f5fe
    style Integration fill:#f3e5f5
    style E2E fill:#fff3e0
```

## 📁 Test Directory Structure

```
tests/
├── unit/                    # Unit tests
│   ├── test_auth.py
│   ├── test_vector_store.py
│   ├── test_mcp_client.py
│   ├── test_rag_pipeline.py
│   └── test_utils.py
├── integration/             # Integration tests
│   ├── test_api_endpoints.py
│   ├── test_database.py
│   ├── test_mcp_server.py
│   └── test_websockets.py
├── e2e/                     # End-to-end tests
│   ├── test_user_flows.py
│   ├── test_document_upload.py
│   └── test_chat_interface.py
├── performance/             # Performance tests
│   ├── test_load.py
│   └── test_stress.py
├── fixtures/                # Test data
│   ├── sample_documents/
│   ├── mock_responses/
│   └── test_data.json
├── conftest.py             # Pytest configuration
├── pytest.ini             # Pytest settings
└── requirements-test.txt   # Test dependencies
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Or install with development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
pytest tests/e2e/          # E2E tests only

# Run tests with specific markers
pytest -m "not slow"       # Skip slow tests
pytest -m "api"            # Run API tests only
pytest -m "database"       # Run database tests only
```

### Test Configuration

```ini
# pytest.ini
[tool:pytest]
minversion = 6.0
addopts = 
    -ra
    --strict-markers
    --strict-config
    --cov=src
    --cov-branch
    --cov-report=term-missing:skip-covered
    --cov-report=html:htmlcov
    --cov-report=xml
    --cov-fail-under=80
testpaths = tests
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    api: marks tests as API tests
    database: marks tests as database tests
    mcp: marks tests as MCP-related tests
    rag: marks tests as RAG-related tests
    auth: marks tests as authentication tests
    websocket: marks tests as WebSocket tests
```

## 🔧 Test Configuration & Fixtures

### conftest.py

```python
# tests/conftest.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch

from src.main import app
from src.database import get_db, Base
from src.config import Settings
from src.auth import get_current_user

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with dependency overrides."""
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    def override_get_current_user():
        return {"id": "test-user", "email": "test@example.com"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

@pytest.fixture
def mock_openai():
    """Mock OpenAI API calls."""
    with patch("openai.Embedding.create") as mock_embed,          patch("openai.ChatCompletion.create") as mock_chat:

        mock_embed.return_value = {
            "data": [{"embedding": [0.1] * 1536}]
        }

        mock_chat.return_value = {
            "choices": [{
                "message": {
                    "content": "Test response from OpenAI"
                }
            }]
        }

        yield {"embed": mock_embed, "chat": mock_chat}

@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock_client = Mock()
    mock_client.table.return_value.insert.return_value.execute.return_value = {
        "data": [{"id": 1, "content": "test"}]
    }
    mock_client.table.return_value.select.return_value.execute.return_value = {
        "data": [{"id": 1, "content": "test", "embedding": [0.1] * 1536}]
    }
    return mock_client

@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return {
        "title": "Test Document",
        "content": "This is a test document for RAG testing.",
        "metadata": {
            "source": "test",
            "type": "text"
        }
    }
```

## 🧪 Unit Tests

### Authentication Tests

```python
# tests/unit/test_auth.py
import pytest
from unittest.mock import patch, Mock
from src.auth import create_access_token, verify_token, hash_password, verify_password

class TestAuthentication:

    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_valid(self):
        """Test token verification with valid token."""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)

        payload = verify_token(token)
        assert payload["sub"] == "test@example.com"

    def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        with pytest.raises(Exception):
            verify_token("invalid.token.here")

    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong_password", hashed)
```

### Vector Store Tests

```python
# tests/unit/test_vector_store.py
import pytest
from unittest.mock import Mock, patch
from src.services.vector_store import VectorStore, embed_text, similarity_search

class TestVectorStore:

    @pytest.fixture
    def vector_store(self, mock_supabase):
        return VectorStore(client=mock_supabase)

    @patch("src.services.vector_store.openai")
    def test_embed_text(self, mock_openai):
        """Test text embedding generation."""
        mock_openai.Embedding.create.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}]
        }

        embedding = embed_text("test text")

        assert isinstance(embedding, list)
        assert len(embedding) == 3
        assert embedding == [0.1, 0.2, 0.3]

    def test_store_document(self, vector_store, sample_document, mock_openai):
        """Test document storage in vector store."""
        result = vector_store.store_document(sample_document)

        assert result["success"] is True
        assert "id" in result

    def test_similarity_search(self, vector_store, mock_openai):
        """Test similarity search functionality."""
        query = "test query"
        results = vector_store.similarity_search(query, limit=5)

        assert isinstance(results, list)
        assert len(results) <= 5
```

### RAG Pipeline Tests

```python
# tests/unit/test_rag_pipeline.py
import pytest
from unittest.mock import Mock, patch
from src.services.rag import RAGPipeline, generate_response

class TestRAGPipeline:

    @pytest.fixture
    def rag_pipeline(self, mock_supabase, mock_openai):
        return RAGPipeline(
            vector_store=mock_supabase,
            llm_client=mock_openai
        )

    def test_retrieve_context(self, rag_pipeline):
        """Test context retrieval for RAG."""
        query = "What is machine learning?"
        context = rag_pipeline.retrieve_context(query)

        assert isinstance(context, list)
        assert len(context) > 0

    def test_generate_response(self, rag_pipeline):
        """Test response generation with context."""
        query = "What is machine learning?"
        context = ["Machine learning is a subset of AI..."]

        response = rag_pipeline.generate_response(query, context)

        assert isinstance(response, str)
        assert len(response) > 0

    def test_full_rag_pipeline(self, rag_pipeline):
        """Test complete RAG pipeline."""
        query = "What is machine learning?"
        result = rag_pipeline.query(query)

        assert "answer" in result
        assert "sources" in result
        assert isinstance(result["answer"], str)
        assert isinstance(result["sources"], list)
```

## 🔗 Integration Tests

### API Endpoint Tests

```python
# tests/integration/test_api_endpoints.py
import pytest
from fastapi.testclient import TestClient

class TestAPIEndpoints:

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_upload_document(self, client):
        """Test document upload endpoint."""
        files = {"file": ("test.txt", "Test content", "text/plain")}
        response = client.post("/api/documents/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "uploaded"

    def test_chat_endpoint(self, client, mock_openai):
        """Test chat endpoint with RAG."""
        payload = {
            "message": "What is machine learning?",
            "conversation_id": "test-conv-123"
        }

        response = client.post("/api/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "sources" in data

    def test_mcp_status(self, client):
        """Test MCP server status endpoint."""
        response = client.get("/api/mcp/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "tools" in data

    def test_task_creation(self, client):
        """Test task creation endpoint."""
        payload = {
            "title": "Test Task",
            "description": "A test task for integration testing",
            "priority": "medium"
        }

        response = client.post("/api/tasks", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Task"
        assert "task_id" in data
```

### WebSocket Tests

```python
# tests/integration/test_websockets.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from fastapi import WebSocket

class TestWebSockets:

    def test_websocket_connection(self, client):
        """Test WebSocket connection establishment."""
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connection_established"

    def test_websocket_chat(self, client, mock_openai):
        """Test real-time chat via WebSocket."""
        with client.websocket_connect("/ws") as websocket:
            # Send message
            websocket.send_json({
                "type": "chat_message",
                "message": "Hello, AI!"
            })

            # Receive response
            response = websocket.receive_json()
            assert response["type"] == "chat_response"
            assert "message" in response

    def test_websocket_task_updates(self, client):
        """Test task status updates via WebSocket."""
        with client.websocket_connect("/ws") as websocket:
            # Subscribe to task updates
            websocket.send_json({
                "type": "subscribe",
                "channel": "task_updates"
            })

            # Create a task (this should trigger an update)
            task_response = client.post("/api/tasks", json={
                "title": "WebSocket Test Task",
                "description": "Testing WebSocket notifications"
            })

            # Receive task update notification
            update = websocket.receive_json()
            assert update["type"] == "task_created"
            assert "task_id" in update
```

## 🌐 End-to-End Tests

### User Flow Tests

```python
# tests/e2e/test_user_flows.py
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestUserFlows:

    @pytest.fixture(scope="class")
    def driver(self):
        """Setup Selenium WebDriver."""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)
        yield driver
        driver.quit()

    def test_complete_document_workflow(self, driver):
        """Test complete document upload and query workflow."""
        # Navigate to application
        driver.get("http://localhost:3737")

        # Upload document
        upload_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        upload_input.send_keys("/path/to/test/document.pdf")

        upload_button = driver.find_element(By.CSS_SELECTOR, "button[data-testid='upload-btn']")
        upload_button.click()

        # Wait for upload confirmation
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".upload-success"))
        )

        # Navigate to chat
        chat_link = driver.find_element(By.CSS_SELECTOR, "a[href='/chat']")
        chat_link.click()

        # Send query
        chat_input = driver.find_element(By.CSS_SELECTOR, "input[data-testid='chat-input']")
        chat_input.send_keys("What is the main topic of the uploaded document?")

        send_button = driver.find_element(By.CSS_SELECTOR, "button[data-testid='send-btn']")
        send_button.click()

        # Wait for response
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".chat-response"))
        )

        response = driver.find_element(By.CSS_SELECTOR, ".chat-response")
        assert len(response.text) > 0

    def test_task_management_workflow(self, driver):
        """Test task creation and management workflow."""
        driver.get("http://localhost:3737/tasks")

        # Create new task
        new_task_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='new-task-btn']")
        new_task_btn.click()

        # Fill task form
        title_input = driver.find_element(By.CSS_SELECTOR, "input[name='title']")
        title_input.send_keys("E2E Test Task")

        description_input = driver.find_element(By.CSS_SELECTOR, "textarea[name='description']")
        description_input.send_keys("This is a test task created during E2E testing")

        create_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='create-task-btn']")
        create_btn.click()

        # Verify task appears in list
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'E2E Test Task')]"))
        )

        task_element = driver.find_element(By.XPATH, "//div[contains(text(), 'E2E Test Task')]")
        assert task_element.is_displayed()
```

## ⚡ Performance Tests

### Load Testing

```python
# tests/performance/test_load.py
import pytest
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

class TestLoadPerformance:

    @pytest.mark.slow
    async def test_concurrent_chat_requests(self):
        """Test system performance under concurrent chat requests."""
        base_url = "http://localhost:8080"
        num_requests = 50

        async def make_chat_request(session, request_id):
            payload = {
                "message": f"Test message {request_id}",
                "conversation_id": f"test-conv-{request_id}"
            }

            start_time = time.time()
            async with session.post(f"{base_url}/api/chat", json=payload) as response:
                await response.json()
                end_time = time.time()
                return end_time - start_time

        async with aiohttp.ClientSession() as session:
            tasks = [make_chat_request(session, i) for i in range(num_requests)]
            response_times = await asyncio.gather(*tasks)

        # Performance assertions
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        assert avg_response_time < 2.0  # Average response under 2 seconds
        assert max_response_time < 5.0  # No request takes more than 5 seconds
        assert len(response_times) == num_requests  # All requests completed

    @pytest.mark.slow
    def test_document_upload_performance(self):
        """Test document upload performance with large files."""
        import requests

        # Create a large test file (1MB)
        test_content = "A" * (1024 * 1024)  # 1MB of 'A' characters

        files = {"file": ("large_test.txt", test_content, "text/plain")}

        start_time = time.time()
        response = requests.post("http://localhost:8080/api/documents/upload", files=files)
        end_time = time.time()

        upload_time = end_time - start_time

        assert response.status_code == 200
        assert upload_time < 10.0  # Upload should complete within 10 seconds
```

## 🔍 Test Coverage & Reporting

### Coverage Configuration

```ini
# .coveragerc
[run]
source = src
omit = 
    src/migrations/*
    src/tests/*
    src/config.py
    */venv/*
    */virtualenv/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    class .*Protocol\):
    @(abc\.)?abstractmethod

[html]
directory = htmlcov
```

### Generating Reports

```bash
# Generate coverage report
pytest --cov=src --cov-report=html --cov-report=term

# Generate XML report for CI/CD
pytest --cov=src --cov-report=xml

# Generate detailed coverage report
coverage report --show-missing
```

## 🚀 Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-test.txt

    - name: Run unit tests
      run: |
        pytest tests/unit/ --cov=src --cov-report=xml

    - name: Run integration tests
      run: |
        pytest tests/integration/ --cov=src --cov-append --cov-report=xml
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost/test_db

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
```

## 🛠️ Testing Best Practices

### Test Organization

1. **Follow AAA Pattern**: Arrange, Act, Assert
2. **Use descriptive test names**: `test_should_return_error_when_invalid_token_provided`
3. **One assertion per test**: Focus on testing one behavior
4. **Use fixtures for setup**: Avoid code duplication
5. **Mock external dependencies**: Keep tests isolated

### Test Data Management

```python
# Use factories for test data
class DocumentFactory:
    @staticmethod
    def create_sample_document(**kwargs):
        defaults = {
            "title": "Sample Document",
            "content": "This is sample content for testing.",
            "metadata": {"source": "test", "type": "text"}
        }
        defaults.update(kwargs)
        return defaults

# Use parametrized tests for multiple scenarios
@pytest.mark.parametrize("input_text,expected_length", [
    ("short", 5),
    ("medium length text", 18),
    ("this is a much longer text for testing", 38)
])
def test_text_processing(input_text, expected_length):
    result = process_text(input_text)
    assert len(result) == expected_length
```

### Performance Testing Guidelines

1. **Set realistic thresholds**: Based on production requirements
2. **Test under load**: Simulate concurrent users
3. **Monitor resource usage**: CPU, memory, database connections
4. **Test edge cases**: Large files, long conversations
5. **Automate performance tests**: Include in CI/CD pipeline

## 🐛 Debugging Tests

### Common Issues

```bash
# Run tests with verbose output
pytest -v

# Run specific test with debugging
pytest tests/unit/test_auth.py::test_create_access_token -v -s

# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest --tb=long
```

### Test Environment Setup

```bash
# Create isolated test environment
python -m venv test_env
source test_env/bin/activate
pip install -r requirements-test.txt

# Run tests with environment variables
TEST_DATABASE_URL=sqlite:///test.db pytest
```

---

**Next Steps:**
- Learn about [Deployment](./deployment) for production setup
- Explore [API Reference](./api-reference) for endpoint testing
- Check [Server Architecture](./server) for system understanding
