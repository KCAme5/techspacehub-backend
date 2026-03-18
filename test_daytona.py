import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DAYTONA_API_KEY")
api_url = os.getenv("DAYTONA_SERVER_URL")
target = os.getenv("DAYTONA_TARGET", "default")

print(f"Testing with target: {target}")

try:
    from daytona_sdk import Daytona, DaytonaConfig
    from daytona_sdk.common.daytona import CreateSandboxFromImageParams
    
    config = DaytonaConfig(
        api_key=api_key,
        api_url=api_url,
        target=target,
    )
    
    print("Initializing Daytona...")
    daytona = Daytona(config=config)
    
    print("Successfully connected. Attempting to create a test sandbox...")
    params = CreateSandboxFromImageParams(
        image="daytonaio/sandbox:0.5.0-slim",
        language="javascript"
    )
    sandbox = daytona.create(params)
    print(f"Sandbox created successfully! ID: {sandbox.id}")
    
    print("Cleaning up...")
    daytona.delete(sandbox)
    print("Done!")
except Exception as e:
    import traceback
    traceback.print_exc()
