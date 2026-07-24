"""Tests της ενσωμάτωσης στο Nomos One: το RBAC gating και η σύνθεση routes.

Δεν καλείται το Claude — ελέγχονται οι διαδρομές ανάγνωσης και το ότι κάθε
endpoint κάθεται πίσω από το παρεχόμενο auth dependency.
"""

from dataclasses import dataclass

import pytest
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from app.integration import DEFAULT_AUDIT_ROLES, create_audit_router


@dataclass
class FakeUser:
    id: str
    role: str


def make_require_role(allowed: list[str], user: FakeUser):
    """Μιμείται το require_role του Nomos One για τους σκοπούς των tests."""

    def dependency() -> FakeUser:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "Ανεπαρκή δικαιώματα.", "code": "forbidden"},
            )
        return user

    return dependency


def build_client(user: FakeUser, allowed: list[str] | None = None, on_result=None):
    allowed = allowed if allowed is not None else DEFAULT_AUDIT_ROLES
    app = FastAPI()
    app.include_router(
        create_audit_router(
            auth_dependency=make_require_role(allowed, user),
            on_result=on_result,
        ),
        prefix="/api",
    )
    return TestClient(app, raise_server_exceptions=True)


def test_routes_mounted_under_api_audit():
    client = build_client(FakeUser("u1", "attorney"))
    res = client.get("/api/audit/document-types")
    assert res.status_code == 200
    assert isinstance(res.json(), list) and res.json()


def test_allowed_roles_reach_reads():
    for role in DEFAULT_AUDIT_ROLES:
        client = build_client(FakeUser("u", role))
        assert client.get("/api/audit/exemplars").status_code == 200


def test_client_role_is_denied_everywhere():
    client = build_client(FakeUser("c1", "client"))
    assert client.get("/api/audit/document-types").status_code == 403
    assert client.get("/api/audit/exemplars").status_code == 403
    assert client.get("/api/audit/exemplars/agogi").status_code == 403
    assert client.get("/api/audit/exemplars/agogi/docx").status_code == 403


def test_analyze_endpoints_are_gated():
    client = build_client(FakeUser("c1", "client"))
    r1 = client.post("/api/audit/analyze", json={"text": "x" * 500})
    r2 = client.post("/api/audit/analyze/stream", json={"text": "x" * 500})
    assert r1.status_code == 403
    assert r2.status_code == 403


def test_custom_role_set_enforced():
    # Μόνο super_admin επιτρέπεται σε αυτή τη διαμόρφωση.
    client_admin = build_client(FakeUser("a", "super_admin"), allowed=["super_admin"])
    client_att = build_client(FakeUser("b", "attorney"), allowed=["super_admin"])
    assert client_admin.get("/api/audit/exemplars").status_code == 200
    assert client_att.get("/api/audit/exemplars").status_code == 403


def test_exemplar_docx_served_when_authorized():
    client = build_client(FakeUser("u", "admin"))
    res = client.get("/api/audit/exemplars/agogi/docx")
    assert res.status_code == 200
    assert res.content[:2] == b"PK"
    assert "wordprocessingml" in res.headers["content-type"]


def test_matter_request_accepts_matter_id():
    from app.integration import MatterAnalyzeRequest

    req = MatterAnalyzeRequest(text="κείμενο", matter_id="mat_123")
    assert req.matter_id == "mat_123"
    # Το matter_id είναι προαιρετικό — συμβατότητα με το βασικό σχήμα.
    assert MatterAnalyzeRequest(text="κείμενο").matter_id is None


@pytest.mark.anyio
async def test_maybe_call_runs_sync_and_async_hooks():
    from app.integration import _maybe_call

    calls: list[str] = []

    def sync_hook(user, matter_id, report):
        calls.append(f"sync:{matter_id}")

    async def async_hook(user, matter_id, report):
        calls.append(f"async:{matter_id}")

    await _maybe_call(sync_hook, None, "m1", None)
    await _maybe_call(async_hook, None, "m2", None)
    await _maybe_call(None, None, "m3", None)  # no-op
    assert calls == ["sync:m1", "async:m2"]


@pytest.fixture
def anyio_backend():
    return "asyncio"
