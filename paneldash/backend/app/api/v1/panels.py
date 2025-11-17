"""API endpoints for panel data retrieval."""

import asyncio
import logging
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.database import db_manager, get_central_db
from app.models.central import Tenant, UserTenant
from app.schemas.config import (
    HealthStatusPanelConfig,
    KPIPanelConfig,
    PanelConfig,
    PanelType,
    TablePanelConfig,
    TimeSeriesPanelConfig,
)
from app.services.config_loader import (
    ConfigLoader,
    ConfigNotFoundError,
    get_config_loader,
)
from app.services.data_aggregator import DataAggregator, get_data_aggregator
from app.services.query_builder import QueryBuilder, get_query_builder

logger = logging.getLogger(__name__)

router = APIRouter()


class PanelDataResponse(BaseModel):
    """Generic panel data response."""

    panel_id: str
    panel_type: PanelType
    data: dict[str, Any]
    aggregation_info: dict[str, Any] | None = None


@router.get("/{panel_id}/data", response_model=PanelDataResponse)
async def get_panel_data(
    panel_id: str,
    tenant_id: str = Query(...),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    disable_aggregation: bool = False,
    sort_column: str | None = None,
    sort_order: str = "desc",
    page: int = Query(default=1, ge=1),
    *,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_central_db)],
    config_loader: ConfigLoader = Depends(get_config_loader),
    query_builder: QueryBuilder = Depends(get_query_builder),
    aggregator: DataAggregator = Depends(get_data_aggregator),
) -> PanelDataResponse:
    """Get data for a specific panel.

    This endpoint handles all panel types:
    - Time Series: Returns time-based data with optional aggregation
    - KPI: Returns single current value with threshold status
    - Health Status: Returns current status for multiple services
    - Table: Returns tabular data with sorting and pagination

    Args:
        panel_id: Panel identifier
        tenant_id: Tenant identifier (string, e.g., "tenant_alpha")
        date_from: Start date for time-based filtering (time series)
        date_to: End date for time-based filtering (time series)
        disable_aggregation: Force no aggregation for time series (drill-down)
        sort_column: Column to sort by (table panels)
        sort_order: Sort order "asc" or "desc" (table panels)
        page: Page number for pagination (table panels)
        current_user: Authenticated user
        db: Database session
        config_loader: Configuration loader service
        query_builder: Query builder service
        aggregator: Data aggregator service

    Returns:
        Panel data with type-specific format

    Raises:
        HTTPException: 403 if user doesn't have access to tenant
        HTTPException: 404 if panel not found or tenant not found
        HTTPException: 501 if panel type not yet implemented
    """
    # Get tenant by tenant_id string
    result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id, Tenant.is_active == True)  # noqa: E712
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant {tenant_id} not found",
        )

    # Check if user has access (admin or assigned to tenant)
    if not current_user.is_admin:
        access_result = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == current_user.id,
                UserTenant.tenant_id == tenant.id,
            )
        )
        user_tenant = access_result.scalar_one_or_none()

        if not user_tenant:
            raise HTTPException(
                status_code=403,
                detail=f"User does not have access to tenant {tenant_id}",
            )

    # Load panel configuration
    # For now, we'll need to know which dashboard file contains this panel
    # In a real implementation, you'd have a panel registry or lookup
    # For this step, we'll assume panels are loaded from a default location
    # This is a simplified implementation

    # Try to load from common panel locations
    panel_config: PanelConfig | None = None
    panel_file_paths = [
        f"panels/{panel_id}.yaml",
        f"panels/{panel_id.replace('_', '-')}.yaml",
    ]

    for panel_path in panel_file_paths:
        try:
            panel_config = config_loader.load_panel_config(tenant_id, panel_path)
            break
        except ConfigNotFoundError:
            continue

    if panel_config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Panel {panel_id} not found for tenant {tenant_id}",
        )

    # Route to appropriate handler based on panel type
    if isinstance(panel_config, TimeSeriesPanelConfig):
        return await _get_timeseries_data(
            panel_id,
            panel_config,
            date_from,
            date_to,
            disable_aggregation,
            query_builder,
            aggregator,
            tenant,
        )
    elif isinstance(panel_config, KPIPanelConfig):
        return await _get_kpi_data(panel_id, panel_config, query_builder, tenant)
    elif isinstance(panel_config, HealthStatusPanelConfig):
        return await _get_health_status_data(panel_id, panel_config, query_builder, tenant)
    elif isinstance(panel_config, TablePanelConfig):
        return await _get_table_data(
            panel_id, panel_config, sort_column, sort_order, page, query_builder, tenant
        )
    else:
        raise HTTPException(
            status_code=501,
            detail=f"Panel type {panel_config.type} not yet implemented",
        )


