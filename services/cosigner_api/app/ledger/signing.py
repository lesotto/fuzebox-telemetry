"""Signing providers.

A provider takes the canonical bytes of a row hash and returns a signature.
It also verifies signatures and exposes a public key (or key id) for offline verifiers.

Three concrete providers:

- StaticHMACProvider: HMAC-SHA256 with a static secret. Dev only.
- KMSProvider: AWS KMS Sign / Verify. Production default.
- VaultProvider: HashiCorp Vault Transit. Fallback.

The ABC is intentionally narrow so `verify.py` can re-verify offline using only
a public key (or shared HMAC secret bundled into an audit export).
"""

from __future__ import annotations

import abc
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any

from .. import settings as settings_module


class SigningError(Exception):
    """Raised when sign or verify fails for a non-recoverable reason."""


@dataclass(frozen=True)
class PublicKeyMaterial:
    """What we ship to an auditor so they can verify offline."""

    algorithm: str  # "HMAC-SHA256" | "ECDSA-P256-SHA256" | ...
    key_id: str
    public_key_pem: str | None  # None for HMAC
    shared_secret_b64: str | None  # only used for static-HMAC dev exports


class SigningProvider(abc.ABC):
    """Abstract signing provider."""

    algorithm: str
    key_id: str

    @abc.abstractmethod
    def sign(self, payload: bytes) -> bytes:
        """Return the signature bytes for `payload`."""

    @abc.abstractmethod
    def verify(self, payload: bytes, signature: bytes) -> bool:
        """Return True iff `signature` is a valid signature over `payload`."""

    @abc.abstractmethod
    def public_material(self) -> PublicKeyMaterial:
        """Return the material an auditor needs to verify offline."""


class StaticHMACProvider(SigningProvider):
    """HMAC-SHA256 with a static shared secret. Dev only.

    Refuses to operate in `prod` unless `FUZEBOX_ALLOW_STATIC_SIGNING=1`.

    Example:
        >>> p = StaticHMACProvider(secret="abc")
        >>> sig = p.sign(b"hello")
        >>> p.verify(b"hello", sig)
        True
    """

    algorithm = "HMAC-SHA256"

    def __init__(self, secret: str, key_id: str = "static-dev") -> None:
        if not secret:
            raise SigningError("static signing key is empty")
        s = settings_module.get_settings()
        if s.environment == "prod" and not s.allow_static_signing_in_prod:
            raise SigningError(
                "static HMAC signing is forbidden in prod. "
                "Set FUZEBOX_ALLOW_STATIC_SIGNING=1 only if you accept the risk."
            )
        self._secret = secret.encode("utf-8")
        self.key_id = key_id

    def sign(self, payload: bytes) -> bytes:
        return hmac.new(self._secret, payload, hashlib.sha256).digest()

    def verify(self, payload: bytes, signature: bytes) -> bool:
        expected = self.sign(payload)
        return hmac.compare_digest(expected, signature)

    def public_material(self) -> PublicKeyMaterial:
        # Dev-only export. Auditors should never see this in prod bundles.
        import base64

        return PublicKeyMaterial(
            algorithm=self.algorithm,
            key_id=self.key_id,
            public_key_pem=None,
            shared_secret_b64=base64.b64encode(self._secret).decode("ascii"),
        )


