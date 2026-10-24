"""Operational insights, reviewed ad categories and opt-in device observations."""
import json
import math
from typing import Literal
from datetime import timedelta
from decimal import Decimal
from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Integer, Float, String, DateTime, select, func, delete, or_
from sqlalchemy.orm import Mapped, mapped_column
from . import main_from_txt as m


Category = Literal['unknown', 'game', 'social', 'finance', 'ecommerce', 'other']


class AdReview(m.Base, m.TimestampMixin):
    __tablename__ = 'ad_category_reviews'
    ad_session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(String(1000))
    admin_id: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ReviewInput(BaseModel):
    category: Category
    title: str = Field(default='', max_length=255)
    reason: str = Field(min_length=1, max_length=1000)
    expected_revision: int = Field(ge=0)


@m.api.put('/ad-sessions/{ad_session_id}/category-review')
def review_category(ad_session_id: str, body: ReviewInput, admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as s:
        ad = m.get_or_404(s, m.AppAdSession, ad_session_id, '广告')
        m.device_risk.game_lock(s, ad.game_id)
        s.refresh(ad)
        if ad.impressed_at is None and ad.status not in ('rewarded', 'impressed'):
            raise HTTPException(409, '仅允许复核已展示或已结算的广告')
        if not body.reason.strip(): raise HTTPException(422, '请填写复核依据')
        row = s.get(AdReview, ad.id)
        if (row.revision if row else 0) != body.expected_revision:
            raise HTTPException(409, '分类已被更新，请刷新记录')
        before = {'category': row.category, 'title': row.title, 'reason': row.reason, 'revision': row.revision} if row else None
        if row is None:
            row = AdReview(ad_session_id=ad.id, member_id=ad.member_id, revision=0)
            s.add(row)
        row.category, row.title, row.reason = body.category, body.title.strip(), body.reason.strip()
        row.admin_id, row.revision = admin.id, row.revision + 1
        s.add(m.AppAdEvent(event_id=f'category:{ad.id}:{row.revision}', ad_session_id=ad.id,
            member_id=ad.member_id, event_type='category_review', result_json=json.dumps({
                'before': before, 'after': body.model_dump(), 'admin_id': admin.id,
                'revision': row.revision, 'source': 'manual_review'}, ensure_ascii=False)))
        s.add(m.AdminOperation(admin_id=admin.id, title=f'复核广告 {ad.id} 类别 {body.category}',
            path=f'/api/v1/ad-sessions/{ad.id}/category-review', ip=''))
        s.commit()
        return {'category': row.category, 'revision': row.revision}


def label_summary(s, member_id, rule):
    # Unknown/unreviewed impressions remain in the denominator; SDK strings never classify money.
    ids = s.scalars(select(m.AppAdSession.id).where(m.AppAdSession.member_id == member_id,
        or_(m.AppAdSession.impressed_at.is_not(None), m.AppAdSession.status == 'rewarded')).order_by(
        func.coalesce(m.AppAdSession.completed_at, m.AppAdSession.impressed_at).desc(),
        m.AppAdSession.id.desc()).limit(rule.label_window)).all()
    counts = {k: 0 for k in ('unknown', 'game', 'social', 'finance', 'ecommerce', 'other')}
    reviewed = {r.ad_session_id: r.category for r in s.scalars(select(AdReview).where(AdReview.ad_session_id.in_(ids)))} if ids else {}
    for ad_id in ids: counts[reviewed.get(ad_id, 'unknown')] += 1
    total = len(ids)
    label = next((k for k, v in counts.items() if k != 'unknown' and total >= rule.label_min_samples
        and Decimal(v) > rule.label_threshold * total), 'unknown')
    return {'label': label, 'total': total, 'counts': counts,
        'ratios': {k: str(Decimal(v)/total if total else Decimal(0)) for k, v in counts.items()},
        'window': rule.label_window, 'min_samples': rule.label_min_samples,
        'threshold': str(rule.label_threshold), 'source': 'manual_review',
        'reason': '按最近已展示或已结算广告统计，未知计入分母；超过阈值且样本充足才生成标签'}


class AdMetadata(BaseModel):
    session_token: str = Field(min_length=1,max_length=256)
    event: Literal['shown','clicked','reward','closed','downloaded','installed','opened']
    network: str = Field(default='',max_length=128)
    source_id: str = Field(default='',max_length=128)
    format: str = Field(default='',max_length=64)
    title: str = Field(default='',max_length=255)
    app_name: str = Field(default='',max_length=255)
    creative_id: str = Field(default='',max_length=255)
    extension_keys: list[str] = Field(default_factory=list,max_length=50)
    e_c: str = Field(default='', max_length=8192)
    e_c_cny: str = Field(default='', max_length=8192)
    s_id: str = Field(default='', max_length=128)
    publisher_revenue_cny: Decimal | None = Field(default=None, gt=0, le=1000000,
        max_digits=24, decimal_places=12)
    sdk_request_id: str = Field(default='', max_length=256)
    sdk_show_id: str = Field(default='', max_length=256)


@m.app_api.post('/ads/{ad_session_id}/metadata')
def ad_metadata(ad_session_id: str, body: AdMetadata, member=Depends(m.require_app_member)):
    with m.SessionLocal() as s:
        ad=m._app_session(s,ad_session_id,member,body.session_token)
        if ad.created_at.replace(tzinfo=m.UTC)<m.now()-timedelta(hours=24):
            raise HTTPException(409,'广告元数据上报窗口已结束')
        key='metadata:'+ad.id+':'+body.event
        if s.scalar(select(m.AppAdEvent.id).where(m.AppAdEvent.event_id==key)):
            return {'data':{'recorded':False}}
        if any(len(k)>100 for k in body.extension_keys):raise HTTPException(422,'扩展字段名称过长')
        data=body.model_dump(mode='json', exclude={'session_token','e_c','e_c_cny'})
        data['trust']='client_reported'
        # Diagnostic only: encryption is not a signature or proof of a unique display.
        from .taku_ecpm import verify_ecpm, EcpmConfigurationError, EcpmValidationError
        revenue = {'status':'missing', 'settlement_eligible':False,
                   'ciphertext_present':{'USD':bool(body.e_c),'CNY':bool(body.e_c_cny)}}
        if body.e_c or body.e_c_cny or body.s_id:
            try:
                proof = verify_ecpm(ad.game_id, body.source_id, body.e_c, body.e_c_cny, body.s_id)
                revenue.update(status='decrypted', prices=[{
                    **price, 'estimated_revenue':format(Decimal(price['ecpm']) / Decimal(1000), 'f')
                } for price in proof['prices']])
            except EcpmConfigurationError:
                revenue['status']='configuration_unavailable'
            except EcpmValidationError:
                revenue['status']='invalid_proof'
        data['revenue_diagnostic']=revenue
        s.add(m.AppAdEvent(event_id=key,ad_session_id=ad.id,member_id=member.id,
            event_type='client_metadata',result_json=json.dumps(data,ensure_ascii=False)))
        s.commit()
        return {'data':{'recorded':True}}


def enrich_ad_list(s, rows):
    requests = [r['request_id'] for r in rows if r.get('request_id')]
    sessions = {ad.request_id: ad for ad in s.scalars(select(m.AppAdSession).where(
        m.AppAdSession.request_id.in_(requests)))} if requests else {}
    ids = [ad.id for ad in sessions.values()]
    reviews = {r.ad_session_id:r for r in s.scalars(select(AdReview).where(AdReview.ad_session_id.in_(ids)))} if ids else {}
    events = {}
    if ids:
        for e in s.scalars(select(m.AppAdEvent).where(m.AppAdEvent.ad_session_id.in_(ids),
                m.AppAdEvent.event_type == 'client_metadata').order_by(m.AppAdEvent.id)):
            events.setdefault(e.ad_session_id, []).append(json.loads(e.result_json))
    for row in rows:
        ad = sessions.get(row.get('request_id'))
        if ad and (ad.member_id != row['user_id'] or ad.game_id != row['game_id']):
            ad = None
        review = reviews.get(ad.id) if ad else None
        metadata = events.get(ad.id, []) if ad else []
        row['ad_category'] = review.category if review else 'unknown'
        row['ad_title'] = review.title if review and review.title else next(
            (e.get('title') or e.get('app_name') for e in metadata if e.get('title') or e.get('app_name')), '')
        row['ad_behaviors'] = sorted({e.get('event') for e in metadata if e.get('event') in
            ('shown','clicked','downloaded','installed','opened')} | ({'shown'} if ad and ad.impressed_at else set()))


def purge_expired():
    with m.SessionLocal() as s:
        s.execute(delete(Observation).where(Observation.created_at < m.now()-timedelta(hours=24)))
        s.commit()


async def retention_loop():
    import asyncio
    import logging
    from starlette.concurrency import run_in_threadpool
    while True:
        try:
            await run_in_threadpool(purge_expired)
        except Exception:
            logging.getLogger(__name__).exception('Observation retention cleanup failed')
        await asyncio.sleep(300)


class Observation(m.Base):
    __tablename__ = 'device_observations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str] = mapped_column(String(64))
    battery: Mapped[int] = mapped_column(Integer)
    charging: Mapped[int] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), index=True)