async def _get_timeseries_data(
    panel_id: str,
    config: TimeSeriesPanelConfig,
    date_from: datetime | None,
    date_to: datetime | None,
    disable_aggregation: bool,
    query_builder: QueryBuilder,
    aggregator: DataAggregator,
    tenant: Tenant,
) -> PanelDataResponse:
    """Get time series panel data.

    Args:
        panel_id: Panel identifier
        config: Time series panel configuration
        date_from: Start date
        date_to: End date
        disable_aggregation: Disable aggregation flag
        query_builder: Query builder
        aggregator: Data aggregator
        tenant: Tenant object with database connection info

    Returns:
        Panel data response with time series data
    """
    # Build query
    query, params = query_builder.build_time_series_query(config, date_from, date_to)

    logger.info(f"Executing timeseries query for panel {panel_id}, tenant {tenant.tenant_id}")

    try:
        # Execute query against tenant database with timeout
        async with asyncio.timeout(20):
            async with db_manager.get_tenant_session(tenant.database_url) as session:
                result = await session.execute(text(query), params)
                rows = result.fetchall()

        logger.debug(f"Query returned {len(rows)} rows for panel {panel_id}")

        # Transform results into series format
        # Group by series_label if present
        series_data: dict[str, dict[str, list]] = {}

        for row in rows:
            # Convert row to dict
            row_dict = row._mapping

            timestamp = row_dict["timestamp"]
            value = float(row_dict["value"]) if row_dict["value"] is not None else None
            series_label = row_dict.get("series_label", "default")

            if series_label not in series_data:
                series_data[series_label] = {
                    "timestamps": [],
                    "values": [],
                    "label": series_label,
                }

            series_data[series_label]["timestamps"].append(timestamp.isoformat())
            series_data[series_label]["values"].append(value)

        # Convert to list format
        series_list = list(series_data.values())

        data = {
            "series": series_list,
            "query_executed": query,
        }

    except asyncio.TimeoutError:
        logger.error(f"Query timeout for panel {panel_id}, tenant {tenant.tenant_id}")
        raise HTTPException(
            status_code=504,
            detail="Database query timed out after 20 seconds",
        )
    except Exception as e:
        logger.error(
            f"Database error for panel {panel_id}, tenant {tenant.tenant_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Failed to query tenant database: {str(e)}",
        )

    # Determine aggregation info
    aggregation_info = None
    if date_from and date_to:
        should_aggregate = aggregator.should_aggregate(
            date_from, date_to, disable_aggregation
        )
        if should_aggregate:
            bucket_interval = aggregator.get_bucket_interval(
                date_from, date_to, disable_aggregation
            )
            aggregation_info = {
                "applied": True,
                "bucket_interval": bucket_interval,
            }
        else:
            aggregation_info = {
                "applied": False,
                "reason": "disable_aggregation flag" if disable_aggregation else "range too small",
            }

    return PanelDataResponse(
        panel_id=panel_id,
        panel_type=PanelType.TIMESERIES,
        data=data,
        aggregation_info=aggregation_info,
    )


