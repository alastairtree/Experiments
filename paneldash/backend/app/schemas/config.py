"""Pydantic models for dashboard and panel configurations loaded from YAML files."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class PanelType(str, Enum):
    """Supported panel types."""

    TIMESERIES = "timeseries"
    KPI = "kpi"
    HEALTH_STATUS = "health_status"
    TABLE = "table"
    CUSTOM_IMAGE = "custom_image"
    CUSTOM_TEMPLATE = "custom_template"


# === Time Series Panel Config ===


class TimeSeriesDataSource(BaseModel):
    """Data source configuration for time series panels."""

    table: str
    columns: dict[str, str]  # e.g., {"timestamp": "recorded_at", "value": "cpu_percent"}
    query: dict[str, Any] | None = None  # {"where": "...", "order_by": "..."}


class TimeSeriesDisplay(BaseModel):
    """Display configuration for time series panels."""

    y_axis_label: str | None = None
    y_axis_range: tuple[float, float] | None = None
    line_color: str | None = "#3B82F6"
    fill_area: bool = False


class TimeSeriesDrillDown(BaseModel):
    """Drill-down configuration for time series panels."""

    enabled: bool = False
    show_table: bool = False
    disable_aggregation: bool = False


class TimeSeriesPanelConfig(BaseModel):
    """Configuration for time series panels."""

    type: Literal[PanelType.TIMESERIES] = PanelType.TIMESERIES
    title: str
    description: str | None = None
    data_source: TimeSeriesDataSource
    display: TimeSeriesDisplay | None = None
    refresh_interval: int = 300  # seconds
    drill_down: TimeSeriesDrillDown | None = None


# === KPI Panel Config ===


class KPIThreshold(BaseModel):
    """Threshold definition for KPI panels."""

    value: float
    color: str
    label: str


class KPIDataSource(BaseModel):
    """Data source configuration for KPI panels."""

    table: str
    columns: dict[str, str]  # e.g., {"value": "memory_percent"}
    query: str | None = None  # SQL WHERE clause + ORDER BY + LIMIT


class KPIDisplay(BaseModel):
    """Display configuration for KPI panels."""

    unit: str | None = None
    decimals: int = 1
    thresholds: list[KPIThreshold] = []


class KPIPanelConfig(BaseModel):
    """Configuration for KPI panels."""

    type: Literal[PanelType.KPI] = PanelType.KPI
    title: str
    description: str | None = None
    data_source: KPIDataSource
    display: KPIDisplay | None = None
    refresh_interval: int = 60  # seconds


# === Health Status Panel Config ===


class HealthStatusMapping(BaseModel):
    """Status value mapping for health status panels."""

    color: str
    label: str


class HealthStatusDataSource(BaseModel):
    """Data source configuration for health status panels."""

    table: str
    columns: dict[str, str]  # e.g., {"service_name": "name", "status_value": "status"}


class HealthStatusDisplay(BaseModel):
    """Display configuration for health status panels."""

    status_mapping: dict[int, HealthStatusMapping]


class HealthStatusPanelConfig(BaseModel):
    """Configuration for health status panels."""

    type: Literal[PanelType.HEALTH_STATUS] = PanelType.HEALTH_STATUS
    title: str
    description: str | None = None
    data_source: HealthStatusDataSource
    display: HealthStatusDisplay
    refresh_interval: int = 120  # seconds


# === Table Panel Config ===


class TableColumn(BaseModel):
    """Column configuration for table panels."""

    name: str
    display: str
    format: str | None = None  # "datetime", "number", etc.


class TableDataSource(BaseModel):
    """Data source configuration for table panels."""

    table: str
    columns: list[TableColumn]
    query: dict[str, Any] | None = None  # {"where": "...", "order_by": "...", "limit": 50}


class TableDisplay(BaseModel):
    """Display configuration for table panels."""

    sortable: bool = True
    default_sort: str | None = None
    default_sort_order: Literal["asc", "desc"] = "desc"
    pagination: int = 25  # rows per page


class TablePanelConfig(BaseModel):
    """Configuration for table panels."""

    type: Literal[PanelType.TABLE] = PanelType.TABLE
    title: str
    description: str | None = None
    data_source: TableDataSource
    display: TableDisplay | None = None
    refresh_interval: int = 300  # seconds


# === Custom Panel Configs ===


class CustomImagePanelConfig(BaseModel):
    """Configuration for custom image panels."""

    type: Literal[PanelType.CUSTOM_IMAGE] = PanelType.CUSTOM_IMAGE
    title: str
    description: str | None = None
    endpoint: str  # Custom backend endpoint that returns image
    parameters: dict[str, Any] | None = None
    refresh_interval: int = 3600  # seconds


class CustomTemplatePanelConfig(BaseModel):
    """Configuration for custom template panels."""

    type: Literal[PanelType.CUSTOM_TEMPLATE] = PanelType.CUSTOM_TEMPLATE
    title: str
    description: str | None = None
    template: str  # Inline template string
    data_source: dict[str, Any] | None = None
    refresh_interval: int = 300  # seconds


# === Dashboard Config ===


class PanelPosition(BaseModel):
    """Grid position for a panel."""

    row: int = Field(..., ge=1)
    col: int = Field(..., ge=1)
    width: int = Field(..., ge=1, le=12)
    height: int = Field(..., ge=1)


class DashboardPanelReference(BaseModel):
    """Reference to a panel in a dashboard."""

    id: str
    config_file: str  # Path to panel YAML file
    position: PanelPosition
    type: PanelType | None = None  # will be populated for API clients


class DashboardLayout(BaseModel):
    """Layout configuration for dashboard."""

    columns: int = 12  # Grid columns


class DashboardConfig(BaseModel):
    """Dashboard configuration."""

    name: str
    description: str | None = None
    refresh_interval: int = 21600  # seconds (6 hours)
    layout: DashboardLayout | None = None
    panels: list[DashboardPanelReference] = []


class DashboardConfigRoot(BaseModel):
    """Root configuration object from dashboard YAML."""

    dashboard: DashboardConfig


# === Panel Config Union ===

# Union type for all panel configurations
PanelConfig = (
    TimeSeriesPanelConfig
    | KPIPanelConfig
    | HealthStatusPanelConfig
    | TablePanelConfig
    | CustomImagePanelConfig
    | CustomTemplatePanelConfig
)


class PanelConfigRoot(BaseModel):
    """Root configuration object from panel YAML."""

    panel: (
        TimeSeriesPanelConfig
        | KPIPanelConfig
        | HealthStatusPanelConfig
        | TablePanelConfig
        | CustomImagePanelConfig
        | CustomTemplatePanelConfig
    )
