"""Unit tests for app.core.audit router helper."""

from unittest.mock import MagicMock, Mock

from fastapi import Request

from app.core import audit as audit_log


def _request_with_registry(factory=None):
    request = MagicMock(spec=Request)
    request.app.state.ctx.registry.get.return_value = factory
    return request


def test_log_skips_when_review_capability_missing():
    request = _request_with_registry(factory=None)
    session = Mock()
    audit_log.log(
        request,
        session,
        workspace_id="11111111-1111-1111-1111-111111111111",
        actor_user_id="22222222-2222-2222-2222-222222222222",
        action="workspace.created",
    )
    session.assert_not_called()


def test_log_skips_non_uuid_workspace():
    request = _request_with_registry(factory=Mock())
    session = Mock()
    audit_log.log(
        request,
        session,
        workspace_id="_NO_WORKSPACE",
        actor_user_id="22222222-2222-2222-2222-222222222222",
        action="account.settings_updated",
    )
    request.app.state.ctx.registry.get.assert_not_called()


def test_log_writes_through_review_service():
    review_svc = Mock()
    factory = Mock(return_value=review_svc)
    request = _request_with_registry(factory=factory)
    session = Mock()
    audit_log.log(
        request,
        session,
        workspace_id="11111111-1111-1111-1111-111111111111",
        actor_user_id="22222222-2222-2222-2222-222222222222",
        action="workspace.created",
        object_type="workspace",
        object_id="11111111-1111-1111-1111-111111111111",
        detail={"name": "Acme"},
    )
    factory.assert_called_once_with(session)
    review_svc.audit.assert_called_once()
    call = review_svc.audit.call_args
    assert call.kwargs["actor"] == "22222222-2222-2222-2222-222222222222"
    assert call.kwargs["action"] == "workspace.created"
