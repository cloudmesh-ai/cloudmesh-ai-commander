import pytest
from click.testing import CliRunner
from cloudmesh.ai.command.commander import commander_group

def test_hello():
    """Test the hello command."""
    runner = CliRunner()
    result = runner.invoke(commander_group, ["hello"])
    assert result.exit_code == 0
    assert "Hello from commander!" in result.output

def test_test_path():
    """Test the test-path command."""
    runner = CliRunner()
    # Using a simple path for testing
    result = runner.invoke(commander_group, ["test-path", "/tmp"])
    assert result.exit_code == 0
    assert "Expanded path:" in result.output