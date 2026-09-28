"""Test the api_secret_key validator in production mode"""
import pytest
from pydantic import ValidationError


def test_prod_rejects_dev_default():
    """生产环境 + dev 默认密钥 → ValidationError"""
    from forgemind.core.config.settings import Settings
    with pytest.raises(ValidationError) as exc:
        Settings(env="prod")
    assert "生产环境禁止" in str(exc.value)


def test_prod_with_custom_key_works():
    """生产环境 + 显式密钥 → OK"""
    from forgemind.core.config.settings import Settings
    s = Settings(env="prod", api_secret_key="a-secure-key-with-at-least-32-chars")
    assert s.env == "prod"
    assert s.api_secret_key == "a-secure-key-with-at-least-32-chars"


def test_dev_with_default_works():
    """开发环境 + 默认密钥 → OK"""
    from forgemind.core.config.settings import Settings
    s = Settings(env="dev")
    assert s.env == "dev"
    assert "dev-only" in s.api_secret_key


def test_prod_short_secret_rejected():
    """生产环境 + 短密钥 (< 32 字符) → ValidationError"""
    from forgemind.core.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings(env="prod", api_secret_key="too-short")