async def _get_kpi_data(
    panel_id: str,
    config: KPIPanelConfig,
    query_builder: QueryBuilder,
    tenant: Tenant,
) -> PanelDataResponse:
    """Get KPI panel data.

    Args:
        panel_id: Panel identifier
        config: KPI panel configuration
        query_builder: Query builder
        tenant: Tenant object with database connection info

    Returns:
        Panel data response with KPI value and threshold status
    """
    # Build query
    query, params = query_builder.build_kpi_query(config)

    logger.info(f"Executing KPI query for panel {panel_id}, tenant {tenant.tenant_id}")

    try:
        # Execute query against tenant database with timeout
        async with asyncio.timeout(20):
            async with db_manager.get_tenant_session(tenant.database_url) as session:
                result = await session.execute(text(query), params)
                row = result.fetchone()

        # Extract value (default to None if no result)
        value = None
        if row is not None:
            row_dict = row._mapping
            value = float(row_dict["value"]) if row_dict["value"] is not None else None

        logger.debug(f"KPI query returned value {value} for panel {panel_id}")

    except asyncio.TimeoutError:
        logger.error(f"Query timeout for panel {panel_id}, tenant {tenant.tenant_id}")
        raise HTTPException(
            status_code=504,
            detail="Database query timed out after 20 seconds",
        )
    except Exception as e:
        logger.error(
            f"Database error for panel {panel_id}, tenant {tenant.tenant_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Failed to query tenant database: {str(e)}",
        )

    # Apply threshold logic
    threshold_status = "good"
    threshold_color = "#10B981"  # Default green

    if value is not None and config.display and config.display.thresholds:
        # Find applicable threshold (highest threshold value <= current value)
        applicable_threshold = None
        for threshold in sorted(
            config.display.thresholds, key=lambda t: t.value, reverse=True
        ):
            if value >= threshold.value:
                applicable_threshold = threshold
                break

        if applicable_threshold:
            threshold_status = applicable_threshold.label
            threshold_color = applicable_threshold.color

    data = {
        "value": value,
        "unit": config.display.unit if config.display else None,
        "decimals": config.display.decimals if config.display else 1,
        "threshold_status": threshold_status,
        "threshold_color": threshold_color,
        "query_executed": query,
    }

    return PanelDataResponse(
        panel_id=panel_id,
        panel_type=PanelType.KPI,
        data=data,
    )


async def _get_health_status_data(
    panel_id: str,
    config: HealthStatusPanelConfig,
    query_builder: QueryBuilder,
    tenant: Tenant,
) -> PanelDataResponse:
    """Get health status panel data.

    Args:
        panel_id: Panel identifier
        config: Health status panel configuration
        query_builder: Query builder
        tenant: Tenant object with database connection info

    Returns:
        Panel data response with service statuses
    """
    # Build query
    query, params = query_builder.build_health_status_query(config)

    logger.info(f"Executing health status query for panel {panel_id}, tenant {tenant.tenant_id}")

    try:
        # Execute query against tenant database with timeout
        async with asyncio.timeout(20):
            async with db_manager.get_tenant_session(tenant.database_url) as session:
                result = await session.execute(text(query), params)
                rows = result.fetchall()

        logger.debug(f"Health status query returned {len(rows)} services for panel {panel_id}")

        # Transform results
        services_with_status = []
        for row in rows:
            row_dict = row._mapping
            service_name = row_dict["service_name"]
            status_value = cast(int, row_dict["status_value"])

            # Apply status mapping
            if status_value in config.display.status_mapping:
                mapping = config.display.status_mapping[status_value]
                services_with_status.append(
                    {
                        "service_name": service_name,
                        "status_value": status_value,
                        "status_label": mapping.label,
                        "status_color": mapping.color,
                    }
                )
            else:
                # Unknown status value - use default
                services_with_status.append(
                    {
                        "service_name": service_name,
                        "status_value": status_value,
                        "status_label": "unknown",
                        "status_color": "#6B7280",  # Gray
                    }
                )

        data = {
            "services": services_with_status,
            "query_executed": query,
        }

    except asyncio.TimeoutError:
        logger.error(f"Query timeout for panel {panel_id}, tenant {tenant.tenant_id}")
        raise HTTPException(
            status_code=504,
            detail="Database query timed out after 20 seconds",
        )
    except Exception as e:
        logger.error(
            f"Database error for panel {panel_id}, tenant {tenant.tenant_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Failed to query tenant database: {str(e)}",
        )

    return PanelDataResponse(
        panel_id=panel_id,
        panel_type=PanelType.HEALTH_STATUS,
        data=data,
    )


