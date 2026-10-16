"""Own a probe invocation and its descendants without third-party dependencies.

POSIX uses a new session/process group. Windows starts suspended, assigns the
process to a kill-on-close Job Object, then resumes its initial thread.
"""

from __future__ import annotations

import os
import signal
import subprocess
from typing import Dict, List, Optional


class ContainmentError(RuntimeError):
    """Execution cannot safely start or finish inside its owned boundary."""


class ProcessInterrupted(Exception):
    def __init__(self, signum: int):
        self.signum = signum
        super().__init__("Probe interrupted")


class _WindowsJob:
    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.handle = None

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimits), ("IoInfo", IOCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class ThreadEntry(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
            ]

        self.ThreadEntry = ThreadEntry
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            "Thread32First": ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
            "Thread32Next": ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
            "OpenThread": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
        }
        for name, (argtypes, restype) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes = argtypes
            function.restype = restype
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign_and_resume(self, process: subprocess.Popen) -> None:
        ctypes = self.ctypes
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        # Popen closes the initial thread handle. Find that thread while the
        # process is still suspended, before any of the CLI's code can run.
        snapshot = self.kernel.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = self.ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            available = self.kernel.Thread32First(snapshot, ctypes.byref(entry))
            while available:
                if entry.th32OwnerProcessID == process.pid:
                    thread = self.kernel.OpenThread(0x0002, False, entry.th32ThreadID)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if self.kernel.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        return
                    finally:
                        self.kernel.CloseHandle(thread)
                available = self.kernel.Thread32Next(snapshot, ctypes.byref(entry))
            raise ContainmentError("Could not find the suspended process's initial thread.")
        finally:
            self.kernel.CloseHandle(snapshot)

    def terminate(self) -> None:
        if self.handle and not self.kernel.TerminateJobObject(self.handle, 1):
            raise self.ctypes.WinError(self.ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def run_command(cmd: List[str], stdin: Optional[str], timeout: int,
                env: Dict[str, str]) -> subprocess.CompletedProcess:
    """Run one command; dispose descendants on success, timeout, or interruption."""
    if os.name not in ("posix", "nt"):
        raise ContainmentError("Process containment is supported only on POSIX and Windows.")
    process = None
    job = None
    previous_handlers = {}
    launching = True
    pending_signal = None

    def interrupt(signum, frame):
        nonlocal pending_signal
        # Defer interruption until Popen returns an owned handle. Raising
        # halfway through creation can leave an untracked child behind.
        if launching:
            pending_signal = signum
        else:
            raise ProcessInterrupted(signum)

    def terminate():
        if process is None:
            return
        if job is not None:
            job.terminate()
            # Also covers failure before assignment to the job.
            if process.poll() is None:
                process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, interrupt)
        if os.name == "nt":
            try:
                job = _WindowsJob()
            except OSError as exc:
                raise ContainmentError("Windows Job Object creation failed.") from exc
        options = {"start_new_session": True} if os.name == "posix" else {
            "creationflags": 0x00000004 | subprocess.CREATE_NEW_PROCESS_GROUP,  # CREATE_SUSPENDED
        }
        process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env, **options,
        )
        if pending_signal is not None:
            raise ProcessInterrupted(pending_signal)
        if job is not None:
            try:
                job.assign_and_resume(process)
            except OSError as exc:
                raise ContainmentError("Windows Job Object assignment/resume failed.") from exc
        launching = False
        if pending_signal is not None:
            raise ProcessInterrupted(pending_signal)
        try:
            stdout, stderr = process.communicate(input=stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as exc:
                raise ContainmentError("Output pipes stayed open after process-tree cleanup.") from exc
            raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr) from None
        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
    finally:
        # A second interrupt must not interrupt the cleanup itself.
        for signum in previous_handlers:
            signal.signal(signum, signal.SIG_IGN)
        try:
            try:
                terminate()
            finally:
                if job is not None:
                    job.close()
                if process is not None:
                    try:
                        process.wait(timeout=5)
                    finally:
                        for stream in (process.stdin, process.stdout, process.stderr):
                            if stream is not None:
                                stream.close()
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ContainmentError("Could not finish process-tree cleanup.") from exc
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
