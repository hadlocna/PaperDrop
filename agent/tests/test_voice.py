import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from voice_assistant import VoiceAssistant, is_wake_phrase

class VoiceTests(unittest.IsolatedAsyncioTestCase):
    def test_wake_phrase_boundaries(self):
        for text in ('hey paper drop', 'Hey PaperDrop', 'please hey paper drop'):
            self.assertTrue(is_wake_phrase(text))
        for text in ('PaperDrop', 'paper drop', 'drop the paper', 'paper', 'hey there', 'newspaper drop', ''):
            self.assertFalse(is_wake_phrase(text))

    async def test_duplicate_wake_starts_only_one_session(self):
        voice = VoiceAssistant(AsyncMock())
        await voice.wake()
        await voice.wake()
        voice.ws.send.assert_awaited_once()
        self.assertEqual(json.loads(voice.ws.send.call_args.args[0])['type'], 'voice_start')

    async def test_closed_conversation_stops_upload_readiness(self):
        voice = VoiceAssistant(AsyncMock())
        voice.enabled = voice.active = voice.ready = True
        await voice.event({'type': 'voice_end'})
        self.assertFalse(voice.active)
        self.assertFalse(voice.ready)
        self.assertEqual(voice.state, 'listening')
        await voice.wake()
        self.assertTrue(voice.active)
        self.assertEqual(json.loads(voice.ws.send.call_args.args[0])['type'], 'voice_start')

    async def test_wake_control_cannot_start_when_disabled(self):
        voice = VoiceAssistant(AsyncMock())
        voice.enabled = False
        await voice.control({'action': 'wake', 'request_id': 'r'})
        response = json.loads(voice.ws.send.call_args.args[0])
        self.assertFalse(response['ok'])
        self.assertFalse(voice.active)

    async def test_stop_cancels_capture_task(self):
        voice = VoiceAssistant(AsyncMock())
        voice.task = asyncio.create_task(asyncio.sleep(100))
        task = voice.task
        await voice.stop()
        self.assertTrue(task.cancelled())
        self.assertEqual(voice.state, 'off')

    async def test_error_notice_is_local_audio_and_does_not_upload_microphone(self):
        from unittest.mock import Mock
        voice = VoiceAssistant(AsyncMock())
        voice.play_task = Mock()
        voice.play_task.done.return_value = False
        await voice.notice('image')
        self.assertTrue(voice.speaking)
        self.assertEqual(voice.output.qsize(), 2)
        voice.ws.send.assert_not_awaited()
        await voice.notice('error')
        self.assertEqual(voice.output.qsize(), 2)

    async def test_wake_during_conversation_ignores_old_session_end(self):
        voice = VoiceAssistant(AsyncMock())
        await voice.wake()
        old = voice.session_id
        await voice.wake(restart=True)
        self.assertNotEqual(old, voice.session_id)
        await voice.event({'type': 'voice_end', 'session_id': old})
        self.assertTrue(voice.active)
        await voice.event({'type': 'voice_end', 'session_id': voice.session_id})
        self.assertFalse(voice.active)

    async def test_drawing_progress_is_not_overwritten_by_input_activity(self):
        voice = VoiceAssistant(AsyncMock())
        voice.queue_clip = AsyncMock()
        await voice.event({'type': 'voice_progress', 'state': 'drawing'})
        await voice.event({'type': 'voice_progress', 'state': 'hearing_request'})
        self.assertEqual(voice.state, 'drawing')
        voice.queue_clip.assert_awaited_once_with('voice-drawing.pcm')
        await voice.event({'type': 'voice_progress', 'state': 'talking'})
        self.assertFalse(voice.drawing)

    async def test_capture_restarts_after_failure_without_heartbeat(self):
        voice = VoiceAssistant(AsyncMock())
        voice.enabled = True
        attempts = 0
        async def listen():
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                voice.enabled = False
        voice.listen = listen
        with patch('voice_assistant.asyncio.sleep', new_callable=AsyncMock):
            await voice.supervise()
        self.assertEqual(attempts, 2)

    async def test_prompt_receipt_is_announced_once_and_not_for_stop(self):
        voice = VoiceAssistant(AsyncMock())
        voice.queue_clip = AsyncMock()
        await voice.wake()
        voice.queue_clip.reset_mock()
        await voice.event({'type': 'voice_heard', 'text': 'stop'})
        voice.queue_clip.assert_not_awaited()
        await voice.event({'type': 'voice_heard', 'text': 'Draw a lizard'})
        await voice.event({'type': 'voice_heard', 'text': 'Draw a lizard'})
        voice.queue_clip.assert_awaited_once_with('voice-received.pcm')
        await voice.event({'type': 'voice_end'})
        await voice.wake()
        await voice.event({'type': 'voice_heard', 'text': 'Draw a cat'})
        self.assertEqual(voice.queue_clip.await_count, 3)

    async def test_wake_beep_is_queued_before_cloud_request(self):
        voice = VoiceAssistant(AsyncMock())
        events = []
        async def clip(name): events.append(name)
        async def send(event): events.append(event['type'])
        voice.queue_clip = clip
        voice.send = send
        await voice.wake()
        self.assertEqual(events, ['voice-wake.pcm', 'voice_start'])
