"""Panel factory and registry for creating panel instances from configurations."""

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.schemas.config import (
    CustomImagePanelConfig,
    CustomTemplatePanelConfig,
    HealthStatusPanelConfig,
    KPIPanelConfig,
    PanelConfig,
    PanelType,
    TablePanelConfig,
    TimeSeriesPanelConfig,
)

logger = logging.getLogger(__name__)


class PanelFactoryError(Exception):
    """Base exception for panel factory errors."""

    pass


class UnknownPanelTypeError(PanelFactoryError):
    """Raised when attempting to create a panel of unknown type."""

    pass


class BasePanel(ABC):
    """Base class for all panel types."""

    panel_type: ClassVar[PanelType]

    def __init__(self, panel_id: str, config: PanelConfig):
        """Initialize the panel.

        Args:
            panel_id: Unique identifier for this panel instance
            config: Panel configuration from YAML
        """
        self.panel_id = panel_id
        self.config = config
        self.title = config.title
        self.description = config.description
        self.refresh_interval = config.refresh_interval

    @abstractmethod
    async def fetch_data(
        self,
        tenant_db_connection: Any,
        date_from: str | None = None,
        date_to: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch data for this panel.

        Args:
            tenant_db_connection: Database connection for tenant data
            date_from: Optional start date for filtering
            date_to: Optional end date for filtering
            **kwargs: Additional parameters (e.g., for drill-down)

        Returns:
            Dictionary containing panel data ready for frontend rendering
        """
        pass

    def get_metadata(self) -> dict[str, Any]:
        """Get panel metadata for frontend.

        Returns:
            Dictionary with panel type, title, refresh interval, etc.
        """
        return {
            "panel_id": self.panel_id,
            "type": self.panel_type.value,
            "title": self.title,
            "description": self.description,
            "refresh_interval": self.refresh_interval,
        }


class TimeSeriesPanel(BasePanel):
    """Panel for displaying time series data (line charts)."""

    panel_type = PanelType.TIMESERIES

    def __init__(self, panel_id: str, config: TimeSeriesPanelConfig):
        super().__init__(panel_id, config)
        self.config: TimeSeriesPanelConfig = config

    async def fetch_data(
        self,
        tenant_db_connection: Any,
        date_from: str | None = None,
        date_to: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch time series data for this panel."""
        # TODO: Implement query builder and data aggregation
        logger.info(
            f"Fetching time series data for panel {self.panel_id} "
            f"(table: {self.config.data_source.table})"
        )
        return {
            "type": "timeseries",
            "data": [],  # Will be populated by query builder
            "display_config": (
                self.config.display.model_dump() if self.config.display else {}
            ),
        }


class KPIPanel(BasePanel):
    """Panel for displaying single KPI metrics."""

    panel_type = PanelType.KPI

    def __init__(self, panel_id: str, config: KPIPanelConfig):
        super().__init__(panel_id, config)
        self.config: KPIPanelConfig = config

    async def fetch_data(
        self,
        tenant_db_connection: Any,
        date_from: str | None = None,
        date_to: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch KPI data for this panel."""
        logger.info(
            f"Fetching KPI data for panel {self.panel_id} "
            f"(table: {self.config.data_source.table})"
        )
        return {
            "type": "kpi",
            "value": None,  # Will be populated by query builder
            "display_config": (
                self.config.display.model_dump() if self.config.display else {}
            ),
        }


class HealthStatusPanel(BasePanel):
    """Panel for displaying health status indicators."""

    panel_type = PanelType.HEALTH_STATUS

    def __init__(self, panel_id: str, config: HealthStatusPanelConfig):
        super().__init__(panel_id, config)
        self.config: HealthStatusPanelConfig = config

    async def fetch_data(
        self,
        tenant_db_connection: Any,
        date_from: str | None = None,
        date_to: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch health status data for this panel."""
        logger.info(
            f"Fetching health status data for panel {self.panel_id} "
            f"(table: {self.config.data_source.table})"
        )
        return {
            "type": "health_status",
            "services": [],  # Will be populated by query builder
            "display_config": self.config.display.model_dump(),
        }


class TablePanel(BasePanel):
    """Panel for displaying tabular data."""

    panel_type = PanelType.TABLE

    def __init__(self, panel_id: str, config: TablePanelConfig):
        super().__init__(panel_id, config)
        self.config: TablePanelConfig = config

    async def fetch_data(
        self,
        tenant_db_connection: Any,
        date_from: str | None = None,
        date_to: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch table data for this panel."""
        logger.info(
            f"Fetching table data for panel {self.panel_id} "
            f"(table: {self.config.data_source.table})"
        )
        return {
            "type": "table",
            "columns": [col.model_dump() for col in self.config.data_source.columns],
            "rows": [],  # Will be populated by query builder
            "display_config": (
                self.config.display.model_dump() if self.config.display else {}
            ),
        }


class CustomImagePanel(BasePanel):
    """Panel for displaying custom server-rendered images."""

    panel_type = PanelType.CUSTOM_IMAGE

    def __init__(self, panel_id: str, config: CustomImagePanelConfig):
        super().__init__(panel_id, config)
        self.config: CustomImagePanelConfig = config

    async def fetch_data(
        self,
        tenant_db_connection: Any,
        date_from: str | None = None,
        date_to: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch custom image panel data."""
        logger.info(f"Fetching custom image for panel {self.panel_id}")
        return {
            "type": "custom_image",
            "endpoint": self.config.endpoint,
            "parameters": self.config.parameters or {},
        }


class CustomTemplatePanel(BasePanel):
    """Panel for displaying custom template-rendered content."""

    panel_type = PanelType.CUSTOM_TEMPLATE

    def __init__(self, panel_id: str, config: CustomTemplatePanelConfig):
        super().__init__(panel_id, config)
        self.config: CustomTemplatePanelConfig = config

    async def fetch_data(
        self,
        tenant_db_connection: Any,
        date_from: str | None = None,
        date_to: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch custom template panel data."""
        logger.info(f"Fetching custom template data for panel {self.panel_id}")
        return {
            "type": "custom_template",
            "template": self.config.template,
            "data": {},  # Will be populated by custom logic
        }


class PanelRegistry:
    """Registry for panel types and their corresponding classes."""

    def __init__(self) -> None:
        """Initialize the panel registry."""
        self._registry: dict[PanelType, type[BasePanel]] = {}
        self._register_builtin_panels()

    def _register_builtin_panels(self) -> None:
        """Register all built-in panel types."""
        self.register(PanelType.TIMESERIES, TimeSeriesPanel)
        self.register(PanelType.KPI, KPIPanel)
        self.register(PanelType.HEALTH_STATUS, HealthStatusPanel)
        self.register(PanelType.TABLE, TablePanel)
        self.register(PanelType.CUSTOM_IMAGE, CustomImagePanel)
        self.register(PanelType.CUSTOM_TEMPLATE, CustomTemplatePanel)

        logger.info(f"Registered {len(self._registry)} built-in panel types")

    def register(self, panel_type: PanelType, panel_class: type[BasePanel]) -> None:
        """Register a panel type with its corresponding class.

        Args:
            panel_type: The panel type to register
            panel_class: The panel class to associate with this type
        """
        self._registry[panel_type] = panel_class
        logger.debug(f"Registered panel type: {panel_type.value} -> {panel_class.__name__}")

    def get_panel_class(self, panel_type: PanelType) -> type[BasePanel]:
        """Get the panel class for a given type.

        Args:
            panel_type: The panel type to look up

        Returns:
            The panel class for this type

        Raises:
            UnknownPanelTypeError: If the panel type is not registered
        """
        if panel_type not in self._registry:
            raise UnknownPanelTypeError(
                f"Unknown panel type: {panel_type}. "
                f"Registered types: {list(self._registry.keys())}"
            )
        return self._registry[panel_type]

    def list_registered_types(self) -> list[PanelType]:
        """List all registered panel types.

        Returns:
            List of registered panel types
        """
        return list(self._registry.keys())


# Singleton registry instance
_panel_registry: PanelRegistry | None = None


def get_panel_registry() -> PanelRegistry:
    """Get the singleton panel registry instance.

    Returns:
        The global panel registry
    """
    global _panel_registry
    if _panel_registry is None:
        _panel_registry = PanelRegistry()
    return _panel_registry


class PanelFactory:
    """Factory for creating panel instances from configurations."""

    def __init__(self, registry: PanelRegistry | None = None):
        """Initialize the panel factory.

        Args:
            registry: Panel registry to use (defaults to singleton)
        """
        self.registry = registry or get_panel_registry()

    def create_panel(self, panel_id: str, config: PanelConfig) -> BasePanel:
        """Create a panel instance from configuration.

        Args:
            panel_id: Unique identifier for the panel
            config: Panel configuration from YAML

        Returns:
            Panel instance of the appropriate type

        Raises:
            UnknownPanelTypeError: If the panel type is not registered
        """
        panel_type = config.type
        panel_class = self.registry.get_panel_class(panel_type)

        logger.info(
            f"Creating panel: {panel_id} (type: {panel_type.value}, "
            f"title: {config.title})"
        )

        # Type-safe panel creation with proper type hints
        if isinstance(config, TimeSeriesPanelConfig):
            return panel_class(panel_id, config)
        elif isinstance(config, KPIPanelConfig):
            return panel_class(panel_id, config)
        elif isinstance(config, HealthStatusPanelConfig):
            return panel_class(panel_id, config)
        elif isinstance(config, TablePanelConfig):
            return panel_class(panel_id, config)
        elif isinstance(config, CustomImagePanelConfig):
            return panel_class(panel_id, config)
        elif isinstance(config, CustomTemplatePanelConfig):
            return panel_class(panel_id, config)
        else:
            # This should never happen due to Pydantic validation
            raise UnknownPanelTypeError(f"Unhandled panel config type: {type(config)}")


def get_panel_factory() -> PanelFactory:
    """Get a panel factory instance.

    Returns:
        PanelFactory instance
    """
    return PanelFactory()
