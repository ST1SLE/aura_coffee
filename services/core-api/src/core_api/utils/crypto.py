import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def hash_phone(normalized_phone: str) -> str:
    """SHA-256 хеш нормализованного телефона (детерминированный, без соли)."""
    return hashlib.sha256(normalized_phone.encode()).hexdigest()


def encrypt_phone(phone: str, key: bytes) -> bytes:
    """AES-256-GCM шифрование телефона. Возвращает nonce (12 bytes) + ciphertext."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, phone.encode(), None)
    return nonce + ciphertext


def decrypt_phone(encrypted: bytes, key: bytes) -> str:
    """AES-256-GCM дешифрование. Принимает nonce (12 bytes) + ciphertext."""
    aesgcm = AESGCM(key)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
