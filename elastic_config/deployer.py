"""Scenario deployer — replaces setup-all.sh and sub-scripts with Python.

Deploys a scenario's Elastic config (workflows, agent, tools, KB, significant
events, dashboard, alerting) to an Elastic Cloud environment.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from scenarios.base import BaseScenario

logger = logging.getLogger("deployer")

# ── Progress reporting ──────────────────────────────────────────────────────

@dataclass
class DeployStep:
    name: str
    status: str = "pending"      # pending | running | ok | failed | skipped
    detail: str = ""
    items_total: int = 0
    items_done: int = 0


@dataclass
class DeployProgress:
    steps: list[DeployStep] = field(default_factory=list)
    finished: bool = False
    error: str = ""
    otlp_endpoint: str = ""

    def to_dict(self) -> dict:
        return {
            "finished": self.finished,
            "error": self.error,
            "otlp_endpoint": self.otlp_endpoint,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "detail": s.detail,
                    "items_total": s.items_total,
                    "items_done": s.items_done,
                }
                for s in self.steps
            ],
        }


ProgressCallback = Callable[[DeployProgress], None]


# ── HTTP helpers ────────────────────────────────────────────────────────────

def _kibana_headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "kbn-xsrf": "true",
        "x-elastic-internal-origin": "kibana",
        "Authorization": f"ApiKey {api_key}",
    }


def _es_headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"ApiKey {api_key}",
    }


# ── Main deployer class ────────────────────────────────────────────────────

class ScenarioDeployer:
    """Deploys a scenario's full Elastic configuration."""

    def __init__(
        self,
        scenario: BaseScenario,
        elastic_url: str,
        kibana_url: str,
        api_key: str,
    ):
        self.scenario = scenario
        self.elastic_url = elastic_url.rstrip("/")
        self.kibana_url = kibana_url.rstrip("/")
        self.api_key = api_key
        self.ns = scenario.namespace
        self.progress = DeployProgress()
        self._workflow_ids: dict[str, str] = {}  # name fragment -> workflow ID

    # ── Public API ─────────────────────────────────────────────────────

    def deploy_all(self, callback: ProgressCallback | None = None) -> DeployProgress:
        """Run the full deployment pipeline.  Returns progress summary."""
        self.progress = DeployProgress(steps=[
            DeployStep("Connectivity check"),
            DeployStep("Derive OTLP endpoint"),
            DeployStep("Deploy workflows", items_total=3),
            DeployStep("Deploy AI agent tools", items_total=7),
            DeployStep("Create AI agent"),
            DeployStep("Index knowledge base", items_total=20),
            DeployStep("Create significant events", items_total=20),
            DeployStep("Create data views"),
            DeployStep("Import executive dashboard"),
            DeployStep("Create alert rules", items_total=20),
        ])
        _notify = callback or (lambda p: None)
        _notify(self.progress)

        try:
            with httpx.Client(timeout=60.0, verify=True) as client:
                self._check_connectivity(client, _notify)
                self._derive_otlp_step(client, _notify)
                self._deploy_workflows(client, _notify)
                self._deploy_tools(client, _notify)
                self._deploy_agent(client, _notify)
                self._deploy_knowledge_base(client, _notify)
                self._deploy_significant_events(client, _notify)
                self._deploy_data_views(client, _notify)
                self._deploy_dashboard(client, _notify)
                self._deploy_alerting(client, _notify)
        except Exception as exc:
            self.progress.error = str(exc)
            logger.exception("Deployment failed")

        self.progress.finished = True
        _notify(self.progress)
        return self.progress

    def check_connection(self) -> dict[str, Any]:
        """Quick connectivity test — returns {ok, cluster_name, error}."""
        try:
            with httpx.Client(timeout=15.0, verify=True) as client:
                resp = client.get(
                    f"{self.elastic_url}/",
                    headers=_es_headers(self.api_key),
                )
                if resp.status_code < 300:
                    data = resp.json()
                    return {"ok": True, "cluster_name": data.get("cluster_name", "unknown")}
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def detect_existing(self) -> dict[str, Any]:
        """Check if this scenario is already deployed."""
        found = {}
        try:
            with httpx.Client(timeout=15.0, verify=True) as client:
                # Check KB index
                resp = client.head(
                    f"{self.elastic_url}/{self.ns}-knowledge-base",
                    headers=_es_headers(self.api_key),
                )
                found["knowledge_base"] = resp.status_code == 200

                # Check dashboard
                resp = client.post(
                    f"{self.kibana_url}/api/saved_objects/_export",
                    headers=_kibana_headers(self.api_key),
                    json={"objects": [{"type": "dashboard", "id": f"{self.ns}-exec-dashboard"}],
                           "includeReferencesDeep": False},
                )
                found["dashboard"] = resp.status_code < 300

                # Check alert rules
                resp = client.get(
                    f"{self.kibana_url}/api/alerting/rules/_find?per_page=1&filter=alert.attributes.tags:{self.ns}",
                    headers=_kibana_headers(self.api_key),
                )
                if resp.status_code < 300:
                    data = resp.json()
                    found["alert_rules"] = data.get("total", 0)
                else:
                    found["alert_rules"] = 0
        except Exception as exc:
            found["error"] = str(exc)

        found["deployed"] = found.get("knowledge_base", False) or found.get("dashboard", False)
        return found

    def teardown(self) -> dict[str, Any]:
        """Remove scenario-specific resources from Elastic."""
        results = {}
        with httpx.Client(timeout=30.0, verify=True) as client:
            # Delete KB index
            resp = client.delete(
                f"{self.elastic_url}/{self.ns}-knowledge-base",
                headers=_es_headers(self.api_key),
            )
            results["knowledge_base"] = resp.status_code < 300

            # Delete audit indices
            for suffix in ["significant-events-audit", "remediation-audit", "escalation-audit"]:
                client.delete(
                    f"{self.elastic_url}/{self.ns}-{suffix}",
                    headers=_es_headers(self.api_key),
                )

            # Delete workflows
            results["workflows_deleted"] = self._cleanup_workflows(client)

            # Delete alert rules
            results["alerts_deleted"] = self._cleanup_alerts(client)

            # Delete agent + tools
            self._cleanup_agent(client)

            # Delete significant events
            self._cleanup_significant_events(client)

        return results

    # ── Step implementations ───────────────────────────────────────────

    def _step(self, idx: int) -> DeployStep:
        return self.progress.steps[idx]

    def _check_connectivity(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(0)
        step.status = "running"
        notify(self.progress)

        # Elasticsearch
        resp = client.get(f"{self.elastic_url}/", headers=_es_headers(self.api_key))
        if resp.status_code >= 300:
            step.status = "failed"
            step.detail = f"Elasticsearch unreachable (HTTP {resp.status_code})"
            raise RuntimeError(step.detail)

        # Kibana
        resp = client.get(f"{self.kibana_url}/api/status", headers=_kibana_headers(self.api_key))
        if resp.status_code >= 300:
            step.detail = f"Kibana may be unavailable (HTTP {resp.status_code}), continuing..."
        else:
            step.detail = "ES + Kibana reachable"

        step.status = "ok"
        notify(self.progress)

    # ── OTLP Endpoint Derivation ──────────────────────────────────────

    def _derive_otlp_step(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(1)
        step.status = "running"
        notify(self.progress)

        endpoint = self._derive_otlp_endpoint(client)
        if endpoint:
            self.progress.otlp_endpoint = endpoint
            step.status = "ok"
            step.detail = f"OTLP: {endpoint}"
        else:
            step.status = "skipped"
            step.detail = "Could not derive OTLP endpoint (non-standard ES URL)"
        notify(self.progress)

    def _derive_otlp_endpoint(self, client: httpx.Client) -> str | None:
        """Derive OTLP ingest endpoint from Elastic URL by swapping .es. for .ingest."""
        if ".es." not in self.elastic_url:
            return None
        endpoint = self.elastic_url.replace(".es.", ".ingest.").rstrip("/")
        if not endpoint.endswith(":443"):
            endpoint += ":443"
        try:
            resp = client.post(
                f"{endpoint}/v1/logs",
                headers={
                    "Authorization": f"ApiKey {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"resourceLogs": []},
                timeout=5,
            )
            if resp.status_code == 200:
                return endpoint
        except Exception:
            pass
        return None

    def verify_otlp(self, otlp_url: str) -> bool:
        """Verify an OTLP endpoint is reachable with our API key."""
        try:
            with httpx.Client(timeout=5, verify=True) as client:
                resp = client.post(
                    f"{otlp_url.rstrip('/')}/v1/logs",
                    headers={
                        "Authorization": f"ApiKey {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"resourceLogs": []},
                )
                return resp.status_code == 200
        except Exception:
            return False

    # ── Workflows ──────────────────────────────────────────────────────

    def _deploy_workflows(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(2)
        step.status = "running"
        notify(self.progress)

        # Clean existing workflows for this namespace
        self._cleanup_workflows(client)

        # Generate templated workflows
        workflow_yamls = self._generate_workflow_yamls()
        step.items_total = len(workflow_yamls)

        for name, yaml_content in workflow_yamls.items():
            body = json.dumps({"yaml": yaml_content})
            resp = client.post(
                f"{self.kibana_url}/api/workflows",
                headers=_kibana_headers(self.api_key),
                content=body,
            )
            if resp.status_code < 300:
                # Extract workflow ID from response
                try:
                    wf_data = resp.json()
                    wf_id = wf_data.get("id", "")
                    if wf_id:
                        self._workflow_ids[name] = wf_id
                except Exception:
                    pass
                step.items_done += 1
                step.detail = f"Deployed: {name}"
            else:
                step.detail = f"Failed: {name} (HTTP {resp.status_code})"
                logger.warning("Workflow %s deploy failed: %s", name, resp.text[:200])
            notify(self.progress)

        step.status = "ok" if step.items_done > 0 else "failed"
        notify(self.progress)

    def _generate_workflow_yamls(self) -> dict[str, str]:
        """Generate 3 workflow YAMLs templated for this scenario."""
        ns = self.ns
        scenario_name = self.scenario.scenario_name
        agent_cfg = self.scenario.agent_config
        agent_id = agent_cfg.get("id", f"{ns}-analyst")

        # Read template YAMLs from elastic-config/workflows/ and substitute
        wf_dir = os.path.join(os.path.dirname(__file__), "..", "elastic-config", "workflows")
        wf_dir = os.path.normpath(wf_dir)

        workflows = {}
        if os.path.isdir(wf_dir):
            for fname in sorted(os.listdir(wf_dir)):
                if not fname.endswith(".yaml"):
                    continue
                with open(os.path.join(wf_dir, fname)) as f:
                    yaml_content = f.read()
                # Template substitutions
                yaml_content = yaml_content.replace("NOVA-7", scenario_name)
                yaml_content = yaml_content.replace("nova7-launch-anomaly-analyst", agent_id)
                yaml_content = yaml_content.replace("nova7-", f"{ns}-")
                yaml_content = re.sub(
                    r'mission_id:\s*"NOVA-7"',
                    f'mission_id: "{scenario_name}"',
                    yaml_content,
                )
                key = fname.replace(".yaml", "")
                workflows[key] = yaml_content
        else:
            # Generate minimal workflows inline
            workflows = self._generate_inline_workflows(scenario_name, ns, agent_id)

        return workflows

    def _generate_inline_workflows(
        self, scenario_name: str, ns: str, agent_id: str,
    ) -> dict[str, str]:
        """Fallback: generate minimal workflow YAMLs if templates not found."""
        notification = f"""version: "1"
name: {scenario_name} Significant Event Notification
description: >
  Notify operations team when a significant event is detected.
  Triggered by alert rules — runs AI root cause analysis.

triggers:
  - type: alert

steps:
  - name: count_errors
    type: elasticsearch.esql.query
    with:
      query: >
        FROM logs,logs.*
        | WHERE @timestamp > NOW() - 15 MINUTES AND severity_text == "ERROR"
        | STATS total_errors = COUNT(*)
      format: json

  - name: run_rca
    type: ai.agent
    agent-id: {agent_id}
    create-conversation: true
    with:
      message: >
        Significant event detected: {{{{ event.rule.name }}}}.
        Error type: {{{{ event.rule.tags[1] }}}}.
        Total errors in last 15 minutes: {{{{ steps.count_errors.output.values[0][0] }}}}.
        Perform a full root cause analysis.

  - name: create_case
    type: kibana.createCaseDefaultSpace
    with:
      title: "{scenario_name} RCA: {{{{ event.rule.name }}}}"
      description: |
        [View Conversation]({{{{ kibanaUrl }}}}/app/agent_builder/conversations/{{{{ steps.run_rca.output.conversation_id }}}})

        {{{{ steps.run_rca.output.message }}}}
      tags:
        - "{ns}"
        - "{{{{ event.rule.tags[1] }}}}"
      severity: "high"
      owner: "observability"
      settings:
        syncAlerts: false
      connector:
        id: "none"
        name: "none"
        type: ".none"
        fields: null

  - name: audit_log
    type: elasticsearch.index
    with:
      index: "{ns}-significant-events-audit"
      document:
        rule_name: "{{{{ event.rule.name }}}}"
        error_type: "{{{{ event.rule.tags[1] }}}}"
        total_errors: "{{{{ steps.count_errors.output.values[0][0] }}}}"
        rca_case_created: true
      refresh: wait_for
"""

        remediation = f"""version: "1"
name: {scenario_name} Remediation Action
description: >
  Execute remediation actions. Extracts callback_url from log
  event_name, resolves the fault channel, and logs the result.

triggers:
  - type: manual

inputs:
  - name: error_type
    type: string
    required: true
  - name: channel
    type: number
    required: true
  - name: action_type
    type: string
    required: true
  - name: target_service
    type: string
    default: ""
  - name: justification
    type: string
    required: true
  - name: dry_run
    type: boolean
    default: true

steps:
  - name: pre_action_snapshot
    type: elasticsearch.esql.query
    with:
      query: >
        FROM logs,logs.* | WHERE KQL("body.text: \\"{{{{ inputs.error_type }}}}\\" AND severity_text: \\"ERROR\\"") | KEEP event_name
      format: json

  - name: extract_callback
    type: data.set
    with:
      var:
        - event_meta: "${{{{ steps.pre_action_snapshot.output.values[1][0] | json_parse }}}}"

  - name: execute_remediation
    type: http
    with:
      url: "{{{{ steps.extract_callback.output.var[0].event_meta.callback_url }}}}/api/chaos/resolve"
      method: POST
      headers:
        Content-Type: application/json
      body:
        action: "{{{{ inputs.action_type }}}}"
        channel: "{{{{ inputs.channel }}}}"
      timeout: 120s

  - name: wait_for_stabilization
    type: wait
    with:
      duration: "30s"

  - name: audit_log
    type: elasticsearch.index
    with:
      index: "{ns}-remediation-audit"
      document:
        channel: "{{{{ inputs.channel }}}}"
        action_type: "{{{{ inputs.action_type }}}}"
        justification: "{{{{ inputs.justification }}}}"
      refresh: wait_for
"""

        escalation = f"""version: "1"
name: {scenario_name} Escalation and Hold Management
description: >
  Manage escalation of critical anomalies and operational hold decisions.

triggers:
  - type: manual

inputs:
  - name: action
    type: string
    required: true
  - name: channel
    type: number
    default: 0
  - name: severity
    type: string
    default: "WARNING"
  - name: justification
    type: string
    required: true
  - name: hold_id
    type: string
    default: ""
  - name: investigation_summary
    type: string
    default: ""

steps:
  - name: route_escalate
    type: if
    condition: "inputs.action : escalate"
    steps:
      - name: escalate_log
        type: console
        with:
          message: >
            ESCALATION - Channel {{{{ inputs.channel }}}}.
            Severity: {{{{ inputs.severity }}}}.
            Justification: {{{{ inputs.justification }}}}.

      - name: escalate_audit
        type: elasticsearch.index
        with:
          index: "{ns}-escalation-audit"
          document:
            action: "escalate"
            channel: "{{{{ inputs.channel }}}}"
            severity: "{{{{ inputs.severity }}}}"
            justification: "{{{{ inputs.justification }}}}"
          refresh: wait_for

  - name: route_hold
    type: if
    condition: "inputs.action : request_hold"
    steps:
      - name: hold_safety_check
        type: ai.agent
        agent-id: {agent_id}
        with:
          message: >
            Hold requested for channel {{{{ inputs.channel }}}}
            (severity: {{{{ inputs.severity }}}}). Reason: {{{{ inputs.justification }}}}.
            Perform a rapid safety assessment.

      - name: hold_audit
        type: elasticsearch.index
        with:
          index: "{ns}-escalation-audit"
          document:
            action: "request_hold"
            channel: "{{{{ inputs.channel }}}}"
            severity: "{{{{ inputs.severity }}}}"
            status: "hold_active"
          refresh: wait_for
"""

        return {
            "significant_event_notification": notification,
            "remediation_action": remediation,
            "escalation_hold": escalation,
        }

    # ── Tools ──────────────────────────────────────────────────────────

    def _deploy_tools(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(3)
        step.status = "running"
        notify(self.progress)

        tools = self._generate_tool_definitions()
        step.items_total = len(tools)

        for tool_def in tools:
            tool_id = tool_def["id"]
            # Delete first, then create
            client.delete(
                f"{self.kibana_url}/api/agent_builder/tools/{tool_id}",
                headers=_kibana_headers(self.api_key),
            )
            resp = client.post(
                f"{self.kibana_url}/api/agent_builder/tools",
                headers=_kibana_headers(self.api_key),
                json=tool_def,
            )
            if resp.status_code < 300:
                step.items_done += 1
                step.detail = f"Created: {tool_id}"
            else:
                step.detail = f"Failed: {tool_id} (HTTP {resp.status_code})"
                logger.warning("Tool %s failed: %s", tool_id, resp.text[:200])
            notify(self.progress)

        step.status = "ok" if step.items_done > 0 else "failed"
        notify(self.progress)

    def _generate_tool_definitions(self) -> list[dict[str, Any]]:
        """Auto-generate agent tools from scenario properties."""
        svc_names = ", ".join(sorted(self.scenario.services.keys()))
        kb_index = f"{self.ns}-knowledge-base"

        tools = [
            {
                "id": "search_error_logs",
                "type": "esql",
                "description": (
                    f"Search telemetry logs for a specific error or exception type. "
                    f"Returns the 50 most recent ERROR-level log entries matching the "
                    f"error type. Services: {svc_names}. "
                    f"The error_type parameter is matched against body.text."
                ),
                "configuration": {
                    "query": (
                        'FROM logs,logs.* '
                        '| WHERE @timestamp > NOW() - 15 MINUTES '
                        'AND body.text LIKE ?error_type AND severity_text == "ERROR" '
                        '| KEEP @timestamp, body.text, service.name, severity_text, event_name '
                        '| SORT @timestamp DESC | LIMIT 50'
                    ),
                    "params": {
                        "error_type": {
                            "description": "Wildcard pattern for the error type, e.g. *FuelPressureException*",
                            "type": "string",
                            "optional": False,
                        }
                    },
                },
            },
            {
                "id": "search_subsystem_health",
                "type": "esql",
                "description": (
                    f"Query health status by aggregating recent telemetry. "
                    f"Returns error/warning counts per service. "
                    f"Services: {svc_names}. "
                    f"Log message field: body.text (never use 'body' alone)."
                ),
                "configuration": {
                    "query": (
                        'FROM logs,logs.* '
                        '| WHERE @timestamp > NOW() - 15 MINUTES '
                        '| STATS error_count = COUNT(*) WHERE severity_text == "ERROR", '
                        'warn_count = COUNT(*) WHERE severity_text == "WARN", '
                        'total = COUNT(*) BY service.name '
                        '| SORT error_count DESC'
                    ),
                    "params": {},
                },
            },
            {
                "id": "search_service_logs",
                "type": "esql",
                "description": (
                    f"Search telemetry logs for a specific service. "
                    f"Returns the 50 most recent ERROR and WARN entries. "
                    f"Available services: {svc_names}."
                ),
                "configuration": {
                    "query": (
                        'FROM logs,logs.* '
                        '| WHERE @timestamp > NOW() - 15 MINUTES '
                        'AND service.name == ?service_name '
                        'AND severity_text IN ("ERROR", "WARN") '
                        '| KEEP @timestamp, body.text, service.name, severity_text '
                        '| SORT @timestamp DESC | LIMIT 50'
                    ),
                    "params": {
                        "service_name": {
                            "description": f"The service to investigate ({svc_names})",
                            "type": "string",
                            "optional": False,
                        }
                    },
                },
            },
            {
                "id": "search_known_anomalies",
                "type": "index_search",
                "description": (
                    f"Search the knowledge base for documented anomalies, failure "
                    f"patterns, and resolution procedures. Contains RCA guides for "
                    f"all 20 fault channels."
                ),
                "configuration": {
                    "pattern": kb_index,
                },
            },
            {
                "id": "trace_anomaly_propagation",
                "type": "esql",
                "description": (
                    "Trace the propagation path of anomalies across services. "
                    "Shows which services have errors and warnings over time to "
                    "identify cascade chains. "
                    "Log message field: body.text (never use 'body' alone)."
                ),
                "configuration": {
                    "query": (
                        'FROM logs,logs.* '
                        '| WHERE @timestamp > NOW() - 15 MINUTES '
                        'AND severity_text IN ("ERROR", "WARN") '
                        '| STATS error_count = COUNT(*) WHERE severity_text == "ERROR", '
                        'warn_count = COUNT(*) WHERE severity_text == "WARN" '
                        'BY service.name | SORT error_count DESC'
                    ),
                    "params": {},
                },
            },
            {
                "id": "launch_safety_assessment",
                "type": "esql",
                "description": (
                    "Comprehensive operational safety assessment. Evaluates all "
                    "services against operational health criteria. Returns data "
                    "for GO/NO-GO evaluation. "
                    "Log message field: body.text (never use 'body' alone)."
                ),
                "configuration": {
                    "query": (
                        'FROM logs,logs.* '
                        '| WHERE @timestamp > NOW() - 15 MINUTES '
                        'AND severity_text IN ("ERROR", "WARN") '
                        '| STATS error_count = COUNT(*) WHERE severity_text == "ERROR", '
                        'warn_count = COUNT(*) WHERE severity_text == "WARN" '
                        'BY service.name | SORT error_count DESC'
                    ),
                    "params": {},
                },
            },
            {
                "id": "browse_recent_errors",
                "type": "esql",
                "description": (
                    "Browse all recent ERROR and WARN log entries across all services. "
                    "Use for general situation awareness when you do not yet know the "
                    "specific error type or service."
                ),
                "configuration": {
                    "query": (
                        'FROM logs,logs.* '
                        '| WHERE @timestamp > NOW() - 15 MINUTES '
                        'AND severity_text IN ("ERROR", "WARN") '
                        '| KEEP @timestamp, body.text, service.name, severity_text '
                        '| SORT @timestamp DESC | LIMIT 50'
                    ),
                    "params": {},
                },
            },
        ]

        # Add workflow tools if we have workflow IDs
        for name_frag, wf_id in self._workflow_ids.items():
            if "remediation" in name_frag:
                tools.append({
                    "id": "remediation_action",
                    "type": "workflow",
                    "description": (
                        "Execute remediation actions for anomalies. Triggers the "
                        "Remediation Action workflow to resolve faults."
                    ),
                    "configuration": {"workflow_id": wf_id},
                })
            elif "escalation" in name_frag:
                tools.append({
                    "id": "escalation_action",
                    "type": "workflow",
                    "description": (
                        "Escalate critical anomalies and manage operational hold decisions."
                    ),
                    "configuration": {"workflow_id": wf_id},
                })

        return tools

    # ── Agent ──────────────────────────────────────────────────────────

    def _deploy_agent(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(4)
        step.status = "running"
        notify(self.progress)

        agent_cfg = self.scenario.agent_config
        agent_id = agent_cfg.get("id", f"{self.ns}-analyst")

        # Build full system prompt from scenario properties
        system_prompt = self._generate_system_prompt(agent_cfg)

        # Collect tool IDs
        tool_ids = [
            "search_error_logs",
            "search_service_logs",
            "browse_recent_errors",
            "search_subsystem_health",
            "search_known_anomalies",
            "trace_anomaly_propagation",
            "launch_safety_assessment",
        ]
        if "remediation_action" in [t["id"] for t in self._generate_tool_definitions()]:
            tool_ids.append("remediation_action")
        if "escalation_action" in [t["id"] for t in self._generate_tool_definitions()]:
            tool_ids.append("escalation_action")
        tool_ids.append("platform.core.cases")

        agent_body = {
            "id": agent_id,
            "name": agent_cfg.get("name", f"{self.scenario.scenario_name} Analyst"),
            "description": agent_cfg.get(
                "description",
                f"AI-powered analyst for {self.scenario.scenario_name}.",
            ),
            "configuration": {
                "instructions": system_prompt,
                "tools": [{"tool_ids": tool_ids}],
            },
        }

        # DELETE + POST for reliable update
        client.delete(
            f"{self.kibana_url}/api/agent_builder/agents/{agent_id}",
            headers=_kibana_headers(self.api_key),
        )
        resp = client.post(
            f"{self.kibana_url}/api/agent_builder/agents",
            headers=_kibana_headers(self.api_key),
            json=agent_body,
        )

        if resp.status_code < 300:
            step.status = "ok"
            step.detail = f"Agent {agent_id} created"
        else:
            step.status = "failed"
            step.detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
        notify(self.progress)

    def _generate_system_prompt(self, agent_cfg: dict[str, Any]) -> str:
        """Build a comprehensive system prompt from scenario properties."""
        scenario = self.scenario
        svc_list = "\n".join(
            f"- {name} ({cfg['cloud_provider'].upper()}, {cfg['subsystem']})"
            for name, cfg in scenario.services.items()
        )
        svc_names = ", ".join(sorted(scenario.services.keys()))

        # Use the scenario's identity text as opening, then add comprehensive guide
        base_prompt = agent_cfg.get("system_prompt", "")

        # Auto-generate a comprehensive prompt
        subsystems = sorted(set(
            cfg["subsystem"] for cfg in scenario.services.values()
        ))

        # Use scenario-provided identity if available, otherwise generic
        identity = base_prompt if base_prompt else (
            f"You are the {scenario.scenario_name} Operations Analyst, "
            f"an expert AI agent embedded in the Elastic observability platform."
        )

        return f"""{identity}

## Mission Context
- **Scenario**: {scenario.scenario_name}
- **Namespace**: {scenario.namespace}
- **Subsystems**: {', '.join(subsystems)}
- **Services**:
{svc_list}
- **Fault Channels**: 20 distinct anomaly channels covering all subsystems
- **Telemetry Source**: OpenTelemetry -> Elasticsearch (logs)

## CRITICAL: Field Names
- Log message field is `body.text` — NEVER use `body` alone (causes "Unknown column [body]")
- NEVER use `message` — this field DOES NOT EXIST. The correct field is `body.text`
- Service name field is `service.name`
- Always query FROM logs,logs.* (includes sub-streams)
- Use LIKE or KQL() for text matching — NEVER use MATCH()

## Tool Selection Guide
1. **Known error type** → `search_error_logs` — parameterized, correct fields
2. **Specific service** → `search_service_logs` — parameterized, correct fields
3. **General awareness** → `browse_recent_errors` or `search_subsystem_health`
4. **Historical patterns** → `search_known_anomalies` — knowledge base lookup
5. **Cascade analysis** → `trace_anomaly_propagation` — cross-service correlation
6. **Operational readiness** → `launch_safety_assessment` — GO/NO-GO evaluation
Do NOT write custom ES|QL queries. Use the parameterized tools.

## Root Cause Analysis Methodology
1. **Identify the Event**: Determine which channel(s) triggered and the error signature
2. **Scope the Blast Radius**: Identify affected and cascade services
3. **Temporal Correlation**: Find first occurrence, correlate with preceding events
4. **Cross-Cloud Tracing**: Trace propagation across AWS, GCP, and Azure
5. **Subsystem Impact**: Evaluate if fault is isolated or propagating
6. **Known Pattern Matching**: Check knowledge base for similar anomalies
7. **Severity Classification**: NOMINAL, ADVISORY, CAUTION, WARNING, or CRITICAL
8. **Remediation**: Use remediation_action tool with appropriate action_type

## Available Services
{svc_names}

## Response Format
1. **Summary** — One-sentence description
2. **Affected Systems** — Impacted services and subsystems
3. **Root Cause** — Underlying cause determination
4. **Evidence** — Specific log entries, timestamps, field values
5. **Cascade Risk** — Propagation assessment
6. **Recommendation** — Prioritized remediation steps
7. **Confidence** — HIGH/MEDIUM/LOW with reasoning"""

    # ── Knowledge Base ─────────────────────────────────────────────────

    def _deploy_knowledge_base(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(5)
        step.status = "running"
        notify(self.progress)

        kb_index = f"{self.ns}-knowledge-base"
        registry = self.scenario.channel_registry

        # Delete and recreate index
        client.delete(
            f"{self.elastic_url}/{kb_index}",
            headers=_es_headers(self.api_key),
        )
        client.put(
            f"{self.elastic_url}/{kb_index}",
            headers=_es_headers(self.api_key),
            json={
                "settings": {"number_of_shards": 1, "number_of_replicas": 1},
                "mappings": {
                    "properties": {
                        "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "content": {"type": "text"},
                        "category": {"type": "keyword"},
                        "tags": {"type": "keyword"},
                        "channel_number": {"type": "integer"},
                        "error_type": {"type": "keyword"},
                        "subsystem": {"type": "keyword"},
                        "affected_services": {"type": "keyword"},
                    }
                },
            },
        )

        # Build bulk body from channel_registry
        bulk_lines = []
        for ch_num, ch_data in sorted(registry.items()):
            doc_id = f"ch{int(ch_num):02d}-{ch_data['error_type'].lower()}"
            content = self._generate_kb_doc(ch_num, ch_data)
            doc = {
                "title": f"Channel {ch_num}: {ch_data['name']}",
                "content": content,
                "category": "anomaly-rca",
                "tags": [self.ns, ch_data["error_type"]],
                "channel_number": int(ch_num),
                "error_type": ch_data["error_type"],
                "subsystem": ch_data.get("subsystem", ""),
                "affected_services": ch_data.get("affected_services", []),
            }
            bulk_lines.append(json.dumps({"index": {"_index": kb_index, "_id": doc_id}}))
            bulk_lines.append(json.dumps(doc))

        if bulk_lines:
            bulk_body = "\n".join(bulk_lines) + "\n"
            resp = client.post(
                f"{self.elastic_url}/_bulk?refresh=true",
                headers={
                    "Content-Type": "application/x-ndjson",
                    "Authorization": f"ApiKey {self.api_key}",
                },
                content=bulk_body.encode(),
            )
            if resp.status_code < 300:
                step.items_done = len(registry)
                step.detail = f"Indexed {len(registry)} KB documents"
            else:
                step.detail = f"Bulk index failed (HTTP {resp.status_code})"
        else:
            step.detail = "No KB documents to index"

        step.status = "ok" if step.items_done > 0 else "failed"
        step.items_total = len(registry)
        notify(self.progress)

    def _generate_kb_doc(self, ch_num: int, ch_data: dict[str, Any]) -> str:
        """Generate a knowledge base document for a fault channel."""
        name = ch_data["name"]
        error_type = ch_data["error_type"]
        subsystem = ch_data.get("subsystem", "unknown")
        affected = ", ".join(ch_data.get("affected_services", []))
        cascade = ", ".join(ch_data.get("cascade_services", []))
        description = ch_data.get("description", "")

        return f"""# Channel {ch_num}: {name}

## Error Signature
- **Error Type**: `{error_type}`
- **Subsystem**: {subsystem}
- **Affected Services**: {affected}
- **Cascade Services**: {cascade}

## Description
{description}

## Investigation Procedure
1. Search for `{error_type}` in recent ERROR logs using `search_error_logs`
2. Check health of affected services: {affected}
3. Trace anomaly propagation to cascade services: {cascade}
4. Check for correlated errors in the same time window

## Root Cause Indicators
- Look for `{error_type}` entries in body.text
- Check if multiple channels in the {subsystem} subsystem are affected
- Verify if errors correlate with infrastructure events

## Remediation
- **Primary**: Resolve the fault channel via remediation_action tool
- **Fallback**: Restart affected services if sensor recalibration fails
- **Escalation**: If cascade detected, escalate to operations lead
"""

    # ── Significant Events ─────────────────────────────────────────────

    def _deploy_significant_events(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(6)
        step.status = "running"
        notify(self.progress)

        # Enable streams
        client.post(
            f"{self.kibana_url}/api/streams/_enable",
            headers=_kibana_headers(self.api_key),
            json={},
        )

        # Clean existing queries
        self._cleanup_significant_events(client)

        # Build bulk operations
        operations = []
        registry = self.scenario.channel_registry
        for ch_num, ch_data in sorted(registry.items()):
            num_str = f"{int(ch_num):02d}"
            error_type = ch_data["error_type"]
            kql_query = f'body.text: "{error_type}" AND severity_text: "ERROR"'
            operations.append({
                "index": {
                    "id": f"{self.ns}-se-ch{num_str}",
                    "title": f"Channel {num_str}: {ch_data['name']}",
                    "kql": {"query": kql_query},
                }
            })

        step.items_total = len(operations)

        if operations:
            resp = client.post(
                f"{self.kibana_url}/api/streams/logs/queries/_bulk",
                headers=_kibana_headers(self.api_key),
                json={"operations": operations},
            )
            if resp.status_code < 300:
                step.items_done = len(operations)
                step.detail = f"Created {len(operations)} stream queries"
            else:
                step.detail = f"Bulk create failed (HTTP {resp.status_code})"

        step.status = "ok" if step.items_done > 0 else "failed"
        notify(self.progress)

    # ── Data Views ─────────────────────────────────────────────────────

    def _deploy_data_views(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(7)
        step.status = "running"
        notify(self.progress)

        views = [
            {
                "data_view": {
                    "id": "logs*",
                    "title": "logs*",
                    "name": f"{self.scenario.scenario_name} Logs",
                    "timeFieldName": "@timestamp",
                },
                "override": True,
            },
            {
                "data_view": {
                    "id": "traces-*",
                    "title": "traces-*",
                    "name": f"{self.scenario.scenario_name} Traces",
                    "timeFieldName": "@timestamp",
                },
                "override": True,
            },
        ]

        created = 0
        for view in views:
            resp = client.post(
                f"{self.kibana_url}/api/data_views/data_view",
                headers=_kibana_headers(self.api_key),
                json=view,
            )
            if resp.status_code < 300:
                created += 1

        step.status = "ok"
        step.detail = f"Created {created} data views"
        notify(self.progress)

    # ── Dashboard ──────────────────────────────────────────────────────

    def _deploy_dashboard(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(8)
        step.status = "running"
        notify(self.progress)

        # Try to find and import the NDJSON file
        ndjson_path = os.path.join(
            os.path.dirname(__file__), "..",
            "elastic-config", "dashboards", "exec-dashboard.ndjson",
        )
        ndjson_path = os.path.normpath(ndjson_path)

        if not os.path.exists(ndjson_path):
            # Try generating it
            gen_script = os.path.join(
                os.path.dirname(__file__), "..",
                "elastic-config", "dashboards", "generate_exec_dashboard.py",
            )
            gen_script = os.path.normpath(gen_script)
            if os.path.exists(gen_script):
                import subprocess
                subprocess.run(
                    ["python3", gen_script],
                    cwd=os.path.dirname(gen_script),
                    capture_output=True,
                )

        if os.path.exists(ndjson_path):
            # Read and template the NDJSON
            with open(ndjson_path, "rb") as f:
                ndjson_content = f.read()

            # Substitute namespace in dashboard ID
            ndjson_str = ndjson_content.decode("utf-8", errors="replace")
            ndjson_str = ndjson_str.replace("nova7-exec-dashboard", f"{self.ns}-exec-dashboard")

            resp = client.post(
                f"{self.kibana_url}/api/saved_objects/_import?overwrite=true",
                headers={
                    "kbn-xsrf": "true",
                    "Authorization": f"ApiKey {self.api_key}",
                },
                files={"file": ("dashboard.ndjson", ndjson_str.encode(), "application/x-ndjson")},
            )
            if resp.status_code < 300:
                try:
                    data = resp.json()
                    count = data.get("successCount", 0)
                    step.detail = f"Imported {count} objects"
                except Exception:
                    step.detail = "Dashboard imported"
                step.status = "ok"
            else:
                step.status = "failed"
                step.detail = f"Import failed (HTTP {resp.status_code})"
        else:
            step.status = "skipped"
            step.detail = "NDJSON file not found"

        notify(self.progress)

    # ── Alerting ───────────────────────────────────────────────────────

    def _deploy_alerting(self, client: httpx.Client, notify: ProgressCallback):
        step = self._step(9)
        step.status = "running"
        notify(self.progress)

        # Find notification workflow ID
        notification_wf_id = ""
        for name_frag, wf_id in self._workflow_ids.items():
            if "notification" in name_frag or "significant" in name_frag:
                notification_wf_id = wf_id
                break

        if not notification_wf_id:
            # Search for it
            resp = client.post(
                f"{self.kibana_url}/api/workflows/search",
                headers=_kibana_headers(self.api_key),
                json={"page": 1, "size": 100},
            )
            if resp.status_code < 300:
                try:
                    data = resp.json()
                    items = data if isinstance(data, list) else data.get("results", data.get("items", []))
                    for item in items:
                        if "Notification" in item.get("name", "") or "Significant" in item.get("name", ""):
                            notification_wf_id = item["id"]
                            break
                except Exception:
                    pass

        if not notification_wf_id:
            step.status = "failed"
            step.detail = "Notification workflow not found"
            notify(self.progress)
            return

        # Clean old rules
        self._cleanup_alerts(client)

        # Create 20 alert rules
        registry = self.scenario.channel_registry
        step.items_total = len(registry)

        for ch_num, ch_data in sorted(registry.items()):
            num_str = f"{int(ch_num):02d}"
            error_type = ch_data["error_type"]
            name = ch_data["name"]
            subsystem = ch_data.get("subsystem", "")

            # Determine severity
            ch_int = int(ch_num)
            if ch_int >= 19:
                severity = "critical"
            elif ch_int <= 6:
                severity = "high"
            else:
                severity = "medium"

            rule_name = f"{self.scenario.scenario_name} CH{num_str}: {name}"

            es_query = json.dumps({
                "query": {
                    "bool": {
                        "filter": [
                            {"range": {"@timestamp": {"gte": "now-1m"}}},
                            {"match_phrase": {"body.text": error_type}},
                            {"term": {"severity_text": "ERROR"}},
                        ]
                    }
                }
            })

            rule = {
                "name": rule_name,
                "rule_type_id": ".es-query",
                "consumer": "alerts",
                "tags": [self.ns, error_type],
                "schedule": {"interval": "1m"},
                "params": {
                    "searchType": "esQuery",
                    "esQuery": es_query,
                    "index": ["logs*"],
                    "timeField": "@timestamp",
                    "threshold": [0],
                    "thresholdComparator": ">",
                    "size": 100,
                    "timeWindowSize": 1,
                    "timeWindowUnit": "m",
                },
                "actions": [{
                    "group": "query matched",
                    "id": "system-connector-.workflows",
                    "frequency": {
                        "summary": False,
                        "notify_when": "onActiveAlert",
                        "throttle": None,
                    },
                    "params": {
                        "subAction": "run",
                        "subActionParams": {
                            "workflowId": notification_wf_id,
                            "inputs": {
                                "channel": ch_int,
                                "error_type": error_type,
                                "subsystem": subsystem,
                                "severity": severity,
                            },
                        },
                    },
                }],
            }

            resp = client.post(
                f"{self.kibana_url}/api/alerting/rule",
                headers=_kibana_headers(self.api_key),
                json=rule,
            )
            if resp.status_code < 300:
                step.items_done += 1
            else:
                logger.warning("Alert rule %s failed: %s", rule_name, resp.text[:200])
            notify(self.progress)

        step.status = "ok" if step.items_done > 0 else "failed"
        step.detail = f"Created {step.items_done}/{step.items_total} alert rules"
        notify(self.progress)

    # ── Cleanup helpers ────────────────────────────────────────────────

    def _cleanup_workflows(self, client: httpx.Client) -> int:
        """Delete workflows matching this scenario's name."""
        deleted = 0
        try:
            resp = client.post(
                f"{self.kibana_url}/api/workflows/search",
                headers=_kibana_headers(self.api_key),
                json={"page": 1, "size": 100},
            )
            if resp.status_code < 300:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("results", data.get("items", []))
                scenario_name = self.scenario.scenario_name
                for item in items:
                    if scenario_name in item.get("name", "") or f"{self.ns}-" in item.get("name", "").lower():
                        wf_id = item.get("id", "")
                        if wf_id:
                            r = client.delete(
                                f"{self.kibana_url}/api/workflows/{wf_id}",
                                headers=_kibana_headers(self.api_key),
                            )
                            if r.status_code < 300:
                                deleted += 1
        except Exception:
            pass
        return deleted

    def _cleanup_alerts(self, client: httpx.Client) -> int:
        """Delete alert rules tagged with this namespace."""
        deleted = 0
        try:
            for page in range(1, 11):
                resp = client.get(
                    f"{self.kibana_url}/api/alerting/rules/_find?per_page=100&page={page}&filter=alert.attributes.tags:{self.ns}",
                    headers=_kibana_headers(self.api_key),
                )
                if resp.status_code >= 300:
                    break
                data = resp.json()
                rules = data.get("data", [])
                if not rules:
                    break
                for rule in rules:
                    rule_id = rule.get("id", "")
                    if rule_id:
                        client.delete(
                            f"{self.kibana_url}/api/alerting/rule/{rule_id}",
                            headers=_kibana_headers(self.api_key),
                        )
                        deleted += 1
        except Exception:
            pass
        return deleted

    def _cleanup_agent(self, client: httpx.Client):
        """Delete agent and custom tools."""
        agent_id = self.scenario.agent_config.get("id", f"{self.ns}-analyst")
        client.delete(
            f"{self.kibana_url}/api/agent_builder/agents/{agent_id}",
            headers=_kibana_headers(self.api_key),
        )
        for tool_id in [
            "search_error_logs", "search_subsystem_health", "search_service_logs",
            "search_known_anomalies", "trace_anomaly_propagation",
            "launch_safety_assessment", "browse_recent_errors",
            "remediation_action", "escalation_action",
        ]:
            client.delete(
                f"{self.kibana_url}/api/agent_builder/tools/{tool_id}",
                headers=_kibana_headers(self.api_key),
            )

    def _cleanup_significant_events(self, client: httpx.Client):
        """Delete stream queries for this namespace."""
        try:
            resp = client.get(
                f"{self.kibana_url}/api/streams/logs/queries",
                headers=_kibana_headers(self.api_key),
            )
            if resp.status_code < 300:
                data = resp.json()
                queries = data if isinstance(data, list) else data.get("queries", [])
                for q in queries:
                    qid = q.get("id", "")
                    if qid.startswith(f"{self.ns}-se-"):
                        client.delete(
                            f"{self.kibana_url}/api/streams/logs/queries/{qid}",
                            headers=_kibana_headers(self.api_key),
                        )
        except Exception:
            pass
