"""Configured subsidy campaigns, eligibility and durable daily reservations."""
import json
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, func, select, text
from sqlalchemy.orm import Mapped, mapped_column

from . import main_from_txt as m


class SubsidyCampaign(m.Base, m.TimestampMixin):
    __tablename__ = 'subsidy_campaigns'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[int] = mapped_column(Integer, default=0)
    daily_quota: Mapped[int] = mapped_column(Integer, default=50)
    withdrawal_cents: Mapped[int] = mapped_column(Integer, default=500)
    recharge_cents: Mapped[int] = mapped_column(Integer, default=600)
    reward_cents: Mapped[int] = mapped_column(Integer, default=1200)
    review_hours: Mapped[int] = mapped_column(Integer, default=24)
    instructions: Mapped[str] = mapped_column(Text, default='')


class SubsidyReservation(m.Base):
    __tablename__ = 'subsidy_reservations'
    __table_args__ = (UniqueConstraint('campaign_id', 'member_id', 'quota_date', name='uq_subsidy_daily_member'),
                      UniqueConstraint('member_id', 'request_key', name='uq_subsidy_request_key'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)
    subsidy_id: Mapped[int] = mapped_column(Integer, unique=True)
    quota_date: Mapped[date] = mapped_column(Date, index=True)
    request_key: Mapped[str] = mapped_column(String(128))
    request_json: Mapped[str] = mapped_column(Text)
    snapshot_json: Mapped[str] = mapped_column(Text)
    review_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CampaignInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    game_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=128)
    enabled: Literal[0, 1] = 0
    daily_quota: int = Field(default=50, ge=1, le=100000)
    withdrawal_cents: int = Field(default=500, ge=1, le=100000000)
    recharge_cents: int = Field(default=600, ge=1, le=100000000)
    reward_cents: int = Field(default=1200, ge=1, le=100000000)
    review_hours: int = Field(default=24, ge=1, le=720)
    instructions: str = Field(default='', max_length=4000)


