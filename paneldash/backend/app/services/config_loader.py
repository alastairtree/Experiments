"""Service for loading and parsing dashboard and panel YAML configuration files."""

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.schemas.config import DashboardConfigRoot, PanelConfig, PanelConfigRoot

logger = logging.getLogger(__name__)


class ConfigLoaderError(Exception):
    """Base exception for configuration loading errors."""

    pass


class ConfigNotFoundError(ConfigLoaderError):
    """Raised when a configuration file is not found."""

    pass


class ConfigValidationError(ConfigLoaderError):
    """Raised when a configuration file fails validation."""

    pass


class ConfigLoader:
    """Loads and parses dashboard and panel YAML configurations."""

    def __init__(self, tenants_config_root: Path | str = Path("tenants")):
        """Initialize the config loader.

        Args:
            tenants_config_root: Root directory containing tenant configuration folders
        """
        self.tenants_config_root = Path(tenants_config_root)
        if not self.tenants_config_root.exists():
            logger.warning(
                f"Tenants config root does not exist: {self.tenants_config_root}"
            )

    def get_tenant_config_path(self, tenant_id: str) -> Path:
        """Get the configuration directory path for a tenant.

        Args:
            tenant_id: The tenant identifier

        Returns:
            Path to the tenant's configuration directory
        """
        return self.tenants_config_root / tenant_id

    def load_dashboard_config(
        self, tenant_id: str, dashboard_name: str = "default"
    ) -> DashboardConfigRoot:
        """Load and parse a dashboard configuration file.

        Args:
            tenant_id: The tenant identifier
            dashboard_name: Name of the dashboard (default: "default")

        Returns:
            Parsed dashboard configuration

        Raises:
            ConfigNotFoundError: If the dashboard config file doesn't exist
            ConfigValidationError: If the config file is invalid
        """
        tenant_path = self.get_tenant_config_path(tenant_id)
        dashboard_file = tenant_path / "dashboards" / f"{dashboard_name}.yaml"

        if not dashboard_file.exists():
            raise ConfigNotFoundError(
                f"Dashboard config not found: {dashboard_file}"
            )

        try:
            with open(dashboard_file, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            config = DashboardConfigRoot.model_validate(raw_config)
            logger.info(
                f"Loaded dashboard config: {tenant_id}/{dashboard_name} "
                f"with {len(config.dashboard.panels)} panels"
            )
            return config

        except yaml.YAMLError as e:
            raise ConfigValidationError(
                f"Invalid YAML in {dashboard_file}: {e}"
            ) from e
        except ValidationError as e:
            raise ConfigValidationError(
                f"Invalid dashboard config in {dashboard_file}: {e}"
            ) from e

    def load_panel_config(self, tenant_id: str, panel_file_path: str) -> PanelConfig:
        """Load and parse a panel configuration file.

        Args:
            tenant_id: The tenant identifier
            panel_file_path: Relative path to panel config (e.g., "panels/cpu_usage.yaml")

        Returns:
            Parsed panel configuration

        Raises:
            ConfigNotFoundError: If the panel config file doesn't exist
            ConfigValidationError: If the config file is invalid
        """
        tenant_path = self.get_tenant_config_path(tenant_id)
        panel_file = tenant_path / panel_file_path

        if not panel_file.exists():
            raise ConfigNotFoundError(f"Panel config not found: {panel_file}")

        try:
            with open(panel_file, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            panel_root = PanelConfigRoot.model_validate(raw_config)
            logger.info(
                f"Loaded panel config: {tenant_id}/{panel_file_path} "
                f"type={panel_root.panel.type}"
            )
            return panel_root.panel

        except yaml.YAMLError as e:
            raise ConfigValidationError(
                f"Invalid YAML in {panel_file}: {e}"
            ) from e
        except ValidationError as e:
            raise ConfigValidationError(
                f"Invalid panel config in {panel_file}: {e}"
            ) from e

    def load_dashboard_with_panels(
        self, tenant_id: str, dashboard_name: str = "default"
    ) -> tuple[DashboardConfigRoot, dict[str, PanelConfig]]:
        """Load a dashboard and all its referenced panel configurations.

        Args:
            tenant_id: The tenant identifier
            dashboard_name: Name of the dashboard (default: "default")

        Returns:
            Tuple of (dashboard_config, panel_configs_dict)
            where panel_configs_dict maps panel_id -> panel_config

        Raises:
            ConfigNotFoundError: If any config file doesn't exist
            ConfigValidationError: If any config file is invalid
        """
        dashboard_config = self.load_dashboard_config(tenant_id, dashboard_name)

        panel_configs: dict[str, PanelConfig] = {}
        for panel_ref in dashboard_config.dashboard.panels:
            panel_config = self.load_panel_config(tenant_id, panel_ref.config_file)
            panel_configs[panel_ref.id] = panel_config

        logger.info(
            f"Loaded dashboard with {len(panel_configs)} panels "
            f"for tenant {tenant_id}"
        )
        return dashboard_config, panel_configs

    def list_dashboards(self, tenant_id: str) -> list[str]:
        """List available dashboard names for a tenant.

        Args:
            tenant_id: The tenant identifier

        Returns:
            List of dashboard names (without .yaml extension)
        """
        tenant_path = self.get_tenant_config_path(tenant_id)
        dashboards_dir = tenant_path / "dashboards"

        if not dashboards_dir.exists():
            return []

        dashboards = []
        for file in dashboards_dir.glob("*.yaml"):
            dashboards.append(file.stem)

        return sorted(dashboards)

    def clear_cache(self) -> None:
        """Clear the configuration cache (useful in dev mode)."""
        # Currently no caching implemented, but this method is here for future use
        logger.info("Config cache cleared")


# Singleton instance with caching for production use
@lru_cache(maxsize=1)
def get_config_loader() -> ConfigLoader:
    """Get the singleton ConfigLoader instance.

    Returns:
        ConfigLoader instance
    """
    # Path to tenants config directory (relative to project root)
    # __file__ is at: backend/app/services/config_loader.py
    # So we need to go up 4 levels to get to project root, then down to tenants/
    tenants_path = Path(__file__).parent.parent.parent.parent / "tenants"
    return ConfigLoader(tenants_path)