async def _get_table_data(
    panel_id: str,
    config: TablePanelConfig,
    sort_column: str | None,
    sort_order: str,
    page: int,
    query_builder: QueryBuilder,
    tenant: Tenant,
) -> PanelDataResponse:
    """Get table panel data.

    Args:
        panel_id: Panel identifier
        config: Table panel configuration
        sort_column: Column to sort by
        sort_order: Sort order
        page: Page number
        query_builder: Query builder
        tenant: Tenant object with database connection info

    Returns:
        Panel data response with tabular data and pagination info
    """
    # Build query
    query, params = query_builder.build_table_query(
        config, sort_column, sort_order, page
    )

    logger.info(f"Executing table query for panel {panel_id}, tenant {tenant.tenant_id}")

    try:
        # Execute query against tenant database with timeout
        async with asyncio.timeout(20):
            async with db_manager.get_tenant_session(tenant.database_url) as session:
                # Execute data query
                result = await session.execute(text(query), params)
                rows_raw = result.fetchall()

                # Build count query (remove LIMIT/OFFSET for count)
                # Extract base query (everything before ORDER BY)
                count_query = query.split(" ORDER BY")[0]
                count_query = f"SELECT COUNT(*) as total FROM ({count_query}) as subq"

                # Execute count query
                count_result = await session.execute(text(count_query), params)
                count_row = count_result.fetchone()
                total_rows = int(count_row._mapping["total"]) if count_row else 0

        logger.debug(f"Table query returned {len(rows_raw)} rows (total: {total_rows}) for panel {panel_id}")

        # Transform results to list of dicts
        rows = []
        for row in rows_raw:
            row_dict = {}
            row_mapping = row._mapping

            for col in config.data_source.columns:
                value = row_mapping.get(col.name)

                # Format based on column format
                if col.format == "datetime" and isinstance(value, datetime):
                    row_dict[col.name] = value.isoformat()
                elif value is not None:
                    row_dict[col.name] = value
                else:
                    row_dict[col.name] = None

            rows.append(row_dict)

        # Build pagination metadata
        page_size = config.display.pagination if config.display else 25
        total_pages = (total_rows + page_size - 1) // page_size  # Ceiling division

        data = {
            "columns": [
                {"name": col.name, "display": col.display, "format": col.format}
                for col in config.data_source.columns
            ],
            "rows": rows,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_rows": total_rows,
                "total_pages": total_pages,
            },
            "sort": {
                "column": sort_column or (config.display.default_sort if config.display else None),
                "order": sort_order,
            },
            "query_executed": query,
        }

    except asyncio.TimeoutError:
        logger.error(f"Query timeout for panel {panel_id}, tenant {tenant.tenant_id}")
        raise HTTPException(
            status_code=504,
            detail="Database query timed out after 20 seconds",
        )
    except Exception as e:
        logger.error(
            f"Database error for panel {panel_id}, tenant {tenant.tenant_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Failed to query tenant database: {str(e)}",
        )

    return PanelDataResponse(
        panel_id=panel_id,
        panel_type=PanelType.TABLE,
        data=data,
    )