class KMSProvider(SigningProvider):
    """AWS KMS asymmetric sign/verify (ECDSA-P256-SHA256).

    Lazy imports `boto3` so the static provider works without AWS deps installed.
    """

    algorithm = "ECDSA-P256-SHA256"

    def __init__(self, key_id: str, region: str | None = None) -> None:
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover — exercised only in prod
            raise SigningError("boto3 is required for KMSProvider") from exc

        self.key_id = key_id
        self._client = boto3.client("kms", region_name=region)

    def sign(self, payload: bytes) -> bytes:
        digest = hashlib.sha256(payload).digest()
        try:
            resp: dict[str, Any] = self._client.sign(
                KeyId=self.key_id,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm="ECDSA_SHA_256",
            )
        except Exception as exc:  # pragma: no cover — network
            raise SigningError(f"KMS sign failed: {exc}") from exc
        return bytes(resp["Signature"])

    def verify(self, payload: bytes, signature: bytes) -> bool:
        digest = hashlib.sha256(payload).digest()
        try:
            resp = self._client.verify(
                KeyId=self.key_id,
                Message=digest,
                MessageType="DIGEST",
                Signature=signature,
                SigningAlgorithm="ECDSA_SHA_256",
            )
        except Exception:  # pragma: no cover — network
            return False
        return bool(resp.get("SignatureValid"))

    def public_material(self) -> PublicKeyMaterial:  # pragma: no cover — network
        resp = self._client.get_public_key(KeyId=self.key_id)
        import base64

        pem = (
            "-----BEGIN PUBLIC KEY-----\n"
            + base64.encodebytes(resp["PublicKey"]).decode("ascii")
            + "-----END PUBLIC KEY-----\n"
        )
        return PublicKeyMaterial(
            algorithm=self.algorithm,
            key_id=self.key_id,
            public_key_pem=pem,
            shared_secret_b64=None,
        )


class VaultProvider(SigningProvider):  # pragma: no cover — exercised in integration tests
    """HashiCorp Vault Transit signer (Ed25519)."""

    algorithm = "ED25519"

    def __init__(self, addr: str, token: str, key_name: str) -> None:
        try:
            import hvac  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SigningError("hvac is required for VaultProvider") from exc

        self._client = hvac.Client(url=addr, token=token)
        self.key_id = key_name
        self._key_name = key_name

    def sign(self, payload: bytes) -> bytes:
        import base64

        digest = hashlib.sha256(payload).digest()
        b64 = base64.b64encode(digest).decode("ascii")
        resp = self._client.secrets.transit.sign_data(name=self._key_name, hash_input=b64)
        sig = resp["data"]["signature"]
        return sig.encode("ascii")  # vault: prefix kept for verify

    def verify(self, payload: bytes, signature: bytes) -> bool:
        import base64

        digest = hashlib.sha256(payload).digest()
        b64 = base64.b64encode(digest).decode("ascii")
        resp = self._client.secrets.transit.verify_signed_data(
            name=self._key_name,
            hash_input=b64,
            signature=signature.decode("ascii"),
        )
        return bool(resp["data"]["valid"])

    def public_material(self) -> PublicKeyMaterial:
        resp = self._client.secrets.transit.read_key(name=self._key_name)
        keys = resp["data"]["keys"]
        latest = keys[max(keys.keys())]
        return PublicKeyMaterial(
            algorithm=self.algorithm,
            key_id=self._key_name,
            public_key_pem=latest.get("public_key"),
            shared_secret_b64=None,
        )


def build_provider(
    provider: str | None = None,
    *,
    overrides: dict[str, Any] | None = None,
) -> SigningProvider:
    """Construct the configured signing provider.

    `overrides` is for tests; production callers should pass `None`.

    Example:
        >>> os.environ["FUZEBOX_SIGNING_PROVIDER"] = "static"
        >>> os.environ["FUZEBOX_STATIC_SIGNING_KEY"] = "test"
        >>> settings_module.reset_settings_cache()
        >>> p = build_provider()
        >>> isinstance(p, StaticHMACProvider)
        True
    """

    s = settings_module.get_settings()
    provider = provider or s.signing_provider
    overrides = overrides or {}

    if provider == "static":
        return StaticHMACProvider(
            secret=overrides.get("secret", s.static_signing_key),
            key_id=overrides.get("key_id", "static-dev"),
        )
    if provider == "kms":
        if not s.kms_key_id:
            raise SigningError("FUZEBOX_KMS_KEY_ID is not set")
        return KMSProvider(key_id=s.kms_key_id, region=s.kms_region)
    if provider == "vault":
        if not (s.vault_addr and s.vault_token and s.vault_key):
            raise SigningError("Vault config incomplete")
        return VaultProvider(addr=s.vault_addr, token=s.vault_token, key_name=s.vault_key)
    raise SigningError(f"unknown signing provider: {provider}")


__all__ = [
    "SigningError",
    "SigningProvider",
    "StaticHMACProvider",
    "KMSProvider",
    "VaultProvider",
    "PublicKeyMaterial",
    "build_provider",
]


# Silence unused-import warning when the module is imported only for the env override doctest.
_ = os
