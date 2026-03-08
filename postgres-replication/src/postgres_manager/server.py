"""Web UI server for postgres-manager.

Exposes all CLI functionality through a browser interface using FastAPI.
Run via: postgres-manager server
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_PATH,
    DEFAULT_PLAN_PATH,
    InstanceConfig,
    ReplicationConfig,
    load_config,
    resolve_instance,
)
from .schema_evolution import RepairPlan, apply_repair_step, detect_and_plan

# ---------------------------------------------------------------------------
# Test hook: override config path in tests without touching the real home dir
# ---------------------------------------------------------------------------

_config_override: Path | None = None


def _config_path() -> Path:
    return _config_override if _config_override is not None else DEFAULT_CONFIG_PATH


def _plan_path() -> Path:
    if _config_override is not None:
        return _config_override.parent / "replication-plan.json"
    return DEFAULT_PLAN_PATH


def _config_dir() -> Path:
    return _config_path().parent


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class InstanceForm(BaseModel):
    cluster_name: str
    port: int
    admin_user: str
    socket_dir: str = "/var/run/postgresql"


class ReplicationForm(BaseModel):
    publication_name: str
    subscription_name: str
    replication_user: str = "replicator"


class ConnectForm(BaseModel):
    pg_version: int = 16
    publisher: InstanceForm
    subscriber: InstanceForm
    db_name: str = "mydb"
    table_name: str = "demo"
    replication: ReplicationForm | None = None


class Credentials(BaseModel):
    pub_password: str
    sub_password: str = ""


class ApplyRequest(BaseModel):
    pub_password: str
    sub_password: str = ""
    dry_run: bool = True
    step: int | None = None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="postgres-manager", docs_url=None, redoc_url=None)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    """Return current config state (no passwords)."""
    cp = _config_path()
    has_config = cp.exists()
    result: dict[str, Any] = {
        "has_config": has_config,
        "config_path": str(cp),
        "has_plan": _plan_path().exists(),
    }
    if has_config:
        try:
            cfg = load_config(cp)
            result["pg_version"] = cfg.pg_version
            result["instances"] = [
                {
                    "cluster_name": i.cluster_name,
                    "port": i.port,
                    "admin_user": i.admin_user,
                    "socket_dir": i.socket_dir,
                }
                for i in cfg.instances
            ]
            result["database"] = cfg.database.name
            result["table"] = cfg.database.table_name
            result["has_replication"] = cfg.replication is not None
            if cfg.replication:
                rep = cfg.replication
                result["replication"] = {
                    "publisher_instance": rep.publisher_instance,
                    "subscriber_instance": rep.subscriber_instance,
                    "publication_name": rep.publication_name,
                    "subscription_name": rep.subscription_name,
                    "replication_user": rep.replication_user,
                }
        except Exception as exc:
            result["config_error"] = str(exc)
    return result


@app.post("/api/connect")
def api_connect(form: ConnectForm) -> dict[str, Any]:
    """Write a new config file from the setup wizard form."""
    from .cli import _build_toml

    pub = InstanceConfig(
        cluster_name=form.publisher.cluster_name,
        port=form.publisher.port,
        admin_user=form.publisher.admin_user,
        socket_dir=form.publisher.socket_dir,
    )
    sub = InstanceConfig(
        cluster_name=form.subscriber.cluster_name,
        port=form.subscriber.port,
        admin_user=form.subscriber.admin_user,
        socket_dir=form.subscriber.socket_dir,
    )
    rep: ReplicationConfig | None = None
    if form.replication:
        rep = ReplicationConfig(
            publisher_instance=form.publisher.cluster_name,
            subscriber_instance=form.subscriber.cluster_name,
            publication_name=form.replication.publication_name,
            subscription_name=form.replication.subscription_name,
            replication_user=form.replication.replication_user,
        )

    _config_dir().mkdir(parents=True, exist_ok=True)
    content = _build_toml(form.pg_version, pub, sub, form.db_name, form.table_name, rep)
    _config_path().write_text(content)
    return {"success": True, "path": str(_config_path())}


@app.post("/api/monitor")
def api_monitor(creds: Credentials) -> dict[str, Any]:
    """Return live replication statistics from the publisher."""
    from .replication import ReplicationError, get_replication_stats

    try:
        cfg = load_config(_config_path())
        rep = cfg.replication
        if rep is None:
            return {"has_replication": False}

        pub = resolve_instance(cfg, rep.publisher_instance)
        sub = resolve_instance(cfg, rep.subscriber_instance)
        eff_sub_pw = creds.sub_password or creds.pub_password

        connections, slots = get_replication_stats(pub, creds.pub_password)
        return {
            "has_replication": True,
            "publisher": {"cluster_name": pub.cluster_name, "port": pub.port},
            "subscriber": {"cluster_name": sub.cluster_name, "port": sub.port},
            "publication": rep.publication_name,
            "subscription": rep.subscription_name,
            "connections": [dict(c) for c in connections],
            "slots": [
                {
                    "slot_name": str(s["slot_name"]),
                    "active": bool(s["active"]),
                    "lag_bytes": int(str(s["lag_bytes"])),
                    "lag_pretty": str(s["lag_pretty"]),
                }
                for s in slots
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/drift")
def api_drift(creds: Credentials) -> dict[str, Any]:
    """Detect schema drift and generate a repair plan; saves plan to disk."""
    try:
        cfg = load_config(_config_path())
        rep = cfg.replication
        if rep is None:
            raise HTTPException(
                status_code=400,
                detail="No [replication] section in config — run setup first.",
            )

        pub = resolve_instance(cfg, rep.publisher_instance)
        sub = resolve_instance(cfg, rep.subscriber_instance)
        eff_sub_pw = creds.sub_password or creds.pub_password

        report, plan = detect_and_plan(
            pub, creds.pub_password, sub, eff_sub_pw, rep, cfg.database.name
        )

        _config_dir().mkdir(parents=True, exist_ok=True)
        _plan_path().write_text(plan.to_json())

        return {
            "drift": json.loads(report.to_json()),
            "plan": json.loads(plan.to_json()),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/plan")
def api_get_plan() -> dict[str, Any]:
    """Return the saved repair plan (or null if none exists)."""
    pp = _plan_path()
    if not pp.exists():
        return {"plan": None}
    return {"plan": json.loads(pp.read_text())}


@app.put("/api/plan")
def api_save_plan(plan_data: dict[str, Any]) -> dict[str, Any]:
    """Overwrite the saved repair plan (allows edits from the UI)."""
    _config_dir().mkdir(parents=True, exist_ok=True)
    _plan_path().write_text(json.dumps(plan_data, indent=2))
    return {"success": True}


@app.post("/api/apply")
def api_apply(req: ApplyRequest) -> dict[str, Any]:
    """Apply repair steps from the saved plan, capturing stdout as output."""
    pp = _plan_path()
    if not pp.exists():
        raise HTTPException(
            status_code=404, detail="No plan file found — run drift detection first."
        )

    try:
        cfg = load_config(_config_path())
        rep = cfg.replication
        if rep is None:
            raise HTTPException(status_code=400, detail="No replication config")

        pub = resolve_instance(cfg, rep.publisher_instance)
        sub = resolve_instance(cfg, rep.subscriber_instance)
        eff_sub_pw = req.sub_password or req.pub_password

        plan = RepairPlan.from_json(pp.read_text())
        steps = plan.steps
        if req.step is not None:
            steps = [s for s in plan.steps if s.step == req.step]
            if not steps:
                raise HTTPException(
                    status_code=404, detail=f"Step {req.step} not found in plan"
                )

        results: list[dict[str, Any]] = []
        for step in steps:
            buf = io.StringIO()
            with redirect_stdout(buf):
                apply_repair_step(
                    step=step,
                    publisher=pub,
                    pub_password=req.pub_password,
                    subscriber=sub,
                    sub_password=eff_sub_pw,
                    db_name=cfg.database.name,
                    dry_run=req.dry_run,
                )
            results.append(
                {
                    "step": step.step,
                    "description": step.description,
                    "target": step.target,
                    "phase": step.phase,
                    "risk": step.risk,
                    "manual_review": step.manual_review,
                    "output": buf.getvalue(),
                }
            )

        return {"results": results, "dry_run": req.dry_run}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# HTML UI (single-page application)
# ---------------------------------------------------------------------------

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>postgres-manager</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #f4f6f9; }
    .navbar-brand { font-family: monospace; font-size: 1.1rem; letter-spacing: .5px; }
    pre.sql-block { background:#1e1e1e; color:#d4d4d4; padding:.75rem 1rem; border-radius:4px; font-size:.82rem; white-space:pre-wrap; word-break:break-all; }
    .drift-card { border-left: 4px solid #dc3545; }
    .step-card { border-left: 4px solid #6c757d; transition: opacity .2s; }
    .step-card.risk-high { border-left-color: #dc3545; }
    .step-card.risk-medium { border-left-color: #fd7e14; }
    .step-card.risk-low { border-left-color: #198754; }
    .step-card.step-disabled { opacity: .4; }
    .tab-pane-custom { background:#fff; border:1px solid #dee2e6; border-top:none; padding:1.25rem; border-radius: 0 0 .375rem .375rem; }
    .toast-container { position:fixed; bottom:1rem; right:1rem; z-index:9999; }
    #section-loading { position:fixed; inset:0; background:rgba(255,255,255,.8); display:flex; align-items:center; justify-content:center; z-index:9000; }
  </style>
</head>
<body>

<div id="section-loading">
  <div class="text-center">
    <div class="spinner-border text-primary mb-2"></div>
    <div class="text-muted">Loading&hellip;</div>
  </div>
</div>

<nav class="navbar navbar-dark bg-dark shadow-sm">
  <div class="container-fluid px-3">
    <span class="navbar-brand">&#x1F418; postgres-manager</span>
    <div id="nav-status" class="text-white-50 small font-monospace"></div>
  </div>
</nav>

<!-- ======================================================= SETUP WIZARD -->
<div id="section-setup" class="container py-4" style="display:none">
  <div class="row justify-content-center">
    <div class="col-lg-7 col-md-9">
      <div class="card shadow-sm">
        <div class="card-header bg-primary text-white">
          <h5 class="mb-0">Setup &mdash; create your configuration</h5>
        </div>
        <div class="card-body">
          <p class="text-muted mb-3">No configuration found. Fill in the details below to get started.
            <br><small>Config will be saved to <code id="cfg-path-label"></code></small>
          </p>

          <form id="setup-form">
            <div class="mb-3">
              <label class="form-label fw-semibold">PostgreSQL version</label>
              <input type="number" class="form-control" id="pg-version" value="16" min="12" max="20" style="max-width:120px">
            </div>

            <!-- Publisher -->
            <h6 class="border-bottom pb-1 mt-4 text-primary">Publisher instance</h6>
            <div class="form-check form-switch mb-2">
              <input class="form-check-input" type="checkbox" id="pub-use-uri">
              <label class="form-check-label small" for="pub-use-uri">Use connection string (postgresql://&hellip;)</label>
            </div>
            <div id="pub-uri-row" class="mb-2" style="display:none">
              <input type="text" class="form-control" id="pub-uri" placeholder="postgresql://user@host:5432/dbname">
            </div>
            <div id="pub-manual-row">
              <div class="row g-2 mb-2">
                <div class="col-8"><input type="text" class="form-control" id="pub-host" placeholder="Host" value="localhost"></div>
                <div class="col-4"><input type="number" class="form-control" id="pub-port" placeholder="Port" value="5432"></div>
              </div>
              <input type="text" class="form-control mb-2" id="pub-admin-user" placeholder="Admin user" value="postgres">
            </div>
            <div class="row g-2 mb-1">
              <div class="col-6"><input type="text" class="form-control" id="pub-cluster" placeholder="Cluster name" value="main1"></div>
              <div class="col-6"><input type="text" class="form-control" id="pub-socket" placeholder="Socket dir" value="/var/run/postgresql"></div>
            </div>

            <!-- Subscriber -->
            <h6 class="border-bottom pb-1 mt-4 text-secondary">Subscriber instance</h6>
            <div class="form-check form-switch mb-2">
              <input class="form-check-input" type="checkbox" id="sub-use-uri">
              <label class="form-check-label small" for="sub-use-uri">Use connection string (postgresql://&hellip;)</label>
            </div>
            <div id="sub-uri-row" class="mb-2" style="display:none">
              <input type="text" class="form-control" id="sub-uri" placeholder="postgresql://user@host:5433/dbname">
            </div>
            <div id="sub-manual-row">
              <div class="row g-2 mb-2">
                <div class="col-8"><input type="text" class="form-control" id="sub-host" placeholder="Host" value="localhost"></div>
                <div class="col-4"><input type="number" class="form-control" id="sub-port" placeholder="Port" value="5433"></div>
              </div>
              <input type="text" class="form-control mb-2" id="sub-admin-user" placeholder="Admin user" value="postgres">
            </div>
            <div class="row g-2 mb-1">
              <div class="col-6"><input type="text" class="form-control" id="sub-cluster" placeholder="Cluster name" value="main2"></div>
              <div class="col-6"><input type="text" class="form-control" id="sub-socket" placeholder="Socket dir" value="/var/run/postgresql"></div>
            </div>

            <!-- Database -->
            <h6 class="border-bottom pb-1 mt-4">Database</h6>
            <div class="row g-2 mb-3">
              <div class="col-6"><input type="text" class="form-control" id="db-name" placeholder="Database name" value="mydb"></div>
              <div class="col-6"><input type="text" class="form-control" id="table-name" placeholder="Table name" value="demo"></div>
            </div>

            <!-- Replication -->
            <div class="form-check form-switch mb-2">
              <input class="form-check-input" type="checkbox" id="setup-replication" checked>
              <label class="form-check-label fw-semibold" for="setup-replication">Configure logical replication</label>
            </div>
            <div id="replication-fields">
              <div class="row g-2 mb-3">
                <div class="col-4"><input type="text" class="form-control form-control-sm" id="pub-pubname" placeholder="Publication name"></div>
                <div class="col-4"><input type="text" class="form-control form-control-sm" id="sub-subname" placeholder="Subscription name"></div>
                <div class="col-4"><input type="text" class="form-control form-control-sm" id="repl-user" placeholder="Replication user" value="replicator"></div>
              </div>
            </div>

            <div id="setup-error" class="alert alert-danger mb-3" style="display:none"></div>
            <button type="submit" class="btn btn-primary">Save configuration &amp; open dashboard</button>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ======================================================= MAIN DASHBOARD -->
<div id="section-main" class="container-fluid px-3 py-3" style="display:none">

  <!-- Instance bar -->
  <div class="alert alert-dark py-2 d-flex align-items-center gap-3 mb-3" id="instance-bar">
    <span id="bar-pub"></span>
    <span class="text-white-50">&rarr;</span>
    <span id="bar-sub"></span>
    <span class="ms-auto d-flex align-items-center gap-2" id="bar-rep"></span>
    <button class="btn btn-sm btn-outline-light" onclick="showSetup()">Reconfigure</button>
  </div>

  <!-- Tabs -->
  <ul class="nav nav-tabs" id="tabs">
    <li class="nav-item"><button class="nav-link active" onclick="showTab('monitor',this)">Monitor</button></li>
    <li class="nav-item"><button class="nav-link" onclick="showTab('drift',this)">Schema Drift</button></li>
    <li class="nav-item"><button class="nav-link" onclick="showTab('plan',this)">Repair Plan</button></li>
  </ul>

  <!-- ---- Monitor ---- -->
  <div id="tab-monitor" class="tab-pane-custom">
    <div class="row mb-3">
      <div class="col-md-6">
        <div class="card">
          <div class="card-body py-2 px-3">
            <div class="row g-2 align-items-end">
              <div class="col">
                <label class="form-label small mb-1">Publisher password</label>
                <input type="password" class="form-control form-control-sm" id="mon-pub-pw" placeholder="required">
              </div>
              <div class="col">
                <label class="form-label small mb-1">Subscriber password</label>
                <input type="password" class="form-control form-control-sm" id="mon-sub-pw" placeholder="same as publisher if blank">
              </div>
              <div class="col-auto">
                <button class="btn btn-sm btn-primary" onclick="runMonitor()">Check</button>
                <button class="btn btn-sm btn-outline-secondary ms-1" id="refresh-btn" onclick="toggleAutoRefresh()">Auto&#x21bb; 10s</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div id="monitor-results"></div>
  </div>

  <!-- ---- Drift ---- -->
  <div id="tab-drift" class="tab-pane-custom" style="display:none">
    <div class="row mb-3">
      <div class="col-md-6">
        <div class="card">
          <div class="card-body py-2 px-3">
            <div class="row g-2 align-items-end">
              <div class="col">
                <label class="form-label small mb-1">Publisher password</label>
                <input type="password" class="form-control form-control-sm" id="drift-pub-pw" placeholder="required">
              </div>
              <div class="col">
                <label class="form-label small mb-1">Subscriber password</label>
                <input type="password" class="form-control form-control-sm" id="drift-sub-pw" placeholder="same as publisher if blank">
              </div>
              <div class="col-auto">
                <button class="btn btn-sm btn-primary" id="drift-btn" onclick="runDrift()">
                  <span id="drift-spinner" class="spinner-border spinner-border-sm me-1" style="display:none;width:.85rem;height:.85rem"></span>
                  Detect drift
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div id="drift-results"></div>
  </div>

  <!-- ---- Plan ---- -->
  <div id="tab-plan" class="tab-pane-custom" style="display:none">
    <div class="alert alert-info" id="plan-empty">
      No repair plan found. Go to <strong>Schema Drift</strong> and run drift detection to generate one.
    </div>
    <div id="plan-content" style="display:none">
      <div class="d-flex align-items-center gap-2 mb-3 flex-wrap">
        <h6 class="mb-0">Repair steps</h6>
        <span id="step-count" class="badge bg-secondary"></span>
        <div class="ms-auto d-flex gap-2 align-items-center flex-wrap">
          <input type="password" class="form-control form-control-sm" id="apply-pub-pw" placeholder="Publisher password" style="max-width:160px">
          <input type="password" class="form-control form-control-sm" id="apply-sub-pw" placeholder="Subscriber password" style="max-width:160px">
          <button class="btn btn-sm btn-outline-warning" onclick="applyPlan(true)">Dry run</button>
          <button class="btn btn-sm btn-danger" onclick="confirmApply()">Apply all enabled</button>
        </div>
      </div>
      <div id="plan-steps"></div>
      <div id="apply-output" class="mt-3"></div>
    </div>
  </div>

</div><!-- /section-main -->

<!-- Toasts -->
<div class="toast-container" id="toasts"></div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let _appStatus = {};
let _plan = null;          // current plan object (may have step._disabled)
let _autoRefreshTimer = null;
let _autoRefreshing = false;

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  // Wire up URI toggles and form defaults
  wireToggle('pub-use-uri', 'pub-uri-row', 'pub-manual-row');
  wireToggle('sub-use-uri', 'sub-uri-row', 'sub-manual-row');
  document.getElementById('setup-replication').addEventListener('change', e => {
    document.getElementById('replication-fields').style.display = e.target.checked ? '' : 'none';
  });
  document.getElementById('pub-cluster').addEventListener('input', updateRepDefaults);
  document.getElementById('sub-cluster').addEventListener('input', updateRepDefaults);
  document.getElementById('pub-pubname').addEventListener('input', e => { e.target._edited = true; });
  document.getElementById('sub-subname').addEventListener('input', e => { e.target._edited = true; });
  document.getElementById('setup-form').addEventListener('submit', onSetupSubmit);

  await init();
});

function wireToggle(checkId, showId, hideId) {
  document.getElementById(checkId).addEventListener('change', e => {
    document.getElementById(showId).style.display = e.target.checked ? '' : 'none';
    document.getElementById(hideId).style.display = e.target.checked ? 'none' : '';
  });
}

async function init() {
  try {
    const status = await apiFetch('/api/status');
    _appStatus = status;
    hide('section-loading');
    if (!status.has_config) {
      document.getElementById('cfg-path-label').textContent = status.config_path;
      updateRepDefaults();
      show('section-setup');
    } else {
      renderMain(status);
      if (status.has_plan) loadPlan();
    }
  } catch (err) {
    hide('section-loading');
    document.body.innerHTML = `<div class="container mt-5"><div class="alert alert-danger">Failed to connect to API: ${esc(err.message)}</div></div>`;
  }
}

// ---------------------------------------------------------------------------
// Setup wizard
// ---------------------------------------------------------------------------
function updateRepDefaults() {
  const pub = document.getElementById('pub-cluster').value;
  const sub = document.getElementById('sub-cluster').value;
  const pn = document.getElementById('pub-pubname');
  const sn = document.getElementById('sub-subname');
  if (!pn._edited) pn.value = pub ? `${pub}_pub` : '';
  if (!sn._edited) sn.value = sub ? `${sub}_sub` : '';
}

async function onSetupSubmit(e) {
  e.preventDefault();
  const errEl = document.getElementById('setup-error');
  errEl.style.display = 'none';

  const pubUri = document.getElementById('pub-use-uri').checked;
  const subUri = document.getElementById('sub-use-uri').checked;

  const parsedPub = pubUri ? parseUri(document.getElementById('pub-uri').value) : null;
  const parsedSub = subUri ? parseUri(document.getElementById('sub-uri').value) : null;

  const setupRep = document.getElementById('setup-replication').checked;

  const body = {
    pg_version: parseInt(document.getElementById('pg-version').value) || 16,
    publisher: {
      cluster_name: document.getElementById('pub-cluster').value,
      port: parsedPub ? parsedPub.port : (parseInt(document.getElementById('pub-port').value) || 5432),
      admin_user: parsedPub ? parsedPub.user : document.getElementById('pub-admin-user').value,
      socket_dir: document.getElementById('pub-socket').value,
    },
    subscriber: {
      cluster_name: document.getElementById('sub-cluster').value,
      port: parsedSub ? parsedSub.port : (parseInt(document.getElementById('sub-port').value) || 5433),
      admin_user: parsedSub ? parsedSub.user : document.getElementById('sub-admin-user').value,
      socket_dir: document.getElementById('sub-socket').value,
    },
    db_name: document.getElementById('db-name').value,
    table_name: document.getElementById('table-name').value,
    replication: setupRep ? {
      publication_name: document.getElementById('pub-pubname').value || `${document.getElementById('pub-cluster').value}_pub`,
      subscription_name: document.getElementById('sub-subname').value || `${document.getElementById('sub-cluster').value}_sub`,
      replication_user: document.getElementById('repl-user').value || 'replicator',
    } : null,
  };

  try {
    await apiFetch('/api/connect', { method: 'POST', body });
    toast('Configuration saved!', 'success');
    const status = await apiFetch('/api/status');
    _appStatus = status;
    hide('section-setup');
    renderMain(status);
  } catch (err) {
    errEl.textContent = err.message;
    errEl.style.display = '';
  }
}

function parseUri(uriStr) {
  try {
    const url = new URL(uriStr);
    return { host: url.hostname, port: parseInt(url.port) || 5432, user: url.username || 'postgres' };
  } catch { return null; }
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
function renderMain(status) {
  show('section-main');
  hide('section-setup');

  document.getElementById('nav-status').textContent = status.config_path;

  if (status.instances && status.instances.length >= 2) {
    const pub = status.instances[0], sub = status.instances[1];
    document.getElementById('bar-pub').innerHTML =
      `<span class="badge bg-primary me-1">[PUB]</span><span class="text-white font-monospace">${esc(pub.cluster_name)}</span><span class="text-white-50 small ms-1">:${pub.port}</span>`;
    document.getElementById('bar-sub').innerHTML =
      `<span class="badge bg-secondary me-1">[SUB]</span><span class="text-white font-monospace">${esc(sub.cluster_name)}</span><span class="text-white-50 small ms-1">:${sub.port}</span>`;
  }
  if (status.replication) {
    const r = status.replication;
    document.getElementById('bar-rep').innerHTML =
      `<span class="text-white-50 small">&#x1F4CB; ${esc(r.publication_name)} &rarr; ${esc(r.subscription_name)}</span>
       <span class="badge bg-info text-dark ms-1">${esc(status.database || '')}</span>`;
  }
}

function showSetup() {
  hide('section-main');
  document.getElementById('cfg-path-label').textContent = _appStatus.config_path || '';
  updateRepDefaults();
  show('section-setup');
}

function showTab(name, btn) {
  document.querySelectorAll('[id^="tab-"]').forEach(el => el.style.display = 'none');
  document.getElementById(`tab-${name}`).style.display = '';
  document.querySelectorAll('#tabs .nav-link').forEach(el => el.classList.remove('active'));
  if (btn) btn.classList.add('active');
}

// ---------------------------------------------------------------------------
// Monitor
// ---------------------------------------------------------------------------
async function runMonitor() {
  const pubPw = document.getElementById('mon-pub-pw').value;
  const subPw = document.getElementById('mon-sub-pw').value;
  const el = document.getElementById('monitor-results');
  el.innerHTML = '<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm text-primary"></div> <span class="text-muted">Querying&hellip;</span></div>';

  try {
    const d = await apiFetch('/api/monitor', { method: 'POST', body: { pub_password: pubPw, sub_password: subPw } });
    if (!d.has_replication) {
      el.innerHTML = '<div class="alert alert-warning">No replication section in config file.</div>';
      return;
    }
    let html = '';
    // Connections
    html += '<h6 class="text-muted small text-uppercase mb-2">Connected subscribers (pg_stat_replication)</h6>';
    if (!d.connections?.length) {
      html += '<div class="alert alert-warning py-2 mb-3">No active subscriber connections.</div>';
    } else {
      html += '<table class="table table-sm table-hover mb-3"><thead><tr><th>Application</th><th>State</th><th>Sent LSN</th><th>Replay LSN</th><th>Lag</th></tr></thead><tbody>';
      for (const c of d.connections) {
        const state = String(c.state || '');
        const badge = state === 'streaming' ? 'bg-success' : 'bg-warning text-dark';
        html += `<tr><td class="font-monospace">${esc(String(c.application_name||''))}</td><td><span class="badge ${badge}">${esc(state)}</span></td><td class="font-monospace small">${esc(String(c.sent_lsn||''))}</td><td class="font-monospace small">${esc(String(c.replay_lsn||''))}</td><td>${esc(String(c.replay_lag||''))}</td></tr>`;
      }
      html += '</tbody></table>';
    }
    // Slots
    html += '<h6 class="text-muted small text-uppercase mb-2">Replication slots (pg_replication_slots)</h6>';
    if (!d.slots?.length) {
      html += '<div class="alert alert-warning py-2">No replication slots found.</div>';
    } else {
      html += '<table class="table table-sm table-hover"><thead><tr><th>Slot</th><th>Active</th><th>Lag</th></tr></thead><tbody>';
      for (const s of d.slots) {
        const actBadge = s.active ? '<span class="badge bg-success">active</span>' : '<span class="badge bg-danger">inactive</span>';
        const lagBadge = s.lag_bytes > 0 ? `<span class="badge bg-warning text-dark">${esc(s.lag_pretty)}</span>` : '<span class="badge bg-success">0 bytes</span>';
        html += `<tr><td class="font-monospace">${esc(s.slot_name)}</td><td>${actBadge}</td><td>${lagBadge}</td></tr>`;
      }
      html += '</tbody></table>';
    }
    el.innerHTML = html;
  } catch (err) {
    el.innerHTML = `<div class="alert alert-danger">${esc(err.message)}</div>`;
  }
}

function toggleAutoRefresh() {
  const btn = document.getElementById('refresh-btn');
  if (_autoRefreshing) {
    clearInterval(_autoRefreshTimer);
    _autoRefreshTimer = null;
    _autoRefreshing = false;
    btn.classList.remove('btn-success');
    btn.classList.add('btn-outline-secondary');
    btn.textContent = 'Auto↻ 10s';
  } else {
    _autoRefreshing = true;
    btn.classList.remove('btn-outline-secondary');
    btn.classList.add('btn-success');
    btn.textContent = 'Stop auto-refresh';
    runMonitor();
    _autoRefreshTimer = setInterval(runMonitor, 10000);
  }
}

// ---------------------------------------------------------------------------
// Drift
// ---------------------------------------------------------------------------
async function runDrift() {
  const pubPw = document.getElementById('drift-pub-pw').value;
  const subPw = document.getElementById('drift-sub-pw').value;
  const el = document.getElementById('drift-results');
  const spinner = document.getElementById('drift-spinner');
  const btn = document.getElementById('drift-btn');
  spinner.style.display = 'inline-block';
  btn.disabled = true;
  el.innerHTML = '<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm text-primary"></div> <span class="text-muted">Scanning for drift&hellip;</span></div>';

  try {
    const d = await apiFetch('/api/drift', { method: 'POST', body: { pub_password: pubPw, sub_password: subPw } });
    const drift = d.drift, plan = d.plan;
    let html = '';

    if (drift.slot_health) {
      const s = drift.slot_health;
      const cls = s.active ? 'success' : 'danger';
      html += `<div class="alert alert-${cls} py-2 mb-3">Slot <strong class="font-monospace">${esc(s.slot_name)}</strong>: ${s.active ? 'active' : 'INACTIVE'} &mdash; lag ${s.lag_bytes} bytes${s.invalidation_reason ? ` (invalidated: ${esc(s.invalidation_reason)})` : ''}</div>`;
    }

    if (!drift.table_drifts?.length) {
      html += '<div class="alert alert-success"><strong>&#x2713; No drift detected</strong> &mdash; publisher and subscriber are in sync.</div>';
    } else {
      html += `<h6 class="mb-2">${drift.table_drifts.length} table(s) with drift</h6>`;
      for (const t of drift.table_drifts) {
        const rename = t.renamed_from ? `<div class="mt-1 small text-warning-emphasis"><span class="badge bg-warning text-dark me-1">ASSUMPTION</span>possible rename from <code>${esc(t.renamed_from)}</code> (${Math.round((t.rename_confidence||0)*100)}% column match)</div>` : '';
        const colDiffs = t.column_diffs?.length ? `<details class="mt-1"><summary class="small text-muted">${t.column_diffs.length} column diff(s)</summary><ul class="small mb-0 mt-1 ps-3">${t.column_diffs.map(c=>`<li><code>${esc(c.name)}</code>: ${esc(c.issue)}${c.publisher_type?` <span class="text-muted">(pub: ${esc(c.publisher_type)})</span>`:''}${c.subscriber_type?` <span class="text-muted">(sub: ${esc(c.subscriber_type)})</span>`:''}</li>`).join('')}</ul></details>` : '';
        html += `<div class="card mb-2 drift-card"><div class="card-body py-2 px-3"><div class="d-flex align-items-start gap-2"><code class="me-2 mt-1">${esc(t.schema)}.${esc(t.table)}</code><div>${t.issues.map(i=>`<span class="badge me-1 ${issueBadge(i)}">${esc(i.replace(/_/g,' '))}</span>`).join('')}${rename}${colDiffs}</div></div></div></div>`;
      }
    }

    el.innerHTML = html;
    _plan = plan;
    renderPlan(plan);
    toast(`Drift scan done: ${plan.steps.length} repair step(s)`, plan.steps.length > 0 ? 'warning' : 'success');
  } catch (err) {
    el.innerHTML = `<div class="alert alert-danger">${esc(err.message)}</div>`;
    toast('Drift scan failed', 'danger');
  } finally {
    spinner.style.display = 'none';
    btn.disabled = false;
  }
}

function issueBadge(issue) {
  const m = { new_unconfigured:'bg-info', dropped_from_publisher:'bg-danger', missing_on_subscriber:'bg-warning text-dark', schema_changed:'bg-warning text-dark', no_replica_identity:'bg-secondary', possible_rename:'bg-warning text-dark' };
  return m[issue] || 'bg-secondary';
}

// ---------------------------------------------------------------------------
// Plan
// ---------------------------------------------------------------------------
async function loadPlan() {
  try {
    const d = await apiFetch('/api/plan');
    if (d.plan) { _plan = d.plan; renderPlan(d.plan); }
  } catch (e) { /* non-critical */ }
}

function renderPlan(plan) {
  const emptyEl = document.getElementById('plan-empty');
  const contentEl = document.getElementById('plan-content');
  if (!plan?.steps?.length) { show('plan-empty'); hide('plan-content'); return; }

  hide('plan-empty');
  show('plan-content');
  document.getElementById('step-count').textContent = `${plan.steps.length} step(s)`;

  const el = document.getElementById('plan-steps');
  el.innerHTML = plan.steps.map(step => {
    const riskClass = { low:'risk-low', medium:'risk-medium', high:'risk-high' }[step.risk] || '';
    const targetBadge = step.target === 'publisher' ? 'bg-primary' : 'bg-secondary';
    const sqlBlock = step.sql?.length ? `<details class="mt-2"><summary class="small text-muted">SQL (${step.sql.length} statement${step.sql.length>1?'s':''})</summary><pre class="sql-block mt-1">${esc(step.sql.join('\n'))}</pre></details>` : '';
    const manualBadge = step.manual_review ? '<span class="badge bg-danger ms-1">MANUAL REVIEW</span>' : '';
    return `<div class="card mb-2 step-card ${riskClass}" id="step-card-${step.step}">
      <div class="card-body py-2 px-3">
        <div class="d-flex align-items-start gap-2">
          <div class="form-check mt-1 flex-shrink-0">
            <input class="form-check-input" type="checkbox" checked id="step-chk-${step.step}" onchange="toggleStep(${step.step},this.checked)" title="Enable/disable step">
          </div>
          <div class="flex-grow-1">
            <div class="d-flex align-items-center gap-1 mb-1 flex-wrap">
              <span class="badge bg-dark">Step ${step.step}</span>
              <span class="badge bg-dark">Phase ${step.phase}</span>
              <span class="badge ${targetBadge}">[${esc(step.target.toUpperCase())}]</span>
              <span class="badge bg-${step.risk==='high'?'danger':step.risk==='medium'?'warning text-dark':'success'}">${esc(step.risk.toUpperCase())}</span>
              ${manualBadge}
            </div>
            <div class="small mb-0">${esc(step.description)}</div>
            ${sqlBlock}
          </div>
          <button class="btn btn-sm btn-outline-dark flex-shrink-0" title="Apply this step only" onclick="applyStep(${step.step})">&#x25B6;</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

function toggleStep(num, enabled) {
  const step = _plan?.steps?.find(s => s.step === num);
  if (step) step._disabled = !enabled;
  const card = document.getElementById(`step-card-${num}`);
  if (card) card.classList.toggle('step-disabled', !enabled);
}

async function applyPlan(dryRun) {
  if (!_plan) { toast('No plan loaded', 'warning'); return; }
  const pubPw = document.getElementById('apply-pub-pw').value;
  if (!pubPw) { toast('Enter publisher password first', 'warning'); return; }
  const subPw = document.getElementById('apply-sub-pw').value;

  // Persist any enable/disable edits
  try { await apiFetch('/api/plan', { method: 'PUT', body: _plan }); } catch (e) {}

  const outEl = document.getElementById('apply-output');
  outEl.innerHTML = '<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm text-primary"></div><span class="text-muted">Applying&hellip;</span></div>';

  try {
    const d = await apiFetch('/api/apply', { method:'POST', body:{ pub_password:pubPw, sub_password:subPw, dry_run:dryRun } });
    const label = dryRun ? '[DRY RUN] ' : '';
    let html = `<h6>${label}Results (${d.results.length} step(s))</h6>`;
    for (const r of d.results) {
      const targetBadge = r.target === 'publisher' ? 'bg-primary' : 'bg-secondary';
      html += `<div class="card mb-2"><div class="card-body py-2 px-3">
        <div class="d-flex align-items-center gap-2 mb-1">
          <span class="badge bg-dark">Step ${r.step}</span>
          <span class="badge ${targetBadge}">[${esc((r.target||'').toUpperCase())}]</span>
          <span class="small">${esc(r.description)}</span>
        </div>
        ${r.output?.trim() ? `<pre class="sql-block mb-0">${esc(r.output.trim())}</pre>` : ''}
      </div></div>`;
    }
    outEl.innerHTML = html;
    toast(dryRun ? 'Dry run complete' : 'Repair applied successfully', dryRun ? 'info' : 'success');
  } catch (err) {
    outEl.innerHTML = `<div class="alert alert-danger">${esc(err.message)}</div>`;
    toast('Apply failed', 'danger');
  }
}

async function applyStep(num) {
  const pubPw = document.getElementById('apply-pub-pw').value;
  if (!pubPw) { toast('Enter publisher password first', 'warning'); return; }
  const subPw = document.getElementById('apply-sub-pw').value;

  const outEl = document.getElementById('apply-output');
  outEl.innerHTML = '<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm text-primary"></div><span class="text-muted">Applying step&hellip;</span></div>';

  try {
    const d = await apiFetch('/api/apply', { method:'POST', body:{ pub_password:pubPw, sub_password:subPw, dry_run:false, step:num } });
    let html = `<h6>Step ${num} result</h6>`;
    for (const r of d.results) html += `<pre class="sql-block">${esc(r.output.trim())}</pre>`;
    outEl.innerHTML = html;
    toast(`Step ${num} applied`, 'success');
  } catch (err) {
    outEl.innerHTML = `<div class="alert alert-danger">${esc(err.message)}</div>`;
  }
}

function confirmApply() {
  if (confirm('Apply all enabled steps? This will make changes to your databases.')) applyPlan(false);
}

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------
async function apiFetch(url, opts = {}) {
  const res = await fetch(url, {
    method: opts.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function show(id) { document.getElementById(id).style.display = ''; }
function hide(id) { document.getElementById(id).style.display = 'none'; }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function toast(msg, type = 'info') {
  const cls = { success:'bg-success', danger:'bg-danger', warning:'bg-warning text-dark', info:'bg-info text-dark' }[type] || 'bg-info text-dark';
  const el = document.createElement('div');
  el.className = `toast align-items-center ${cls} border-0 show mb-1`;
  el.setAttribute('role','alert');
  el.innerHTML = `<div class="d-flex"><div class="toast-body fw-semibold">${esc(msg)}</div><button type="button" class="btn-close ${type==='danger'?'btn-close-white':''} me-2 m-auto" onclick="this.closest('.toast').remove()"></button></div>`;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), 5000);
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _HTML
