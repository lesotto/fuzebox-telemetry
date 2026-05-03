"""Tests for SigningProvider implementations."""

from __future__ import annotations

import os

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from services.cosigner_api.app import settings as app_settings
from services.cosigner_api.app.ledger.signing import (
    SigningError,
    StaticHMACProvider,
    build_provider,
)


def _reset() -> None:
    app_settings.reset_settings_cache()


def test_static_signs_and_verifies() -> None:
    _reset()
    p = StaticHMACProvider(secret="abc", key_id="kid")
    sig = p.sign(b"hello")
    assert p.verify(b"hello", sig) is True
    assert p.verify(b"goodbye", sig) is False


def test_static_rejects_empty_secret() -> None:
    _reset()
    with pytest.raises(SigningError):
        StaticHMACProvider(secret="")


def test_static_blocked_in_prod_by_default() -> None:
    os.environ["FUZEBOX_ENVIRONMENT"] = "prod"
    os.environ.pop("FUZEBOX_ALLOW_STATIC_SIGNING", None)
    _reset()
    try:
        with pytest.raises(SigningError):
            StaticHMACProvider(secret="abc")
    finally:
        os.environ["FUZEBOX_ENVIRONMENT"] = "dev"
        _reset()


def test_static_allowed_in_prod_with_override() -> None:
    os.environ["FUZEBOX_ENVIRONMENT"] = "prod"
    os.environ["FUZEBOX_ALLOW_STATIC_SIGNING"] = "1"
    _reset()
    try:
        StaticHMACProvider(secret="abc")
    finally:
        os.environ["FUZEBOX_ENVIRONMENT"] = "dev"
        os.environ.pop("FUZEBOX_ALLOW_STATIC_SIGNING", None)
        _reset()


def test_build_provider_static() -> None:
    _reset()
    p = build_provider()
    assert isinstance(p, StaticHMACProvider)


def test_build_provider_unknown() -> None:
    with pytest.raises(SigningError):
        build_provider(provider="bogus")


def test_public_material_carries_secret_for_static() -> None:
    _reset()
    p = StaticHMACProvider(secret="abc")
    material = p.public_material()
    assert material.algorithm == "HMAC-SHA256"
    assert material.shared_secret_b64 is not None


@given(payload=st.binary(min_size=0, max_size=256))
@hsettings(deadline=None, max_examples=50)
def test_signature_round_trip(payload: bytes) -> None:
    p = StaticHMACProvider(secret="seed")
    sig = p.sign(payload)
    assert p.verify(payload, sig)


@given(payload=st.binary(min_size=1, max_size=64))
@hsettings(deadline=None, max_examples=50)
def test_tampered_signature_rejected(payload: bytes) -> None:
    p = StaticHMACProvider(secret="seed")
    sig = bytearray(p.sign(payload))
    sig[0] ^= 0xFF  # flip a bit
    assert not p.verify(payload, bytes(sig))


def test_kms_sign_and_verify_with_mocked_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover the KMS sign/verify paths without needing real AWS."""
    import sys
    import types

    fake_boto3 = types.ModuleType("boto3")

    class FakeKMS:
        def __init__(self) -> None:
            self.signed: list[bytes] = []

        def sign(self, **kw: object) -> dict[str, object]:
            self.signed.append(bytes(kw["Message"]))  # type: ignore[arg-type]
            return {"Signature": b"fake-sig"}

        def verify(self, **kw: object) -> dict[str, object]:
            return {"SignatureValid": kw["Signature"] == b"fake-sig"}

    fake_kms = FakeKMS()
    fake_boto3.client = lambda *_args, **_kw: fake_kms  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    from services.cosigner_api.app.ledger.signing import KMSProvider

    p = KMSProvider(key_id="alias/test", region="us-east-1")
    sig = p.sign(b"payload")
    assert sig == b"fake-sig"
    assert p.verify(b"payload", b"fake-sig") is True
    assert p.verify(b"payload", b"wrong") is False


def test_kms_sign_wraps_underlying_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    fake_boto3 = types.ModuleType("boto3")

    class FakeKMS:
        def sign(self, **_kw: object) -> dict[str, object]:
            raise RuntimeError("kms exploded")

    fake_boto3.client = lambda *_a, **_kw: FakeKMS()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    from services.cosigner_api.app.ledger.signing import KMSProvider

    p = KMSProvider(key_id="alias/test")
    with pytest.raises(SigningError):
        p.sign(b"x")


def test_build_provider_kms_requires_key_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUZEBOX_SIGNING_PROVIDER", "kms")
    monkeypatch.delenv("FUZEBOX_KMS_KEY_ID", raising=False)
    _reset()
    with pytest.raises(SigningError):
        build_provider()


def test_build_provider_vault_requires_full_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUZEBOX_SIGNING_PROVIDER", "vault")
    monkeypatch.delenv("FUZEBOX_VAULT_ADDR", raising=False)
    _reset()
    with pytest.raises(SigningError):
        build_provider()


def test_kms_provider_requires_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    """KMS provider should raise SigningError if boto3 is missing."""
    import builtins

    real = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "boto3":
            raise ImportError("no boto3 in tests")
        return real(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from services.cosigner_api.app.ledger.signing import KMSProvider

    with pytest.raises(SigningError):
        KMSProvider(key_id="alias/test", region="us-east-1")
