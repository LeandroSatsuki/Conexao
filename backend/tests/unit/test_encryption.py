from __future__ import annotations

import json

from app.core.encryption import decrypt_secret, encrypt_secret, mask_secret


def test_encrypt_and_decrypt_secret_roundtrip():
    payload = {"token": "secret-token", "password": "secret-password"}

    encrypted = encrypt_secret(payload)
    assert encrypted != json.dumps(payload, sort_keys=True)

    decrypted = decrypt_secret(encrypted)
    assert json.loads(decrypted) == payload


def test_mask_secret_hides_middle_section():
    assert mask_secret("123456789") == "12***89"
    assert mask_secret("abc") == "****"
