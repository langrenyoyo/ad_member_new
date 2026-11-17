"""Per-application release policy controlled by administrators."""
import json
from urllib.parse import urlparse
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from . import main_from_txt as m


class UpdatePolicy(BaseModel):
    enabled: bool = False
    force_update: bool = False
    package_name: str = Field(default='', max_length=160)
    version_code: int = Field(default=1, ge=1)
    version_name: str = Field(default='', max_length=64)
    download_url: str = Field(default='', max_length=2048)
    notes: str = Field(default='', max_length=5000)

    @model_validator(mode='after')
    def validate_release(self):
        if self.enabled:
            url = urlparse(self.download_url)
            if not self.package_name.strip() or not self.version_name.strip() or url.scheme != 'https' or not url.hostname or url.username:
                raise ValueError('启用更新须填写包名、版本名称和 HTTPS 下载地址')
        return self


def read_policy(game):
    return UpdatePolicy.model_validate(json.loads(game.settings_json or '{}').get('app_update', {}))


@m.api.get('/games/{game_id}/app-update')
def get_update(game_id: int, admin=Depends(m.require_admin)):
    with m.SessionLocal() as s:
        game = s.get(m.Game, game_id)
        if not game: raise HTTPException(404, '应用不存在')
        return read_policy(game).model_dump()


@m.api.put('/games/{game_id}/app-update')
def set_update(game_id: int, body: UpdatePolicy, admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as s:
        m.payouts.lock(s)
        game = s.scalar(select(m.Game).where(m.Game.id == game_id).with_for_update())
        if not game: raise HTTPException(404, '应用不存在')
        settings = json.loads(game.settings_json or '{}')
        settings['app_update'] = body.model_dump()
        game.settings_json = json.dumps(settings, ensure_ascii=False)
        s.add(m.AdminOperation(admin_id=admin.id, title='修改应用更新策略', path=f'/api/v1/games/{game_id}/app-update', ip=''))
        s.commit()
        return body.model_dump()


@m.app_api.get('/app-update')
def public_update(game_id: int = Query(ge=1)):
    from fastapi.responses import JSONResponse
    with m.SessionLocal() as s:
        game = s.get(m.Game, game_id)
        if not game or game.status != 1: raise HTTPException(404, '应用不可用')
        return JSONResponse(read_policy(game).model_dump(), headers={'Cache-Control':'no-store'})
