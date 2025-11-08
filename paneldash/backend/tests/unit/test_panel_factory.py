"""Unit tests for panel factory service."""

from pathlib import Path

import pytest

from app.schemas.config import PanelType
from app.services.config_loader import ConfigLoader
from app.services.panel_factory import (
    BasePanel,
    CustomImagePanel,
    CustomTemplatePanel,
    HealthStatusPanel,
    KPIPanel,
    PanelFactory,
    PanelRegistry,
    TablePanel,
    TimeSeriesPanel,
    UnknownPanelTypeError,
    get_panel_factory,
    get_panel_registry,
)


@pytest.fixture
def panel_registry() -> PanelRegistry:
    """Create a fresh panel registry for testing."""
    return PanelRegistry()


@pytest.fixture
def panel_factory(panel_registry: PanelRegistry) -> PanelFactory:
    """Create a panel factory with test registry."""
    return PanelFactory(registry=panel_registry)


@pytest.fixture
def config_loader() -> ConfigLoader:
    """Create a config loader for loading test panel configs."""
    root_dir = Path(__file__).parent.parent.parent.parent
    return ConfigLoader(tenants_config_root=root_dir / "tenants")


class TestPanelRegistry:
    """Tests for PanelRegistry."""

    def test_registry_initializes_with_builtin_types(
        self, panel_registry: PanelRegistry
    ) -> None:
        """Test that registry initializes with all built-in panel types."""
        registered_types = panel_registry.list_registered_types()

        assert PanelType.TIMESERIES in registered_types
        assert PanelType.KPI in registered_types
        assert PanelType.HEALTH_STATUS in registered_types
        assert PanelType.TABLE in registered_types
        assert PanelType.CUSTOM_IMAGE in registered_types
        assert PanelType.CUSTOM_TEMPLATE in registered_types
        assert len(registered_types) == 6

    def test_get_panel_class_returns_correct_class(
        self, panel_registry: PanelRegistry
    ) -> None:
        """Test getting panel classes from registry."""
        assert panel_registry.get_panel_class(PanelType.TIMESERIES) == TimeSeriesPanel
        assert panel_registry.get_panel_class(PanelType.KPI) == KPIPanel
        assert panel_registry.get_panel_class(PanelType.HEALTH_STATUS) == HealthStatusPanel
        assert panel_registry.get_panel_class(PanelType.TABLE) == TablePanel
        assert panel_registry.get_panel_class(PanelType.CUSTOM_IMAGE) == CustomImagePanel
        assert (
            panel_registry.get_panel_class(PanelType.CUSTOM_TEMPLATE)
            == CustomTemplatePanel
        )

    def test_unknown_panel_type_raises_error(
        self, panel_registry: PanelRegistry
    ) -> None:
        """Test that unknown panel types raise UnknownPanelTypeError."""
        # Create a fake panel type that's not registered
        fake_type = "fake_panel_type"  # type: ignore

        with pytest.raises(UnknownPanelTypeError) as exc_info:
            panel_registry.get_panel_class(fake_type)

        assert "Unknown panel type" in str(exc_info.value)

    def test_singleton_registry(self) -> None:
        """Test that get_panel_registry returns same instance."""
        registry1 = get_panel_registry()
        registry2 = get_panel_registry()

        assert registry1 is registry2


class TestPanelFactory:
    """Tests for PanelFactory."""

    def test_create_timeseries_panel(
        self,
        panel_factory: PanelFactory,
        config_loader: ConfigLoader,
    ) -> None:
        """Test creating a timeseries panel from config."""
        config = config_loader.load_panel_config("example-tenant", "panels/cpu_usage.yaml")

        panel = panel_factory.create_panel("test-cpu-usage", config)

        assert isinstance(panel, TimeSeriesPanel)
        assert isinstance(panel, BasePanel)
        assert panel.panel_id == "test-cpu-usage"
        assert panel.title == "CPU Usage Over Time"
        assert panel.panel_type == PanelType.TIMESERIES
        assert panel.config.data_source.table == "metrics"

    def test_create_kpi_panel(
        self,
        panel_factory: PanelFactory,
        config_loader: ConfigLoader,
    ) -> None:
        """Test creating a KPI panel from config."""
        config = config_loader.load_panel_config(
            "example-tenant", "panels/memory_kpi.yaml"
        )

        panel = panel_factory.create_panel("test-memory-kpi", config)

        assert isinstance(panel, KPIPanel)
        assert panel.panel_id == "test-memory-kpi"
        assert panel.title == "Current Memory Usage"
        assert panel.panel_type == PanelType.KPI
        assert panel.config.display is not None
        assert panel.config.display.unit == "%"

    def test_create_health_status_panel(
        self,
        panel_factory: PanelFactory,
        config_loader: ConfigLoader,
    ) -> None:
        """Test creating a health status panel from config."""
        config = config_loader.load_panel_config(
            "example-tenant", "panels/health_status.yaml"
        )

        panel = panel_factory.create_panel("test-health", config)

        assert isinstance(panel, HealthStatusPanel)
        assert panel.panel_id == "test-health"
        assert panel.title == "Service Health"
        assert panel.panel_type == PanelType.HEALTH_STATUS

    def test_create_table_panel(
        self,
        panel_factory: PanelFactory,
        config_loader: ConfigLoader,
    ) -> None:
        """Test creating a table panel from config."""
        config = config_loader.load_panel_config(
            "example-tenant", "panels/error_log.yaml"
        )

        panel = panel_factory.create_panel("test-errors", config)

        assert isinstance(panel, TablePanel)
        assert panel.panel_id == "test-errors"
        assert panel.title == "Recent Errors"
        assert panel.panel_type == PanelType.TABLE
        assert len(panel.config.data_source.columns) == 4

    def test_panel_metadata(
        self,
        panel_factory: PanelFactory,
        config_loader: ConfigLoader,
    ) -> None:
        """Test that panels return correct metadata."""
        config = config_loader.load_panel_config("example-tenant", "panels/cpu_usage.yaml")

        panel = panel_factory.create_panel("test-panel", config)
        metadata = panel.get_metadata()

        assert metadata["panel_id"] == "test-panel"
        assert metadata["type"] == "timeseries"
        assert metadata["title"] == "CPU Usage Over Time"
        assert metadata["description"] == "Server CPU utilization percentage"
        assert metadata["refresh_interval"] == 300

    @pytest.mark.asyncio
    async def test_fetch_data_returns_structure(
        self,
        panel_factory: PanelFactory,
        config_loader: ConfigLoader,
    ) -> None:
        """Test that panel fetch_data returns expected structure."""
        config = config_loader.load_panel_config("example-tenant", "panels/cpu_usage.yaml")

        panel = panel_factory.create_panel("test-panel", config)
        # Note: fetch_data requires db connection, but we're testing structure
        data = await panel.fetch_data(None)  # type: ignore

        assert "type" in data
        assert data["type"] == "timeseries"
        assert "data" in data
        assert "display_config" in data

    def test_factory_singleton(self) -> None:
        """Test that get_panel_factory uses singleton registry."""
        factory = get_panel_factory()

        assert factory.registry is get_panel_registry()
