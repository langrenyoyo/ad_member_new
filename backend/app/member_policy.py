"""Configurable member onboarding, reward policy and auditable commissions."""
import json
import secrets
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Literal

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import BigInteger, Integer, String, Text, DateTime, Numeric, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from . import main_from_txt as m


class Enrollment(m.Base, m.TimestampMixin):
    __tablename__ = 'member_enrollments'
    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(32), unique=True)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=0)
    usage_granted: Mapped[int] = mapped_column(Integer, default=0)
    usage_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageReport(m.Base, m.TimestampMixin):
    __tablename__ = 'member_usage_reports'
    __table_args__ = (UniqueConstraint('member_id', 'report_date', 'package_name', name='uq_member_usage_day_package'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)
    report_date: Mapped[str] = mapped_column(String(10))
    package_name: Mapped[str] = mapped_column(String(255))
    duration_ms: Mapped[int] = mapped_column(BigInteger)
    opens: Mapped[int] = mapped_column(Integer)


class RewardLedger(m.Base, m.TimestampMixin):
    __tablename__ = 'member_reward_ledgers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ad_session_id: Mapped[str] = mapped_column(String(80), index=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)
    beneficiary_id: Mapped[int] = mapped_column(Integer, index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    rule_json: Mapped[str] = mapped_column(Text)
    coin_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    __table_args__ = (UniqueConstraint('ad_session_id', 'beneficiary_id', 'kind', name='uq_ad_beneficiary_kind'),)


class DeviceCooldown(m.Base):
    __tablename__ = 'device_login_cooldowns'
    device_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blocked_until: Mapped[object] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[object] = mapped_column(DateTime(timezone=True))


def check_cooldown(session, member, install_id=None):
    rule = policy(session, member.game_id)
    if not rule.reset_login_block or (member.is_white and rule.whitelist_risk_exempt): return
    d = m.device_risk
    ids = set(session.scalars(select(d.DeviceCheck.device_id).where(d.DeviceCheck.member_id == member.id,
        d.DeviceCheck.device_id.is_not(None))).all())
    if install_id:
        ids.update(session.scalars(select(d.DeviceInstall.device_id).where(d.DeviceInstall.install_hash == m._token_hash(install_id))).all())
    for device_id in ids:
        device = session.get(d.RiskDevice, device_id)
        cooldown = session.get(DeviceCooldown, device_id)
        if device and device.game_id == member.game_id and d.risky(device) and cooldown and cooldown.blocked_until.replace(tzinfo=m.UTC) > m.now():
            raise HTTPException(403, {'code': 'DEVICE_COOLDOWN', 'message': '风险设备暂时禁止登录', 'blocked_until': cooldown.blocked_until.isoformat()})


def check_access(session, member, request):
    path = request.url.path
    if request.method == 'DELETE' and path == '/api/app/v1/device-observations': return
    if path.endswith('/auth/logout'): return
    # Event acknowledgements and recovery remain possible for the last admitted ad.
    if ('/ads/' not in path or path.endswith('/request')) and not path.endswith(('/me', '/wallet', '/withdrawals')) and '/withdrawals/' not in path:
        check_cooldown(session, member)
    rule = policy(session, member.game_id)
    if not (member.is_white and rule.whitelist_risk_exempt):
        signals = set(request.headers.get('X-Device-Risk', '').split(','))
        if signals & set(rule.block_signals):
            raise HTTPException(403, {'code': 'DEVICE_POLICY_BLOCKED', 'message': '设备状态不符合当前使用规则'})
    require_onboarding(session, member, path)


def rolling_usage(session, device):
    cooldown = session.get(DeviceCooldown, device.id)
    if cooldown and cooldown.blocked_until.replace(tzinfo=m.UTC) <= m.now():
        start = max(cooldown.window_start.replace(tzinfo=m.UTC), cooldown.blocked_until.replace(tzinfo=m.UTC))
    else:
        start = cooldown.window_start.replace(tzinfo=m.UTC) if cooldown else m.now()-timedelta(hours=24)
    return session.scalar(select(m.func.count()).select_from(m.device_risk.DeviceAdAdmission).where(
        m.device_risk.DeviceAdAdmission.device_id == device.id, m.device_risk.DeviceAdAdmission.created_at >= start)) or 0


def admit_rolling(session, device, member, limit):
    rule = policy(session, member.game_id)
    if not rule.reset_login_block: return False
    if member.is_white and rule.whitelist_risk_exempt: return True
    cooldown = session.get(DeviceCooldown, device.id)
    if cooldown and cooldown.blocked_until.replace(tzinfo=m.UTC) > m.now():
        raise HTTPException(403, '风险设备处于 24 小时限制期')
    if cooldown and cooldown.window_start.replace(tzinfo=m.UTC) < cooldown.blocked_until.replace(tzinfo=m.UTC):
        cooldown.window_start = m.now()
    used = rolling_usage(session, device)
    if used >= limit or used + 1 >= limit:
        if cooldown is None:
            cooldown = DeviceCooldown(device_id=device.id, window_start=m.now()-timedelta(hours=24), blocked_until=m.now())
            session.add(cooldown)
        cooldown.blocked_until = m.now()+timedelta(hours=24)
        if used >= limit:
            session.commit()
            raise HTTPException(429, '风险设备额度已耗尽，24 小时后恢复')
    return True


class EcpmTier(BaseModel):
    upper: Decimal = Field(ge=0, le=1000000)
    percent: Decimal = Field(ge=0, le=1000)


class Policy(BaseModel):
    require_alipay: bool = False
    require_invite: bool = False
    invite_min_level: int = Field(default=1, ge=0, le=3)
    require_usage: bool = False
    block_signals: list[Literal['emulator', 'root', 'hook', 'developer', 'accessibility', 'bluetooth']] = Field(default_factory=list)
    reset_login_block: bool = False
    reward_enabled: bool = False
    tier_enabled: bool = False
    ecpm_tiers: list[EcpmTier] = Field(default_factory=list, max_length=100)
    label_rewards_enabled: bool = False
    label_window: int = Field(default=100, ge=1, le=1000)
    label_min_samples: int = Field(default=10, ge=1, le=1000)
    label_threshold: Decimal = Field(default=Decimal('0.5'), ge=Decimal('0.5'), lt=1)
    label_rewards: dict[Literal['game', 'social', 'finance', 'ecommerce', 'other'], Decimal] = Field(default_factory=dict)
    commission_enabled: bool | None = None
    reward_basis: Literal['verified_cny_ecpm', 'fixed_ecpm'] = 'verified_cny_ecpm'
    fixed_ecpm: Decimal = Field(default=Decimal('0'), ge=0, le=100000)
    coins_per_yuan: Decimal = Field(default=Decimal('1'), gt=0, le=1000000)
    network_rates: dict[str, Decimal] = Field(default_factory=lambda: {k: Decimal('1') for k in ['kuaishou', 'gdt', 'csj', 'baidu', 'other']})
    # Explicit adsource mapping, not the unsigned client label/network name.
    source_networks: dict[str, Literal['kuaishou', 'gdt', 'csj', 'baidu', 'other']] = Field(default_factory=dict)
    whitelist_multiplier: Decimal = Field(default=Decimal('1'), ge=0, le=100)
    whitelist_risk_exempt: bool = False
    max_reward: Decimal = Field(default=Decimal('100'), ge=0, le=1000000)
    commission_rates: list[Decimal] = Field(default_factory=lambda: [Decimal('0')] * 4, min_length=4, max_length=4)
    agent_member_id: int = Field(default=0, ge=0)
    announcement: str = Field(default='', max_length=5000)
    announcement_version: int = Field(default=1, ge=1)

    @model_validator(mode='after')
    def validate_rates(self):
        if self.label_min_samples > self.label_window:
            raise ValueError('标签最少样本数不能超过统计窗口')
        if any(v < 0 or v > 1000000 or v.as_tuple().exponent < -6 for v in self.label_rewards.values()):
            raise ValueError('标签奖励须为 0–100 万金币，最多六位小数')
        if self.label_rewards_enabled and not self.reward_enabled:
            raise ValueError('标签固定奖励需要启用自定义奖励策略')
        if self.tier_enabled and not self.ecpm_tiers:
            raise ValueError('开启分段释放必须填写阈值和比例')
        if any(a.upper >= b.upper for a, b in zip(self.ecpm_tiers, self.ecpm_tiers[1:])):
            raise ValueError('ECPM 阈值必须严格递增')
        if self.tier_enabled and self.reward_basis != 'verified_cny_ecpm':
            raise ValueError('分段释放以本次可信人民币 ECPM 为依据，请选择可信 ECPM')
        if set(self.network_rates) != {'kuaishou', 'gdt', 'csj', 'baidu', 'other'}:
            raise ValueError('必须配置五类广告来源比例')
        if any(x < 0 or x > 1 for x in [*self.network_rates.values(), *self.commission_rates]):
            raise ValueError('比例须在 0 到 1 之间')
        if sum(self.commission_rates) > 1:
            raise ValueError('四级分佣比例合计不得超过 1')
        if len(self.source_networks) > 500 or any(not k.isdigit() for k in self.source_networks):
            raise ValueError('广告来源必须使用数字 adsource_id')
        return self


def policy(session, game_id):
    game = session.get(m.Game, game_id)
    if not game: raise HTTPException(404, '游戏不存在')
    return Policy.model_validate(json.loads(game.settings_json or '{}').get('member_policy', {}))


def enrollment(session, member):
    row = session.get(Enrollment, member.id)
    if row is None:
        row = Enrollment(member_id=member.id, invite_code=secrets.token_hex(6).upper(), parent_id=member.parent_id or 0)
        session.add(row)
        session.flush()
    return row


def require_onboarding(session, member, path):
    rule = policy(session, member.game_id)
    # Recovery/read endpoints remain reachable while business actions are gated.
    if path.endswith(('/onboarding', '/usage', '/me', '/bootstrap', '/me/alipay', '/auth/wechat-password', '/auth/sms/password', '/auth/change-password', '/auth/logout')) or '/device-risk/' in path:
        return
    row = session.get(Enrollment, member.id)
    if rule.require_invite and (row is None or not row.parent_id):
        raise HTTPException(403, {'code': 'INVITE_REQUIRED', 'message': '请先绑定邀请码'})
    if rule.require_alipay and session.get(m.payouts.AlipayAccount, member.id) is None:
        raise HTTPException(403, {'code': 'ALIPAY_REQUIRED', 'message': '请先绑定支付宝'})
    if rule.require_usage and (row is None or not row.usage_granted or row.usage_seen_at is None or row.usage_seen_at.replace(tzinfo=m.UTC) < m.now()-timedelta(minutes=15)):
        raise HTTPException(403, {'code': 'USAGE_REQUIRED', 'message': '请授权并同步应用使用情况'})


@m.app_api.get('/policy')
def public_policy(game_id: int = Query(ge=1)):
    with m.SessionLocal() as session:
        rule = policy(session, game_id)
        return {'data': rule.model_dump(mode='json', include={'require_alipay', 'require_invite', 'require_usage', 'announcement', 'announcement_version', 'invite_min_level'})}


@m.api.get('/games/{game_id}/member-policy')
def get_policy(game_id: int, admin=Depends(m.require_admin)):
    with m.SessionLocal() as session:
        return policy(session, game_id).model_dump(mode='json')


@m.api.get('/games/{game_id}/reward-readiness')
def reward_readiness(game_id: int, admin=Depends(m.require_admin)):
    with m.SessionLocal() as session:
        rule = policy(session, game_id)
        try:
            check_reward_configuration(game_id, rule)
            return {'ready': True, 'message': '本地密钥配置检查通过；平台人民币证明仍需实际回调验证'}
        except HTTPException as exc:
            return {'ready': False, 'message': exc.detail}


@m.api.put('/games/{game_id}/member-policy')
def set_policy(game_id: int, body: Policy, admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as session:
        game = session.scalar(select(m.Game).where(m.Game.id == game_id).with_for_update())
        if not game: raise HTTPException(404, '游戏不存在')
        # Management must remain available during a keyring outage. Admission
        # retains its independent fail-closed validation.
        original = policy(session, game_id)
        independent = {'announcement', 'announcement_version', 'require_alipay', 'require_invite',
            'invite_min_level', 'require_usage', 'block_signals', 'reset_login_block', 'whitelist_risk_exempt'}
        settlement_changed = original.model_dump(exclude=independent) != body.model_dump(exclude=independent)
        if settlement_changed and body.reward_enabled and (body.reward_basis == 'verified_cny_ecpm' or body.source_networks):
            check_reward_configuration(game_id, body)
        if body.reset_login_block:
            risk = session.get(m.device_risk.DeviceRule, game_id)
            if not risk or not risk.enabled or not risk.limit_enabled:
                raise HTTPException(422, '请先开启阿里云设备识别及限次')
        if body.agent_member_id:
            agent = session.get(Enrollment, body.agent_member_id)
            member = session.get(m.Member, body.agent_member_id)
            if not agent or agent.level != 3 or not member or member.status != 1 or member.game_id != game_id:
                raise HTTPException(422, '全 APP 代理必须是本游戏的代理级会员')
        settings = json.loads(game.settings_json or '{}')
        settings['member_policy'] = body.model_dump(mode='json')
        game.settings_json = json.dumps(settings, ensure_ascii=False)
        session.add(m.AdminOperation(admin_id=admin.id,
            title='修改 APP 会员策略', path=f'/api/v1/games/{game_id}/member-policy', ip=''))
        session.commit()
        return body.model_dump(mode='json')


class InviteInput(BaseModel):
    invite_code: str = Field(min_length=1, max_length=32)


def check_reward_configuration(game_id, rule):
    from .taku_ecpm import require_configuration, EcpmConfigurationError
    required = rule.reward_enabled and (rule.reward_basis == 'verified_cny_ecpm' or bool(rule.source_networks))
    try:
        require_configuration(game_id, required=required)
    except EcpmConfigurationError:
        raise HTTPException(503, '广告结算证明配置不可用，请检查服务端 ECPM 密钥文件及本应用配置') from None


@m.app_api.get('/onboarding')
def onboarding(member=Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        m.device_risk.game_lock(session, member.game_id)
        row = enrollment(session, member)
        rule = policy(session, member.game_id)
        result = {'policy': rule.model_dump(mode='json', include={'require_alipay', 'require_invite', 'require_usage', 'announcement', 'announcement_version'}),
            'level': row.level, 'invite_code': row.invite_code if row.level >= rule.invite_min_level else None,
            'parent_id': row.parent_id, 'alipay_bound': session.get(m.payouts.AlipayAccount, member.id) is not None,
            'usage_granted': bool(row.usage_granted)}
        session.commit()
        return {'data': result}


@m.app_api.post('/onboarding')
def bind_invite(body: InviteInput, member=Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        m.device_risk.game_lock(session, member.game_id)
        stored = session.get(m.Member, member.id)
        row = enrollment(session, stored)
        parent = session.scalar(select(Enrollment).where(Enrollment.invite_code == body.invite_code.strip().upper()))
        parent_member = session.get(m.Member, parent.member_id) if parent else None
        if not parent or not parent_member or parent_member.status != 1 or parent_member.game_id != member.game_id or parent.level < policy(session, member.game_id).invite_min_level:
            raise HTTPException(422, '邀请码无效或邀请人不具备资格')
        if row.parent_id:
            if row.parent_id == parent.member_id: return {'data': {'parent_id': row.parent_id}}
            raise HTTPException(409, '邀请关系已绑定，不能修改')
        seen = {member.id}
        cursor = parent
        while cursor:
            if cursor.member_id in seen: raise HTTPException(422, '不允许自邀或循环邀请')
            seen.add(cursor.member_id)
            cursor = session.get(Enrollment, cursor.parent_id) if cursor.parent_id else None
        row.parent_id = parent.member_id
        stored.parent_id = parent.member_id
        session.commit()
        return {'data': {'parent_id': row.parent_id}}


class LevelInput(BaseModel):
    level: int = Field(ge=0, le=3)


class BalanceAdjustment(BaseModel):
    # Operational ceiling retained after migration; SQLite is for local testing only.
    coin: Decimal = Field(ge=0, le=1000000000, max_digits=16, decimal_places=6)
    freeze_coin: Decimal = Field(ge=0, max_digits=24, decimal_places=6)
    expected_coin: Decimal
    expected_freeze_coin: Decimal
    reason: str = Field(min_length=1, max_length=200)


@m.api.post('/members/{member_id}/adjust-balance')
def adjust_balance(member_id: int, body: BalanceAdjustment, admin=Depends(m.allow_roles('operator'))):
    with m.SessionLocal() as session:
        m.payouts.lock(session)
        member = session.scalar(select(m.Member).where(m.Member.id == member_id).with_for_update())
        if not member: raise HTTPException(404, '会员不存在')
        before = m.payouts.decimal_coin(member.coin or 0)
        frozen = m.payouts.decimal_coin(member.freeze_coin or 0)
        if before != body.expected_coin or frozen != body.expected_freeze_coin:
            raise HTTPException(409, '余额已变化，请重新打开窗口后核对')
        if frozen != body.freeze_coin:
            raise HTTPException(409, '冻结资金只能通过提现业务流转变更')
        if not body.reason.strip(): raise HTTPException(422, '请填写调账原因')
        if before != body.coin:
            member.coin = body.coin
            session.add(m.CoinLog(user_id=member.id, agent_id=member.agent_id, game_id=member.game_id,
                coin_before=before, coin=body.coin-before, coin_after=member.coin, type=9, remark=body.reason.strip()))
            session.add(m.AdminOperation(admin_id=admin.id, title=f'会员 {member_id} 调账 {before} -> {body.coin}：{body.reason.strip()}',
                path=f'/api/v1/members/{member_id}/adjust-balance', ip=''))
        session.commit()
        return m.serialize_member(member)


class RebindInput(BaseModel):
    parent_id: int = Field(ge=0)
    expected_parent_id: int = Field(ge=0)
    ht_id: int = Field(ge=0)
    ht_top_id: int = Field(ge=0)


@m.api.post('/members/{member_id}/rebind')
def rebind_member(member_id: int, body: RebindInput, admin=Depends(m.allow_roles('operator'))):
    with m.SessionLocal() as session:
        member = m.get_or_404(session, m.Member, member_id, '会员')
        m.device_risk.game_lock(session, member.game_id)
        session.refresh(member)
        row = enrollment(session, member)
        if member.parent_id != body.expected_parent_id:
            raise HTTPException(409, '邀请关系已变化，请重新加载')
        if body.parent_id:
            parent = session.get(m.Member, body.parent_id)
            if not parent or parent.game_id != member.game_id or parent.status != 1:
                raise HTTPException(422, '上级必须是同应用的正常会员')
            if enrollment(session, parent).level < policy(session, member.game_id).invite_min_level:
                raise HTTPException(422, '上级不具备邀请资格')
            seen = {member.id}
            cursor = parent
            while cursor:
                if cursor.id in seen: raise HTTPException(422, '不能自邀或循环邀请')
                seen.add(cursor.id)
                link = session.get(Enrollment, cursor.id)
                parent_id = link.parent_id if link else cursor.parent_id
                cursor = session.get(m.Member, parent_id) if parent_id else None
        old_parent = row.parent_id
        row.parent_id = member.parent_id = body.parent_id
        member.ht_id, member.ht_top_id = body.ht_id, body.ht_top_id
        session.add(m.AdminOperation(admin_id=admin.id, title=f'会员 {member_id} 上级 {old_parent} -> {body.parent_id}',
            path=f'/api/v1/members/{member_id}/rebind', ip=''))
        session.commit()
        return m.serialize_member(member)


@m.api.put('/members/{member_id}/level')
def set_level(member_id: int, body: LevelInput, admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as session:
        member = m.get_or_404(session, m.Member, member_id, 'Member')
        m.device_risk.game_lock(session, member.game_id)
        row = enrollment(session, member)
        row.level = body.level
        session.add(m.AdminOperation(admin_id=admin.id,
            title=f'修改会员 {member_id} 等级为 {body.level}', path=f'/api/v1/members/{member_id}/level', ip=''))
        session.commit()
        return {'level': row.level, 'invite_code': row.invite_code}


class UsageItem(BaseModel):
    package_name: str = Field(min_length=1, max_length=255, pattern=r'^[A-Za-z0-9_.]+$')
    duration_ms: int = Field(ge=0, le=86400000)
    opens: int = Field(ge=0, le=100000)


class UsageInput(BaseModel):
    granted: bool
    report_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    items: list[UsageItem] = Field(default_factory=list, max_length=1000)


@m.app_api.post('/usage')
def save_usage(body: UsageInput, member=Depends(m.require_app_member)):
    today = (m.now()+timedelta(hours=8)).date()
    if body.report_date not in {today.isoformat(), (today-timedelta(days=1)).isoformat()}:
        raise HTTPException(422, '只接受今天或昨天的使用统计')
    with m.SessionLocal() as session:
        m.device_risk.game_lock(session, member.game_id)
        row = enrollment(session, member)
        row.usage_granted = int(body.granted)
        row.usage_seen_at = m.now()
        for item in body.items if body.granted else []:
            existing = session.scalar(select(UsageReport).where(UsageReport.member_id == member.id,
                UsageReport.report_date == body.report_date, UsageReport.package_name == item.package_name))
            if existing is None:
                existing = UsageReport(member_id=member.id, report_date=body.report_date, **item.model_dump())
                session.add(existing)
            else:
                existing.duration_ms = item.duration_ms
                existing.opens = item.opens
        session.commit()
        return {'data': {'granted': body.granted}}


@m.api.get('/members/{member_id}/usage')
def get_usage(member_id: int, report_date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$'), admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as session:
        rows = session.scalars(select(UsageReport).where(UsageReport.member_id == member_id, UsageReport.report_date == report_date)).all()
        return {'items': [{'package_name': r.package_name, 'duration_ms': r.duration_ms, 'opens': r.opens} for r in rows]}


def calculate_reward(rule, member, source_id, proof):
    network = rule.source_networks.get(source_id, 'other')
    if rule.source_networks and not proof:
        raise HTTPException(503, '分平台奖励需要经过验证的广告来源证明')
    if rule.reward_basis == 'fixed_ecpm':
        ecpm = rule.fixed_ecpm
    else:
        prices = (proof or {}).get('prices', [])
        price = next((p for p in prices if p.get('currency') == 'CNY'), None)
        if not price: raise HTTPException(503, '奖励策略需要经过验证的人民币 ECPM')
        ecpm = Decimal(price['ecpm'])
    base = ecpm / 1000 * rule.coins_per_yuan
    multiplier = rule.whitelist_multiplier if member.is_white else Decimal(1)
    rate = rule.network_rates[network]
    tier = None
    if rule.tier_enabled:
        tier = next((item for item in rule.ecpm_tiers if ecpm <= item.upper), rule.ecpm_tiers[-1])
        rate = tier.percent / 100
    reward = min(rule.max_reward, base * rate * multiplier).quantize(Decimal('.000001'), rounding=ROUND_DOWN)
    label = getattr(member, 'ad_label', 'unknown')
    fixed = rule.label_rewards.get(label) if rule.label_rewards_enabled else None
    if fixed is not None:
        # An explicit fixed coin amount replaces ECPM and whitelist multiplication.
        reward = min(rule.max_reward, fixed).quantize(Decimal('.000001'), rounding=ROUND_DOWN)
    return reward, {'network': network, 'ecpm': str(ecpm), 'base': str(base), 'release_rate': str(rate),
        'reward_mode': 'label_fixed' if fixed is not None else 'ecpm', 'ad_label': label,
        'tier': tier.model_dump(mode='json') if tier else None, 'rule': rule.model_dump(mode='json')}


class RewardPreview(BaseModel):
    policy: Policy
    ecpm: Decimal = Field(ge=0, le=1000000)
    source_id: str = Field(default='', max_length=64)
    is_white: bool = False
    ad_label: Literal['unknown', 'game', 'social', 'finance', 'ecommerce', 'other'] = 'unknown'


@m.api.post('/member-policy/reward-preview')
def reward_preview(body: RewardPreview, admin=Depends(m.allow_roles('superadmin'))):
    from types import SimpleNamespace
    if not body.policy.reward_enabled:
        raise HTTPException(422, '请先启用自定义奖励策略；关闭时使用旧结算')
    amount, detail = calculate_reward(body.policy, SimpleNamespace(is_white=body.is_white, ad_label=body.ad_label), body.source_id,
        {'prices': [{'currency': 'CNY', 'ecpm': str(body.ecpm)}]})
    return {'coin': str(amount), 'detail': detail, 'simulation': True}


def commission_recipients(session, member, rule):
    row = session.get(Enrollment, member.id)
    parent_id = row.parent_id if row else member.parent_id
    selected, seen = {}, {member.id}
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        parent = session.get(Enrollment, parent_id)
        if parent is None: break
        recipient = session.get(m.Member, parent_id)
        if recipient and recipient.status == 1 and recipient.game_id == member.game_id:
            selected.setdefault(parent.level, parent.member_id)
        parent_id = parent.parent_id
    if rule.agent_member_id: selected[3] = rule.agent_member_id
    return selected


def settlement_snapshot(session, member, game_id):
    rule = policy(session, game_id)
    return {'version': 2, 'rule': rule.model_dump(mode='json'),
        'label_summary': m.member_insights.label_summary(session, member.id, rule) if rule.label_rewards_enabled else {'label':'unknown','reason':'标签奖励未启用'},
        'is_white': bool(member.is_white),
        'recipients': commission_recipients(session, member, rule)}


def settle(session, member, ad, source_id, proof, legacy_reward):
    event = session.scalar(select(m.AppAdEvent).where(m.AppAdEvent.event_id == 'policy:'+ad.id))
    captured = json.loads(event.result_json) if event else {}
    modern = captured.get('version') == 2
    rule = Policy.model_validate(captured['rule'] if modern else captured) if event else policy(session, ad.game_id)
    commission_on = rule.commission_enabled if rule.commission_enabled is not None else rule.reward_enabled
    if not rule.reward_enabled and not commission_on: return legacy_reward
    if rule.reward_enabled:
        from types import SimpleNamespace
        basis = SimpleNamespace(is_white=captured['is_white'],
            ad_label=captured.get('label_summary', {}).get('label', 'unknown')) if modern else member
        reward, snapshot = calculate_reward(rule, basis, source_id, proof)
        snapshot['label_summary'] = captured.get('label_summary', {'label': 'unknown'})
    else:
        reward = Decimal(str(legacy_reward)).quantize(Decimal('.000001'), rounding=ROUND_DOWN)
        snapshot = {'basis': 'legacy_reward', 'rule': rule.model_dump(mode='json')}
    selected = {int(k): v for k, v in captured['recipients'].items()} if modern else commission_recipients(session, member, rule)
    snapshot['recipients'] = selected
    snapshot['attribution'] = 'ad_request' if modern else 'legacy_callback'
    snapshot['commission_audit_version'] = 1
    commission_outcomes = []
    reward_ledger = RewardLedger(ad_session_id=ad.id, member_id=member.id, beneficiary_id=member.id,
        game_id=ad.game_id, kind='reward', amount=reward, rule_json=json.dumps(snapshot))
    session.add(reward_ledger)
    if not commission_on:
        snapshot['commission_outcomes'] = [
            {'level': level, 'beneficiary_id': beneficiary, 'eligible': False,
             'amount': '0', 'reason': '分佣未启用'} for level, beneficiary in sorted(selected.items())]
        reward_ledger.rule_json = json.dumps(snapshot, ensure_ascii=False)
        return reward
    for level, beneficiary in sorted(selected.items()):
        outcome = {'level': level, 'beneficiary_id': beneficiary, 'eligible': False, 'amount': '0', 'reason': ''}
        if beneficiary == member.id:
            outcome['reason'] = '不能向自己分佣'
            commission_outcomes.append(outcome)
            continue
        enrollment_row = session.get(Enrollment, beneficiary)
        if not enrollment_row or enrollment_row.level < level:
            outcome['reason'] = '等级不满足'
            commission_outcomes.append(outcome)
            continue
        recipient = session.scalar(select(m.Member).where(m.Member.id == beneficiary).with_for_update())
        if recipient is None:
            outcome['reason'] = '会员不存在'
            commission_outcomes.append(outcome)
            continue
        if recipient.status != 1:
            outcome['reason'] = '会员已停用'
            commission_outcomes.append(outcome)
            continue
        if recipient.game_id != ad.game_id:
            outcome['reason'] = '游戏不一致'
            commission_outcomes.append(outcome)
            continue
        amount = (reward * rule.commission_rates[level]).quantize(Decimal('.000001'), rounding=ROUND_DOWN)
        outcome.update(eligible=True, amount=str(amount))
        commission_outcomes.append(outcome)
        if not amount:
            outcome['reason'] = '计算金额为零'
            continue
        before = Decimal(str(recipient.coin or 0))
        recipient.coin = m.coin_amount(before + amount)
        log = m.CoinLog(user_id=recipient.id, agent_id=recipient.agent_id, game_id=ad.game_id,
            coin_before=before, coin=amount, coin_after=recipient.coin, type=301, remark=f'广告分佣 {ad.id}')
        session.add(log); session.flush()
        session.add(RewardLedger(ad_session_id=ad.id, member_id=member.id, beneficiary_id=recipient.id,
            game_id=ad.game_id, kind=f'commission_{level}', amount=amount, coin_log_id=log.id, rule_json=json.dumps(snapshot)))
    snapshot['commission_outcomes'] = commission_outcomes
    reward_ledger.rule_json = json.dumps(snapshot, ensure_ascii=False)
    return reward


@m.app_api.get('/commissions')
def commissions(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), member=Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        rows = session.scalars(select(RewardLedger).where(RewardLedger.beneficiary_id == member.id,
            RewardLedger.kind != 'reward').order_by(RewardLedger.id.desc()).offset(offset).limit(limit)).all()
        total = session.scalar(select(m.func.count()).select_from(RewardLedger).where(RewardLedger.beneficiary_id == member.id, RewardLedger.kind != 'reward')) or 0
        condition = (RewardLedger.beneficiary_id == member.id, RewardLedger.kind != 'reward')
        today = (m.now()+timedelta(hours=8)).replace(hour=0, minute=0, second=0, microsecond=0)-timedelta(hours=8)
        earned = session.scalar(select(m.func.sum(RewardLedger.amount)).where(*condition)) or Decimal(0)
        daily = session.scalar(select(m.func.sum(RewardLedger.amount)).where(*condition, RewardLedger.created_at >= today)) or Decimal(0)
        direct = session.scalar(select(m.func.count()).select_from(Enrollment).join(m.Member, m.Member.id == Enrollment.member_id).where(Enrollment.parent_id == member.id, m.Member.game_id == member.game_id)) or 0
        row = session.get(Enrollment, member.id)
        return {'data': {'summary': {'total_earned': str(earned), 'today_earned': str(daily), 'direct_members': direct, 'level': row.level if row else 0}, 'total': total, 'items': [{'id': r.id, 'amount': str(r.amount), 'kind': r.kind,
            'source_member_id': r.member_id, 'ad_session_id': r.ad_session_id, 'created_at': m.stringify(r.created_at)} for r in rows]}}


@m.app_api.get('/commission-team')
def commission_team(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), member=Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        condition = (Enrollment.parent_id == member.id, m.Member.game_id == member.game_id)
        base = select(Enrollment).join(m.Member, m.Member.id == Enrollment.member_id).where(*condition)
        rows = session.scalars(base.order_by(Enrollment.member_id.desc()).offset(offset).limit(limit)).all()
        total = session.scalar(select(m.func.count()).select_from(Enrollment).join(m.Member, m.Member.id == Enrollment.member_id).where(*condition)) or 0
        # Only show the caller's direct referrals; never expose phone or payout details.
        return {'data': {'total': total, 'items': [{'id': r.member_id, 'level': r.level} for r in rows]}}


@m.api.get('/games/{game_id}/reward-ledgers')
def reward_ledgers(game_id: int, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as session:
        rows = session.scalars(select(RewardLedger).where(RewardLedger.game_id == game_id).order_by(RewardLedger.id.desc()).offset(offset).limit(limit)).all()
        total = session.scalar(select(m.func.count()).select_from(RewardLedger).where(RewardLedger.game_id == game_id)) or 0
        return {'total': total, 'items': [{'id': r.id, 'ad_session_id': r.ad_session_id, 'member_id': r.member_id,
            'beneficiary_id': r.beneficiary_id, 'kind': r.kind, 'amount': str(r.amount), 'rule': json.loads(r.rule_json)} for r in rows]}
