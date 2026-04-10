"""Smoke-тест фикстуры cart_redis."""
import fakeredis


def test_cart_redis_fixture_is_fakeredis(cart_redis) -> None:
    assert isinstance(cart_redis, fakeredis.FakeRedis)
