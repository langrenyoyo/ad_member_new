from pathlib import Path
import re
import paramiko

ROOT = Path(__file__).resolve().parents[1]

def configuration():
    raw = (ROOT/'apk/server.md').read_text(encoding='utf-8')
    def field(key):
        return re.search(r'^'+key+r'\s*[:：]\s*(\S+)', raw, re.M|re.I).group(1)
    return dict(hostname=field('IP'), port=int(field('prot')), username=field('username'), password=field('password'))

def connect():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    known = ROOT/'artifacts/new-server-deploy/known_hosts'
    if known.exists(): client.load_host_keys(str(known))
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(**configuration(), timeout=20, allow_agent=False, look_for_keys=False)
    client.save_host_keys(str(known))
    return client

def run(client, command, timeout=120):
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    output = stdout.read().decode(errors='replace')
    error = stderr.read().decode(errors='replace')
    code = stdout.channel.recv_exit_status()
    if code: raise RuntimeError('Remote command failed: '+error[-1500:]+output[-1500:])
    return output
