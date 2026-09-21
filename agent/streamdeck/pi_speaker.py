#!/usr/bin/python3
"""Keep the saved speaker in A2DP stereo; USB owns microphone capture."""
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.append('/opt/paperdrop')
from speaker_manager import Speakers, load_settings

def main():
    settings=load_settings()
    if not settings.get('autoConnect') or not settings.get('address'):
        return
    speaker=Speakers()
    obj=speaker.target(settings['address'])
    speaker.prepare_playback(obj)
    pcm='/org/bluealsa/hci0/dev_'+settings['address'].replace(':','_')+'/a2dpsrc/sink'
    info=subprocess.run(['bluealsa-cli','info',pcm],capture_output=True,text=True,timeout=5)
    if info.returncode or 'Channels: 2' not in info.stdout or 'Sampling: 44100 Hz' not in info.stdout:
        subprocess.run(['bluealsa-cli','codec','--channels=2','--sampling=44100',pcm,'SBC'],check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    speaker.restore_volume()
if __name__=='__main__':main()
