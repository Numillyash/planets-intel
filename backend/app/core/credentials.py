from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class CredentialEncryptionError(RuntimeError):
    pass


def _get_fernet() -> Fernet:
    key = get_settings().credential_encryption_key

    if not key:
        raise CredentialEncryptionError(
            "CREDENTIAL_ENCRYPTION_KEY is not configured"
        )

    try:
        return Fernet(
            key.encode("ascii")
        )
    except (TypeError, ValueError) as exc:
        raise CredentialEncryptionError(
            "CREDENTIAL_ENCRYPTION_KEY is invalid"
        ) from exc


def encrypt_credential(
    plaintext: str,
) -> str:
    return (
        _get_fernet()
        .encrypt(
            plaintext.encode("utf-8")
        )
        .decode("ascii")
    )


def decrypt_credential(
    ciphertext: str,
) -> str:
    try:
        return (
            _get_fernet()
            .decrypt(
                ciphertext.encode("ascii")
            )
            .decode("utf-8")
        )
    except InvalidToken as exc:
        raise CredentialEncryptionError(
            "Stored credential cannot be decrypted"
        ) from exc
