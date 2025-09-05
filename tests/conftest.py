import sys
import types


def pytest_sessionstart(session):
    """Provide lightweight stubs for optional runtime deps so test import works without network installs."""
    # Stub `litellm` so importing TinyAgent doesn't fail during collection
    if "litellm" not in sys.modules:
        mod = types.ModuleType("litellm")

        async def _acompletion(**kwargs):
            raise RuntimeError("litellm acompletion stub called during tests")

        mod.acompletion = _acompletion
        mod.drop_params = True
        # Common exception classes referenced by string in config; define for safety
        class APIError(Exception):
            pass

        class InternalServerError(APIError):
            pass

        class APIConnectionError(APIError):
            pass

        class RateLimitError(APIError):
            pass

        class ServiceUnavailableError(APIError):
            pass

        class APITimeoutError(APIError):
            pass

        class BadRequestError(APIError):
            pass

        mod.APIError = APIError
        mod.InternalServerError = InternalServerError
        mod.APIConnectionError = APIConnectionError
        mod.RateLimitError = RateLimitError
        mod.ServiceUnavailableError = ServiceUnavailableError
        mod.APITimeoutError = APITimeoutError
        mod.BadRequestError = BadRequestError
        sys.modules["litellm"] = mod

    # Stub `mcp` to satisfy optional imports during test collection
    if "mcp" not in sys.modules:
        mcp_mod = types.ModuleType("mcp")

        class ClientSession:
            async def list_tools(self):
                class _Resp:
                    tools = []

                return _Resp()

            async def close(self):
                return None

        class StdioServerParameters:
            def __init__(self, command, args=None, env=None):
                self.command = command
                self.args = args or []
                self.env = env or {}

        mcp_mod.ClientSession = ClientSession
        mcp_mod.StdioServerParameters = StdioServerParameters
        # Build package hierarchy mcp.client.stdio
        client_mod = types.ModuleType("mcp.client")

        stdio_mod = types.ModuleType("mcp.client.stdio")

        async def stdio_client(params):
            class _Dummy:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

            return _Dummy()

        stdio_mod.stdio_client = stdio_client

        # Attach to sys.modules
        sys.modules["mcp"] = mcp_mod
        sys.modules["mcp.client"] = client_mod
        sys.modules["mcp.client.stdio"] = stdio_mod

    # Provide a stub for tinyagent.mcp_client to avoid parsing type hints incompatible with Python 3.8
    if "tinyagent.mcp_client" not in sys.modules:
        ta_mcp = types.ModuleType("tinyagent.mcp_client")

        class MCPClient:
            def __init__(self, *args, **kwargs):
                self._tools = []

            async def list_tools(self):
                class _Resp:
                    tools = []

                return _Resp()

            async def call_tool(self, name, args):
                return []

            async def close(self):
                return None

        ta_mcp.MCPClient = MCPClient
        sys.modules["tinyagent.mcp_client"] = ta_mcp

    # Stub cloudpickle with stdlib pickle to satisfy provider imports
    if "cloudpickle" not in sys.modules:
        import pickle as _pickle
        cp = types.ModuleType("cloudpickle")
        cp.dumps = _pickle.dumps
        cp.loads = _pickle.loads
        sys.modules["cloudpickle"] = cp
