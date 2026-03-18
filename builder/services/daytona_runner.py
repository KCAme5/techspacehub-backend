import os
import logging
import time
from typing import List, Dict, Tuple
from daytona_sdk import Daytona, DaytonaConfig
from daytona_sdk.common.daytona import CreateSandboxFromImageParams

logger = logging.getLogger(__name__)

class DaytonaRunner:
    def __init__(self):
        # Use DAYTONA_API_URL if present, fallback to DAYTONA_SERVER_URL (deprecated)
        self.api_key = os.getenv("DAYTONA_API_KEY")
        self.api_url = os.getenv("DAYTONA_API_URL") or os.getenv("DAYTONA_SERVER_URL")
        
        if not self.api_key or not self.api_url:
            logger.error("Daytona credentials missing in environment variables.")
            raise ValueError("DAYTONA_API_KEY and DAYTONA_API_URL must be set.")

        self.config = DaytonaConfig(
            api_key=self.api_key,
            api_url=self.api_url,
            target="local" # Default target for OSS
        )
        self.client = Daytona(config=self.config)

    def run_build_test(self, files: List[Dict[str, str]], timeout: int = 300) -> Tuple[bool, str]:
        """
        Creates a sandbox, uploads files, runs npm install & build.
        Returns (success_boolean, logs_string).
        """
        sandbox = None
        try:
            logger.info("Creating Daytona sandbox for build test...")
            # Create sandbox from image params
            params = CreateSandboxFromImageParams(
                image="daytonaio/sandbox:0.5.0-slim",
                language="javascript" # We are testing Node/Vite
            )
            sandbox = self.client.create(params)
            
            # 1. Upload files
            # Note: files is list of {"name": "filename", "content": "filecontent"}
            logger.info(f"Uploading {len(files)} files to sandbox {sandbox.id}...")
            for file in files:
                # Ensure we handle multi-file structure
                # The SDK upload_file takes (source_bytes_or_path, destination_path)
                content_bytes = file['content'].encode('utf-8')
                sandbox.fs.upload_file(content_bytes, file['name'])

            # 2. Run npm install
            logger.info("Running 'npm install'...")
            # exec returns ExecuteResponse: {exit_code, result, artifacts}
            install_res = sandbox.process.exec("npm install")
            if install_res.exit_code != 0:
                combined_err = f"npm install failed (Exit {install_res.exit_code}):\n{install_res.result}"
                return False, combined_err

            # 3. Run npm run build
            logger.info("Running 'npm run build'...")
            build_res = sandbox.process.exec("npm run build")
            
            combined_logs = f"STDOUT/STDERR:\n{build_res.result}"
            
            if build_res.exit_code == 0:
                logger.info("Build test SUCCEEDED.")
                return True, combined_logs
            else:
                logger.warning(f"Build test FAILED with exit code {build_res.exit_code}.")
                return False, combined_logs

        except Exception as e:
            logger.error(f"Daytona execution error: {str(e)}")
            return False, f"Daytona Error: {str(e)}"
        finally:
            if sandbox:
                try:
                    logger.info(f"Cleaning up sandbox {sandbox.id}...")
                    self.client.delete(sandbox)
                except Exception as cleanup_err:
                    logger.error(f"Failed to cleanup sandbox: {cleanup_err}")

    def test_connection(self) -> bool:
        """Verifies if the SDK can talk to the server."""
        try:
            res = self.client.list()
            return res is not None
        except Exception as e:
            logger.error(f"Daytona connection test failed: {e}")
            return False
