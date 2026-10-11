"""One-shot local stdio MCP client. Never requests calendar access."""
import json
import os
import selectors
import subprocess
import sys
import time
from pathlib import Path


class RPCError(RuntimeError):
    def __init__(self, error):
        self.code = error['code']
        super().__init__(error['message'])


class Client:
    def __init__(self, command=None, *, env=None, timeout=20):
        state = Path(os.environ.get('LOCAL_APPLE_CALENDAR_HOME', Path.home() / 'Library/Application Support/LocalAppleCalendar'))
        self.selector = selectors.DefaultSelector()
        self.process = None
        self.counter = 0
        self.buffer = b''
        self.timeout = timeout
        self.closed = False
        try:
            self.process = subprocess.Popen(command or [str(state / 'calendar-mcp')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0, env=env)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            result = self.call('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'calendar-local-client', 'version': '0.1.0'}})
            if result['protocolVersion'] != '2025-06-18':
                raise RuntimeError('Unsupported protocol version')
            self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        except BaseException:
            self.close()
            raise

    def send(self, message):
        data = (json.dumps(message) + '\n').encode()
        while data:
            written = self.process.stdin.write(data)
            if not written:
                raise BrokenPipeError('Local Calendar MCP input closed')
            data = data[written:]

    def call(self, method, params):
        self.counter += 1
        self.send({'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params})
        deadline = time.monotonic() + self.timeout
        while True:
            if b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                message = json.loads(line)
                if message.get('id') != self.counter:
                    raise RuntimeError('Unexpected MCP response ID')
                if 'error' in message:
                    raise RPCError(message['error'])
                return message['result']
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(timeout=remaining):
                raise TimeoutError('Local Calendar MCP did not respond. No cached result is available.')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('Local Calendar MCP is unavailable. No cached result is available.')
            self.buffer += chunk

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.selector.close()
        if self.process is None:
            return
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process.stdout.close()


if __name__ == '__main__':
    client = None
    try:
        client = Client()
        if len(sys.argv) == 1:
            result = client.call('tools/list', {})
        else:
            result = client.call('tools/call', {'name': sys.argv[1], 'arguments': json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1 if result.get('isError') else 0)
    except (OSError, ValueError, RuntimeError, TimeoutError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    finally:
        if client:
            client.close()
