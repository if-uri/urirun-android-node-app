import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

from main import ROUTES, UriNodeServer, UriRuntime


def _http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = dict(headers or {})
    if data is not None:
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_status_route() -> None:
    runtime = UriRuntime(port=8765)
    out = runtime.handle_uri("android://device/app/query/status")
    assert out["ok"] is True
    assert out["routeCount"] == len(ROUTES)
    assert out["url"].endswith(":8765")


def test_routes_route() -> None:
    runtime = UriRuntime()
    out = runtime.handle_uri("android://device/app/query/routes")
    assert out["ok"] is True
    assert "android://device/app/query/status" in {route["uri"] for route in out["routes"]}


def test_ping_route_echoes_payload() -> None:
    runtime = UriRuntime()
    out = runtime.handle_uri("android://device/app/command/ping", {"x": 1})
    assert out["ok"] is True
    assert out["pong"] is True
    assert out["payload"] == {"x": 1}


def test_unknown_route_is_error() -> None:
    runtime = UriRuntime()
    out = runtime.handle_uri("android://device/nope/query/missing")
    assert out["ok"] is False
    assert "unknown android route" in out["error"]


def test_termux_status_reports_missing_script_without_starting() -> None:
    runtime = UriRuntime()
    out = runtime.handle_uri("android://device/termux/query/status")
    assert out["ok"] is True
    assert out["termux"]["running"] is False
    assert out["termux"]["runScript"].endswith("run-node.sh")


def test_start_termux_fails_cleanly_when_bootstrap_missing() -> None:
    runtime = UriRuntime()
    out = runtime.handle_uri("android://device/termux/command/start")
    assert out["ok"] is False
    assert "not found" in out["error"]


def test_heyasa_open_panel_validation_and_foreground_state() -> None:
    opened_urls: list[str] = []
    runtime = UriRuntime(url_opener=lambda url: (opened_urls.append(url), True)[1])

    bad = runtime.handle_uri("android://device/heyasa/command/open-panel", {"url": "javascript:alert(1)"})
    assert bad["ok"] is False and bad["goalVerified"] is False

    bad_creds = runtime.handle_uri("android://device/heyasa/command/open-panel", {"url": "https://user:pass@heyasa.local/mobile/notes"})
    assert bad_creds["ok"] is False

    ok = runtime.handle_uri("android://device/heyasa/command/open-panel", {"url": "https://heyasa.local/mobile/notes"})
    assert ok["ok"] is True and ok["opened"] is True and ok["goalVerified"] is True
    assert opened_urls == ["https://heyasa.local/mobile/notes"]

    # Without a trusted runtime state_verifier, caller-supplied goal_verified=True is untrusted.
    unverified = runtime.handle_uri(
        "android://device/heyasa/command/confirm-state",
        {"note_id": "note_abc123", "status": "saved", "goal_verified": True},
    )
    assert unverified["ok"] is True
    assert unverified["goalVerified"] is False
    assert unverified["callerAssertedGoalVerified"] is True
    assert unverified["verificationSource"] == "unverified_caller_assertion"

    state = runtime.handle_uri("android://device/heyasa/query/foreground-state")
    assert state["ok"] is True
    assert state["foregroundState"]["activePanelUrl"] == "https://heyasa.local/mobile/notes"
    assert state["foregroundState"]["lastConfirmedNoteId"] is None
    assert state["foregroundState"]["lastReportedNoteId"] == "note_abc123"
    assert state["foregroundState"]["accessibilityEnabled"] is False


def test_heyasa_open_panel_failure_does_not_claim_active_panel() -> None:
    runtime = UriRuntime(url_opener=lambda _url: False)
    failed = runtime.handle_uri("android://device/heyasa/command/open-panel", {"url": "https://heyasa.local/mobile/notes"})
    assert failed["ok"] is False
    assert failed["opened"] is False
    assert failed["goalVerified"] is False
    assert failed["foregroundState"]["activePanelUrl"] is None
    assert failed["foregroundState"]["lastOpenedAt"] is None
    assert failed["foregroundState"]["lastFailedPanelUrl"] == "https://heyasa.local/mobile/notes"
    assert failed["foregroundState"]["lastOpenError"] == "failed to open panel URL"


def test_heyasa_confirm_state_uses_trusted_runtime_verifier() -> None:
    runtime = UriRuntime(
        url_opener=lambda _url: True,
        state_verifier=lambda note_id, state: note_id == "note_verified" and bool(state.get("activePanelUrl")),
    )
    # Panel not open yet -> cannot verify.
    before_open = runtime.handle_uri(
        "android://device/heyasa/command/confirm-state",
        {"note_id": "note_verified", "status": "saved", "goal_verified": True},
    )
    assert before_open["ok"] is True and before_open["goalVerified"] is False

    runtime.handle_uri("android://device/heyasa/command/open-panel", {"url": "https://heyasa.local/mobile/notes"})
    verified = runtime.handle_uri(
        "android://device/heyasa/command/confirm-state",
        {"note_id": "note_verified", "status": "saved", "goal_verified": False},
    )
    assert verified["ok"] is True
    assert verified["goalVerified"] is True
    assert verified["verificationSource"] == "runtime_verifier"
    assert verified["foregroundState"]["lastConfirmedNoteId"] == "note_verified"

    rejected = runtime.handle_uri(
        "android://device/heyasa/command/confirm-state",
        {"note_id": "note_forged", "status": "saved", "goal_verified": True},
    )
    assert rejected["ok"] is True
    assert rejected["goalVerified"] is False
    assert rejected["verificationSource"] == "unverified_caller_assertion"
    assert rejected["foregroundState"]["lastConfirmedNoteId"] == "note_verified"


def test_server_enforces_bearer_auth_and_rejects_query_tokens() -> None:
    runtime = UriRuntime(port=0, url_opener=lambda _url: True)
    bearer_secret = secrets.token_urlsafe(16)
    server_opts = {"auth_token": bearer_secret}
    server = UriNodeServer(runtime, host="127.0.0.1", port=0, **server_opts)
    server.start()
    assert server.httpd is not None
    port = server.httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    try:
        code, _ = _http_json(f"{base}/health")
        assert code == 401
        code, _ = _http_json(f"{base}/health", headers={"Authorization": "Bearer wrong"})
        assert code == 401
        query = urllib.parse.urlencode({"token": bearer_secret})
        code, _ = _http_json(f"{base}/health?{query}")
        assert code == 403

        hdr = {"Authorization": f"Bearer {bearer_secret}"}
        code, health = _http_json(f"{base}/health", headers=hdr)
        assert code == 200 and health["ok"] is True

        code, res = _http_json(
            f"{base}/run",
            method="POST",
            headers=hdr,
            body={"uri": "android://device/heyasa/command/open-panel", "payload": {"url": "https://heyasa.local/mobile/notes"}},
        )
        assert code == 200 and res["goalVerified"] is True
    finally:
        server.stop()
