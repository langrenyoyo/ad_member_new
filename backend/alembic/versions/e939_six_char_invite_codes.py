"""Replace enrollment codes with unique six-character alphanumeric codes."""
import secrets
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = 'e939_six_char_invite_codes'
down_revision = 'e938_three_member_roles'
branch_labels = None
depends_on = None

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
DIGITS = '0123456789'
ALPHABET = LETTERS + DIGITS


def _new_code(used):
    while True:
        chars = [secrets.choice(ALPHABET) for _ in range(6)]
        if not any(char in LETTERS for char in chars):
            chars[0] = secrets.choice(LETTERS)
        if not any(char in DIGITS for char in chars):
            chars[-1] = secrets.choice(DIGITS)
        secrets.SystemRandom().shuffle(chars)
        code = ''.join(chars)
        if code not in used:
            used.add(code)
            return code


def _replace_codes(alphanumeric):
    connection = op.get_bind()
    members = connection.execute(sa.text(
        'SELECT id, parent_id FROM members ORDER BY id'
    )).all()
    rows = connection.execute(sa.text(
        'SELECT member_id, invite_code FROM member_enrollments ORDER BY member_id'
    )).all()
    existing_member_ids = {row.member_id for row in rows}
    missing = [member for member in members if member.id not in existing_member_ids]
    if alphanumeric and len(rows) + len(missing) > 36 ** 6:
        raise RuntimeError('Cannot assign unique six-character invite codes to all members')

    used = {row.invite_code for row in rows}
    updates = []
    for row in rows:
        used.remove(row.invite_code)
        if alphanumeric:
            code = _new_code(used)
        else:
            while True:
                code = secrets.token_hex(6).upper()
                if code not in used:
                    used.add(code)
                    break
        updates.append({'code': code, 'member_id': row.member_id})
    if updates:
        connection.execute(sa.text(
            'UPDATE member_enrollments SET invite_code = :code WHERE member_id = :member_id'
        ), updates)

    if alphanumeric and missing:
        stamp = datetime.now(timezone.utc)
        inserts = []
        for member in missing:
            code = _new_code(used)
            inserts.append({'member_id': member.id, 'invite_code': code, 'parent_id': member.parent_id or 0,
                'level': 0, 'usage_granted': 0, 'usage_seen_at': None, 'created_at': stamp, 'updated_at': stamp})
        connection.execute(sa.text(
            'INSERT INTO member_enrollments '
            '(member_id, invite_code, parent_id, level, usage_granted, usage_seen_at, created_at, updated_at) '
            'VALUES (:member_id, :invite_code, :parent_id, :level, :usage_granted, :usage_seen_at, :created_at, :updated_at)'
        ), inserts)


def upgrade():
    _replace_codes(True)


def downgrade():
    _replace_codes(False)
