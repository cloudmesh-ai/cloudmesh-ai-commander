import os
import subprocess
import time
from typing import Optional
from cloudmesh.ai.common.io import console
from cloudmesh.ai.common.logging_utils import get_contextual_logger
from cloudmesh.ai.uva import Uva

logger = get_contextual_logger("commander")


class Commander:
    """Orchestrates AI server deployment and access on UVA."""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.uva = Uva(debug=debug)

    def run_mock(self, port: int = 18123, partition: str = "bii-gpu") -> Optional[str]:
        """
        Orchestrates the full mock server workflow:
        1. Start iJob on UVA.
        2. Deploy and start mock_vllm.py.
        3. Setup local SSH tunnel.
        """
        console.banner(
            "AI Commander Mock", f"Deploying mock server on partition {partition}..."
        )

        # 1. Start iJob and get the node
        # We use a dummy key or the default one.
        # In a real scenario, we'd let the user provide the key.
        try:
            # This is a simplified call; in reality, we might need to handle the interactive part
            # or use a pre-defined key.
            node_hostname = self.uva.login(host="uva", key="v100")
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
            console.error(f"Failed to read mock server code from {mock_server_path}: {e}")
            return None

        remote_path = f"/tmp/mock_vllm_{int(time.time())}.py"

        try:
            # Upload the mock server code
            # We use a simple ssh command to write the file
            cmd = f"ssh {node_hostname} 'echo \"{mock_code}\" > {remote_path}'"
            subprocess.run(cmd, shell=True, check=True)

            # Start the server in the background
            start_cmd = f"ssh {node_hostname} 'nohup python3 {remote_path} --port {port} > /tmp/mock_vllm.log 2>&1 &'"
            subprocess.run(start_cmd, shell=True, check=True)
            console.ok(f"Mock server started on {node_hostname}:{port}")
        except Exception as e:
            console.error(f"Failed to deploy mock server: {e}")
            return None

        # 3. Setup local SSH tunnel
        try:
            tunnel_cmd = ["ssh", "-L", f"{port}:{node_hostname}:{port}", "uva", "-N"]
            subprocess.Popen(tunnel_cmd)
            console.ok(
                f"SSH tunnel established: localhost:{port} -> {node_hostname}:{port}"
            )
        except Exception as e:
            console.error(f"Failed to setup SSH tunnel: {e}")
            return None

        return node_hostname

    def setup_tunnel(self, node: str, remote_port: int, local_port: int):
        """Utility to create an SSH tunnel to a specific node."""
        try:
            tunnel_cmd = [
                "ssh",
                "-L",
                f"{local_port}:{node}:{remote_port}",
                "uva",
                "-N",
            ]
            subprocess.Popen(tunnel_cmd)
            console.ok(
                f"Tunnel established: localhost:{local_port} -> {node}:{remote_port}"
            )
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
            setup_cmds = [
                "mkdir -p ~/.config/cloudmesh/llm",
                "chmod -R 700 ~/.config/cloudmesh",
                "mkdir -p /scratch/thf2bn/hf_cache",
            ]
            full_cmd = f"ssh uva '{' && '.join(setup_cmds)}'"
            subprocess.run(full_cmd, shell=True, check=True)

            # 2. Handle keys: Copy from local to remote if they exist locally
            local_dir = os.path.expanduser("~/.config/cloudmesh/llm")
            keys = ["HF_token.txt", "server_master_key.txt"]

            missing_keys = []
            for key in keys:
                local_path = os.path.join(local_dir, key)
                remote_path = f"uva:~/.config/cloudmesh/llm/{key}"

                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    console.info(f"Copying {key} to UVA...")
                    subprocess.run(
                        f"scp {local_path} {remote_path}", shell=True, check=True
                    )
                    subprocess.run(
                        f"ssh uva 'chmod 600 {remote_path.split(':')[-1]}'", shell=True, check=True
                    )
                else:
                    missing_keys.append(key)
                    # Create remote placeholder if local is missing or empty
                    subprocess.run(
                        f"ssh uva 'touch {remote_path} && chmod 600 {remote_path.split(':')[-1]}'", shell=True, check=True
                    )

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
                        console.warn(f"Updated permissions for directory {d_path} to 700.")
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

    def run_vllm(self, port: int = 18123, partition: str = "bii-gpu") -> Optional[str]:
        """
        Orchestrates the full vLLM server workflow:
        1. Ensure remote setup is complete.
        2. Start iJob on UVA.
        3. Deploy and start vLLM via Apptainer.
        4. Setup local SSH tunnel.
        """
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
            node_hostname = self.uva.login(host="uva", key="v100")
            if not node_hostname:
                console.error("Failed to obtain a compute node from UVA.")
                return None
            console.ok(f"Allocated compute node: {node_hostname}")
        except Exception as e:
            console.error(f"Error during UVA login: {e}")
            return None

        # 3. Deploy and start vLLM using Apptainer
        try:
            vllm_cmd_path = os.path.join(os.path.dirname(__file__), "vllm_cmd.txt")
            with open(vllm_cmd_path, "r") as f:
                vllm_script = f.read().strip().format(port=port)
            
            # Upload the script to the compute node
            remote_script_path = "/tmp/vllm_deploy.sh"
            # Use a temporary local file to scp the script
            local_tmp_script = f"/tmp/vllm_deploy_{int(time.time())}.sh"
            with open(local_tmp_script, "w") as f:
                f.write(vllm_script)
            
            subprocess.run(f"scp {local_tmp_script} {node_hostname}:{remote_script_path}", shell=True, check=True)
            os.remove(local_tmp_script)
            
            # Make executable and run
            subprocess.run(f"ssh {node_hostname} 'chmod +x {remote_script_path} && {remote_script_path}'", shell=True, check=True)
            console.ok(f"vLLM server started on {node_hostname}:{port}")
        except Exception as e:
            console.error(f"Failed to deploy vLLM server: {e}")
            return None

        # 3. Setup local SSH tunnel
        try:
            tunnel_cmd = ["ssh", "-L", f"{port}:{node_hostname}:{port}", "uva", "-N"]
            subprocess.Popen(tunnel_cmd)
            console.ok(
                f"SSH tunnel established: localhost:{port} -> {node_hostname}:{port}"
            )
        except Exception as e:
            console.error(f"Failed to setup SSH tunnel: {e}")
            return None

        return node_hostname
