"""Install/restore the macOS test controller without editing the old prototype."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
LABEL='com.paperdrop.cousins-streamdeck'
OLD='com.paperdrop.streamdeck-soundboard'
DOMAIN=f'gui/{os.getuid()}'
AGENTS=Path.home()/'Library/LaunchAgents'
PLIST=AGENTS/(LABEL+'.plist')
STATE=ROOT/'.state'


def ctl(*args,check=False):
    return subprocess.run(['launchctl',*args],capture_output=True,text=True,check=check)


def main():
    STATE.mkdir(exist_ok=True)
    if sys.argv[1:] == ['stop']:
        ctl('bootout',DOMAIN,str(PLIST))
        ctl('disable',f'{DOMAIN}/{LABEL}')
        ctl('enable',f'{DOMAIN}/{OLD}')
        old=AGENTS/(OLD+'.plist')
        if old.exists():ctl('bootstrap',DOMAIN,str(old))
        print('Cousins test stopped; previous Stream Deck prototype restored.')
        return
    if not (ROOT/'.venv/bin/python').exists():
        raise SystemExit('Create .venv and install requirements.txt first.')
    ctl('bootout',DOMAIN,str(PLIST))
    ctl('bootout',f'{DOMAIN}/{OLD}')
    ctl('disable',f'{DOMAIN}/{OLD}')
    config={
        'Label':LABEL,'ProgramArguments':[str(ROOT/'.venv/bin/python'),str(ROOT/('bridge.py' if '--bridge' in sys.argv else 'app.py'))],
        'WorkingDirectory':str(ROOT),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':5,
        'StandardOutPath':str(STATE/'controller.log'),'StandardErrorPath':str(STATE/'controller.log'),
        'EnvironmentVariables':{'PATH':'/opt/homebrew/bin:/usr/bin:/bin','PYTHONUNBUFFERED':'1'}
    }
    PLIST.write_bytes(plistlib.dumps(config))
    ctl('enable',f'{DOMAIN}/{LABEL}')
    ctl('bootstrap',DOMAIN,str(PLIST),check=True)
    print(('Pi button bridge' if '--bridge' in sys.argv else 'Cousins test')+' installed. Companion: http://127.0.0.1:8766')


if __name__=='__main__':main()