class ObservationInput(BaseModel):
    battery: int = Field(ge=0, le=100)
    charging: bool
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    accuracy: float | None = Field(default=None, gt=0, le=10000, allow_inf_nan=False)
    location_age_seconds: int | None = Field(default=None, ge=0, le=120)

    @model_validator(mode='after')
    def location_complete(self):
        fields = (self.latitude, self.longitude, self.accuracy, self.location_age_seconds)
        if any(x is not None for x in fields) and any(x is None for x in fields):
            raise ValueError('定位需要坐标、精度和采样年龄')
        return self


@m.app_api.post('/device-observations')
def observe(body: ObservationInput, request: Request, member=Depends(m.require_app_member)):
    with m.SessionLocal() as s:
        m.device_risk.game_lock(s, member.game_id)
        now = m.now()
        latest = s.scalar(select(Observation).where(Observation.member_id == member.id).order_by(Observation.id.desc()))
        if latest and latest.created_at.replace(tzinfo=m.UTC) > now-timedelta(seconds=45):
            return {'data': {'recorded': False, 'retry_after': 45}}
        check = s.scalar(select(m.device_risk.DeviceCheck).where(
            m.device_risk.DeviceCheck.member_id == member.id,
            m.device_risk.DeviceCheck.install_hash == m._token_hash(request.headers.get('X-Device-Id', '')),
            m.device_risk.DeviceCheck.status.in_(['verified', 'consumed']),
            m.device_risk.DeviceCheck.verified_at >= now-timedelta(hours=24)
            ).order_by(m.device_risk.DeviceCheck.verified_at.desc()))
        # request.client must be supplied by a trusted, configured proxy chain.
        s.add(Observation(member_id=member.id, game_id=member.game_id,
            device_id=check.device_id if check else None, ip=(request.client.host if request.client else '')[:64],
            battery=body.battery, charging=int(body.charging), latitude=body.latitude,
            longitude=body.longitude, accuracy=body.accuracy, created_at=now))
        s.execute(delete(Observation).where(Observation.game_id == member.game_id, Observation.created_at < now-timedelta(hours=24)))
        s.commit()
        return {'data': {'recorded': True}}


