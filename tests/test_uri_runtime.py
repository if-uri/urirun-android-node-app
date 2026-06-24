from main import ROUTES, UriRuntime


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
