# test_daytona.py
import os
from daytona_sdk import Daytona, DaytonaConfig
from daytona_sdk.common.daytona import CreateSandboxFromImageParams

config = DaytonaConfig(
    api_key="your-api-key",
    api_url="http://92.4.131.203:3000/api",
    target="us"  # ← Must match DEFAULT_REGION_ID in docker-compose
)

daytona = Daytona(config=config)

print("Creating sandbox...")
sandbox = daytona.create(CreateSandboxFromImageParams(
    image="daytonaio/sandbox:0.5.0-slim",
    language="javascript"
))
print(f"Sandbox created: {sandbox.id}")

result = sandbox.process.exec("echo 'Hello from Daytona!'")
print(f"Output: {result.result}")

daytona.delete(sandbox)
print("Sandbox deleted. Everything works! ✅")