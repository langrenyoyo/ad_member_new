"""One-use SMS login codes; Aliyun SendSms credentials remain server-side."""
import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import timedelta
from urllib.parse import quote, urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, DateTime, select, func, text
from sqlalchemy.orm import Mapped, mapped_column
from . import main_from_txt as m


class SmsCode(m.Base, m.TimestampMixin):
    __tablename__ = 'app_sms_codes'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    phone_hash: Mapped[str] = mapped_column(String(64), index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(16), default='sending')


def digest(value):
    return hmac.new(m.JWT_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def send_sms(phone, code):
    key, secret, sign, template = [os.getenv(n, '').strip() for n in
        ('SMS_ALIYUN_ACCESS_KEY_ID', 'SMS_ALIYUN_ACCESS_KEY_SECRET', 'SMS_ALIYUN_SIGN_NAME', 'SMS_ALIYUN_TEMPLATE_CODE')]
    if not all((key, secret, sign, template)): raise HTTPException(503, '短信服务尚未配置')
    params = {'Action': 'SendSms', 'Version': '2017-05-25', 'Format': 'JSON', 'AccessKeyId': key,
        'SignatureMethod': 'HMAC-SHA1', 'SignatureVersion': '1.0', 'SignatureNonce': secrets.token_hex(16),
        'Timestamp': m.now().strftime('%Y-%m-%dT%H:%M:%SZ'), 'RegionId': 'cn-hangzhou',
        'PhoneNumbers': phone, 'SignName': sign, 'TemplateCode': template,
        'TemplateParam': json.dumps({'code': code}, separators=(',', ':'))}
    enc = lambda x: quote(str(x), safe='~')
    canonical = '&'.join(f'{enc(k)}={enc(v)}' for k, v in sorted(params.items()))
    signature = hmac.new((secret+'&').encode(), ('POST&%2F&'+enc(canonical)).encode(), hashlib.sha1).digest()
    params['Signature'] = base64.b64encode(signature).decode()
    try:
        request = UrlRequest('https://dysmsapi.aliyuncs.com/', data=urlencode(params).encode(), method='POST')
        with urlopen(request, timeout=10) as response: result = json.loads(response.read())
        if result.get('Code') != 'OK': raise HTTPException(503, '短信发送失败，请稍后重试')
    except (OSError, ValueError) as error:
        raise HTTPException(503, '短信服务暂不可用') from error


class SendCode(BaseModel):
    phone: str = Field(pattern=r'^1[3-9]\d{9}$')
    game_id: int = Field(ge=1)


class SmsLogin(m.AppClient):
    phone: str = Field(pattern=r'^1[3-9]\d{9}$')
    game_id: int = Field(ge=1)
    challenge_id: str = Field(min_length=1, max_length=64)
    code: str = Field(pattern=r'^\d{6}$')
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class SmsPassword(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    code: str = Field(pattern=r'^\d{6}$')
    new_password: str = Field(min_length=8, max_length=128)


@m.app_api.post('/auth/sms/password')
def sms_password(body: SmsPassword, member=Depends(m.require_app_member)):
    m._app_validate_password(body.new_password)
    with m.SessionLocal() as session:
        m.device_risk.game_lock(session, member.game_id)
        stored = session.get(m.Member, member.id)
        row = session.get(SmsCode, body.challenge_id)
        if row is None or row.game_id != stored.game_id or row.phone_hash != digest(stored.username) or row.state != 'ready' or row.attempts >= 5 or row.expires_at.replace(tzinfo=m.UTC) <= m.now():
            raise HTTPException(401, '验证码无效或不属于当前账号')
        row.attempts += 1
        if not hmac.compare_digest(row.code_hash, digest(row.id+body.code)):
            session.commit()
            raise HTTPException(401, '验证码不正确')
        stored.password_hash, stored.password_salt = m.hash_password(body.new_password)
        row.state = 'used'
        session.commit()
        return {'data': {'password_set': True}}


@m.app_api.post('/auth/sms/send')
def send_code(body: SendCode, request: Request):
    phone_hash = digest(body.phone)
    ip_hash = digest(request.client.host if request.client else '')
    code, challenge = f'{secrets.randbelow(1000000):06d}', secrets.token_urlsafe(24)
    with m.SessionLocal() as session:
        m.device_risk.game_lock(session, body.game_id)
        if session.get_bind().dialect.name == 'postgresql':
            # Global quotas must serialize across games as well as within one game.
            keys = sorted({int(digest('sms-phone:'+phone_hash)[:16], 16) % (2**63),
                           int(digest('sms-ip:'+ip_hash)[:16], 16) % (2**63)})
            for key in keys:
                session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})
        m._wechat_game(session, body.game_id)
        rows = list(session.scalars(select(SmsCode).where(SmsCode.created_at >= m.now()-timedelta(hours=24),
            (SmsCode.phone_hash == phone_hash) | (SmsCode.ip_hash == ip_hash))))
        phones = [r for r in rows if r.phone_hash == phone_hash]
        if len(phones) >= 10 or len(rows) >= 50 or any(r.created_at.replace(tzinfo=m.UTC) > m.now()-timedelta(seconds=60) for r in phones):
            raise HTTPException(429, '验证码请求过于频繁，请稍后再试')
        row = SmsCode(id=challenge, phone_hash=phone_hash, ip_hash=ip_hash, game_id=body.game_id,
            code_hash=digest(challenge+code), expires_at=m.now()+timedelta(minutes=5))
        session.add(row)
        session.commit()
    try: send_sms(body.phone, code)
    except HTTPException:
        with m.SessionLocal() as session:
            session.get(SmsCode, challenge).state = 'failed'
            session.commit()
        raise
    with m.SessionLocal() as session:
        session.get(SmsCode, challenge).state = 'ready'
        session.commit()
    return {'data': {'challenge_id': challenge, 'retry_after': 60, 'expires_in': 300}}


@m.app_api.post('/auth/sms/login')
def sms_login(body: SmsLogin, request: Request):
    if body.new_password: m._app_validate_password(body.new_password)
    with m.SessionLocal() as session:
        m.device_risk.game_lock(session, body.game_id)
        row = session.get(SmsCode, body.challenge_id)
        if row is None or row.game_id != body.game_id or row.phone_hash != digest(body.phone) or row.state != 'ready' or row.attempts >= 5 or row.expires_at.replace(tzinfo=m.UTC) <= m.now():
            raise HTTPException(401, '验证码无效或已过期')
        row.attempts += 1
        if not hmac.compare_digest(row.code_hash, digest(row.id+body.code)):
            session.commit()
            raise HTTPException(401, '验证码不正确')
        game = m._wechat_game(session, body.game_id)
        member = session.scalar(select(m.Member).where(m.Member.username == body.phone))
        if member is None:
            hashed, salt = m.hash_password(secrets.token_urlsafe(32))
            member = m.Member(username=body.phone, name=body.phone, game_id=game.id, agent_id=game.agent_id,
                password_hash=hashed, password_salt=salt, status=1)
            session.add(member)
            session.flush()
        if member.game_id != body.game_id or member.status != 1:
            raise HTTPException(403, '账号不可用于当前应用')
        if body.new_password:
            member.password_hash, member.password_salt = m.hash_password(body.new_password)
        device = session.get(m.MemberDevice, member.id)
        if device and device.device_id_ban and device.device_id != body.device_id:
            raise HTTPException(403, '设备不可用')
        row.state = 'used'
        m._app_device(session, member, body.device_id, request, body.app_version)
        tokens = m._app_tokens(session, member, body.device_id)
        session.commit()
        return {'data': {'user': m._app_member_payload(member, body.device_id), **tokens}}
