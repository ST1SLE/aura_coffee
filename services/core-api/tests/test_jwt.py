import uuid
from unittest.mock import patch

import jwt
import pytest

from core_api.services.auth import AuthService


class TestJWT:
    @patch("core_api.services.auth.settings")
    def test_create_and_decode(self, mock_settings) -> None:
        mock_settings.jwt_secret_key = "aura-coffee-tests-jwt-secret-0001"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900

        user_id = uuid.uuid4()
        token = AuthService.create_access_token(
            AuthService.__new__(AuthService), user_id, "customer"
        )
        payload = AuthService.decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "customer"

    @patch("core_api.services.auth.settings")
    def test_expired_token(self, mock_settings) -> None:
        mock_settings.jwt_secret_key = "aura-coffee-tests-jwt-secret-0001"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = -1  # сразу истёк

        user_id = uuid.uuid4()
        token = AuthService.create_access_token(
            AuthService.__new__(AuthService), user_id, "customer"
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            AuthService.decode_access_token(token)

    @patch("core_api.services.auth.settings")
    def test_invalid_signature(self, mock_settings) -> None:
        mock_settings.jwt_secret_key = "aura-coffee-tests-jwt-secret-0001"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900

        user_id = uuid.uuid4()
        token = AuthService.create_access_token(
            AuthService.__new__(AuthService), user_id, "customer"
        )

        mock_settings.jwt_secret_key = "wrong-aura-coffee-tests-jwt-secret-0001"
        with pytest.raises(jwt.InvalidSignatureError):
            AuthService.decode_access_token(token)