@m.app_api.delete('/device-observations')
def forget_observations(member=Depends(m.require_app_member)):
    with m.SessionLocal() as s:
        m.device_risk.game_lock(s, member.game_id)
        s.execute(delete(Observation).where(Observation.member_id == member.id))
        s.commit()
    return {'data': {'deleted': True}}


def distance(a, b):
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat, dlon = lat2-lat1, math.radians(b.longitude-a.longitude)
    value = math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(min(1, math.sqrt(value)))


def stable_duration(history):
    """Count only continuous >=5 minute segments whose entire extent fits 100m."""
    segment, total = [], 0.0
    def duration(points):
        seconds = (points[-1].created_at-points[0].created_at).total_seconds() if len(points)>1 else 0
        return seconds if seconds >= 299.99 else 0
    for point in history:
        valid = point.latitude is not None and point.accuracy is not None and point.accuracy <= 30
        continuous = not segment or (0 < (point.created_at-segment[-1].created_at).total_seconds() <= 120
                                    and point.device_id == segment[-1].device_id)
        fits = valid and all(distance(point, p)+point.accuracy+p.accuracy <= 100 for p in segment)
        if not valid or not continuous or not fits:
            total += duration(segment)
            segment = []
        if valid: segment.append(point)
    return round(total+duration(segment))


