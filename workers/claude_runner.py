"""
Shared helper for running claude -p via tmux sessions.

Follows the same pattern as houseofjawn-bot's scheduler:
  - base64-encodes the prompt so it passes through bash safely
  - writes a shell script, runs it in a named tmux session
  - polls an output file for a completion marker
  - cleans up session and temp files on exit

Session names use hawk-{prefix}-{uid8} to avoid colliding with scheduler
sessions (claude-wake-*, scheduled-wake-*, etc.).
"""
import base64
import logging
import os
import subprocess
import time
import uuid

logger = logging.getLogger(__name__)

COMPLETION_MARKER = "---HAWK_CLAUDE_DONE---"


def run_claude_p(prompt: str, session_prefix: str, timeout: int = 60) -> str | None:
    """
    Run `claude -p <prompt>` in a detached tmux session and return stdout.

    Returns the output string on success, or None on timeout or failure.
    Uses `timeout --foreground` inside the shell script (not Python's subprocess
    timeout parameter) to avoid the process-group kill issue with Node.js.
    """
    uid = uuid.uuid4().hex[:8]
    session_name = f"hawk-{session_prefix}-{uid}"
    output_file = f"/tmp/{session_name}.out"
    script_file = f"/tmp/{session_name}.sh"

    prompt_b64 = base64.b64encode(prompt.encode()).decode()

    script_content = f"""#!/bin/bash
export PATH="/home/jamditis/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/snap/bin"

PROMPT=$(echo "{prompt_b64}" | base64 -d)
timeout --foreground --kill-after=10 {timeout} claude -p "$PROMPT" > "{output_file}" 2>&1
EXIT_CODE=${{PIPESTATUS[0]}}

echo "" >> "{output_file}"
echo "{COMPLETION_MARKER}:$EXIT_CODE" >> "{output_file}"
"""

    try:
        with open(script_file, "w") as f:
            f.write(script_content)
        os.chmod(script_file, 0o755)

        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, script_file],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning(
                "Failed to create tmux session %s: %s", session_name, result.stderr.strip()
            )
            return None

        # Poll for completion marker — the script appends it when claude exits
        deadline = time.time() + timeout + 15  # buffer beyond the script's own timeout
        while time.time() < deadline:
            if os.path.exists(output_file):
                try:
                    content = open(output_file).read()
                    if COMPLETION_MARKER in content:
                        output = content[: content.index(COMPLETION_MARKER)].strip()
                        return output or None
                except OSError:
                    pass
            time.sleep(0.5)

        logger.warning("claude -p timed out in tmux session %s", session_name)
        return None

    finally:
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name], capture_output=True
        )
        for f in [script_file, output_file]:
            try:
                os.unlink(f)
            except FileNotFoundError:
                pass
