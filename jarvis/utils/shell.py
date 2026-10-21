"""Subprocess execution helper. Async, cross-platform, with timeout."""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    cmd: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


async def run_command(
    cmd: str,
    cwd: str | Path | None = None,
    timeout: int = 60,
    shell: str | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run a single command line. Uses cmd.exe on Windows, sh elsewhere.

    On Windows, PowerShell can be selected by passing shell='powershell'.
    """
    cwd_str = str(cwd) if cwd else os.getcwd()
    final_env = os.environ.copy()
    if env:
        final_env.update(env)

    from ..extensions.processes import ProcessManager
    if sys.platform == "win32":
        command, args = ("powershell", ["-NoProfile", "-Command", cmd]) if shell == "powershell" else (os.environ.get("COMSPEC", "cmd.exe"), ["/d", "/s", "/c", cmd])
    else:
        command, args = (shell or "/bin/sh"), ["-c", cmd]
    manager = ProcessManager()
    result = await manager.run(command, args, cwd_str, max(1, min(timeout, 1800)), final_env)
    stdout = "".join(text for channel, text in result["output"] if channel == "stdout")
    stderr = "".join(text for channel, text in result["output"] if channel == "stderr")
    if result.get("timed_out"):
        stderr += f"\n[timeout after {timeout}s]"
    return CommandResult(cmd=cmd, cwd=cwd_str,
                         returncode=result["returncode"] if result["returncode"] is not None else -1,
                         stdout=stdout, stderr=stderr, timed_out=result.get("timed_out", False))
