"""Hidden Windows child tree supervised by a private kill-on-close job."""
import ctypes
import math
import subprocess
import sys
from ctypes import wintypes as W


def start_hidden_process(command, cwd):
    if sys.platform != 'win32':
        raise RuntimeError('El receptor requiere Windows.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    class Basic(ctypes.Structure):
        _fields_ = [('ProcessTime', ctypes.c_int64), ('JobTime', ctypes.c_int64),
                    ('Flags', W.DWORD), ('MinWorkingSet', ctypes.c_size_t),
                    ('MaxWorkingSet', ctypes.c_size_t), ('ActiveProcessLimit', W.DWORD),
                    ('Affinity', ctypes.c_size_t), ('Priority', W.DWORD), ('Scheduling', W.DWORD)]
    class Counters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('ReadOps', 'WriteOps', 'OtherOps', 'ReadBytes', 'WriteBytes', 'OtherBytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('Basic', Basic), ('Counters', Counters), ('ProcessMemory', ctypes.c_size_t),
                    ('JobMemory', ctypes.c_size_t), ('PeakProcessMemory', ctypes.c_size_t), ('PeakJobMemory', ctypes.c_size_t)]
    class Startup(ctypes.Structure):
        _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR), ('title', W.LPWSTR),
                    *[(name, W.DWORD) for name in ('x', 'y', 'width', 'height', 'xchars', 'ychars', 'fill', 'flags')],
                    ('show', W.WORD), ('reservedSize', W.WORD), ('reservedBytes', ctypes.c_void_p),
                    ('stdin', W.HANDLE), ('stdout', W.HANDLE), ('stderr', W.HANDLE)]
    class ProcessInfo(ctypes.Structure):
        _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]
    signatures = {
        'CreateJobObjectW': ([ctypes.c_void_p, W.LPCWSTR], W.HANDLE),
        'SetInformationJobObject': ([W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD], W.BOOL),
        'AssignProcessToJobObject': ([W.HANDLE, W.HANDLE], W.BOOL),
        'CreateProcessW': ([W.LPCWSTR, W.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, W.BOOL, W.DWORD,
                            ctypes.c_void_p, W.LPCWSTR, ctypes.POINTER(Startup), ctypes.POINTER(ProcessInfo)], W.BOOL),
        'ResumeThread': ([W.HANDLE], W.DWORD), 'CloseHandle': ([W.HANDLE], W.BOOL),
        'TerminateJobObject': ([W.HANDLE, W.UINT], W.BOOL),
        'TerminateProcess': ([W.HANDLE, W.UINT], W.BOOL),
        'WaitForSingleObject': ([W.HANDLE, W.DWORD], W.DWORD),
        'GetExitCodeProcess': ([W.HANDLE, ctypes.POINTER(W.DWORD)], W.BOOL),
    }
    for name, (args, result) in signatures.items():
        fn = getattr(kernel, name); fn.argtypes = args; fn.restype = result
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = ProcessInfo()
    try:
        limits = Extended(); limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        startup = Startup(); startup.cb = ctypes.sizeof(startup)
        line = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in command]))
        # Assign the suspended bootloader before it can create its Python child.
        if not kernel.CreateProcessW(str(command[0]), line, None, None, False, 0x08000004,
                                     None, str(cwd), ctypes.byref(startup), ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(job, info.process):
            raise ctypes.WinError(ctypes.get_last_error())
        if kernel.ResumeThread(info.thread) == 0xffffffff:
            raise ctypes.WinError(ctypes.get_last_error())
        kernel.CloseHandle(info.thread); info.thread = None
        return JobProcess(kernel, job, info.process, command)
    except BaseException:
        if info.process:
            kernel.TerminateProcess(info.process, 1)
            kernel.CloseHandle(info.process)
        if info.thread: kernel.CloseHandle(info.thread)
        kernel.CloseHandle(job)
        raise


class JobProcess:
    def __init__(self, kernel, job, process, command):
        self.kernel, self.job, self.process, self.command = kernel, job, process, command
        self.returncode = None

    def poll(self):
        if self.returncode is not None: return self.returncode
        code = self.kernel.WaitForSingleObject(self.process, 0)
        if code == 258: return None
        if code != 0: raise ctypes.WinError(ctypes.get_last_error())
        result = W.DWORD()
        if not self.kernel.GetExitCodeProcess(self.process, ctypes.byref(result)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.returncode = result.value
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            ms = 0xffffffff if timeout is None else min(0xfffffffe, max(0, math.ceil(timeout * 1000)))
            code = self.kernel.WaitForSingleObject(self.process, ms)
            if code == 258: raise subprocess.TimeoutExpired(self.command, timeout)
            if code != 0: raise ctypes.WinError(ctypes.get_last_error())
            self.poll()
        self.close()
        return self.returncode

    def terminate(self):
        if self.job and not self.kernel.TerminateJobObject(self.job, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    kill = terminate

    def close(self):
        if self.job:
            self.kernel.CloseHandle(self.job); self.job = None
        if self.process:
            self.kernel.CloseHandle(self.process); self.process = None
