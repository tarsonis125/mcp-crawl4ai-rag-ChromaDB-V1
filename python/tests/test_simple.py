"""Simple test to verify pytest is working in the container"""

def test_addition():
    """Test basic addition"""
    assert 2 + 2 == 4

def test_string():
    """Test string operations"""
    assert "hello" + " world" == "hello world"

def test_list():
    """Test list operations"""
    items = [1, 2, 3]
    items.append(4)
    assert len(items) == 4
    assert items[-1] == 4

def test_dict():
    """Test dictionary operations"""
    data = {"key": "value"}
    data["new_key"] = "new_value"
    assert len(data) == 2
    assert data.get("key") == "value"