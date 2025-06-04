from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_dockerfile_exists():
    assert (ROOT / 'archon-ui-main' / 'Dockerfile').exists()


def test_pyserver_dockerfile_exists():
    assert (ROOT / 'python' / 'Dockerfile').exists()


def test_docker_compose_exists():
    assert (ROOT / 'docker-compose.yml').exists()


def test_env_example_exists():
    assert (ROOT / '.env.example').exists()
