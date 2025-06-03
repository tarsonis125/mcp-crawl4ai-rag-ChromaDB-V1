"""
Tests for Docker build process and container orchestration.
These tests will initially fail until Docker infrastructure is implemented.
"""
import pytest
import subprocess
import os
import time
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.mark.integration
def test_frontend_dockerfile_exists():
    """Test that the frontend Dockerfile exists."""
    frontend_dockerfile = Path("archon-ui-main/Dockerfile")
    assert frontend_dockerfile.exists(), "Frontend Dockerfile should exist"


@pytest.mark.integration
def test_pyserver_dockerfile_exists():
    """Test that the Python server Dockerfile exists."""
    pyserver_dockerfile = Path("Dockerfile")
    assert pyserver_dockerfile.exists(), "Python server Dockerfile should exist"


@pytest.mark.integration
def test_docker_compose_file_exists():
    """Test that docker-compose.yml exists."""
    compose_file = Path("docker-compose.yml")
    assert compose_file.exists(), "docker-compose.yml should exist"


@pytest.mark.integration
def test_frontend_dockerfile_structure():
    """Test that the frontend Dockerfile has required stages and commands."""
    frontend_dockerfile = Path("archon-ui-main/Dockerfile")
    
    with open(frontend_dockerfile, 'r') as f:
        content = f.read()
    
    # Test multi-stage build
    assert "FROM node:" in content, "Should use Node.js base image"
    assert "WORKDIR" in content, "Should set working directory"
    assert "COPY package" in content, "Should copy package files"
    assert "RUN npm install" in content, "Should install dependencies"
    assert "RUN npm run build" in content, "Should build the app"
    assert "FROM nginx:" in content, "Should use nginx for serving"
    assert "COPY --from=" in content, "Should copy from build stage"
    assert "EXPOSE 80" in content, "Should expose port 80"


@pytest.mark.integration
def test_pyserver_dockerfile_structure():
    """Test that the Python server Dockerfile has required commands."""
    pyserver_dockerfile = Path("Dockerfile")
    
    with open(pyserver_dockerfile, 'r') as f:
        content = f.read()
    
    assert "FROM python:" in content, "Should use Python base image"
    assert "WORKDIR" in content, "Should set working directory"
    assert "COPY pyproject.toml" in content, "Should copy project file"
    assert "RUN pip install uv" in content, "Should install uv"
    assert "RUN uv pip install" in content, "Should install dependencies"
    assert "COPY src/" in content, "Should copy source code"
    assert "EXPOSE 8080" in content, "Should expose port 8080"
    assert "CMD" in content, "Should have startup command"


@pytest.mark.integration
def test_docker_compose_structure():
    """Test that docker-compose.yml has required services and configuration."""
    compose_file = Path("docker-compose.yml")
    
    with open(compose_file, 'r') as f:
        content = f.read()
    
    # Test services
    assert "services:" in content, "Should have services section"
    assert "frontend:" in content, "Should have frontend service"
    assert "archon-pyserver:" in content, "Should have archon-pyserver service"
    
    # Test networking
    assert "networks:" in content, "Should define networks"
    assert "ports:" in content, "Should define port mappings"
    
    # Test environment
    assert "environment:" in content, "Should define environment variables"
    
    # Test volumes for development
    assert "volumes:" in content, "Should define volumes"


