"""TAKU eCPM key protocol. Private keys stay in a server-only JSON keyring.

RSA encryption is not a provider signature. This verification supplements the
signed reward callback; it does not independently authenticate a display.
"""
import base64
import hashlib
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class EcpmConfigurationError(Exception):
    pass


class EcpmValidationError(Exception):
    pass


def _keyring():
    filename = os.getenv("TAKU_ECPM_KEYRING_FILE", "").strip()
    if not filename:
        return {}
    try:
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (OSError, ValueError) as exc:
        raise EcpmConfigurationError() from exc


def _decrypt(ciphertext, private_key, currency):
    try:
        encoded = base64.b64decode(ciphertext, validate=True)
        if len(encoded) != (private_key.key_size + 7) // 8:
            raise ValueError()
        payload = private_key.decrypt(encoded, padding.PKCS1v15()).decode("utf-8")
        fields = payload.split("_", 2)
        if len(fields) not in (2, 3) or not re.fullmatch(r"[0-9]+", fields[0]):
            raise ValueError()
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", fields[1]):
            raise ValueError()
        price = Decimal(fields[1])
        if not price.is_finite() or price < 0:
            raise ValueError()
        request_id = fields[2] if len(fields) == 3 else ""
        if len(request_id) > 256 or (request_id and not re.fullmatch(r"[A-Za-z0-9_-]+", request_id)):
            raise ValueError()
        return {"adsource_id": fields[0], "ecpm": str(price), "currency": currency,
                "sdk_request_id": request_id or None,
                "ciphertext_sha256": hashlib.sha256(encoded).hexdigest()}
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise EcpmValidationError() from exc


def _game_keys(game_id):
    configured = _keyring().get(str(game_id))
    if configured is not None:
        return configured
    from .taku_settings import global_ecpm_keys
    keys = global_ecpm_keys()
    return {'keys': keys} if keys else None


def require_configuration(game_id, required=False):
    """Validate deployment readiness without disclosing keys or promising provider delivery."""
    game = _game_keys(game_id)
    if game is None and not required:
        return False
    try:
        keys = game['keys']
        if not isinstance(keys, dict) or not keys:
            raise ValueError()
        for key_id, pem in keys.items():
            if not isinstance(key_id, str) or not key_id:
                raise ValueError()
            key = serialization.load_pem_private_key(pem.encode('utf-8'), password=None)
            if not isinstance(key, rsa.RSAPrivateKey):
                raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise EcpmConfigurationError() from exc
    return True


def verify_ecpm(game_id, adsource_id, e_c, e_c_cny, s_id):
    """Configured games require proof: omitting parameters cannot bypass checks.

    Unconfigured games retain legacy behavior only when no proof is supplied.
    Supports multiple key IDs for server/client bidding keys and key rotation.
    """
    game = _game_keys(game_id)
    supplied = bool(e_c or e_c_cny or s_id)
    if game is None:
        if supplied:
            raise EcpmConfigurationError()
        return None
    if not isinstance(game, dict) or not isinstance(game.get("keys"), dict):
        raise EcpmConfigurationError()
    if not s_id or not (e_c or e_c_cny):
        raise EcpmValidationError()
    pem = game["keys"].get(s_id)
    if not pem:
        raise EcpmValidationError()
    try:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise ValueError()
    except (ValueError, TypeError, AttributeError) as exc:
        raise EcpmConfigurationError() from exc
    prices = []
    for value, currency in ((e_c, "USD"), (e_c_cny, "CNY")):
        if value:
            prices.append(_decrypt(value, key, currency))
    if any(p["adsource_id"] != adsource_id for p in prices):
        raise EcpmValidationError()
    if len({p["sdk_request_id"] for p in prices}) != 1:
        raise EcpmValidationError()
    return {"key_id": s_id, "prices": prices, "verification": "decrypted_source_matched",
            "display_binding": "signed_callback_session_only"}
