import click
from cloudmesh.ai.common.io import console, path_expand
from cloudmesh.ai.common.logging_utils import get_contextual_logger
from cloudmesh.ai.common.telemetry import Telemetry

# Initialize Logger and Telemetry
logger = get_contextual_logger("commander")
telemetry = Telemetry("commander")

# Define the group for the command
commander_group = click.group(name="commander")

from cloudmesh.ai.commander.commander import Commander
from cloudmesh.ai.mesh.command.mesh import register as register_mesh


@commander_group.command(name="tunnel")
@click.argument("node")
@click.argument("remote_port", type=int)
@click.argument("local_port", type=int)
@click.option("--dir", type=click.Path(), help="Directory containing config.yaml and vllm_cmd.txt")
@click.option("--config", type=click.Path(), help="Path to custom config YAML file")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def tunnel_cmd(node, remote_port, local_port, dir, config, debug):
    """Creates an SSH tunnel to a specific UVA compute node."""
    commander = Commander(debug=debug, config_path=config, config_dir=dir)
    commander.setup_tunnel(node, remote_port, local_port)

@commander_group.command(name="status")
@click.option("--port", type=int, help="Port to check (overrides config)")
@click.option("--dir", type=click.Path(), help="Directory containing config.yaml and vllm_cmd.txt")
@click.option("--config", type=click.Path(), help="Path to custom config YAML file")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def status_cmd(port, dir, config, debug):
    """Checks if the mock server is reachable locally."""
    commander = Commander(debug=debug, config_path=config, config_dir=dir)
    # Use provided port or fallback to config
    target_port = port or commander.config["vllm"]["default_port"]
    if commander.check_status(target_port):
        console.ok(f"Mock server is ONLINE at http://localhost:{port}")
    else:
        console.error(f"Mock server is OFFLINE at http://localhost:{port}")

@commander_group.command(name="setup")
@click.argument("target")
@click.option("--dir", type=click.Path(), help="Directory containing config.yaml and vllm_cmd.txt")
@click.option("--config", type=click.Path(), help="Path to custom config YAML file")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def setup_cmd(target, dir, config, debug):
    """Sets up the environment for the specified target (e.g., vllm)."""
    commander = Commander(debug=debug, config_path=config, config_dir=dir)
    if target == "vllm":
        if commander.setup_vllm():
            console.ok("vLLM environment setup successfully.")
        else:
            console.error("Failed to setup vLLM environment.")
    else:
        console.error(f"Unknown setup target: {target}")

@commander_group.command(name="run")
@click.argument("target")
@click.option("--port", type=int, help="Port for the server (overrides config)")
@click.option("--partition", default="bii-gpu", help="UVA partition to use")
@click.option("--dir", type=click.Path(), help="Directory containing config.yaml and vllm_cmd.txt")
@click.option("--config", type=click.Path(), help="Path to custom config YAML file")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def run_cmd(target, port, partition, dir, config, debug):
    """Runs the specified target server on UVA (e.g., mock, vllm)."""
    commander = Commander(debug=debug, config_path=config, config_dir=dir)
    if target == "vllm":
        node = commander.run_vllm(port=port, partition=partition)
        if node:
            console.ok(f"vLLM server is now available at http://localhost:{port}")
        else:
            console.error("Failed to start vLLM server.")
    elif target == "mock":
        node = commander.run_mock(port=port, partition=partition)
        if node:
            console.ok(f"Mock server is now available at http://localhost:{port}")
        else:
            console.error("Failed to start mock server.")
    else:
        console.error(f"Unknown run target: {target}")

@commander_group.command(name="init")
@click.option("--port", type=int, required=True, help="Default port for the server")
def init_cmd(port):
    """Initializes the user configuration with a specific port."""
    commander = Commander()
    if commander.init_config(port):
        console.ok(f"Configuration initialized with port {port}")
    else:
        console.error("Failed to initialize configuration.")

@commander_group.command(name="export")
@click.option("--dir", type=click.Path(), default=".", help="Directory to export config and scripts to")
def export_cmd(dir):
    """Exports the default configuration and deployment scripts to a directory."""
    commander = Commander()
    if commander.export_config(dir):
        console.ok(f"Exported configuration to {dir}")
    else:
        console.error("Failed to export configuration.")

@commander_group.command(name="hello")
def hello_cmd():
    """Hello command for commander."""
    logger.info("Executing hello command")
    console.ok(f"Hello from commander!")

@commander_group.command(name="test-path")
@click.argument("path")
def test_path_cmd(path):
    """Example command showing path expansion."""
    expanded = path_expand(path)
    console.info(f"Expanded path: {expanded}")

def register(cli):
    """Registers the commander command group to the main CLI."""
    cli.add_command(commander_group)
    register_mesh(cli)
