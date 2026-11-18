"""Persist device denials after the business transaction has unwound."""
import json
import logging
from datetime import datetime

from fastapi import Depends, HTTPException, Query, Request
from fastapi.exception_handlers import http_exception_handler
from sqlalchemy import select, func
from . import main_from_txt as m


def denied(member, status, detail, code, device_id=None, **context):
    exc = HTTPException(status, detail)
    exc.device_block = dict(member_id=member.id, game_id=member.game_id, code=code,
        device_id=device_id, reason=detail.get('message', '') if isinstance(detail, dict) else detail,
        **context)
    return exc


@m.app.exception_handler(HTTPException)
async def record_denial(request: Request, exc: HTTPException):
    data = getattr(exc, 'device_block', None)
    if data:
        try:
            with m.SessionLocal() as session:
                if session.get(m.Member, data['member_id']) is None:
                    data = {**data, 'member_id': 0, 'identity_note': '注册未完成，尚未建立会员身份'}
                session.add(m.AdFlowLog(member_id=data['member_id'], game_id=data['game_id'],
                    event_type='device_blocked', status='blocked', provider='device_policy',
                    error_code=data['code'], detail_json=json.dumps({**data,
                        'path': request.url.path, 'http_status': exc.status_code}, ensure_ascii=False)))
                session.commit()
        except Exception:
            logging.getLogger(__name__).exception('Failed to persist device denial')
    return await http_exception_handler(request, exc)


@m.api.get('/device-risk/blocks')
def list_blocks(game_id: int | None = Query(None, ge=1), member_id: int | None = Query(None, ge=1),
                code: str | None = None, start: datetime | None = None, end: datetime | None = None,
                limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                admin=Depends(m.allow_roles('risk'))):
    if start and end and start > end:
        raise HTTPException(422, '开始时间不能晚于结束时间')
    with m.SessionLocal() as session:
        filters = [m.AdFlowLog.event_type.in_(['device_blocked', 'device_limit_rejected'])]
        if game_id: filters.append(m.AdFlowLog.game_id == game_id)
        if member_id: filters.append(m.AdFlowLog.member_id == member_id)
        if code:
            filters.append(m.AdFlowLog.event_type == 'device_limit_rejected' if code == 'legacy_daily_limit'
                           else m.AdFlowLog.error_code == code)
        if start: filters.append(m.AdFlowLog.created_at >= start)
        if end: filters.append(m.AdFlowLog.created_at <= end)
        rows = session.scalars(select(m.AdFlowLog).where(*filters).order_by(m.AdFlowLog.id.desc()).offset(offset).limit(limit)).all()
        total = session.scalar(select(func.count()).select_from(m.AdFlowLog).where(*filters)) or 0
        items = []
        for row in rows:
            detail = json.loads(row.detail_json or '{}')
            member = session.get(m.Member, row.member_id)
            game = session.get(m.Game, row.game_id)
            items.append(dict(id=row.id, member_id=row.member_id, nickname=member.name if member else '',
                game_id=row.game_id, game_name=game.name if game else '', device_id=detail.get('device_id'),
                code=row.error_code or 'legacy_daily_limit',
                reason=detail.get('reason') or '今日风险设备广告次数已达上限（历史记录）',
                path=detail.get('path', ''), context=detail,
                created_at=m.stringify(row.created_at.replace(tzinfo=m.UTC))))
        return {'items': items, 'total': total}