class TestDockerBuild:
    """Tests for Docker build functionality."""
    
    @pytest.mark.slow
    def test_frontend_docker_build(self):
        """Test that the frontend Docker image can be built."""
        # This will fail until Dockerfile is created
        result = subprocess.run([
            "docker", "build", 
            "-t", "archon-frontend:test",
            "-f", "archon-ui-main/Dockerfile",
            "archon-ui-main/"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Frontend build failed: {result.stderr}"
        assert "Successfully tagged archon-frontend:test" in result.stdout
    
    @pytest.mark.slow
    def test_pyserver_docker_build(self):
        """Test that the Python server Docker image can be built."""
        # This will fail until Dockerfile is created
        result = subprocess.run([
            "docker", "build", 
            "-t", "archon-pyserver:test",
            "."
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Python server build failed: {result.stderr}"
        assert "Successfully tagged archon-pyserver:test" in result.stdout
    
    @pytest.mark.slow
    def test_docker_compose_build(self):
        """Test that docker-compose can build all services."""
        result = subprocess.run([
            "docker-compose", "build"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Compose build failed: {result.stderr}"


class TestContainerStartup:
    """Tests for container startup and basic functionality."""
    
    @pytest.mark.slow
    def test_pyserver_container_starts(self):
        """Test that the Python server container starts successfully."""
        # Start container
        start_result = subprocess.run([
            "docker", "run", "-d", 
            "--name", "test-pyserver",
            "-p", "8080:8080",
            "-e", "OPENAI_API_KEY=sk-test123",
            "-e", "SUPABASE_URL=https://test.supabase.co",
            "-e", "SUPABASE_SERVICE_KEY=test-key",
            "archon-pyserver:test"
        ], capture_output=True, text=True)
        
        try:
            assert start_result.returncode == 0, f"Container start failed: {start_result.stderr}"
            
            # Wait for container to be ready
            time.sleep(5)
            
            # Check if container is running
            status_result = subprocess.run([
                "docker", "ps", "--filter", "name=test-pyserver", "--format", "{{.Status}}"
            ], capture_output=True, text=True)
            
            assert "Up" in status_result.stdout, "Container should be running"
            
        finally:
            # Cleanup
            subprocess.run(["docker", "stop", "test-pyserver"], capture_output=True)
            subprocess.run(["docker", "rm", "test-pyserver"], capture_output=True)
    
    @pytest.mark.slow
    def test_frontend_container_starts(self):
        """Test that the frontend container starts successfully."""
        # Start container
        start_result = subprocess.run([
            "docker", "run", "-d", 
            "--name", "test-frontend",
            "-p", "3000:80",
            "archon-frontend:test"
        ], capture_output=True, text=True)
        
        try:
            assert start_result.returncode == 0, f"Container start failed: {start_result.stderr}"
            
            # Wait for container to be ready
            time.sleep(5)
            
            # Check if container is running
            status_result = subprocess.run([
                "docker", "ps", "--filter", "name=test-frontend", "--format", "{{.Status}}"
            ], capture_output=True, text=True)
            
            assert "Up" in status_result.stdout, "Container should be running"
            
        finally:
            # Cleanup
            subprocess.run(["docker", "stop", "test-frontend"], capture_output=True)
            subprocess.run(["docker", "rm", "test-frontend"], capture_output=True)


class TestContainerNetworking:
    """Tests for container-to-container communication."""
    
    @pytest.mark.slow
    def test_docker_compose_networking(self):
        """Test that containers can communicate via docker-compose."""
        # Start services
        start_result = subprocess.run([
            "docker-compose", "up", "-d"
        ], capture_output=True, text=True)
        
        try:
            assert start_result.returncode == 0, f"Compose start failed: {start_result.stderr}"
            
            # Wait for services to be ready
            time.sleep(10)
            
            # Test API health endpoint
            api_response = requests.get("http://localhost:8080/api/mcp/status", timeout=5)
            assert api_response.status_code in [200, 503], "API should be accessible"
            
            # Test frontend accessibility
            frontend_response = requests.get("http://localhost:3000", timeout=5)
            assert frontend_response.status_code == 200, "Frontend should be accessible"
            
        finally:
            # Cleanup
            subprocess.run(["docker-compose", "down"], capture_output=True)
    
    @pytest.mark.slow
    def test_frontend_can_call_api(self):
        """Test that frontend container can make API calls to the backend."""
        # This test would simulate the frontend making API calls
        # For now, we'll test that the network allows cross-container communication
        
        # Start services
        subprocess.run(["docker-compose", "up", "-d"], capture_output=True)
        
        try:
            time.sleep(10)
            
            # Test that API is accessible from outside (simulating frontend call)
            response = requests.get("http://localhost:8080/api/mcp/status")
            assert response.status_code in [200, 503], "API should be accessible"
            
            # Check CORS headers are present
            assert "access-control-allow-origin" in response.headers.keys() or \
                   "Access-Control-Allow-Origin" in response.headers.keys(), \
                   "CORS headers should be present"
                   
        finally:
            subprocess.run(["docker-compose", "down"], capture_output=True)


class TestEnvironmentConfiguration:
    """Tests for environment variable handling in containers."""
    
    @pytest.mark.integration
    def test_docker_compose_environment_variables(self):
        """Test that docker-compose.yml defines required environment variables."""
        compose_file = Path("docker-compose.yml")
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Python server environment variables
        assert "OPENAI_API_KEY" in content, "Should define OPENAI_API_KEY"
        assert "SUPABASE_URL" in content, "Should define SUPABASE_URL"
        assert "SUPABASE_SERVICE_KEY" in content, "Should define SUPABASE_SERVICE_KEY"
        
        # API URL for frontend
        assert "REACT_APP_API_URL" in content or "VITE_API_URL" in content, \
               "Should define API URL for frontend"
    
    @pytest.mark.integration
    def test_env_file_template_exists(self):
        """Test that .env.example file exists with required variables."""
        env_example = Path(".env.example")
        assert env_example.exists(), ".env.example should exist"
        
        with open(env_example, 'r') as f:
            content = f.read()
        
        required_vars = [
            "OPENAI_API_KEY",
            "SUPABASE_URL", 
            "SUPABASE_SERVICE_KEY",
            "REACT_APP_API_URL"
        ]
        
        for var in required_vars:
            assert var in content, f"{var} should be in .env.example"


class TestProductionReadiness:
    """Tests for production-ready Docker configuration."""
    
    @pytest.mark.integration
    def test_dockerignore_files_exist(self):
        """Test that .dockerignore files exist to optimize builds."""
        backend_dockerignore = Path(".dockerignore")
        frontend_dockerignore = Path("archon-ui-main/.dockerignore")
        
        assert backend_dockerignore.exists(), "Python server .dockerignore should exist"
        assert frontend_dockerignore.exists(), "Frontend .dockerignore should exist"
    
    @pytest.mark.integration
    def test_health_checks_defined(self):
        """Test that docker-compose defines health checks."""
        compose_file = Path("docker-compose.yml")
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        assert "healthcheck:" in content, "Should define health checks"
        assert "test:" in content, "Should define health check tests"
    
    @pytest.mark.integration
    def test_security_configuration(self):
        """Test that containers are configured securely."""
        compose_file = Path("docker-compose.yml")
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Test that we don't run as root (optional but good practice)
        # Test that sensitive data is handled via environment variables, not hardcoded
        assert "sk-" not in content, "Should not hardcode API keys"
        assert "postgresql://" not in content, "Should not hardcode database URLs"


@pytest.mark.integration
def test_development_workflow():
    """Test that development workflow with Docker works."""
    # Test that we can:
    # 1. Build containers
    # 2. Start development environment
    # 3. Make changes and see them reflected
    # 4. Stop environment cleanly
    
    # This is a placeholder for the full development workflow test
    assert True, "Development workflow test placeholder"


# Cleanup fixtures
@pytest.fixture(autouse=True, scope="session")
def cleanup_test_containers():
    """Clean up any test containers after tests complete."""
    yield
    
    # Cleanup any remaining test containers
    test_containers = ["test-pyserver", "test-frontend"]
    for container in test_containers:
        subprocess.run(["docker", "stop", container], capture_output=True)
        subprocess.run(["docker", "rm", container], capture_output=True)
    
    # Cleanup test images
    subprocess.run(["docker", "rmi", "archon-frontend:test"], capture_output=True)
    subprocess.run(["docker", "rmi", "archon-pyserver:test"], capture_output=True) 