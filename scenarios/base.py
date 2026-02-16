"""Base scenario class and UITheme dataclass — all scenarios implement this interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class UITheme:
    """Visual theme for a scenario's UI pages."""

    # Colors
    bg_primary: str = "#0d1117"         # Main background
    bg_secondary: str = "#161b22"       # Card/panel backgrounds
    bg_tertiary: str = "#21262d"        # Input/accent backgrounds
    accent_primary: str = "#00BFB3"     # Primary accent (buttons, borders)
    accent_secondary: str = "#58a6ff"   # Secondary accent
    text_primary: str = "#e6edf3"       # Main text
    text_secondary: str = "#8b949e"     # Muted text
    text_accent: str = "#00BFB3"        # Highlighted text
    status_nominal: str = "#3fb950"     # Green — healthy
    status_warning: str = "#d29922"     # Amber — degraded
    status_critical: str = "#f85149"    # Red — error
    status_info: str = "#58a6ff"        # Blue — info

    # Typography
    font_family: str = "'Inter', 'Segoe UI', system-ui, sans-serif"
    font_mono: str = "'JetBrains Mono', 'Fira Code', monospace"
    font_size_base: str = "14px"

    # Effects
    scanline_effect: bool = False       # CRT scanline overlay (Space theme)
    glow_effect: bool = False           # Neon glow on accents (Gaming theme)
    grid_background: bool = False       # Subtle grid pattern (Fanatics theme)
    gradient_accent: str = ""           # CSS gradient for accent areas

    # Terminology
    dashboard_title: str = "Operations Dashboard"
    chaos_title: str = "Incident Simulator"
    landing_title: str = "Control Center"
    service_label: str = "Service"      # "Service", "System", "Module"
    channel_label: str = "Channel"      # "Channel", "Scenario", "Incident"

    # CSS custom properties dict (for injection into templates)
    def to_css_vars(self) -> str:
        """Generate CSS custom property declarations."""
        return "\n".join([
            f"  --bg-primary: {self.bg_primary};",
            f"  --bg-secondary: {self.bg_secondary};",
            f"  --bg-tertiary: {self.bg_tertiary};",
            f"  --accent-primary: {self.accent_primary};",
            f"  --accent-secondary: {self.accent_secondary};",
            f"  --text-primary: {self.text_primary};",
            f"  --text-secondary: {self.text_secondary};",
            f"  --text-accent: {self.text_accent};",
            f"  --status-nominal: {self.status_nominal};",
            f"  --status-warning: {self.status_warning};",
            f"  --status-critical: {self.status_critical};",
            f"  --status-info: {self.status_info};",
            f"  --font-family: {self.font_family};",
            f"  --font-mono: {self.font_mono};",
            f"  --font-size-base: {self.font_size_base};",
        ])


@dataclass
class CountdownConfig:
    """Optional countdown timer configuration."""

    enabled: bool = False
    start_seconds: int = 600
    speed: float = 1.0
    phases: dict[str, tuple[int, int]] = field(default_factory=dict)
    # phases maps phase_name -> (min_remaining, max_remaining)
    # e.g. {"PRE-LAUNCH": (300, 9999), "COUNTDOWN": (60, 300), ...}


class BaseScenario(ABC):
    """Abstract base class that all scenarios must implement."""

    # ── Identity ──────────────────────────────────────────────────────

    @property
    @abstractmethod
    def scenario_id(self) -> str:
        """Unique key: 'space', 'fanatics', 'financial', etc."""
        ...

    @property
    @abstractmethod
    def scenario_name(self) -> str:
        """Display name: 'NOVA-7 Space Mission'."""
        ...

    @property
    @abstractmethod
    def scenario_description(self) -> str:
        """Card description for the scenario selector."""
        ...

    @property
    @abstractmethod
    def namespace(self) -> str:
        """ES/telemetry namespace prefix: 'nova7', 'fanatics', etc."""
        ...

    # ── Services & Topology ──────────────────────────────────────────

    @property
    @abstractmethod
    def services(self) -> dict[str, dict[str, Any]]:
        """9 service definitions with cloud/region/subsystem/language."""
        ...

    @property
    @abstractmethod
    def channel_registry(self) -> dict[int, dict[str, Any]]:
        """20 fault channels with error types, messages, stack traces."""
        ...

    @property
    @abstractmethod
    def service_topology(self) -> dict[str, list[tuple[str, str, str]]]:
        """Trace call graph: caller -> [(callee, endpoint, method)]."""
        ...

    @property
    @abstractmethod
    def entry_endpoints(self) -> dict[str, list[tuple[str, str]]]:
        """API endpoints per service: service -> [(path, method)]."""
        ...

    @property
    @abstractmethod
    def db_operations(self) -> dict[str, list[tuple[str, str, str]]]:
        """DB operations: service -> [(op, table, statement)]."""
        ...

    # ── Infrastructure ───────────────────────────────────────────────

    @property
    @abstractmethod
    def hosts(self) -> list[dict[str, Any]]:
        """3 host definitions (one per cloud)."""
        ...

    @property
    @abstractmethod
    def k8s_clusters(self) -> list[dict[str, Any]]:
        """3 K8s cluster definitions."""
        ...

    # ── UI & Theme ───────────────────────────────────────────────────

    @property
    @abstractmethod
    def theme(self) -> UITheme:
        """Visual theme configuration."""
        ...

    @property
    def countdown_config(self) -> CountdownConfig:
        """Optional countdown timer. Override if scenario has one."""
        return CountdownConfig(enabled=False)

    # ── Agent & Elastic Config ───────────────────────────────────────

    @property
    @abstractmethod
    def agent_config(self) -> dict[str, Any]:
        """Agent ID, name, system prompt for Agent Builder."""
        ...

    @property
    @abstractmethod
    def tool_definitions(self) -> list[dict[str, Any]]:
        """Agent Builder tool configurations."""
        ...

    @property
    @abstractmethod
    def knowledge_base_docs(self) -> list[dict[str, Any]]:
        """20 KB documents for agent knowledge base."""
        ...

    # ── Service Classes ──────────────────────────────────────────────

    @abstractmethod
    def get_service_classes(self) -> list[type]:
        """Return list of 9 service implementation classes."""
        ...

    # ── Fault Parameters ─────────────────────────────────────────────

    @abstractmethod
    def get_fault_params(self, channel: int) -> dict[str, Any]:
        """Generate realistic random fault parameters for a channel."""
        ...

    # ── Convenience ──────────────────────────────────────────────────

    @property
    def cloud_groups(self) -> dict[str, list[str]]:
        """Group services by cloud provider."""
        groups: dict[str, list[str]] = {}
        for svc_name, svc_cfg in self.services.items():
            provider = svc_cfg["cloud_provider"]
            groups.setdefault(provider, []).append(svc_name)
        return groups

    @property
    def subsystem_groups(self) -> dict[str, list[str]]:
        """Group services by subsystem."""
        groups: dict[str, list[str]] = {}
        for svc_name, svc_cfg in self.services.items():
            sub = svc_cfg["subsystem"]
            groups.setdefault(sub, []).append(svc_name)
        return groups
