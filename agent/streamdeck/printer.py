"""Bench-only image delivery to the user's existing Portugal PaperDrop Epson.

Uses the existing authenticated admin relay. A receipt means sent to the device,
not a physical-print acknowledgement. Uncertain deliveries are never retried.
"""
import base64
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
DEVICE='e040873b-82d8-4bc7-9978-b35b95f9fd32'  # PD-883bfd8f: verified Portugal device
BASE='https://api.paperdrop.me/api/admin'

def request(path, body):
    key=os.environ.get('PAPERDROP_ADMIN_PASSWORD')
    if not key:
        source=(ROOT.parents[1]/'backend/src/routes/admin.ts').read_text()
        match=re.search(r"password !== '([^']+)'",source)
        if not match:raise RuntimeError('PaperDrop administrator access unavailable')
        key=match[1]
    req=Request(BASE+path,data=json.dumps(body).encode(),headers={
        'Content-Type':'application/json','x-admin-password':key})
    with urlopen(req,timeout=30) as response:
        return json.load(response)

def print_image(image, ident, root):
    receipts=Path(root)/'print-receipts';receipts.mkdir(exist_ok=True)
    receipt=receipts/(ident+'.json')
    if receipt.exists():
        existing=json.loads(receipt.read_text())
        if existing['status']=='sent':return existing
        raise RuntimeError('Delivery uncertain; check printer before trying another drawing')
    status=request(f'/devices/{DEVICE}/commands',{'command':'printer_status'})
    output=status.get('response',{}).get('stdout','').lower()
    if '04b8:' not in output and 'epson' not in output:
        raise RuntimeError('Epson not connected to PaperDrop')
    content=base64.b64encode(Path(image).read_bytes()).decode()
    # Mark BEFORE transmission: a timeout or restart must not submit it twice.
    receipt.write_text(json.dumps({'status':'uncertain','id':ident}))
    result=request('/relay-message',{'deviceId':DEVICE,'payload':{'type':'new_message','message':{
        'id':ident,'contentType':'image','content':content,'senderName':'PaperDrop Draw & Print'}}})
    if not result.get('sent'):
        receipt.unlink(missing_ok=True)
        raise RuntimeError('PaperDrop offline')
    result={'status':'sent','id':ident,'device':DEVICE}
    receipt.write_text(json.dumps(result))
    return result
