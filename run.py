import os
import pty
import fcntl
import termios
import signal
import os
import select
import subprocess
import signal
import time
from typing import List, Union, Optional, Mapping

def run_with_subprocess(
    args: Union[str, List[str]],
    *,
    input: Optional[bytes] = None,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
    check: bool = False,
    encoding: Optional[str] = None,
    errors: Optional[str] = None,
) -> subprocess.CompletedProcess:
    with subprocess.Popen(args,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          cwd=cwd,
                          env=env) as process:
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise
        except:
            process.kill()
            raise
        retcode = process.poll()
        if check and retcode:
            raise subprocess.CalledProcessError(
                retcode, process.args, output=stdout, stderr=stderr)

    if encoding is not None:
        if isinstance(stdout, bytes):
            stdout = stdout.decode(encoding, errors or "strict")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(encoding, errors or "strict")

    return subprocess.CompletedProcess(process.args, retcode, stdout, stderr)

def run_with_tty(
    args: Union[str, List[str]],
    *,
    input: Optional[bytes] = None,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
    check: bool = False,
    encoding: Optional[str] = None,
    errors: Optional[str] = None,
) -> subprocess.CompletedProcess:
    master_fd, slave_fd = pty.openpty()

    popen_kwargs = dict(
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=cwd,
        env=env,
        preexec_fn=os.setsid,
        close_fds=False,
    )

    proc = subprocess.Popen(args, **popen_kwargs)

    os.close(slave_fd)

    import select

    out_chunks: List[bytes] = []
    written = 0
    input_bytes = input if input is not None else b""

    deadline = None if timeout is None else (select._time() + timeout)

    while True:
        rlist = [master_fd]
        wlist = []
        if written < len(input_bytes):
            wlist.append(master_fd)

        if deadline is not None:
            timeout_remaining = max(0, deadline - select._time())
        else:
            timeout_remaining = None

        rdy_r, rdy_w, _ = select.select(rlist, wlist, [], timeout_remaining)

        if master_fd in rdy_r:
            try:
                data = os.read(master_fd, 4096)
            except OSError:
                data = b""
            if data:
                out_chunks.append(data)
            else:
                break

        if master_fd in rdy_w:
            to_write = input_bytes[written:]
            n = os.write(master_fd, to_write)
            written += n

        if deadline is not None and select._time() >= deadline:
            proc.kill()
            raise subprocess.TimeoutExpired(
                args, timeout, output=b"".join(out_chunks)
            )

        if proc.poll() is not None:
            if not rdy_r:
                continue

    os.close(master_fd)
    returncode = proc.wait()

    raw_output = b"".join(out_chunks)

    if encoding is not None:
        stdout = raw_output.decode(encoding, errors or "strict")
        stderr = None
    else:
        stdout = raw_output
        stderr = None

    completed = subprocess.CompletedProcess(
        args,
        returncode,
        stdout,
        stderr,
    )

    if check and returncode != 0:
        raise subprocess.CalledProcessError(
            returncode, args, output=stdout, stderr=stderr
        )
    return completed

def pty_fork_and_exec(argv,
                      cwd: str | None = None,
                      env: dict | None = None,
                      restore_sigmask: bool = True) -> int:

    master_fd, slave_fd = pty.openpty()

    pid = os.fork()
    if pid == 0:
        os.setsid()

        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

        os.dup2(slave_fd, 0)   # stdin
        os.dup2(slave_fd, 1)   # stdout
        os.dup2(slave_fd, 2)   # stderr

        os.close(master_fd)
        os.close(slave_fd)

        if cwd is not None:
            os.chdir(cwd)

        if isinstance(argv, str):
            os.execvp(argv, [argv])
        else:
            if env is None:
                os.execvpe(argv[0], argv, os.environ)
            else:
                os.execve(argv[0], argv, env)

        os._exit(127)
    else:
        os.close(slave_fd)
        return pid, master_fd
    
def run_in_pty(
    args: Union[str, List[str]],
    *,
    input: Optional[bytes] = None,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
    check: bool = False,
    encoding: Optional[str] = None,
    errors: Optional[str] = None,
) -> subprocess.CompletedProcess:
    pid, master_fd = pty_fork_and_exec(args, cwd=cwd, env=env)

    out_chunks: List[bytes] = []
    to_send = input if input is not None else b""
    sent = 0

    deadline = None if timeout is None else (time.monotonic() + timeout)

    while True:
        rlist = [master_fd]
        wlist = [master_fd] if sent < len(to_send) else []

        if deadline is not None:
            remaining = max(0.0, deadline - time.monotonic())
        else:
            remaining = None

        rdy_r, rdy_w, _ = select.select(rlist, wlist, [], remaining)

        if master_fd in rdy_r:
            try:
                data = os.read(master_fd, 4096)
            except OSError:
                data = b""
            if data:
                out_chunks.append(data)
            else:
                break

        if master_fd in rdy_w:
            n = os.write(master_fd, to_send[sent:])
            sent += n

        if deadline is not None and time.monotonic() >= deadline:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            raise subprocess.TimeoutExpired(
                args,
                timeout,
                output=b"".join(out_chunks)
            )

        if os.waitpid(pid, os.WNOHANG)[0] != 0:
            continue

    os.close(master_fd)
    pid, status = os.waitpid(pid, 0)

    if os.WIFEXITED(status):
        returncode = os.WEXITSTATUS(status)
    elif os.WIFSIGNALED(status):
        returncode = -os.WTERMSIG(status)
    else:
        returncode = -1

    raw_output = b"".join(out_chunks)
    if encoding is not None:
        stdout = raw_output.decode(encoding, errors or "strict")
    else:
        stdout = raw_output

    completed = subprocess.CompletedProcess(args, returncode, stdout, None)

    if check and returncode != 0:
        raise subprocess.CalledProcessError(
            returncode, args, output=stdout, stderr=None
        )
    return completed
