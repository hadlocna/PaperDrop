#!/usr/bin/env python3
"""Probe the real portal/DNS/nftables in isolated Linux namespaces, without changing Wi-Fi.

Run as root: python3 verify_captive_portal_network.py /path/to/wifi_portal.py
The installed or staged setup-logo.png must live alongside that helper.
"""
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=20)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Linux root is required for isolated network probes.')
    portal = Path(sys.argv[1]).resolve()
    if not portal.is_file() or not portal.with_name('setup-logo.png').is_file():
        raise SystemExit('Provide the portal helper with its installed logo alongside it.')
    suffix = secrets.token_hex(3)
    access, client = 'pd-ap-' + suffix, 'pd-client-' + suffix
    a_link, c_link = 'pda' + suffix, 'pdc' + suffix
    created = []
    server = None
    try:
        for namespace in (access, client):
            run('ip', 'netns', 'add', namespace)
            created.append(namespace)
        run('ip', 'link', 'add', a_link, 'type', 'veth', 'peer', 'name', c_link)
        run('ip', 'link', 'set', a_link, 'netns', access)
        run('ip', 'link', 'set', c_link, 'netns', client)
        for namespace, link, name, address in (
                (access, a_link, 'wlan0', '10.42.0.1/24'),
                (client, c_link, 'eth0', '10.42.0.50/24')):
            run('ip', '-n', namespace, 'link', 'set', link, 'name', name)
            run('ip', '-n', namespace, 'address', 'add', address, 'dev', name)
            run('ip', '-n', namespace, 'link', 'set', name, 'up')
            run('ip', '-n', namespace, 'link', 'set', 'lo', 'up')
        run('ip', '-n', client, 'route', 'add', 'default', 'via', '10.42.0.1')
        program = '''import importlib.util, time, sys
spec=importlib.util.spec_from_file_location('portal',sys.argv[1])
wifi=importlib.util.module_from_spec(spec);spec.loader.exec_module(wifi)
portal=wifi.Portal()
portal.scan=lambda **kwargs: {'networks':[],'message':''}
portal.start_dns()
wifi.serve(portal)
while True: time.sleep(1)
'''
        server = subprocess.Popen(['ip', 'netns', 'exec', access, 'python3', '-c', program, str(portal)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        probe = '''import http.client,json,socket,struct
results={}
for host in ('paperdrop.me','www.paperdrop.me','anything.example'):
    question=b''.join(bytes([len(part)])+part.encode() for part in host.split('.'))+b'\\x00'+struct.pack('!HH',1,1)
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.settimeout(3)
    sock.sendto(struct.pack('!HHHHHH',1234,256,1,0,0,0)+question,('10.42.0.1',53))
    answer=sock.recv(4096)
    assert socket.inet_ntoa(answer[-4:])=='10.42.0.1'
    sock.close()
results['wildcard_dns']='passed'
for destination,host,path in (
        ('10.42.0.1','example.com','/some/page?x=1'),
        ('198.51.100.77','cached.example','/cached'),
        ('203.0.113.25','203.0.113.25','/literal-ip'),
        ('10.42.0.1','connectivitycheck.gstatic.com','/generate_204')):
    connection=http.client.HTTPConnection(destination,80,timeout=3)
    connection.request('GET',path,headers={'Host':host});response=connection.getresponse()
    assert response.status==302 and response.getheader('Location')=='http://paperdrop.me/'
    response.read();connection.close()
results['arbitrary_http_host_and_cached_or_literal_ip']='passed'
for port in (80,8080):
    connection=http.client.HTTPConnection('10.42.0.1',port,timeout=3)
    connection.request('GET','/',headers={'Host':'paperdrop.me'});response=connection.getresponse()
    assert response.status==200 and b'Nearby networks' in response.read()
    connection.close()
results['paperdrop_me_both_ports']='passed'
connection=http.client.HTTPConnection('10.42.0.1',80,timeout=3)
connection.request('GET','/paperdrop-logo.png',headers={'Host':'paperdrop.me'});response=connection.getresponse()
body=response.read();assert response.status==200 and response.getheader('Content-Type')=='image/png' and body.startswith(b'\\x89PNG')
results['offline_logo']='passed'
print(json.dumps(results))
'''
        for attempt in range(20):
            if server.poll() is not None:
                raise RuntimeError('Portal process failed: ' + server.communicate()[1])
            try:
                result = run('ip', 'netns', 'exec', client, 'python3', '-c', probe)
                print(json.dumps(json.loads(result.stdout), indent=2))
                break
            except subprocess.CalledProcessError:
                if attempt == 19:
                    raise
                time.sleep(0.25)
    finally:
        # Kill only processes in namespaces created by this invocation.
        for namespace in reversed(created):
            pids = subprocess.run(['ip', 'netns', 'pids', namespace], capture_output=True, text=True)
            for pid in pids.stdout.split():
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            subprocess.run(['ip', 'netns', 'delete', namespace], capture_output=True)
        if server is not None:
            try:
                server.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate()


if __name__ == '__main__':
    main()
