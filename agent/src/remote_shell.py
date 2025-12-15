import os
import pty
import select
import subprocess
import struct
import fcntl
import termios
import asyncio
import logging

logger = logging.getLogger(__name__)

class RemoteShell:
    def __init__(self, on_output):
        self.master_fd = None
        self.process = None
        self.on_output = on_output
        self.loop = asyncio.get_event_loop()

    def start(self, cols=80, rows=24):
        if self.process:
            return

        # Create pty
        self.master_fd, slave_fd = pty.openpty()

        # Set size
        self.resize(cols, rows)

        # Spawn process
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        
        self.process = subprocess.Popen(
            ["/bin/bash"],
            preexec_fn=os.setsid,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            close_fds=True
        )

        os.close(slave_fd)
        
        # Monitor output
        self.loop.add_reader(self.master_fd, self._read_output)
        
        logger.info("Remote shell started")

    def _read_output(self):
        try:
            data = os.read(self.master_fd, 1024)
            if data:
                # Send to callback (async)
                asyncio.create_task(self.on_output(data.decode('utf-8', errors='ignore')))
            else:
                self.stop()
        except OSError:
            self.stop()

    def write(self, data):
        if self.master_fd:
            try:
                os.write(self.master_fd, data.encode('utf-8'))
            except Exception as e:
                logger.error(f"Error writing to shell: {e}")

    def resize(self, cols, rows):
        if self.master_fd:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    def stop(self):
        if self.master_fd:
            self.loop.remove_reader(self.master_fd)
            os.close(self.master_fd)
            self.master_fd = None
        
        if self.process:
            self.process.terminate()
            self.process = None
        
        logger.info("Remote shell stopped")
