"""Elastic Observability Demo Platform — FastAPI entry point."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    ACTIVE_SCENARIO, APP_HOST, APP_PORT, CHANNEL_REGISTRY,
    MISSION_ID, MISSION_NAME, NAMESPACE, SERVICES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Suppress noisy httpx request logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("nova7")

# Late imports to avoid circular deps — populated at startup
service_manager = None
chaos_controller = None
dashboard_ws = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start all services and chaos controller on startup; stop on shutdown."""
    global service_manager, chaos_controller, dashboard_ws

    from app.chaos.controller import ChaosController
    from app.dashboard.websocket import DashboardWebSocket
    from app.services import manager

    chaos_controller = ChaosController()
    dashboard_ws = DashboardWebSocket()
    service_manager = manager.ServiceManager(chaos_controller, dashboard_ws)
    service_manager.start_all()
    logger.info("%s online — all services started", MISSION_NAME)

    yield

    service_manager.stop_all()
    logger.info("%s shutdown complete", MISSION_NAME)


app = FastAPI(
    title="Elastic Observability Demo Platform",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Static file mounts ─────────────────────────────────────────────────────
_base = os.path.dirname(__file__)
app.mount(
    "/dashboard/static",
    StaticFiles(directory=os.path.join(_base, "dashboard", "static")),
    name="dashboard-static",
)
app.mount(
    "/chaos/static",
    StaticFiles(directory=os.path.join(_base, "chaos_ui", "static")),
    name="chaos-static",
)
app.mount(
    "/landing/static",
    StaticFiles(directory=os.path.join(_base, "landing", "static")),
    name="landing-static",
)
app.mount(
    "/selector/static",
    StaticFiles(directory=os.path.join(_base, "selector", "static")),
    name="selector-static",
)

# ── Scenario helper ──────────────────────────────────────────────────────────

def _get_scenario():
    from scenarios import get_scenario
    return get_scenario(ACTIVE_SCENARIO)


def _inject_theme(html: str) -> str:
    """Inject active scenario's theme CSS vars and metadata into HTML."""
    scenario = _get_scenario()
    theme = scenario.theme

    # Build CSS that maps theme vars to the variable names used in existing stylesheets
    css_override = f""":root {{
{theme.to_css_vars()}
  --nominal: {theme.status_nominal};
  --advisory: {theme.status_warning};
  --caution: {theme.status_warning};
  --warning: {theme.status_warning};
  --critical: {theme.status_critical};
  --bg-card: {theme.bg_tertiary};
  --border: {theme.bg_tertiary};
  --text-dim: {theme.text_secondary};
}}
body {{ font-family: {theme.font_family}; }}"""

    replacements = {
        "<!--THEME_CSS-->": f"<style>{css_override}</style>",
        "SCENARIO_NAME_PLACEHOLDER": scenario.scenario_name,
        "SCENARIO_ID_PLACEHOLDER": scenario.scenario_id,
        "NAMESPACE_PLACEHOLDER": scenario.namespace,
        "MISSION_ID_PLACEHOLDER": MISSION_ID,
        "DASHBOARD_TITLE_PLACEHOLDER": theme.dashboard_title,
        "CHAOS_TITLE_PLACEHOLDER": theme.chaos_title,
        "LANDING_TITLE_PLACEHOLDER": theme.landing_title,
        "KIBANA_URL_PLACEHOLDER": _kibana_url,
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html


# ── Environment ──────────────────────────────────────────────────────────────
_kibana_url = os.getenv("KIBANA_URL", "https://localhost:5601").rstrip("/")
_demo_url = os.getenv("DEMO_URL", "/").rstrip("/")


# ── Scenario Selector (new front page) ───────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def selector_page():
    """Scenario selector — choose industry vertical and connect."""
    path = os.path.join(_base, "selector", "static", "index.html")
    if os.path.exists(path):
        with open(path) as f:
            return HTMLResponse(content=f.read())
    # Fallback to legacy landing if selector not yet built
    return await landing_page()


# ── Per-Scenario Landing Page ─────────────────────────────────────────────────

@app.get("/home", response_class=HTMLResponse)
async def landing_page():
    """Scenario-specific landing page with themed links."""
    path = os.path.join(_base, "landing", "static", "index.html")
    with open(path) as f:
        html = f.read()
    return HTMLResponse(content=_inject_theme(html))


@app.get("/slides", response_class=HTMLResponse)
async def slides_page():
    path = os.path.join(_base, "landing", "static", "slides.html")
    with open(path) as f:
        html = f.read().replace("DEMO_URL_PLACEHOLDER", _demo_url)
    return HTMLResponse(content=html)


# ── Health ──────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "scenario": ACTIVE_SCENARIO, "namespace": NAMESPACE}


# ── Dashboard ───────────────────────────────────────────────────────────────


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    path = os.path.join(_base, "dashboard", "static", "index.html")
    with open(path) as f:
        html = f.read()
    return HTMLResponse(content=_inject_theme(html))


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await dashboard_ws.connect(websocket)
    try:
        while True:
            # Keep connection alive; client sends pings
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_ws.disconnect(websocket)


# ── Chaos Controller UI ────────────────────────────────────────────────────


@app.get("/chaos", response_class=HTMLResponse)
async def chaos_page():
    path = os.path.join(_base, "chaos_ui", "static", "index.html")
    with open(path) as f:
        html = f.read()
    return HTMLResponse(content=_inject_theme(html))


# ── Scenario API ───────────────────────────────────────────────────────────


@app.get("/api/scenarios")
async def list_scenarios():
    """List all available scenarios."""
    from scenarios import list_scenarios as _list
    return _list()


@app.get("/api/scenario")
async def current_scenario():
    """Return active scenario metadata and theme."""
    scenario = _get_scenario()
    theme = scenario.theme
    return {
        "id": scenario.scenario_id,
        "name": scenario.scenario_name,
        "description": scenario.scenario_description,
        "namespace": scenario.namespace,
        "services": scenario.services,
        "channel_registry": {
            str(k): {
                "name": v["name"],
                "subsystem": v["subsystem"],
                "error_type": v["error_type"],
                "affected_services": v["affected_services"],
                "cascade_services": v["cascade_services"],
                "description": v["description"],
            }
            for k, v in scenario.channel_registry.items()
        },
        "theme": {
            "bg_primary": theme.bg_primary,
            "bg_secondary": theme.bg_secondary,
            "bg_tertiary": theme.bg_tertiary,
            "accent_primary": theme.accent_primary,
            "accent_secondary": theme.accent_secondary,
            "text_primary": theme.text_primary,
            "text_secondary": theme.text_secondary,
            "text_accent": theme.text_accent,
            "status_nominal": theme.status_nominal,
            "status_warning": theme.status_warning,
            "status_critical": theme.status_critical,
            "dashboard_title": theme.dashboard_title,
            "chaos_title": theme.chaos_title,
            "landing_title": theme.landing_title,
            "font_family": theme.font_family,
            "font_mono": theme.font_mono,
            "scanline_effect": theme.scanline_effect,
            "glow_effect": theme.glow_effect,
            "grid_background": theme.grid_background,
            "gradient_accent": theme.gradient_accent,
        },
        "countdown": {
            "enabled": scenario.countdown_config.enabled,
            "start_seconds": scenario.countdown_config.start_seconds,
        },
    }


# ── Chaos API ───────────────────────────────────────────────────────────────


@app.post("/api/chaos/trigger")
async def chaos_trigger(body: dict):
    channel = int(body.get("channel", 0))
    mode = body.get("mode", "calibration")
    se_name = body.get("se_name", "")
    callback_url = body.get("callback_url", "")
    user_email = body.get("user_email", "")
    result = chaos_controller.trigger(channel, mode, se_name, callback_url, user_email)
    if dashboard_ws:
        await dashboard_ws.broadcast_status(chaos_controller, service_manager)
    return result


@app.post("/api/chaos/resolve")
async def chaos_resolve(body: dict):
    channel = int(body.get("channel", 0))
    result = chaos_controller.resolve(channel)
    if dashboard_ws:
        await dashboard_ws.broadcast_status(chaos_controller, service_manager)
    return result


@app.get("/api/chaos/status")
async def chaos_status():
    return chaos_controller.get_status()


@app.get("/api/chaos/status/{channel}")
async def chaos_channel_status(channel: int):
    return chaos_controller.get_channel_status(channel)


# ── Status API ──────────────────────────────────────────────────────────────


@app.get("/api/status")
async def system_status():
    return {
        "scenario": ACTIVE_SCENARIO,
        "mission_id": MISSION_ID,
        "mission_name": MISSION_NAME,
        "namespace": NAMESPACE,
        "services": service_manager.get_all_status() if service_manager else {},
        "generators": service_manager.get_generator_status() if service_manager else {},
        "chaos": chaos_controller.get_status() if chaos_controller else {},
        "countdown": service_manager.get_countdown() if service_manager else {},
    }


# ── Countdown Control ──────────────────────────────────────────────────────


@app.post("/api/countdown/start")
async def countdown_start():
    service_manager.countdown_start()
    return {"status": "started"}


@app.post("/api/countdown/pause")
async def countdown_pause():
    service_manager.countdown_pause()
    return {"status": "paused"}


@app.post("/api/countdown/reset")
async def countdown_reset():
    service_manager.countdown_reset()
    return {"status": "reset"}


@app.post("/api/countdown/speed")
async def countdown_speed(body: dict):
    speed = float(body.get("speed", 1.0))
    service_manager.countdown_set_speed(speed)
    return {"status": "speed_set", "speed": speed}


# ── Remediation endpoint (called by Elastic Workflow) ──────────────────────


@app.post("/api/remediate/{channel}")
async def remediate_channel(channel: int):
    result = chaos_controller.resolve(channel)
    if dashboard_ws:
        await dashboard_ws.broadcast_status(chaos_controller, service_manager)
    return {"action": "remediated", "channel": channel, **result}


# ── User Info (for auto-populating email) ─────────────────────────────────


@app.get("/api/user/info")
async def user_info(request: Request):
    email = request.headers.get("X-Forwarded-User", "")
    return {"email": email}


# ── Email Notification endpoint (called by Elastic Workflow) ──────────────


@app.post("/api/notify/email")
async def notify_email(body: dict):
    from app.notify.email_handler import send_email

    to = body.get("to", "")
    subject = body.get("subject", "")
    message = body.get("body", "")
    result = await send_email(to, subject, message)
    return result


# ── Setup / Deployer API ───────────────────────────────────────────────────


def _update_env(elastic_url: str, kibana_url: str, api_key: str, otlp_endpoint: str):
    """Write/update .env with credentials so they persist across restarts."""
    env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    updates = {
        "ELASTIC_URL": elastic_url,
        "ELASTIC_ENDPOINT": elastic_url,
        "KIBANA_URL": kibana_url,
        "ELASTIC_API_KEY": api_key,
    }
    if otlp_endpoint:
        updates["OTLP_ENDPOINT"] = otlp_endpoint
        updates["OTLP_API_KEY"] = api_key
        updates["OTLP_AUTH_TYPE"] = "ApiKey"

    # Read existing .env, preserving lines we don't update
    existing_lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            existing_lines = f.readlines()

    seen_keys = set()
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                seen_keys.add(key)
                continue
        new_lines.append(line if line.endswith("\n") else line + "\n")

    # Append any keys not already in the file
    for key, value in updates.items():
        if key not in seen_keys:
            new_lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)
    logger.info("Updated .env at %s", env_path)


# In-memory progress tracker for active deployment
_deploy_progress: dict | None = None


@app.post("/api/setup/test-connection")
async def test_connection(body: dict):
    """Test connectivity to an Elastic environment.

    Accepts kibana_url + api_key (minimum).  Derives ES and OTLP URLs
    from the Kibana URL unless explicit overrides are provided.
    """
    from elastic_config.deployer import ScenarioDeployer

    kibana_url = body.get("kibana_url", "")
    api_key = body.get("api_key", "")

    if not kibana_url or not api_key:
        return {"ok": False, "error": "Missing kibana_url or api_key"}

    # Derive ES URL from Kibana URL unless explicitly provided
    elastic_url = body.get("elastic_url") or ""
    if not elastic_url and ".kb." in kibana_url:
        elastic_url = kibana_url.replace(".kb.", ".es.")

    if not elastic_url:
        return {"ok": False, "error": "Cannot derive Elasticsearch URL — provide it in Advanced settings"}

    # Derive OTLP endpoint
    otlp_url = body.get("otlp_url") or ""
    if not otlp_url and ".kb." in kibana_url:
        otlp_url = kibana_url.replace(".kb.", ".ingest.").rstrip("/")
        if not otlp_url.endswith(":443"):
            otlp_url += ":443"

    scenario = _get_scenario()
    deployer = ScenarioDeployer(scenario, elastic_url, kibana_url, api_key)
    result = deployer.check_connection()

    # Also verify OTLP if we have an endpoint
    if result.get("ok") and otlp_url:
        otlp_ok = deployer.verify_otlp(otlp_url)
        result["otlp_endpoint"] = otlp_url if otlp_ok else None
        result["otlp_ok"] = otlp_ok
    else:
        result["otlp_endpoint"] = None
        result["otlp_ok"] = False

    result["elastic_url"] = elastic_url
    return result


@app.post("/api/setup/launch")
async def launch_setup(body: dict):
    """Launch full deployment of the active scenario to Elastic.

    Accepts kibana_url + api_key (minimum).  Derives ES and OTLP URLs.
    Runs in a background thread and updates _deploy_progress.
    After deployment, reconfigures the running OTLPClient and writes .env.
    """
    import threading

    from elastic_config.deployer import ScenarioDeployer

    global _deploy_progress

    kibana_url = body.get("kibana_url", os.getenv("KIBANA_URL", ""))
    api_key = body.get("api_key", os.getenv("ELASTIC_API_KEY", ""))

    # Derive ES URL from Kibana URL unless explicitly provided
    elastic_url = body.get("elastic_url") or ""
    if not elastic_url and ".kb." in kibana_url:
        elastic_url = kibana_url.replace(".kb.", ".es.")
    if not elastic_url:
        elastic_url = os.getenv("ELASTIC_URL", "")

    if not kibana_url or not api_key:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing kibana_url or api_key"},
        )

    # Explicit OTLP override from Advanced settings
    explicit_otlp = body.get("otlp_url") or ""

    scenario = _get_scenario()
    deployer = ScenarioDeployer(scenario, elastic_url, kibana_url, api_key)

    def _progress_cb(progress):
        global _deploy_progress
        _deploy_progress = progress.to_dict()

    def _run():
        result = deployer.deploy_all(callback=_progress_cb)

        # Use explicit OTLP override if provided, otherwise use derived
        otlp_endpoint = explicit_otlp or result.otlp_endpoint

        # Reconfigure the running OTLPClient
        if otlp_endpoint and service_manager:
            service_manager.otlp.reconfigure(otlp_endpoint, api_key)
            logger.info("OTLPClient reconfigured to %s", otlp_endpoint)

        # Write .env so credentials persist across app restarts
        if not result.error:
            _update_env(elastic_url, kibana_url, api_key, otlp_endpoint or "")

    _deploy_progress = {"finished": False, "error": "", "steps": []}
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"status": "started", "scenario": scenario.scenario_id}


