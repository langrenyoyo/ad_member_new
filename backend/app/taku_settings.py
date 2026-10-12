"""Write-only global publisher credentials and rotating eCPM private keys."""
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from . import main_from_txt as m


class GlobalKeysInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    publisher_key: str = Field(default='', max_length=512)
    server_ecpm_key: str = Field(default='', max_length=16384)
    server_ecpm_key_id: str = Field(default='', max_length=128)
    client_ecpm_key: str = Field(default='', max_length=16384)
    client_ecpm_key_id: str = Field(default='', max_length=128)


def status(row):
    result = {'publisher_key_configured': bool(row and row.publisher_key)}
    for kind in ('server', 'client'):
        keys = json.loads(getattr(row, kind+'_ecpm_key') or '{}') if row else {}
        result[kind+'_ecpm_key_configured'] = bool(keys)
        result[kind+'_ecpm_key_ids'] = list(keys)
    return result


@m.api.get('/settings/taku-keys')
def get_keys(admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as session:
        return status(session.get(m.TakuGlobalConfig, 1))


@m.api.patch('/settings/taku-keys')
def save_keys(body: GlobalKeysInput, admin=Depends(m.allow_roles('superadmin'))):
    updates = {}
    for kind in ('server', 'client'):
        pem = getattr(body, kind+'_ecpm_key').strip()
        key_id = getattr(body, kind+'_ecpm_key_id').strip()
        if bool(pem) != bool(key_id):
            raise HTTPException(422, 'eCPM Key 与对应 Key ID 必须一起填写')
        if not pem:
            continue
        try:
            key = serialization.load_pem_private_key(pem.encode(), password=None)
            if not isinstance(key, rsa.RSAPrivateKey):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(422, 'eCPM Key 必须是有效的未加密 RSA PEM 私钥') from None
        updates[kind] = (key_id, key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())
    with m.SessionLocal() as session:
        # Serialize global edits, including on SQLite.
        if session.bind.dialect.name == 'sqlite':
            session.execute(m.text('BEGIN IMMEDIATE'))
        row = session.scalar(m.select(m.TakuGlobalConfig).where(m.TakuGlobalConfig.id == 1).with_for_update())
        if row is None:
            row = m.TakuGlobalConfig(id=1, publisher_key='', server_ecpm_key='{}', client_ecpm_key='{}')
            session.add(row)
        maps = {k: json.loads(getattr(row, k+'_ecpm_key') or '{}') for k in ('server', 'client')}
        for kind, (key_id, pem) in updates.items():
            # Never replace an existing id with a different private key.
            existing = maps['server'].get(key_id) or maps['client'].get(key_id)
            if existing and existing != pem:
                raise HTTPException(409, '该 Key ID 已存在不同密钥，请使用新 Key ID 轮换')
            maps[kind][key_id] = pem
            setattr(row, kind+'_ecpm_key', json.dumps(maps[kind]))
        if body.publisher_key.strip():
            row.publisher_key = body.publisher_key.strip()
        session.add(m.AdminOperation(admin_id=admin.id, title='更新 TAKU 全局密钥（不记录密钥内容）',
                                     path='/api/v1/settings/taku-keys', ip=''))
        session.commit()
        return status(row)


def global_ecpm_keys():
    with m.SessionLocal() as session:
        row = session.get(m.TakuGlobalConfig, 1)
        if not row:
            return {}
        return {**json.loads(row.server_ecpm_key or '{}'), **json.loads(row.client_ecpm_key or '{}')}
