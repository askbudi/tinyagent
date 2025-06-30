# TinyAgent Modal sandbox utilities
# ---------------------------------

from __future__ import annotations

import inspect
import json
import os
import sys
from textwrap import dedent
from typing import Any, Iterable, Sequence, Tuple

import modal
from modal.stream_type import StreamType

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# By default we use the interpreter version running this code.
DEFAULT_PYTHON_VERSION: str = f"{sys.version_info.major}.{sys.version_info.minor}"
PYTHON_VERSION: str = os.getenv("TINYAGENT_PYTHON_VERSION", DEFAULT_PYTHON_VERSION)

# Simple ANSI colour helper for interactive feedback
COLOR = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "ENDC": "\033[0m",
}

# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def get_source(obj: Any) -> str:
    """Return a *dedented* string with the source code of *obj*.

    Raises ValueError if the source cannot be inspected.  A dedicated utility
    avoids a hard dependency on the public `inspect.getsource` semantics
    scattered throughout the rest of the library.
    """
    try:
        return dedent(inspect.getsource(obj))
    except (OSError, TypeError) as exc:  # pragma: no cover – environment specific
        raise ValueError(f"Unable to retrieve source for {obj!r}") from exc


# ---------------------------------------------------------------------------
# Sandbox creation helpers
# ---------------------------------------------------------------------------

def create_sandbox(
    modal_secrets: modal.Secret,  # Same semantics as the demo util
    *,
    timeout: int = 5 * 60,
    volumes: dict | None = None,
    workdir: str | None = None,
    python_version: str | None = None,
    apt_packages: Sequence[str] | None = None,
    default_packages: Sequence[str] | None = None,
    pip_install: Sequence[str] | None = None,
    image_name: str = "tinyagent-sandbox-image",
    app_name: str = "persistent-code-session",
    force_build: bool = False,
    **sandbox_kwargs,
) -> Tuple[modal.Sandbox, modal.App]:
    """Create (or lookup) a `modal.Sandbox` pre-configured for code execution.

    The parameters largely bubble up to the underlying *modal* API while
    providing TinyAgent-friendly defaults.  Developers can override any aspect
    of the environment without patching library internals.
    """

    # Resolve defaults ------------------------------------------------------
    python_version = python_version or PYTHON_VERSION

    if apt_packages is None:
        # Always install the basics required for most workflows
        apt_packages = ("git", "curl", "nodejs", "npm","ripgrep","tree")

    if default_packages is None:
        default_packages = (
            "asyncpg>=0.27.0",
            "aiosqlite>=0.18.0",
            "gradio>=3.50.0",
            "jinja2",
            "pyyaml",
            "cloudpickle",
            "modal",
            "nest-asyncio",
            "mcp[cli]",
            "PyGithub",
            "fastmcp",
            "gitingest",
        )

    full_pip_list = set(default_packages).union(pip_install or [])

    # Build image -----------------------------------------------------------
    agent_image = (
        modal.Image.debian_slim(python_version=python_version,force_build=force_build)
        .apt_install(*apt_packages)
        .pip_install(*full_pip_list)
    )

    # Re-use a named Modal app so subsequent calls share cached state / layers
    app = modal.App.lookup(app_name, create_if_missing=True)

    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            image=agent_image,
            timeout=timeout,
            app=app,
            volumes=volumes or {},
            workdir=workdir,
            secrets=[modal_secrets],
            **sandbox_kwargs,
        )

    return sandbox, app


# ---------------------------------------------------------------------------
# Streaming execution helpers
# ---------------------------------------------------------------------------


def _pretty(header: str, text: str) -> None:  # Convenience printing wrapper
    print(f"{COLOR[header]}{text}{COLOR['ENDC']}")


