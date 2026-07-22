import pytest

from app.core.registry import CapabilityUnavailable, ServiceRegistry


def test_get_returns_none_for_missing_capability():
    reg = ServiceRegistry()
    assert reg.get("rulepacks.loader") is None
    assert reg.get("rulepacks.loader", default="fallback") == "fallback"


def test_require_raises_for_missing_capability():
    reg = ServiceRegistry()
    with pytest.raises(CapabilityUnavailable):
        reg.require("boq.items")


def test_provide_and_consume():
    reg = ServiceRegistry()
    svc = object()
    reg.provide("risk.findings", svc)
    assert reg.require("risk.findings") is svc
    assert reg.has("risk.findings")
    assert reg.names() == ["risk.findings"]


def test_double_provide_rejected_unless_replace():
    reg = ServiceRegistry()
    reg.provide("x", 1)
    with pytest.raises(ValueError):
        reg.provide("x", 2)
    reg.provide("x", 2, replace=True)
    assert reg.get("x") == 2
