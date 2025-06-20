"""Demo: TinyCodeAgent + Modal sandbox via the new utilities.

Run this script from a Jupyter notebook or python -m to see how *much* less
boilerplate is required compared with the original `tinycode_modal_sandbox.py`.

Steps shown:
1.  Build a sandbox with a volume mount and install the local TinyAgent tree.
2.  Execute an arbitrary *python -c* snippet with live streaming.
3.  Launch the stateful driver and run two code snippets inside the same
    process, demonstrating preserved state.
4.  Instantiate `TinyCodeAgent` and let it execute inside the sandbox via the
    driver.
"""

from __future__ import annotations

import asyncio
import os
from textwrap import dedent

import modal
from dotenv import load_dotenv

from tinyagent.code_agent.modal_sandbox import (
    SandboxSession,
)
from tinyagent.code_agent import TinyCodeAgent

# ---------------------------------------------------------------------------
# Environment & secrets
# ---------------------------------------------------------------------------

load_dotenv()

modal_secrets = modal.Secret.from_dict(
    {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    }
)

# ---------------------------------------------------------------------------
# Prepare a volume containing the local source tree so the sandbox can pip-install it
# ---------------------------------------------------------------------------

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
vol = modal.Volume.from_name("tinyagent-src", create_if_missing=True)
with vol.batch_upload(force=True) as batch:
    batch.put_directory(ROOT, "/workspace/tinyagent-src/")

# ---------------------------------------------------------------------------
# Start a session (creates sandbox lazily)
# ---------------------------------------------------------------------------

session = SandboxSession(
    modal_secrets,
    timeout=300,
    volumes={"/workspace": vol},
    workdir="/workspace/tinyagent-src",
)

# ---------------------------------------------------------------------------
# 1) Install the local editable TinyAgent package inside sandbox
# ---------------------------------------------------------------------------

session.run(["pip", "install", "-e", "."])

# ---------------------------------------------------------------------------
# 2) Quick one-off command with live streaming
# ---------------------------------------------------------------------------

session.run_python(
    "import time; [print(f'⏱  tick {i}') or time.sleep(1) for i in range(3)]"
)

# ---------------------------------------------------------------------------
# 3) Stateful Python execution via driver
# ---------------------------------------------------------------------------

# First snippet defines a variable in driver globals
session.run_stateful(
    dedent(
        """
        counter = 0
        def inc():
            global counter
            counter += 1
            print(f"counter is now {counter}")
        """
    )
)

# Second snippet demonstrates the state is preserved
session.run_stateful("for _ in range(3): inc()")

# ---------------------------------------------------------------------------
# 4) TinyCodeAgent running inside the same sandbox
# ---------------------------------------------------------------------------

agent = TinyCodeAgent(model="gpt-4.1-mini", local_execution=True)

async def _run():
    prompt = "Calculate the sum of the numbers 1..10 in Python and show the result."
    response = await agent.run(prompt, max_turns=3)
    print("\n🧠 Agent response:\n", response)

# Execute the agent through the driver (stateful)
code_to_run = dedent(
    f"""
    import asyncio
    from tinyagent.code_agent import TinyCodeAgent

    agent = TinyCodeAgent(model='gpt-4.1-mini', local_execution=True)
    result = asyncio.run(agent.run('Calculate the sum of numbers 1..5', max_turns=3))
    print(result)
    """
)

session.run_stateful(code_to_run)

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

session.terminate() 