@app.get("/api/setup/progress")
async def setup_progress():
    """Return current deployment progress."""
    if _deploy_progress is None:
        return {"finished": True, "error": "", "steps": []}
    return _deploy_progress


@app.get("/api/setup/detect")
async def detect_existing():
    """Check if the active scenario is already deployed to Elastic."""
    from elastic_config.deployer import ScenarioDeployer

    elastic_url = os.getenv("ELASTIC_URL", "")
    kibana_url = os.getenv("KIBANA_URL", "")
    api_key = os.getenv("ELASTIC_API_KEY", "")

    if not elastic_url or not api_key:
        return {"deployed": False, "error": "No Elastic credentials configured"}

    scenario = _get_scenario()
    deployer = ScenarioDeployer(scenario, elastic_url, kibana_url, api_key)
    return deployer.detect_existing()


@app.post("/api/setup/teardown")
async def teardown_setup():
    """Remove active scenario's Elastic config (KB, workflows, alerts, etc)."""
    from elastic_config.deployer import ScenarioDeployer

    elastic_url = os.getenv("ELASTIC_URL", "")
    kibana_url = os.getenv("KIBANA_URL", "")
    api_key = os.getenv("ELASTIC_API_KEY", "")

    if not elastic_url or not api_key:
        return JSONResponse(
            status_code=400,
            content={"error": "No Elastic credentials configured"},
        )

    scenario = _get_scenario()
    deployer = ScenarioDeployer(scenario, elastic_url, kibana_url, api_key)
    return deployer.teardown()


# ── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, reload=False)