class CampaignApplication(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_key: str = Field(min_length=8, max_length=128)
    download_image: str = Field(min_length=1, max_length=255)
    install_image: str = Field(min_length=1, max_length=255)
    recharge_image: str = Field(min_length=1, max_length=255)
    receive_name: str = Field(min_length=1, max_length=64)
    receive_tel: str = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def distinct_images(self):
        if len({self.download_image, self.install_image, self.recharge_image}) != 3:
            raise ValueError('请分别上传下载、安装来源、充值截图')
        return self


def day_bounds(at=None):
    day = ((at or m.now()) + timedelta(hours=8)).date()
    start = datetime.combine(day, datetime.min.time(), UTC) - timedelta(hours=8)
    return day, start, start + timedelta(days=1)


def write_lock(session):
    if session.get_bind().dialect.name == 'sqlite':
        session.execute(text('BEGIN IMMEDIATE'))


def campaign_payload(session, campaign, at=None):
    day, _, _ = day_bounds(at)
    used = session.scalar(select(func.count()).select_from(SubsidyReservation).where(
        SubsidyReservation.campaign_id == campaign.id, SubsidyReservation.quota_date == day)) or 0
    result = m.serialize(campaign, list(campaign.__table__.columns.keys()))
    result.update(quota_date=day.isoformat(), used=used, remaining=max(0, campaign.daily_quota - used))
    return result


def eligibility(session, campaign, member, at=None):
    at = at or m.now()
    day, start, end = day_bounds(at)
    # Only confirmed transfers count, using their transfer time, not creation
    # time or a client supplied amount. Historical unconfirmed rows never count.
    amounts = session.scalars(select(m.Withdrawal.exchange_value).where(
        m.Withdrawal.user_id == member.id, m.Withdrawal.game_id == campaign.game_id,
        m.Withdrawal.agent_id == member.agent_id, m.Withdrawal.status == 1,
        m.Withdrawal.plan_status == 1, m.Withdrawal.transferred_at >= start,
        m.Withdrawal.transferred_at < end)).all()
    confirmed = sum((Decimal(str(x)) for x in amounts), Decimal(0))
    confirmed_cents = int(confirmed * 100)
    used = session.scalar(select(SubsidyReservation.id).where(
        SubsidyReservation.member_id == member.id, SubsidyReservation.campaign_id == campaign.id,
        SubsidyReservation.quota_date == day)) is not None
    pending = session.scalar(select(m.Subsidy.id).where(m.Subsidy.user_id == member.id,
        m.Subsidy.game_id == campaign.game_id, m.Subsidy.status == 0)) is not None
    info = campaign_payload(session, campaign, at)
    reasons = []
    if not campaign.enabled: reasons.append('活动未开放')
    if info['remaining'] <= 0: reasons.append('今日名额已满')
    if used: reasons.append('今日已申请该活动')
    if pending: reasons.append('该游戏已有待审核申请')
    if confirmed_cents < campaign.withdrawal_cents: reasons.append('今日已确认提现金额不足')
    info.update(confirmed_withdrawal_cents=confirmed_cents, eligible=not reasons, reasons=reasons,
                required_images=['download_image', 'install_image', 'recharge_image'])
    return info


def scoped_campaign(session, campaign_id, member, lock=False):
    stmt = select(SubsidyCampaign).where(SubsidyCampaign.id == campaign_id)
    campaign = session.scalar(stmt.with_for_update() if lock else stmt)
    if campaign is None: raise HTTPException(404, '补贴活动不存在')
    game = session.get(m.Game, campaign.game_id)
    agent = session.get(m.Agent, member.agent_id)
    if game is None or game.agent_id != member.agent_id: raise HTTPException(404, '补贴活动不存在')
    if game.status != 1 or agent is None or agent.status != 1: raise HTTPException(403, '主体或游戏已停用')
    return campaign


def application_snapshot(session, subsidy):
    reservation = session.scalar(select(SubsidyReservation).where(SubsidyReservation.subsidy_id == subsidy.id))
    if reservation is None: return None
    result = json.loads(reservation.snapshot_json)
    due = reservation.review_due_at.replace(tzinfo=UTC)
    result.update(review_due_at=due.isoformat(), overdue=subsidy.status == 0 and m.now() > due)
    return result


@m.app_api.get('/subsidy-campaigns')
def app_campaigns(game_id: int | None = Query(None, ge=1), member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        agent = session.get(m.Agent, member.agent_id)
        if agent is None or agent.status != 1: raise HTTPException(403, '主体已停用')
        stmt = select(SubsidyCampaign).join(m.Game, m.Game.id == SubsidyCampaign.game_id).where(
            m.Game.agent_id == member.agent_id, m.Game.status == 1, SubsidyCampaign.enabled == 1)
        if game_id is not None: stmt = stmt.where(SubsidyCampaign.game_id == game_id)
        rows = session.scalars(stmt.order_by(SubsidyCampaign.id.desc())).all()
        return {'data': {'items': [eligibility(session, x, member) for x in rows], 'total': len(rows)},
                'request_id': secrets.token_urlsafe(12)}


@m.app_api.get('/subsidy-campaigns/{campaign_id}')
def app_campaign_detail(campaign_id: int, member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        return {'data': eligibility(session, scoped_campaign(session, campaign_id, member), member),
                'request_id': secrets.token_urlsafe(12)}


@m.app_api.post('/subsidy-campaigns/{campaign_id}/applications', status_code=201)
def apply_campaign(campaign_id: int, payload: CampaignApplication, member: m.Member = Depends(m.require_app_member)):
    request_json = json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False)
    with m.SessionLocal() as session:
        write_lock(session)
        # Serialize requests across campaigns for the same member, and then
        # across members for the campaign's daily quota.
        member = session.scalar(select(m.Member).where(m.Member.id == member.id).with_for_update())
        if member is None or member.status != 1: raise m._app_auth_error()
        prior = session.scalar(select(SubsidyReservation).where(
            SubsidyReservation.member_id == member.id, SubsidyReservation.request_key == payload.request_key))
        if prior is not None:
            if prior.campaign_id != campaign_id or prior.request_json != request_json:
                raise HTTPException(409, '请求编号已用于其他申请内容')
            item = session.get(m.Subsidy, prior.subsidy_id)
            if item is None: raise HTTPException(410, '原申请记录已删除，请联系管理员')
            return {'data': m._app_subsidy_payload(item), 'request_id': secrets.token_urlsafe(12)}
        campaign = scoped_campaign(session, campaign_id, member, lock=True)
        applied_at = m.now()
        info = eligibility(session, campaign, member, applied_at)
        if not info['eligible']: raise HTTPException(409, '；'.join(info['reasons']))
        images = [payload.download_image, payload.install_image, payload.recharge_image]
        for url in images:
            match = re.fullmatch(r'/api/member-images/([a-f0-9]{48}\.png)', url)
            if match is None or not (m.image_directory() / match.group(1)).is_file():
                raise HTTPException(422, '请先上传有效的三类截图')
        item = m.Subsidy(user_id=member.id, agent_id=member.agent_id, game_id=campaign.game_id,
            tx_price=campaign.withdrawal_cents / 100, price=campaign.reward_cents / 100,
            pics=','.join(images), receive_name=payload.receive_name, receive_tel=payload.receive_tel, status=0)
        session.add(item)
        session.flush()
        snapshot = {key: info[key] for key in ['id', 'title', 'game_id', 'withdrawal_cents',
            'recharge_cents', 'reward_cents', 'review_hours', 'instructions', 'confirmed_withdrawal_cents', 'quota_date']}
        snapshot['evidence'] = {k: getattr(payload, k) for k in ['download_image', 'install_image', 'recharge_image']}
        session.add(SubsidyReservation(campaign_id=campaign.id, member_id=member.id, subsidy_id=item.id,
            quota_date=date.fromisoformat(info['quota_date']), request_key=payload.request_key, request_json=request_json,
            snapshot_json=json.dumps(snapshot, ensure_ascii=False), review_due_at=applied_at + timedelta(hours=campaign.review_hours)))
        session.commit()
        session.refresh(item)
        return {'data': m._app_subsidy_payload(item), 'request_id': secrets.token_urlsafe(12)}


@m.api.get('/subsidy-campaigns')
def admin_campaigns(admin: m.AdminUser = Depends(m.require_admin)):
    with m.SessionLocal() as session:
        rows = session.scalars(select(SubsidyCampaign).order_by(SubsidyCampaign.id.desc())).all()
        return {'items': [campaign_payload(session, x) for x in rows], 'total': len(rows),
                'can_write': admin.role in ('superadmin', 'operator')}


def save_campaign(payload, request, admin, campaign_id=None):
    with m.SessionLocal() as session:
        write_lock(session)
        game = session.get(m.Game, payload.game_id)
        if game is None: raise HTTPException(404, '游戏不存在')
        if campaign_id is None:
            item = SubsidyCampaign(**payload.model_dump())
            session.add(item)
        else:
            item = session.scalar(select(SubsidyCampaign).where(SubsidyCampaign.id == campaign_id).with_for_update())
            if item is None: raise HTTPException(404, '活动不存在')
            if item.game_id != payload.game_id: raise HTTPException(422, '活动所属游戏不可修改，请创建新活动')
            if payload.daily_quota < campaign_payload(session, item)['used']:
                raise HTTPException(409, '每日名额不能小于今日已用名额')
            for key, value in payload.model_dump().items(): setattr(item, key, value)
        session.flush()
        session.add(m.AdminOperation(admin_id=admin.id, title=f'保存补贴活动（{item.id}）',
            path=request.url.path, ip=request.client.host if request.client else ''))
        session.commit()
        return campaign_payload(session, item)


@m.api.post('/subsidy-campaigns', status_code=201)
def create_campaign(payload: CampaignInput, request: Request, admin: m.AdminUser = Depends(m.allow_roles('operator'))):
    return save_campaign(payload, request, admin)


@m.api.put('/subsidy-campaigns/{campaign_id}')
def update_campaign(campaign_id: int, payload: CampaignInput, request: Request,
                    admin: m.AdminUser = Depends(m.allow_roles('operator'))):
    return save_campaign(payload, request, admin, campaign_id)
