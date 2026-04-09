import os

from core_api.utils.crypto import decrypt_phone, encrypt_phone, hash_phone


class TestHashPhone:
    def test_deterministic(self) -> None:
        h1 = hash_phone("+79161234567")
        h2 = hash_phone("+79161234567")
        assert h1 == h2

    def test_hex_64_chars(self) -> None:
        h = hash_phone("+79161234567")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_phones_different_hashes(self) -> None:
        assert hash_phone("+79161234567") != hash_phone("+79161234568")


class TestEncryptDecryptPhone:
    def setup_method(self) -> None:
        self.key = os.urandom(32)

    def test_roundtrip(self) -> None:
        phone = "+79161234567"
        encrypted = encrypt_phone(phone, self.key)
        decrypted = decrypt_phone(encrypted, self.key)
        assert decrypted == phone

    def test_unique_nonces(self) -> None:
        phone = "+79161234567"
        e1 = encrypt_phone(phone, self.key)
        e2 = encrypt_phone(phone, self.key)
        assert e1 != e2  # разные nonce → разный ciphertext

    def test_nonce_is_12_bytes_prefix(self) -> None:
        encrypted = encrypt_phone("+79161234567", self.key)
        assert len(encrypted) > 12
