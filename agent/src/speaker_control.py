"""Keep Bluetooth discovery/pairing off the WebSocket receive loop."""
import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger('Speakers')
lock = asyncio.Lock()
tasks = set()


async def run_speaker(action, address=None, audio=None):
    cmd = ['/usr/bin/python3', str(Path(__file__).with_name('speaker_manager.py')), action]
    if address:
        cmd.append(address)
    if action == 'play' and (not isinstance(audio, str) or len(audio) > 2000000):
        return {'ok': False, 'error': 'A short WAV audio clip is required.'}
    process = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(audio.encode() if audio else None), timeout=55)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        logger.warning('Speaker helper failed: %s', stderr.decode()[-1000:])
        return {'ok': False, 'error': 'Bluetooth audio is unavailable. Update this PaperDrop and try again.'}
    return json.loads(stdout)


async def handle_speaker(websocket, data):
    try:
        if lock.locked():
            result = {'ok': False, 'error': 'Another speaker operation is running. Please wait.'}
        elif data.get('action') not in ('status', 'scan', 'connect', 'disconnect', 'test', 'microphone_test', 'play'):
            result = {'ok': False, 'error': 'Unsupported speaker action.'}
        else:
            async with lock:
                result = await run_speaker(data['action'], data.get('address'), data.get('audio'))
        await websocket.send(json.dumps({**result, 'type': 'speaker_result', 'request_id': data.get('request_id')}))
    except Exception as error:
        logger.warning('Speaker request failed: %s', error)
        try:
            await websocket.send(json.dumps({'type': 'speaker_result', 'request_id': data.get('request_id'),
                                             'ok': False, 'error': 'Speaker request timed out or failed. Try again.'}))
        except Exception:
            pass


def dispatch_speaker(websocket, data):
    task = asyncio.create_task(handle_speaker(websocket, data))
    tasks.add(task)
    task.add_done_callback(tasks.discard)


async def reconnect_speaker():
    while True:
        await asyncio.sleep(30)
        if lock.locked() or not Path('/etc/paperdrop/speaker.json').exists():
            continue
        try:
            async with lock:
                await run_speaker('reconnect')
        except Exception as error:
            logger.debug('Speaker reconnect deferred: %s', error)
