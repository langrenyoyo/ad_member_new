"""Repair the explicitly selected Hehe deployment; preserve a database/env backup."""
import json
from pathlib import Path
from new_server_connection import connect, run, ROOT

REMOTE = r'''
import json, sqlite3, shutil, sys, secrets
from pathlib import Path
from datetime import datetime, timezone
base = Path('/opt/guangjiyexing')
backup = base / 'backups' / ('hehe-repair-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
backup.mkdir(mode=0o700)
with sqlite3.connect(base/'backend/app.db') as source, sqlite3.connect(backup/'app.db') as target:
    source.backup(target)
shutil.copy2(base/'.env', backup/'.env')
sys.path.insert(0, str(base/'backend'))
from app import main_from_txt as m, member_policy as p
with m.SessionLocal() as session:
    game = session.get(m.Game, 1)
    assert game and game.name == '\u79be\u5408' and game.status == 1, 'Unexpected deployment'
    config = json.loads(game.settings_json or '{}')
    ads = config.get('ad_config', {})
    assert ads.get('provider') == 'taku' and ads.get('app_id') and ads.get('app_key')
    assert ads.get('placements', {}).get('rewarded', {}).get('unit_id')
    rule_data = dict(config.get('member_policy', {}))
    rule_data.update(reward_enabled=True, commission_enabled=False)
    rule = p.Policy.model_validate(rule_data)
    assert rule.coins_per_yuan == 1 and rule.reward_basis == 'verified_cny_ecpm'
    p.check_reward_configuration(game.id, rule)
    agent = session.get(m.Agent, game.agent_id)
    if agent is None:
        assert game.agent_id == 0, 'Unexpected missing nonzero agent'
        assert session.query(m.Agent).count() == 0, 'Select the correct existing operator first'
        agent = m.Agent(name='\u79be\u5408\u8fd0\u8425\u4e3b\u4f53', status=1,
                        game_ad_status=1, security_key=secrets.token_urlsafe(32))
        session.add(agent)
        session.flush()
        old_agent_id = game.agent_id
        game.agent_id = agent.id
        session.query(m.Member).filter(m.Member.game_id == game.id,
            m.Member.agent_id == old_agent_id).update({m.Member.agent_id:agent.id})
    assert agent.status == 1
    game.ad_status = 1
    ads['enabled'] = True
    config['ad_config'] = ads
    config['member_policy'] = rule_data
    game.settings_json = json.dumps(config, ensure_ascii=False)
    session.commit()
    print(json.dumps({'agent_id':agent.id,'game_id':game.id,'ads_enabled':True,
        'verified_ecpm_rewards':True,'backup':str(backup)}))
env = (base/'.env').read_text()
for key,value in {'APP_DOWNLOAD_URL':'/downloads/hehe-latest.apk','APP_INVITE_SCHEME':'hehe'}.items():
    lines = [line for line in env.splitlines() if not line.startswith(key+'=')]
    lines.append(key+'='+value)
    env = '\n'.join(lines)+'\n'
(base/'.env').write_text(env)
(base/'.env').chmod(0o600)
'''

if __name__ == '__main__':
    client = connect()
    try:
        sftp = client.open_sftp()
        remote = '/opt/guangjiyexing/backups/repair_hehe_runtime.py'
        with sftp.file(remote, 'w') as file:
            file.write(REMOTE.encode('utf-8'))
        sftp.chmod(remote, 0o600)
        sftp.close()
        print(run(client, 'cd /opt/guangjiyexing && set -a && . ./.env && set +a && .venv/bin/python backups/repair_hehe_runtime.py'))
    finally:
        client.close()
