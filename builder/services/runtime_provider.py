import uuid
from dataclasses import dataclass


@dataclass
class RuntimeBundle:
    provider: str
    runtime_status: str
    runtime_session_id: str
    payload: dict


class BaseRuntimeProvider:
    provider_name = "base"

    def prepare(self, session) -> RuntimeBundle:
        raise NotImplementedError


class WebContainerRuntimeProvider(BaseRuntimeProvider):
    provider_name = "webcontainer"

    def prepare(self, session) -> RuntimeBundle:
        runtime_session_id = session.runtime_session_id or str(uuid.uuid4())
        files = session.files or []
        output_type = session.output_type

        if output_type == "react":
            install_command = ["npm", "install"]
            dev_command = ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "4173"]
            preview = {
                "port": 4173,
                "open_path": "/",
            }
        else:
            install_command = []
            dev_command = []
            preview = {
                "port": None,
                "open_path": "/index.html",
            }

        payload = {
            "provider": self.provider_name,
            "output_type": output_type,
            "project_name": session.project_name,
            "runtime_session_id": runtime_session_id,
            "files": files,
            "commands": {
                "install": install_command,
                "dev": dev_command,
            },
            "preview": preview,
            "capabilities": {
                "supports_terminal": True,
                "supports_preview": True,
                "supports_runtime_events": True,
                "supports_browser_errors": True,
            },
        }
        return RuntimeBundle(
            provider=self.provider_name,
            runtime_status="prepared",
            runtime_session_id=runtime_session_id,
            payload=payload,
        )


def get_runtime_provider(output_type: str) -> BaseRuntimeProvider:
    if output_type in {"react", "html"}:
        return WebContainerRuntimeProvider()
    raise ValueError(f"No runtime provider available for output_type={output_type}")
