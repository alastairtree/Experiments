"""Unit tests for config loader service."""

from pathlib import Path

import pytest

from app.schemas.config import PanelType
from app.services.config_loader import (
    ConfigLoader,
    ConfigNotFoundError,
    ConfigValidationError,
)


@pytest.fixture
def config_loader() -> ConfigLoader:
    """Create a config loader instance pointing to test configs."""
    # Use the example tenant configs for testing
    # Go up two levels from backend directory to reach paneldash root
    root_dir = Path(__file__).parent.parent.parent.parent
    return ConfigLoader(tenants_config_root=root_dir / "tenants")


class TestConfigLoader:
    """Tests for ConfigLoader service."""

    def test_load_dashboard_config(self, config_loader: ConfigLoader) -> None:
        """Test loading a dashboard configuration."""
        dashboard_config = config_loader.load_dashboard_config("example-tenant")

        assert dashboard_config.dashboard.name == "System Health Dashboard"
        assert dashboard_config.dashboard.refresh_interval == 21600
        assert len(dashboard_config.dashboard.panels) == 4
        assert dashboard_config.dashboard.layout is not None
        assert dashboard_config.dashboard.layout.columns == 12

    def test_load_timeseries_panel_config(self, config_loader: ConfigLoader) -> None:
        """Test loading a timeseries panel configuration."""
        panel_config = config_loader.load_panel_config(
            "example-tenant", "panels/cpu_usage.yaml"
        )

        assert panel_config.type == PanelType.TIMESERIES
        assert panel_config.title == "CPU Usage Over Time"
        assert panel_config.data_source.table == "metrics"
        assert panel_config.data_source.columns["timestamp"] == "recorded_at"
        assert panel_config.data_source.columns["value"] == "cpu_percent"
        assert panel_config.display is not None
        assert panel_config.display.y_axis_label == "CPU %"
        assert panel_config.drill_down is not None
        assert panel_config.drill_down.enabled is True

    def test_load_kpi_panel_config(self, config_loader: ConfigLoader) -> None:
        """Test loading a KPI panel configuration."""
        panel_config = config_loader.load_panel_config(
            "example-tenant", "panels/memory_kpi.yaml"
        )

        assert panel_config.type == PanelType.KPI
        assert panel_config.title == "Current Memory Usage"
        assert panel_config.data_source.table == "metrics"
        assert panel_config.display is not None
        assert panel_config.display.unit == "%"
        assert len(panel_config.display.thresholds) == 3
        assert panel_config.display.thresholds[0].value == 0
        assert panel_config.display.thresholds[0].color == "#10B981"

    def test_load_health_status_panel_config(
        self, config_loader: ConfigLoader
    ) -> None:
        """Test loading a health status panel configuration."""
        panel_config = config_loader.load_panel_config(
            "example-tenant", "panels/health_status.yaml"
        )

        assert panel_config.type == PanelType.HEALTH_STATUS
        assert panel_config.title == "Service Health"
        assert panel_config.data_source.table == "service_health"
        assert panel_config.display.status_mapping[0].label == "Healthy"
        assert panel_config.display.status_mapping[1].label == "Degraded"
        assert panel_config.display.status_mapping[2].label == "Down"

    def test_load_table_panel_config(self, config_loader: ConfigLoader) -> None:
        """Test loading a table panel configuration."""
        panel_config = config_loader.load_panel_config(
            "example-tenant", "panels/error_log.yaml"
        )

        assert panel_config.type == PanelType.TABLE
        assert panel_config.title == "Recent Errors"
        assert panel_config.data_source.table == "error_logs"
        assert len(panel_config.data_source.columns) == 4
        assert panel_config.data_source.columns[0].name == "timestamp"
        assert panel_config.data_source.columns[0].format == "datetime"
        assert panel_config.display is not None
        assert panel_config.display.pagination == 25

    def test_load_dashboard_with_panels(self, config_loader: ConfigLoader) -> None:
        """Test loading a dashboard with all its panel configurations."""
        dashboard_config, panel_configs = config_loader.load_dashboard_with_panels(
            "example-tenant"
        )

        assert dashboard_config.dashboard.name == "System Health Dashboard"
        assert len(panel_configs) == 4

        # Check all panels were loaded
        assert "cpu_usage" in panel_configs
        assert "memory_kpi" in panel_configs
        assert "system_health" in panel_configs
        assert "error_log" in panel_configs

        # Verify panel types
        assert panel_configs["cpu_usage"].type == PanelType.TIMESERIES
        assert panel_configs["memory_kpi"].type == PanelType.KPI
        assert panel_configs["system_health"].type == PanelType.HEALTH_STATUS
        assert panel_configs["error_log"].type == PanelType.TABLE

    def test_config_not_found_error(self, config_loader: ConfigLoader) -> None:
        """Test that ConfigNotFoundError is raised for missing configs."""
        with pytest.raises(ConfigNotFoundError):
            config_loader.load_dashboard_config("nonexistent-tenant")

        with pytest.raises(ConfigNotFoundError):
            config_loader.load_panel_config("example-tenant", "panels/missing.yaml")

    def test_list_dashboards(self, config_loader: ConfigLoader) -> None:
        """Test listing available dashboards for a tenant."""
        dashboards = config_loader.list_dashboards("example-tenant")

        assert "default" in dashboards
        assert len(dashboards) >= 1

    def test_list_dashboards_nonexistent_tenant(
        self, config_loader: ConfigLoader
    ) -> None:
        """Test listing dashboards for nonexistent tenant returns empty list."""
        dashboards = config_loader.list_dashboards("nonexistent-tenant")

        assert dashboards == []
