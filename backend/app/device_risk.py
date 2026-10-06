"""Aliyun verified device associations and transactional ad admission limits."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from fastapi import Depends, HTTPException, Query, Request as WebRequest
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column

from . import main_from_txt as m


class DeviceRule(m.Base, m.TimestampMixin):
    __tablename__ = 'device_risk_rules'
    game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[int] = mapped_column(Integer, default=0)
    limit_enabled: Mapped[int] = mapped_column(Integer, default=0)
    daily_limit: Mapped[int] = mapped_column(Integer, default=10)
    risk_days: Mapped[int] = mapped_column(Integer, default=7)
    reset_tags: Mapped[str] = mapped_column(Text, default='[]')


class RiskDevice(m.Base, m.TimestampMixin):
    __tablename__ = 'risk_devices'
    __table_args__ = (UniqueConstraint('game_id', 'device_key', name='uq_risk_game_device'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    device_key: Mapped[str] = mapped_column(String(64))
    tags: Mapped[str] = mapped_column(Text, default='[]')
    reason: Mapped[str] = mapped_column(String(255), default='')
    risk_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    override: Mapped[str] = mapped_column(String(16), default='auto')
    last_member_id: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=m.now)


class DeviceInstall(m.Base, m.TimestampMixin):
    __tablename__ = 'risk_device_installs'
    __table_args__ = (UniqueConstraint('device_id', 'install_hash', name='uq_risk_device_install'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(Integer, index=True)
    install_hash: Mapped[str] = mapped_column(String(64))


class DeviceCheck(m.Base, m.TimestampMixin):
    __tablename__ = 'device_risk_checks'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    install_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), default='')
    provider_request_id: Mapped[str] = mapped_column(String(128), default='')
    status: Mapped[str] = mapped_column(String(32), default='issued')


class DeviceAdAdmission(m.Base):
    __tablename__ = 'device_ad_admissions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(Integer, index=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    ad_session_id: Mapped[str] = mapped_column(String(80), unique=True)
    check_id: Mapped[str] = mapped_column(String(64), unique=True)
    quota_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=m.now)


class RuleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    limit_enabled: bool = False
    daily_limit: int = Field(default=10, ge=0, le=10000)
    risk_days: int = Field(default=7, ge=1, le=365)
    reset_tags: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def validate_rule(self):
        if self.limit_enabled and not self.enabled: raise ValueError('启用广告限次前请先开启设备识别')
        if any(not re.fullmatch(r'[A-Za-z0-9_:-]{1,64}', x) for x in self.reset_tags):
            raise ValueError('风险标签必须是阿里云控制台中的标签代码')
        return self


class ChallengeInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    game_id: int = Field(ge=1)
    install_id: str = Field(min_length=16, max_length=128)


class CheckInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    challenge_id: str = Field(min_length=20, max_length=64)
    aliyun_device_token: str = Field(min_length=10, max_length=16384)


class OverrideInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    mode: str = Field(pattern=r'^(auto|allow|restrict)$')
    reason: str = Field(min_length=1, max_length=200)


def configured():
    return bool(os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID') and os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET'))


def aliyun_check(token, biz_id):
    """SAF ExecuteRequest RPC v2019-05-21, enhanced device_risk_pro."""
    if not configured(): raise HTTPException(503, '阿里云设备风控尚未配置')
    region = os.getenv('ALIYUN_RISK_REGION', 'cn-shanghai')
    if region != 'cn-shanghai': raise HTTPException(503, '当前设备风控仅配置上海地域')
    values = {'Format':'JSON', 'Version':'2019-05-21', 'AccessKeyId':os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'],
        'SignatureMethod':'HMAC-SHA1', 'SignatureVersion':'1.0', 'SignatureNonce':secrets.token_hex(16),
        'Timestamp':datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), 'Action':'ExecuteRequest',
        'RegionId':region, 'Service':'device_risk_pro',
        'ServiceParameters':json.dumps({'deviceToken':token, 'deviceTokenBizId':biz_id}, separators=(',',':'))}
    if os.getenv('ALIBABA_CLOUD_SECURITY_TOKEN'): values['SecurityToken'] = os.environ['ALIBABA_CLOUD_SECURITY_TOKEN']
    encode = lambda s: quote(str(s), safe='~')
    canonical = '&'.join(encode(k)+'='+encode(values[k]) for k in sorted(values))
    signed = 'POST&%2F&'+encode(canonical)
    values['Signature'] = base64.b64encode(hmac.new((os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET']+'&').encode(),
        signed.encode(), hashlib.sha1).digest()).decode()
    try:
        req = Request('https://saf.cn-shanghai.aliyuncs.com/',data=urlencode(values).encode(),
            headers={'Content-Type':'application/x-www-form-urlencoded'})
        with urlopen(req, timeout=5) as response: raw = response.read(131073)
        if len(raw)>131072: raise ValueError()
        result = json.loads(raw)
        code = result.get('Code',result.get('code'))
        if str(code) != '200': raise ValueError()
        data = result.get('Data',result.get('data'))
        if isinstance(data,str): data=json.loads(data)
        device = data.get('extend')
        tags = data.get('tags', '')
        if not isinstance(device,str) or not device or len(device)>512 or not isinstance(tags,str) or len(tags)>8192:
            raise ValueError()
        return device, [x.strip() for x in tags.split(',') if x.strip()], str(result.get('RequestId',result.get('requestId','')))[:128]
    except Exception:
        raise HTTPException(503, '设备校验暂不可用，请稍后重试；未授权广告') from None


def game_lock(session, game_id):
    # All admissions and rule/device mutations lock game first. This also
    # serializes first-device insertion on PostgreSQL (no absent-row race).
    m.payouts.lock(session)
    game = session.scalar(select(m.Game).where(m.Game.id==game_id).with_for_update())
    if game is None: raise HTTPException(404,'游戏不存在')
    return game


def scoped_game(game, member):
    if game.agent_id != member.agent_id or game.status != 1: raise HTTPException(403,'游戏不可用')


def rule_data(rule):
    if rule is None: return RuleInput().model_dump()
    return dict(enabled=bool(rule.enabled),limit_enabled=bool(rule.limit_enabled),daily_limit=rule.daily_limit,
                risk_days=rule.risk_days,reset_tags=json.loads(rule.reset_tags))


def risky(device):
    if device.override=='allow': return False
    return device.override=='restrict' or bool(device.risk_until and device.risk_until.replace(tzinfo=UTC)>m.now())


def usage(session, device, member_id=None):
    today=(m.now()+timedelta(hours=8)).date()
    query=select(func.count()).select_from(DeviceAdAdmission).where(DeviceAdAdmission.game_id==device.game_id,
        DeviceAdAdmission.quota_date==today)
    count=session.scalar(query.where(DeviceAdAdmission.device_id==device.id)) or 0
    if member_id is not None:
        count=max(count,session.scalar(query.where(DeviceAdAdmission.member_id==member_id)) or 0)
    return count


@m.app_api.post('/device-risk/challenge',status_code=201)
def challenge(payload:ChallengeInput,member:m.Member=Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        game=game_lock(session,payload.game_id);scoped_game(game,member)
        rule=session.get(DeviceRule,game.id)
        if rule is None or not rule.enabled: raise HTTPException(409,'该游戏未开启设备识别')
        recent=session.scalar(select(func.count()).select_from(DeviceCheck).where(DeviceCheck.member_id==member.id,
            DeviceCheck.created_at>=m.now()-timedelta(minutes=1))) or 0
        if recent>=10: raise HTTPException(429,'设备校验请求过于频繁')
        item=DeviceCheck(id=secrets.token_urlsafe(24),member_id=member.id,game_id=game.id,
            install_hash=m._token_hash(payload.install_id),expires_at=m.now()+timedelta(minutes=5))
        session.add(item);session.commit()
        return {'data':{'challenge_id':item.id,'biz_id':item.id,'expires_at':m.stringify(item.expires_at)},'request_id':item.id}


@m.app_api.post('/device-risk/verify')
def verify(payload:CheckInput,member:m.Member=Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        item=session.get(DeviceCheck,payload.challenge_id)
        if item is None or item.member_id!=member.id: raise HTTPException(404,'设备校验不存在')
        gid=item.game_id
    with m.SessionLocal() as session:
        game=game_lock(session,gid);scoped_game(game,member)
        item=session.get(DeviceCheck,payload.challenge_id)
        if item.expires_at.replace(tzinfo=UTC)<=m.now() or item.status!='issued': raise HTTPException(409,'校验已使用或过期，请重新申请')
        item.status='checking';session.commit()
    try:
        provider_device,tags,request_id=aliyun_check(payload.aliyun_device_token,payload.challenge_id)
    except HTTPException:
        with m.SessionLocal() as session:
            game_lock(session,gid);item=session.get(DeviceCheck,payload.challenge_id);item.status='failed';session.commit()
        raise
    with m.SessionLocal() as session:
        game=game_lock(session,gid);scoped_game(game,member)
        item=session.get(DeviceCheck,payload.challenge_id)
        rule=session.get(DeviceRule,gid)
        if not rule or not rule.enabled or item.expires_at.replace(tzinfo=UTC)<=m.now(): raise HTTPException(409,'校验或规则已失效')
        key=m._token_hash('aliyun:device_risk_pro:'+provider_device)
        device=session.scalar(select(RiskDevice).where(RiskDevice.game_id==gid,RiskDevice.device_key==key))
        if device is None:
            device=RiskDevice(game_id=gid,device_key=key)
            session.add(device);session.flush()
        install=session.scalar(select(DeviceInstall).where(DeviceInstall.device_id==device.id,DeviceInstall.install_hash==item.install_hash))
        reason=''
        if install is None:
            if session.scalar(select(DeviceInstall.id).where(DeviceInstall.device_id==device.id).limit(1)):
                reason='同一阿里云设备出现新的安装实例（疑似清数据或重装）'
            session.add(DeviceInstall(device_id=device.id,install_hash=item.install_hash))
        matched=set(tags)&set(json.loads(rule.reset_tags))
        if matched: reason='命中配置的清机风险标签：'+','.join(sorted(matched))
        if reason:
            device.reason=reason[:255];device.risk_until=m.now()+timedelta(days=rule.risk_days)
        device.tags=json.dumps(tags);device.last_member_id=member.id;device.last_checked_at=m.now()
        item.device_id=device.id;item.token_hash=m._token_hash(payload.aliyun_device_token)
        item.provider_request_id=request_id;item.verified_at=m.now();item.status='verified'
        session.commit()
        used=usage(session,device,member.id)
        return {'data':{'risk_check_id':item.id,'device_id':device.id,'suspected_reset':risky(device),
            'limited':bool(rule.limit_enabled and risky(device)),'daily_limit':rule.daily_limit,'used':used,
            'remaining':max(0,rule.daily_limit-used) if rule.limit_enabled and risky(device) else None},'request_id':request_id}


def authorize_ad(session,payload,member,ad_id):
    rule=session.get(DeviceRule,payload.game_id)
    if rule is None or not rule.enabled:return
    check=session.get(DeviceCheck,payload.risk_check_id) if payload.risk_check_id else None
    if (check is None or check.member_id!=member.id or check.game_id!=payload.game_id or check.status!='verified'
        or check.expires_at.replace(tzinfo=UTC)<=m.now()):
        raise HTTPException(403,'请先完成阿里云设备校验')
    device=session.get(RiskDevice,check.device_id)
    if rule.limit_enabled and risky(device) and usage(session,device,member.id)>=rule.daily_limit:
        session.add(m.AdFlowLog(member_id=member.id,game_id=payload.game_id,event_type='device_limit_rejected',
            status='blocked',provider='aliyun',detail_json=json.dumps({'device_id':device.id,'daily_limit':rule.daily_limit})))
        session.commit()
        raise HTTPException(429,'今日风险设备广告次数已达上限')
    check.status='consumed'
    session.add(DeviceAdAdmission(device_id=device.id,member_id=member.id,game_id=payload.game_id,
        ad_session_id=ad_id,check_id=check.id,quota_date=(m.now()+timedelta(hours=8)).date()))


def authorize_retry(session, payload, existing):
    rule = session.get(DeviceRule, payload.game_id)
    if rule is None or not rule.enabled:
        return
    admission = session.scalar(select(DeviceAdAdmission).where(DeviceAdAdmission.ad_session_id == existing.id))
    if admission is None or admission.check_id != payload.risk_check_id:
        raise HTTPException(403, '重试须使用原广告申请的设备校验凭证')


@m.app_api.get('/device-risk/config')
def app_config(game_id: int = Query(ge=1), member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        m._app_game_for_member(session, member, game_id)
        rule = rule_data(session.get(DeviceRule, game_id))
        return {'data': {k: rule[k] for k in ('enabled', 'limit_enabled', 'daily_limit')},
                'request_id': secrets.token_urlsafe(12)}


@m.api.get('/games/{game_id}/device-risk')
def get_rule(game_id:int,admin:m.AdminUser=Depends(m.require_admin)):
    with m.SessionLocal() as session:
        m.get_or_404(session,m.Game,game_id,'游戏')
        return {**rule_data(session.get(DeviceRule,game_id)),'game_id':game_id,'aliyun_configured':configured(),
            'can_write':admin.role in ('superadmin','risk')}


@m.api.put('/games/{game_id}/device-risk')
def put_rule(game_id:int,payload:RuleInput,request:WebRequest,admin:m.AdminUser=Depends(m.allow_roles('risk'))):
    if payload.enabled and not configured():raise HTTPException(503,'请先配置阿里云增强版设备风控凭据')
    with m.SessionLocal() as session:
        game_lock(session,game_id)
        item=session.get(DeviceRule,game_id)
        before=rule_data(item)
        if item is None:item=DeviceRule(game_id=game_id);session.add(item)
        for k,v in payload.model_dump().items():
            setattr(item,k,json.dumps(v) if k=='reset_tags' else int(v) if isinstance(v,bool) else v)
        session.add(m.AdminOperation(admin_id=admin.id,title=f'设备风控规则 #{game_id}',path=request.url.path,ip=request.client.host if request.client else ''))
        session.add(m.AdFlowLog(member_id=0,game_id=game_id,event_type='device_rule_changed',status='ok',provider='aliyun',
            detail_json=json.dumps({'admin_id':admin.id,'before':before,'after':payload.model_dump()})))
        session.commit();return rule_data(item)


@m.api.get('/device-risk/devices')
def list_devices(game_id:int=Query(ge=1),limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0),admin:m.AdminUser=Depends(m.require_admin)):
    with m.SessionLocal() as session:
        rows=session.scalars(select(RiskDevice).where(RiskDevice.game_id==game_id).order_by(RiskDevice.last_checked_at.desc()).offset(offset).limit(limit)).all()
        result=[]
        for row in rows:
            value=m.serialize(row,list(row.__table__.columns.keys()));value['tags']=json.loads(row.tags)
            value['suspected_reset']=risky(row);value['used_today']=usage(session,row)
            value['member_ids']=list(session.scalars(select(DeviceCheck.member_id).where(DeviceCheck.device_id==row.id).distinct()))
            result.append(value)
        return {'items':result,'total':session.scalar(select(func.count()).select_from(RiskDevice).where(RiskDevice.game_id==game_id)) or 0}


@m.api.patch('/device-risk/devices/{device_id}')
def override_device(device_id:int,payload:OverrideInput,request:WebRequest,admin:m.AdminUser=Depends(m.allow_roles('risk'))):
    with m.SessionLocal() as session:
        row=m.get_or_404(session,RiskDevice,device_id,'设备');gid=row.game_id
    with m.SessionLocal() as session:
        game_lock(session,gid);row=session.get(RiskDevice,device_id);before=row.override;row.override=payload.mode
        session.add(m.AdminOperation(admin_id=admin.id,title=f'设备 #{device_id} {before}→{payload.mode}：{payload.reason}'[:128],path=request.url.path,ip=request.client.host if request.client else ''))
        session.add(m.AdFlowLog(member_id=row.last_member_id,game_id=gid,event_type='device_override',status='ok',provider='aliyun',
            detail_json=json.dumps({'device_id':device_id,'admin_id':admin.id,'before':before,'after':payload.mode,'reason':payload.reason})))
        session.commit();return {'id':device_id,'override':row.override}
