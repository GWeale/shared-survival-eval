"""Bound subprocess stdout AND stderr while reading; POSIX process-tree cleanup."""
import os
import selectors
import signal
import subprocess
import tempfile
import time


def bounded_command(argv, payload, timeout, limit=100_000):
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryFile() as request:
        request.write(payload.encode('utf-8')); request.seek(0)
        process = subprocess.Popen(argv, stdin=request, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        chunks, sizes = [], {'stdout': 0, 'stderr': 0}
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
                selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(argv, timeout)
                    for key, _ in selector.select(remaining):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj); continue
                        sizes[key.data] += len(chunk)
                        if sizes[key.data] > limit:
                            raise ValueError('command output exceeds 100 KB stream limit')
                        if key.data == 'stdout': chunks.append(chunk)
            return process.wait(timeout=max(.001, deadline-time.monotonic())), b''.join(chunks).decode('utf-8')
        finally:
            # A grandchild can hold a pipe open after its parent exits.
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
            process.stdout.close(); process.stderr.close()