@m.api.get('/games/{game_id}/observation-board')
def observation_board(game_id: int, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                      admin=Depends(m.allow_roles('superadmin', 'risk'))):
    with m.SessionLocal() as s:
        m.get_or_404(s, m.Game, game_id, '应用')
        cutoff = m.now()-timedelta(minutes=10)
        latest_ids = select(func.max(Observation.id)).where(Observation.game_id == game_id,
            Observation.created_at >= cutoff).group_by(Observation.member_id)
        total = s.scalar(select(func.count()).select_from(latest_ids.subquery())) or 0
        rows = s.scalars(select(Observation).where(Observation.id.in_(latest_ids)).order_by(Observation.id.desc()).offset(offset).limit(limit)).all()
        peers = s.scalars(select(Observation).where(Observation.id.in_(latest_ids))).all()
        items = []
        histories = {}
        for sample in s.scalars(select(Observation).where(Observation.game_id == game_id,
                Observation.member_id.in_([r.member_id for r in rows]),
                Observation.created_at >= m.now()-timedelta(hours=1)).order_by(Observation.created_at)):
            histories.setdefault(sample.member_id, []).append(sample)
        for row in rows:
            same_ip = {p.device_id for p in peers if p.ip == row.ip and p.device_id is not None}
            nearby = None
            if row.device_id is not None and row.latitude is not None and row.accuracy <= 30:
                nearby = len({p.device_id for p in peers if p.device_id is not None and p.device_id != row.device_id
                    and p.latitude is not None and p.accuracy <= 30
                    and distance(row, p)+row.accuracy+p.accuracy <= 100})
            history = histories.get(row.member_id, [])
            observed = charged = located = 0.0
            for a, b in zip(history, history[1:]):
                seconds = (b.created_at-a.created_at).total_seconds()
                if not 0 < seconds <= 120 or a.device_id != b.device_id: continue
                observed += seconds
                if a.charging and b.charging: charged += seconds
                if a.latitude is not None and b.latitude is not None and a.accuracy <= 30 and b.accuracy <= 30:
                    located += seconds
            items.append({'member_id': row.member_id, 'device_id': row.device_id, 'ip': row.ip,
                'battery': row.battery, 'charging': bool(row.charging), 'location_available': row.latitude is not None,
                'accuracy_m': row.accuracy, 'same_ip_verified_devices': len(same_ip),
                'same_device_accounts': len({p.member_id for p in peers if p.device_id == row.device_id}) if row.device_id is not None else None,
                'nearby_verified_devices': nearby, 'observed_seconds': round(observed),
                'charging_ratio': charged/observed if observed >= 300 else None,
                'location_stable_seconds': stable_duration(history) if located >= 299.99 else None,
                'samples': len(history), 'updated_at': m.stringify(row.created_at)})
        return {'total': total, 'items': items, 'mode': 'observe_only', 'window_minutes': 10}


