"""Public, game-scoped invitation metadata. Authentication uses the existing SMS flow."""
import os
import re
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Query
from sqlalchemy import select
from . import main_from_txt as m, member_policy as p


def invite_path(game_id, code):
    return '/invite.html?' + urlencode({'game_id': game_id, 'invite_code': code})


def download_url():
    configured = os.getenv('APP_DOWNLOAD_URL', '').strip()
    if configured:
        parsed = urlsplit(configured)
        if (parsed.scheme == 'https' and parsed.netloc and not parsed.username and not parsed.password
                and not any(c in configured for c in '\r\n')):
            return configured
        # Allow files served by this site, never protocol-relative URLs.
        if configured.startswith('/downloads/') and not parsed.scheme and not parsed.netloc and '..' not in parsed.path:
            return configured
        return None
    if (m.PUBLIC_DIR / 'downloads' / 'yazhiyiji-latest.apk').is_file():
        return '/downloads/yazhiyiji-latest.apk'
    return None


@m.app_api.get('/invitations/resolve')
def resolve_invitation(game_id: int = Query(..., ge=1), invite_code: str = Query(..., min_length=6, max_length=6)):
    code = invite_code.strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{6}', code):
        raise HTTPException(422, '邀请码必须为6位英文或数字')
    with m.SessionLocal() as session:
        game = session.get(m.Game, game_id)
        row = session.scalar(select(p.Enrollment).where(p.Enrollment.invite_code == code))
        owner = session.get(m.Member, row.member_id) if row else None
        if not game or game.status != 1 or not owner or owner.status != 1 or owner.game_id != game_id:
            raise HTTPException(404, '邀请链接已失效或不属于当前应用')
        rule = p.policy(session, game_id)
        return {'data': {'game_id': game_id, 'app_name': game.name, 'invite_code': code,
            'registration_eligible': row.level in (1, 3),
            'require_registration_invite': rule.require_registration_invite,
            'invite_path': invite_path(game_id, code), 'download_url': download_url(),
            'app_open_url': app_open_url(game_id, code)}}


def app_open_url(game_id, code):
    scheme = os.getenv('APP_INVITE_SCHEME', 'yazhiyiji').strip()
    if scheme not in ('yazhiyiji', 'guangjiyexing', 'hehe'):
        scheme = 'yazhiyiji'
    return scheme + '://invite?' + urlencode({'game_id': game_id, 'invite_code': code})
