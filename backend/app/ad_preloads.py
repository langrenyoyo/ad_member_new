"""Non-settling startup cache quotes; never create impressions or credit coins."""
import json
import hashlib
from uuid import UUID
from datetime import timedelta
from typing import Literal
from fastapi import Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import select, func
from . import main_from_txt as m
from .member_insights import AdMetadata, metadata_payload


class PreloadEvent(AdMetadata):
    session_token: str = ''
    event: Literal['preload']
    impression_id: UUID
    game_id: int = Field(ge=1)
    ad_type: Literal['splash','rewarded','interstitial','banner','native']
    ad_unit_id: str = Field(default='', max_length=255)
    status: Literal['loaded','failed','timeout','unconfigured']
    duration_ms: int = Field(ge=0, le=120000)
    occurred_at: m.datetime


@m.app_api.post('/ads/preload-events', status_code=202)
def record_preload(body: PreloadEvent, member=Depends(m.require_app_member)):
    with m.SessionLocal() as s:
        m.device_risk.game_lock(s,body.game_id)
        game=m._app_game_for_member(s,member,body.game_id)
        unit=m.game_ad_config(game)['placements'][body.ad_type]['unit_id']
        if body.ad_unit_id != (unit or '') or (not unit and body.status != 'unconfigured'):
            raise HTTPException(422,'预加载广告位不匹配')
        if body.occurred_at.tzinfo is None or not m.now()-timedelta(hours=24) <= body.occurred_at <= m.now()+timedelta(minutes=5):
            raise HTTPException(422,'预加载上报时间超出范围')
        digest=hashlib.sha256(f'{member.id}:{game.id}:{body.impression_id}:{body.ad_type}'.encode()).hexdigest()
        key='preload:'+digest
        if s.scalar(select(m.AppAdEvent.id).where(m.AppAdEvent.event_id==key)):
            return {'data':{'recorded':False}}
        data=metadata_payload(body,game.id)
        if body.status != 'loaded':
            data['revenue_diagnostic']={'status':'missing','settlement_eligible':False}
        s.add(m.AppAdEvent(event_id=key,ad_session_id=f'preload_{game.id}_{digest[:40]}',
            member_id=member.id,event_type='ad_preload',result_json=json.dumps(data,ensure_ascii=False)))
        s.commit()
        return {'data':{'recorded':True}}


@m.api.get('/games/{game_id}/ad-preloads')
def list_preloads(game_id:int, member_id:int|None=Query(None,ge=1), offset:int=Query(0,ge=0),
                  limit:int=Query(50,ge=1,le=100), admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as s:
        criteria=[m.AppAdEvent.event_type=='ad_preload',m.AppAdEvent.ad_session_id.startswith(f'preload_{game_id}_', autoescape=True)]
        if member_id: criteria.append(m.AppAdEvent.member_id==member_id)
        total=s.scalar(select(func.count()).select_from(m.AppAdEvent).where(*criteria))
        events=s.scalars(select(m.AppAdEvent).where(*criteria).order_by(m.AppAdEvent.id.desc()).offset(offset).limit(limit))
        rows=[]
        for event in events:
            row=json.loads(event.result_json)
            prices=row.get('revenue_diagnostic',{}).get('prices',[])
            row.update(id=event.id,member_id=event.member_id,
                ecpm_cny=next((p['ecpm'] for p in prices if p['currency']=='CNY'),None))
            rows.append(row)
        return {'items':rows,'total':total}