@m.api.get('/members/{member_id}/insights')
def member_insights(member_id: int, admin=Depends(m.allow_roles('superadmin', 'operator', 'risk'))):
    p = m.member_policy
    with m.SessionLocal() as s:
        member = m.get_or_404(s, m.Member, member_id, '会员')
        row = s.get(p.Enrollment, member.id)
        today = (m.now()+timedelta(hours=8)).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(hours=8)
        def total(model, field, *conditions):
            return s.scalar(select(func.sum(field)).where(*conditions)) or 0
        commissions = (p.RewardLedger.beneficiary_id == member_id, p.RewardLedger.kind != 'reward')
        views = (m.AppAdSession.member_id == member_id, m.AppAdSession.impressed_at.is_not(None))
        account = s.get(m.payouts.AlipayAccount, member_id)
        checks = select(m.device_risk.DeviceCheck.device_id).where(m.device_risk.DeviceCheck.member_id == member_id,
            m.device_risk.DeviceCheck.device_id.is_not(None), m.device_risk.DeviceCheck.verified_at >= m.now()-timedelta(days=30))
        related = s.scalars(select(m.device_risk.DeviceCheck.member_id).where(m.device_risk.DeviceCheck.device_id.in_(checks),
            m.device_risk.DeviceCheck.member_id != member_id,
            m.device_risk.DeviceCheck.verified_at >= m.now()-timedelta(days=30)).distinct().limit(51)).all()
        return {'id': member.id, 'name': member.name, 'status': member.status,
            'level': row.level if row else 0, 'parent_id': row.parent_id if row else member.parent_id,
            'invite_code': row.invite_code if row else None,
            'coin': str(member.coin), 'frozen_coin': str(member.freeze_coin),
            'commission_total_coin': str(total(p.RewardLedger,p.RewardLedger.amount,*commissions)),
            'commission_today_coin': str(total(p.RewardLedger,p.RewardLedger.amount,*commissions,p.RewardLedger.created_at>=today)),
            'contribution_coin': str(total(p.RewardLedger,p.RewardLedger.amount,p.RewardLedger.member_id==member_id,p.RewardLedger.kind!='reward')),
            'paid_withdrawal_cents': int(total(m.payouts.Payout,m.payouts.Payout.amount_cents,m.payouts.Payout.member_id==member_id,m.payouts.Payout.state=='succeeded')),
            'direct_count': s.scalar(select(func.count()).select_from(p.Enrollment).where(p.Enrollment.parent_id==member_id)) or 0,
            'ad_views': s.scalar(select(func.count()).select_from(m.AppAdSession).where(*views)) or 0,
            'ad_views_today': s.scalar(select(func.count()).select_from(m.AppAdSession).where(*views,m.AppAdSession.impressed_at>=today)) or 0,
            'category_status': 'unknown', 'category_reason': '类别仅在人工复核后可用，SDK 上报不会自动影响标签',
            'label_summary': label_summary(s, member.id, p.policy(s, member.game_id)),
            'commission_in_wallet': True,
            'alipay_bound': account is not None,
            'alipay_masked': ('***'+account.account[-4:]) if account else None,
            'related_member_ids_30d': related[:50], 'related_truncated': len(related)>50,
            'direct_members': [{'id': e.member_id, 'level': e.level} for e in s.scalars(select(p.Enrollment)
                .where(p.Enrollment.parent_id==member_id).order_by(p.Enrollment.member_id.desc()).limit(50))]}


@m.api.get('/members/{member_id}/ad-settlements')
def ad_settlements(member_id: int, limit: int=Query(20,ge=1,le=100), offset: int=Query(0,ge=0),
                   admin=Depends(m.allow_roles('superadmin', 'operator', 'risk'))):
    with m.SessionLocal() as s:
        m.get_or_404(s,m.Member,member_id,'会员')
        rows=s.scalars(select(m.AppAdSession).where(m.AppAdSession.member_id==member_id)
            .order_by(m.AppAdSession.created_at.desc(),m.AppAdSession.id.desc()).offset(offset).limit(limit)).all()
        items=[]
        for ad in rows:
            ledgers=s.scalars(select(m.member_policy.RewardLedger).where(m.member_policy.RewardLedger.ad_session_id==ad.id)).all()
            log=s.get(m.CoinLog,ad.coin_log_id) if ad.coin_log_id else None
            review = s.get(AdReview, ad.id)
            items.append({'id':ad.id,'provider':ad.provider,'status':ad.status,'category':review.category if review else 'unknown',
                'review': {'title':review.title, 'reason':review.reason, 'revision':review.revision,
                    'admin_id':review.admin_id, 'source':'manual_review'} if review else None,
                'client_metadata':[json.loads(e.result_json) for e in s.scalars(select(m.AppAdEvent).where(
                    m.AppAdEvent.ad_session_id==ad.id,m.AppAdEvent.event_type=='client_metadata').order_by(m.AppAdEvent.id))],
                'created_at':m.stringify(ad.created_at),'impressed_at':m.stringify(ad.impressed_at),
                'user_reward_coin':str(log.coin) if log else '0',
                'allocations':[{'member_id':r.beneficiary_id,'kind':r.kind,'coin':str(r.amount),'rule':json.loads(r.rule_json)} for r in ledgers],
                'events':[{'type':e.event_type,'time':m.stringify(e.created_at)} for e in s.scalars(select(m.AdFlowLog).where(m.AdFlowLog.ad_session_id==ad.id).order_by(m.AdFlowLog.id).limit(100))]})
        total=s.scalar(select(func.count()).select_from(m.AppAdSession).where(m.AppAdSession.member_id==member_id)) or 0
        return {'total':total,'items':items}
