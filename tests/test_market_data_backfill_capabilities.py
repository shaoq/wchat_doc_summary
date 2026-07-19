"""task 8.1: get_category_capabilities 动态 historical_safe 单测。"""

from config import settings as settings_mod
from src.api.finance import FinanceClient


def test_default_off_keeps_realtime_behavior():
    """off（默认）模式：indices/sectors 保持 historical_safe=False（原行为，向后兼容）。"""
    assert settings_mod.settings.market_data_provider == "off"
    caps = FinanceClient.get_category_capabilities()
    assert caps["indices"]["historical_safe"] is False
    assert caps["sectors"]["historical_safe"] is False
    # volume/limit_up 仍 True
    assert caps["volume"]["historical_safe"] is True
    assert caps["limit_up"]["historical_safe"] is True


def test_mixed_mode_upgrades_indices_sectors(monkeypatch):
    """mixed 模式：TickFlow 支持历史，indices/sectors 升 historical_safe。"""
    monkeypatch.setattr(settings_mod.settings, "market_data_provider", "mixed")
    caps = FinanceClient.get_category_capabilities()
    assert caps["indices"]["historical_safe"] is True
    assert caps["sectors"]["historical_safe"] is True


def test_tickflow_mode_upgrades(monkeypatch):
    """tickflow 模式同样升级。"""
    monkeypatch.setattr(settings_mod.settings, "market_data_provider", "tickflow")
    caps = FinanceClient.get_category_capabilities()
    assert caps["indices"]["historical_safe"] is True
    assert caps["sectors"]["historical_safe"] is True


def test_returns_deep_copy(monkeypatch):
    """返回深拷贝，改副本不影响常量，且每次重新计算。"""
    monkeypatch.setattr(settings_mod.settings, "market_data_provider", "tickflow")
    caps = FinanceClient.get_category_capabilities()
    caps["indices"]["historical_safe"] = False  # 篡改副本
    assert caps is not FinanceClient.CATEGORY_CAPABILITIES
    caps2 = FinanceClient.get_category_capabilities()
    assert caps2["indices"]["historical_safe"] is True