def run_streaming(
    command: Sequence[str],
    sb: modal.Sandbox,
    *,
    prefix: str = "📦",
) -> Tuple[str, str]:
    """Run *command* inside *sb* streaming stdout/stderr in real-time."""

    _pretty("HEADER", f"{prefix}: Running in sandbox")
    _pretty("GREEN", " ".join(map(str, command)))

    exc = sb.exec(
        *command,
        stdout=StreamType.PIPE,
        stderr=StreamType.PIPE,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    # Forward STDOUT lines as they arrive
    try:
        for line in exc.stdout:  # type: ignore[attr-defined]
            print(f"{COLOR['BLUE']}OUT: {line.rstrip()}{COLOR['ENDC']}")
            stdout_lines.append(line)
    except Exception as e:  # noqa: BLE001
        _pretty("RED", f"Error during stdout streaming: {e}")

    # Forward STDERR after stdout stream completes
    try:
        for line in exc.stderr:  # type: ignore[attr-defined]
            print(f"{COLOR['RED']}ERR: {line.rstrip()}{COLOR['ENDC']}")
            stderr_lines.append(line)
    except Exception as e:  # noqa: BLE001
        _pretty("RED", f"Error during stderr streaming: {e}")

    exc.wait()
    if exc.returncode != 0:
        _pretty("HEADER", f"{prefix}: Failed with exitcode {exc.returncode}")
    else:
        _pretty("GREEN", f"{prefix}: Completed successfully")

    return "".join(stdout_lines), "".join(stderr_lines)


# Specialisation for quick *python ‑c* jobs ------------------------------

def run_streaming_python(code: str, sb: modal.Sandbox) -> Tuple[str, str]:
    """Convenience wrapper to execute *code* via `python -c` with printing flush."""

    full_code = "from functools import partial\nprint = partial(print, flush=True)\n" + code
    return run_streaming(["python", "-c", full_code], sb)


# ---------------------------------------------------------------------------
# Stateful session wrapper
# ---------------------------------------------------------------------------

class SandboxSession:
    """Maintain a persistent sandbox instance across multiple executions."""

    def __init__(
        self,
        modal_secrets: modal.Secret,
        *,
        timeout: int = 5 * 60,
        
        **create_kwargs,
    ) -> None:
        self.modal_secrets = modal_secrets
        self.timeout = timeout
        self._create_kwargs = create_kwargs
        self.sandbox: modal.Sandbox | None = None
        self.app: modal.App | None = None
        self._driver_proc: "modal.container_process.ContainerProcess" | None = None

    # Public API -----------------------------------------------------------

    def ensure_sandbox(self) -> modal.Sandbox:
        if self.sandbox is None:
            self.sandbox, self.app = create_sandbox(
                self.modal_secrets,
                timeout=self.timeout,
                **self._create_kwargs,
            )
            _pretty("GREEN", "📦: Created new sandbox session")
        return self.sandbox

    def run_python(self, code: str) -> Tuple[str, str]:
        """Shortcut for *python -c* streaming runs."""
        return run_streaming_python(code, self.ensure_sandbox())

    def run(self, command: Sequence[str]) -> Tuple[str, str]:
        """Run arbitrary command with streaming output."""
        return run_streaming(command, self.ensure_sandbox())

    def terminate(self) -> None:
        if self.sandbox is not None:
            # Terminate driver first (if any)
            self.terminate_driver()
            self.sandbox.terminate()
            self.sandbox = None
            _pretty("HEADER", "📦: Terminated sandbox session")

    # Context-manager interface -------------------------------------------

    def __enter__(self) -> "SandboxSession":
        self.ensure_sandbox()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: D401
        self.terminate()

    # -------------------------------------------------------------------
    # Driver / stateful Python execution helpers
    # -------------------------------------------------------------------

    def start_driver(self) -> "modal.container_process.ContainerProcess":
        """Launch *driver_program* inside the sandbox (if not already running)."""

        import modal.container_process  # Local import to avoid hard dep at top

        sandbox = self.ensure_sandbox()

        if self._driver_proc is not None:
            return self._driver_proc  # Already running

        driver_code = get_source(driver_program) + "\n\ndriver_program()"

        self._driver_proc = sandbox.exec(
            "python",
            "-c",
            driver_code,
            stdout=StreamType.PIPE,
            stderr=StreamType.PIPE,
        )

        _pretty("GREEN", "🚀 Driver program started in sandbox")
        return self._driver_proc

    def run_stateful(self, code: Any) -> str:  # noqa: ANN401 – allow flexible input
        """Execute *code* (or the source of *obj*) in the persistent driver with streaming.

        If *code* is not a string, the helper attempts to obtain its
        source using :pyfunc:`get_source` so that users can conveniently
        pass in callables or other Python objects directly.
        """

        # Accept arbitrary objects for convenience ------------------------
        if not isinstance(code, str):
            try:
                code = get_source(code)
            except ValueError as exc:  # Fallback to string representation
                _pretty(
                    "RED",
                    f"⚠️  Unable to retrieve source for object {code!r}: {exc}. Falling back to str(obj).",
                )
                code = str(code)

        proc = self.start_driver()
        return run_code_streaming(proc, code)

    def terminate_driver(self) -> None:
        """Terminate the stateful driver process if running."""

        if self._driver_proc is not None:
            try:
                self._driver_proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            self._driver_proc = None
            _pretty("HEADER", "📦: Driver process terminated")


# ---------------------------------------------------------------------------
# Stateful in-sandbox code execution helper
# ---------------------------------------------------------------------------

# Below we *copy verbatim* the proven driver + streaming logic from the demo
# script so as not to break existing behaviour.  Only minimal stylistic tweaks
# (type annotations, comments) are applied.


def driver_program():
    import json
    import sys
    import time
    import builtins

    globals: dict[str, Any] = {}
    
    # Store original stdout and stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    original_print = builtins.print
    
    def streaming_print(*args, sep=' ', end='\n', file=None, flush=False):
        """Custom print function that streams output immediately"""
        if file is None or file == sys.stdout:
            # Convert args to string like normal print
            output = sep.join(str(arg) for arg in args) + end
            # Send immediately as JSON
            original_stdout.write(json.dumps({"type": "stdout", "content": output}) + '\n')
            original_stdout.flush()
        elif file == sys.stderr:
            # Convert args to string like normal print
            output = sep.join(str(arg) for arg in args) + end
            # Send immediately as JSON
            original_stdout.write(json.dumps({"type": "stderr", "content": output}) + '\n')
            original_stdout.flush()
        else:
            # Use original print for other files
            original_print(*args, sep=sep, end=end, file=file, flush=flush)
    
    class StreamingStdout:
        def write(self, text):
            if text and not text.isspace():
                original_stdout.write(json.dumps({"type": "stdout", "content": text}) + '\n')
                original_stdout.flush()
            return len(text)
        
        def flush(self):
            original_stdout.flush()
        
        def fileno(self):
            return original_stdout.fileno()
        
        def isatty(self):
            return False
        
        def readable(self):
            return False
        
        def writable(self):
            return True
        
        def seekable(self):
            return False
    
    class StreamingStderr:
        def write(self, text):
            if text and not text.isspace():
                original_stdout.write(json.dumps({"type": "stderr", "content": text}) + '\n')
                original_stdout.flush()
            return len(text)
        
        def flush(self):
            original_stdout.flush()
        
        def fileno(self):
            return original_stderr.fileno()
        
        def isatty(self):
            return False
        
        def readable(self):
            return False
        
        def writable(self):
            return True
        
        def seekable(self):
            return False
    
    while True:
        try:
            command = json.loads(input())
            if (code := command.get("code")) is None:
                original_stdout.write(json.dumps({"error": "No code to execute"}) + '\n')
                original_stdout.flush()
                continue

            # Send start marker
            original_stdout.write(json.dumps({"type": "start"}) + '\n')
            original_stdout.flush()
            
            # Replace print and stdout/stderr for streaming
            builtins.print = streaming_print
            sys.stdout = StreamingStdout()
            sys.stderr = StreamingStderr()
            
            try:
                exec(code, globals)
            except Exception as e:
                # Send error through stderr
                sys.stderr.write(f"Execution Error: {e}\n")
            finally:
                # Restore original stdout/stderr/print
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                builtins.print = original_print
                
            # Send completion marker
            original_stdout.write(json.dumps({"type": "complete"}) + '\n')
            original_stdout.flush()
            
        except EOFError:
            break
        except Exception as e:
            original_stdout.write(json.dumps({"type": "error", "message": str(e)}) + '\n')
            original_stdout.flush()


def run_code_streaming(
    p: "modal.container_process.ContainerProcess",
    code: str,
) -> str:
    """Send *code* to an already-running `driver_program` process and stream output."""

    p.stdin.write(json.dumps({"code": code}))
    p.stdin.write("\n")
    p.stdin.drain()

    buffer = ""

    for chunk in p.stdout:
        buffer += chunk
        while buffer.strip():
            try:
                result, idx = json.JSONDecoder().raw_decode(buffer)
            except json.JSONDecodeError:
                break  # Need more data

            buffer = buffer[idx:].lstrip()
            _type = result.get("type")
            if _type == "start":
                print("🔄 Executing code…")
            elif _type == "stdout":
                print(result["content"], end="")
            elif _type == "stderr":
                print(f"\033[91m{result['content']}\033[0m", end="")
            elif _type == "complete":
                print("✅ Execution complete")
                return buffer
            elif result.get("error"):
                print(f"❌ Error: {result['error']}")
                return buffer


# Convenience shortcut --------------------------------------------------------

def start_sandbox_session(modal_secrets: modal.Secret, **kwargs) -> SandboxSession:
    """Helper returning an *active* `SandboxSession` instance."""

    session = SandboxSession(modal_secrets, **kwargs)
    session.ensure_sandbox()
    return session 