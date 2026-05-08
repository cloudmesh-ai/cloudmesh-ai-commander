import os
import subprocess
import time
import yaml
from typing import Optional
from cloudmesh.ai.common.io import console
from cloudmesh.ai.common.logging_utils import get_contextual_logger
from cloudmesh.ai.common.Shell import Shell
from cloudmesh.ai.common.ssh import Tunnel
from cloudmesh.ai.uva import Uva

logger = get_contextual_logger("commander")


class Commander:
    """Orchestrates AI server deployment and access on UVA."""

    def __init__(self, debug: bool = False, config_path: Optional[str] = None, config_dir: Optional[str] = None):
        self.debug = debug
        self.uva = Uva(debug=debug)
        self.tunnels = {}
        self.config_dir = config_dir
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[str] = None):
        """Loads the configuration from the specified path or default config.yaml."""
        if config_path:
            target_path = config_path
        elif self.config_dir:
            target_path = os.path.join(self.config_dir, "config.yaml")
        else:
            # Try user config first, then package default
            user_config = os.path.expanduser("~/.config/cloudmesh/llm/config.yaml")
            if os.path.exists(user_config):
                target_path = user_config
            else:
                target_path = os.path.join(os.path.dirname(__file__), "config.yaml")
            
        try:
            with open(target_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            console.warn(f"Could not load config from {target_path}, using defaults: {e}")
            return {
                "deployment": {
                    "partition": "bii-gpu",
                    "ssh_host": "uva",
                    "remote_scratch_path": "/scratch/thf2bn",
                    "remote_cache_path": "/scratch/thf2bn/hf_cache",
                },
                "vllm": {
                    "model": "google/gemma-4-31B-it",
                    "tensor_parallel_size": 4,
                    "gpu_memory_utilization": 0.85,
                    "max_model_len": 131072,
                    "load_format": "safetensors",
                    "tool_call_parser": "gemma4",
                    "default_port": 18123,
                },
            }

    def init_config(self, port: int):
        """Initializes the user configuration with a specific port."""
        try:
            config_dir = os.path.expanduser("~/.config/cloudmesh/llm")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "config.yaml")
            
            # Load existing or use defaults
            current_config = self._load_config(config_path) if os.path.exists(config_path) else {
                "deployment": {
                    "partition": "bii-gpu",
                    "ssh_host": "uva",
                    "remote_scratch_path": "/scratch/thf2bn",
                    "remote_cache_path": "/scratch/thf2bn/hf_cache",
                },
                "vllm": {
                    "model": "google/gemma-4-31B-it",
                    "tensor_parallel_size": 4,
                    "gpu_memory_utilization": 0.85,
                    "max_model_len": 131072,
                    "load_format": "safetensors",
                    "tool_call_parser": "gemma4",
                    "default_port": port,
                },
            }
            
            # Update only the port
            if "vllm" in current_config:
                current_config["vllm"]["default_port"] = port
            
            with open(config_path, "w") as f:
                yaml.dump(current_config, f)
                
            console.ok(f"Initialized configuration at {config_path} with port {port}")
            return True
        except Exception as e:
            console.error(f"Failed to initialize config: {e}")
            return False

    def export_config(self, output_dir: str):
        """Exports the default config and deployment scripts to the specified directory."""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # Export config.yaml
            src_config = os.path.join(os.path.dirname(__file__), "config.yaml")
            dst_config = os.path.join(output_dir, "config.yaml")
            with open(src_config, "r") as f:
                content = f.read()
            with open(dst_config, "w") as f:
                f.write(content)
            
            # Export vllm_cmd.txt
            src_cmd = os.path.join(os.path.dirname(__file__), "vllm_cmd.txt")
            dst_cmd = os.path.join(output_dir, "vllm_cmd.txt")
            with open(src_cmd, "r") as f:
                content = f.read()
            with open(dst_cmd, "w") as f:
                f.write(content)
                
            console.ok(f"Configuration and scripts exported to {output_dir}")
            return True
        except Exception as e:
            console.error(f"Failed to export configuration: {e}")
            return False
        except Exception as e:
            console.warn(f"Could not load config from {config_path}, using defaults: {e}")
            return {
                "deployment": {
                    "partition": "bii-gpu",
                    "ssh_host": "uva",
                    "remote_scratch_path": "/scratch/thf2bn",
                    "remote_cache_path": "/scratch/thf2bn/hf_cache",
                },
                "vllm": {
                    "model": "google/gemma-4-31B-it",
                    "tensor_parallel_size": 4,
                    "gpu_memory_utilization": 0.85,
                    "max_model_len": 131072,
                    "load_format": "safetensors",
                    "tool_call_parser": "gemma4",
                    "default_port": 18123,
                },
            }

    def run_mock(self, port: Optional[int] = None, partition: Optional[str] = None) -> Optional[str]:
        """
        Orchestrates the full mock server workflow:
        1. Start iJob on UVA.
        2. Deploy and start mock_vllm.py.
        3. Setup local SSH tunnel.
        """
        port = port or self.config["vllm"]["default_port"]
        partition = partition or self.config["deployment"]["partition"]
        
        console.banner(
            "AI Commander Mock", f"Deploying mock server on partition {partition}..."
        )

        # 1. Start iJob and get the node
        try:
            node_hostname = self.uva.login(host=self.config["deployment"]["ssh_host"], key="v100")
            if not node_hostname:
                console.error("Failed to obtain a compute node from UVA.")
                return None
            console.ok(f"Allocated compute node: {node_hostname}")
        except Exception as e:
            console.error(f"Error during UVA login: {e}")
            return None

        # 2. Deploy and start the mock server
        try:
            mock_server_path = os.path.join(os.path.dirname(__file__), "mock_server.py")
            with open(mock_server_path, "r") as f:
                mock_code = f.read()
        except Exception as e:
            console.error(
                f"Failed to read mock server code from {mock_server_path}: {e}"
            )
            return None

        remote_path = f"/tmp/mock_vllm_{int(time.time())}.py"

        try:
            # Upload the mock server code
            cmd = f"ssh {node_hostname} 'echo \"{mock_code}\" > {remote_path}'"
            Shell.run(cmd)

            # Start the server in the background
            start_cmd = f"ssh {node_hostname} 'nohup python3 {remote_path} --port {port} > /tmp/mock_vllm.log 2>&1 &'"
            Shell.run(start_cmd)
            console.ok(f"Mock server started on {node_hostname}:{port}")
        except Exception as e:
            console.error(f"Failed to deploy mock server: {e}")
            return None

        # 3. Setup local SSH tunnel
        try:
            tunnel = Tunnel(local_port=port, remote_host=node_hostname, remote_port=port, ssh_host="uva")
            if tunnel.start():
                self.tunnels[port] = tunnel
            else:
                return None
        except Exception as e:
            console.error(f"Failed to setup SSH tunnel: {e}")
            return None

        return node_hostname

    def stop(self, port: int = 18123):
        """Stops the SSH tunnel and cleans up local processes."""
        console.banner("AI Commander Stop", f"Stopping tunnel on port {port}...")
        
        # 1. Stop tracked tunnels
        if port in self.tunnels:
            self.tunnels[port].stop()
        
        # 2. Fallback: Kill any ssh process forwarding this port
        try:
            # Find PID of process listening on the local port
            find_pid_cmd = f"lsof -t -iTCP:{port} -sTCP:LISTEN"
            pid = Shell.run(find_pid_cmd).strip()
            if pid:
                Shell.run(f"kill -9 {pid}")
                console.ok(f"Killed process {pid} listening on port {port}")
            else:
                console.info(f"No active process found listening on port {port}")
        except Exception as e:
            console.warn(f"Could not clean up process on port {port}: {e}")

    def setup_tunnel(self, node: str, remote_port: int, local_port: int):
        """Utility to create an SSH tunnel to a specific node."""
        try:
            tunnel = Tunnel(local_port=local_port, remote_host=node, remote_port=remote_port, ssh_host="uva")
            if tunnel.start():
                self.tunnels[local_port] = tunnel
        except Exception as e:
            console.error(f"Failed to setup tunnel: {e}")

    def check_status(self, local_port: int = 18123) -> bool:
        """Verify if the mock server is reachable locally."""
        import requests

        try:
            res = requests.get(f"http://localhost:{local_port}/v1/models", timeout=5)
            return res.status_code == 200
        except Exception:
            return False

    def _ensure_remote_setup(self) -> bool:
        """Ensures the remote UVA environment is prepared for vLLM, copying keys if available."""
        try:
            console.info("Ensuring remote UVA environment is prepared...")

            # 1. Create remote directories
            remote_scratch = self.config["deployment"]["remote_scratch_path"]
            remote_cache = self.config["deployment"]["remote_cache_path"]
            ssh_host = self.config["deployment"]["ssh_host"]

            setup_cmds = [
                "mkdir -p ~/.config/cloudmesh/llm",
                "chmod -R 700 ~/.config/cloudmesh",
                f"mkdir -p {remote_cache}",
            ]
            full_cmd = f"ssh {ssh_host} '{' && '.join(setup_cmds)}'"
            Shell.run(full_cmd)

            # 2. Handle keys: Copy from local to remote if they exist locally
            local_dir = os.path.expanduser("~/.config/cloudmesh/llm")
            keys = ["HF_token.txt", "server_master_key.txt"]

            missing_keys = []
            for key in keys:
                local_path = os.path.join(local_dir, key)
                remote_path = f"uva:~/.config/cloudmesh/llm/{key}"

                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    console.info(f"Copying {key} to UVA...")
                    Shell.run(f"scp {local_path} {remote_path}")
                    Shell.run(f"ssh uva 'chmod 600 {remote_path.split(':')[-1]}'")
                else:
                    missing_keys.append(key)
                    # Create remote placeholder if local is missing or empty
                    Shell.run(f"ssh uva 'touch {remote_path} && chmod 600 {remote_path.split(':')[-1]}'")

            if missing_keys:
                console.error(
                    f"Missing or empty local credentials: {', '.join(missing_keys)}"
                )
                console.error(
                    "Please refer to the 'Troubleshooting' section in README-gemma.md to set up your keys."
                )
            else:
                console.ok("Remote environment prepared on UVA (keys synchronized).")
            return True
        except Exception as e:
            console.error(f"Failed to prepare remote environment: {e}")
            return False

    def setup_vllm(self):
        """Prepares the local and remote environment for vLLM deployment."""
        console.banner("AI Commander Setup", "Preparing vLLM environment...")

        # 1. Local Setup
        config_root = os.path.expanduser("~/.config/cloudmesh")
        gemma_dir = os.path.join(config_root, "llm")
        try:
            if not os.path.exists(gemma_dir):
                os.makedirs(gemma_dir, exist_ok=True)
                console.ok(f"Created local directory: {gemma_dir}")

            # Recursive permission check and update for ~/.config/cloudmesh
            console.info("Securing local configuration directory...")
            for root, dirs, files in os.walk(config_root):
                for d in dirs:
                    d_path = os.path.join(root, d)
                    if (os.stat(d_path).st_mode & 0o777) != 0o700:
                        os.chmod(d_path, 0o700)
                        console.warn(
                            f"Updated permissions for directory {d_path} to 700."
                        )
                for f in files:
                    f_path = os.path.join(root, f)
                    if (os.stat(f_path).st_mode & 0o777) != 0o600:
                        os.chmod(f_path, 0o600)
                        console.warn(f"Updated permissions for file {f_path} to 600.")

            # Ensure token files exist
            token_files = ["HF_token.txt", "server_master_key.txt"]
            for tf in token_files:
                path = os.path.join(gemma_dir, tf)
                if not os.path.exists(path):
                    with open(path, "w") as file:
                        file.write("")
                    os.chmod(path, 0o600)
                    console.warn(
                        f"Created placeholder: {path}. Please add your token/key to this file."
                    )
                else:
                    console.ok(f"Found existing file: {path}")
        except Exception as e:
            console.error(f"Error during local setup: {e}")
            return False

        # 2. Remote Setup (UVA)
        return self._ensure_remote_setup()

    def run_vllm(self, port: Optional[int] = None, partition: Optional[str] = None) -> Optional[str]:
        """
        Orchestrates the full vLLM server workflow:
        1. Ensure remote setup is complete.
        2. Start iJob on UVA.
        3. Deploy and start vLLM via Apptainer.
        4. Setup local SSH tunnel.
        """
        port = port or self.config["vllm"]["default_port"]
        partition = partition or self.config["deployment"]["partition"]
        
        console.banner(
            "AI Commander vLLM",
            f"Deploying real vLLM server on partition {partition}...",
        )

        # 1. Ensure remote setup is complete
        if not self._ensure_remote_setup():
            console.error("Remote setup failed. Please check your UVA connection.")
            return None

        # 2. Start iJob and get the node
        try:
            node_hostname = self.uva.login(host=self.config["deployment"]["ssh_host"], key="v100")
            if not node_hostname:
                console.error("Failed to obtain a compute node from UVA.")
                return None
            console.ok(f"Allocated compute node: {node_hostname}")
        except Exception as e:
            console.error(f"Error during UVA login: {e}")
            return None

        # 3. Deploy and start vLLM using Apptainer
        try:
            # Use config_dir if provided, otherwise fallback to package default
            if self.config_dir:
                vllm_cmd_path = os.path.join(self.config_dir, "vllm_cmd.txt")
                if not os.path.exists(vllm_cmd_path):
                    vllm_cmd_path = os.path.join(os.path.dirname(__file__), "vllm_cmd.txt")
            else:
                vllm_cmd_path = os.path.join(os.path.dirname(__file__), "vllm_cmd.txt")
                
            with open(vllm_cmd_path, "r") as f:
                template = f.read().strip()
            
            # Combine deployment and vllm configs for template expansion
            params = {**self.config["deployment"], **self.config["vllm"], "port": port}
            vllm_script = template.format(**params)

            # Upload the script to the compute node
            remote_script_path = "/tmp/vllm_deploy.sh"
            # Use a temporary local file to scp the script
            local_tmp_script = f"/tmp/vllm_deploy_{int(time.time())}.sh"
            with open(local_tmp_script, "w") as f:
                f.write(vllm_script)

            Shell.run(f"scp {local_tmp_script} {node_hostname}:{remote_script_path}")
            os.remove(local_tmp_script)

            # Make executable and run
            Shell.run(f"ssh {node_hostname} 'chmod +x {remote_script_path} && {remote_script_path}'")
            console.ok(f"vLLM server started on {node_hostname}:{port}")
        except Exception as e:
            console.error(f"Failed to deploy vLLM server: {e}")
            return None

        # 3. Setup local SSH tunnel
        try:
            tunnel = Tunnel(local_port=port, remote_host=node_hostname, remote_port=port, ssh_host="uva")
            if tunnel.start():
                self.tunnels[port] = tunnel
            else:
                return None
        except Exception as e:
            console.error(f"Failed to setup SSH tunnel: {e}")
            return None

        return node_hostname
