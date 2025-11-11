"""Service for building safe SQL queries from panel configurations."""

import re
from datetime import datetime
from typing import Any

from app.schemas.config import (
    HealthStatusPanelConfig,
    KPIPanelConfig,
    PanelConfig,
    TablePanelConfig,
    TimeSeriesPanelConfig,
)


class QueryBuilderError(Exception):
    """Base exception for query builder errors."""

    pass


class SQLInjectionError(QueryBuilderError):
    """Raised when potential SQL injection is detected."""

    pass


class InvalidQueryConfigError(QueryBuilderError):
    """Raised when query configuration is invalid."""

    pass


class QueryBuilder:
    """Builds safe parameterized SQL queries from panel configurations."""

    # Valid SQL identifier pattern (letters, numbers, underscores only)
    _IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    def __init__(self) -> None:
        """Initialize the query builder."""
        pass

    def _validate_identifier(self, identifier: str) -> str:
        """Validate that an identifier (table/column name) is safe.

        Args:
            identifier: Table or column name to validate

        Returns:
            The validated identifier

        Raises:
            SQLInjectionError: If identifier contains unsafe characters
        """
        if not self._IDENTIFIER_PATTERN.match(identifier):
            raise SQLInjectionError(
                f"Invalid identifier '{identifier}': "
                "must contain only letters, numbers, and underscores"
            )
        return identifier

    def _quote_identifier(self, identifier: str) -> str:
        """Quote a SQL identifier to prevent injection.

        Args:
            identifier: Table or column name (already validated)

        Returns:
            Quoted identifier safe for SQL
        """
        # Validate first
        self._validate_identifier(identifier)
        # Quote with double quotes (PostgreSQL standard)
        return f'"{identifier}"'

    def build_time_series_query(
        self,
        config: TimeSeriesPanelConfig,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Build a SELECT query for time series panel.

        Args:
            config: Time series panel configuration
            date_from: Optional start date for filtering
            date_to: Optional end date for filtering

        Returns:
            Tuple of (SQL query string, parameters dict)

        Raises:
            SQLInjectionError: If identifiers are invalid
            InvalidQueryConfigError: If configuration is invalid
        """
        # Validate and quote table name
        table = self._quote_identifier(config.data_source.table)

        # Build column list
        columns = config.data_source.columns
        if "timestamp" not in columns or "value" not in columns:
            raise InvalidQueryConfigError(
                "Time series must have 'timestamp' and 'value' columns"
            )

        select_parts = [
            f"{self._quote_identifier(columns['timestamp'])} AS timestamp",
            f"{self._quote_identifier(columns['value'])} AS value",
        ]

        # Add optional series_label column
        if "series_label" in columns:
            select_parts.append(
                f"{self._quote_identifier(columns['series_label'])} AS series_label"
            )

        select_clause = ", ".join(select_parts)

        # Build WHERE clause
        where_conditions: list[str] = []
        params: dict[str, Any] = {}

        # Add date range filters
        if date_from is not None:
            where_conditions.append(f"{self._quote_identifier(columns['timestamp'])} >= %(date_from)s")
            params["date_from"] = date_from

        if date_to is not None:
            where_conditions.append(f"{self._quote_identifier(columns['timestamp'])} <= %(date_to)s")
            params["date_to"] = date_to

        # Add custom WHERE clause from config
        if config.data_source.query and "where" in config.data_source.query:
            # Use the WHERE clause as-is (assuming it's already safe from YAML)
            custom_where = config.data_source.query["where"]
            if custom_where:
                where_conditions.append(f"({custom_where})")

        # Build ORDER BY clause
        order_by = f"{self._quote_identifier(columns['timestamp'])} ASC"  # Default
        if config.data_source.query and "order_by" in config.data_source.query:
            # Use custom ORDER BY (already from YAML config)
            order_by = config.data_source.query["order_by"]

        # Construct full query
        query = f"SELECT {select_clause} FROM {table}"

        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        query += f" ORDER BY {order_by}"

        return query, params

    def build_kpi_query(
        self,
        config: KPIPanelConfig,
    ) -> tuple[str, dict[str, Any]]:
        """Build a SELECT query for KPI panel.

        Args:
            config: KPI panel configuration

        Returns:
            Tuple of (SQL query string, parameters dict)

        Raises:
            SQLInjectionError: If identifiers are invalid
            InvalidQueryConfigError: If configuration is invalid
        """
        # Validate and quote table name
        table = self._quote_identifier(config.data_source.table)

        # Build column list
        columns = config.data_source.columns
        if "value" not in columns:
            raise InvalidQueryConfigError("KPI must have 'value' column")

        value_column = self._quote_identifier(columns["value"])

        # KPI query is typically a single value with ORDER BY + LIMIT
        query = f"SELECT {value_column} AS value FROM {table}"

        # Add custom query clause if provided
        if config.data_source.query:
            # For KPI, the query is a string containing WHERE + ORDER BY + LIMIT
            query += f" {config.data_source.query}"

        params: dict[str, Any] = {}
        return query, params

    def build_health_status_query(
        self,
        config: HealthStatusPanelConfig,
    ) -> tuple[str, dict[str, Any]]:
        """Build a SELECT query for health status panel.

        Args:
            config: Health status panel configuration

        Returns:
            Tuple of (SQL query string, parameters dict)

        Raises:
            SQLInjectionError: If identifiers are invalid
            InvalidQueryConfigError: If configuration is invalid
        """
        # Validate and quote table name
        table = self._quote_identifier(config.data_source.table)

        # Build column list
        columns = config.data_source.columns
        if "service_name" not in columns or "status_value" not in columns:
            raise InvalidQueryConfigError(
                "Health status must have 'service_name' and 'status_value' columns"
            )

        select_parts = [
            f"{self._quote_identifier(columns['service_name'])} AS service_name",
            f"{self._quote_identifier(columns['status_value'])} AS status_value",
        ]

        select_clause = ", ".join(select_parts)

        # Simple query - just get all current statuses
        query = f"SELECT {select_clause} FROM {table}"

        params: dict[str, Any] = {}
        return query, params

    def build_table_query(
        self,
        config: TablePanelConfig,
        sort_column: str | None = None,
        sort_order: str = "desc",
        page: int = 1,
    ) -> tuple[str, dict[str, Any]]:
        """Build a SELECT query for table panel.

        Args:
            config: Table panel configuration
            sort_column: Column name to sort by (overrides default)
            sort_order: Sort order ("asc" or "desc")
            page: Page number for pagination (1-indexed)

        Returns:
            Tuple of (SQL query string, parameters dict)

        Raises:
            SQLInjectionError: If identifiers are invalid
            InvalidQueryConfigError: If configuration is invalid
        """
        # Validate and quote table name
        table = self._quote_identifier(config.data_source.table)

        # Build column list
        if not config.data_source.columns:
            raise InvalidQueryConfigError("Table must have at least one column")

        select_parts = []
        column_names = []
        for col in config.data_source.columns:
            column_names.append(col.name)
            quoted_name = self._quote_identifier(col.name)
            select_parts.append(f"{quoted_name}")

        select_clause = ", ".join(select_parts)

        # Build WHERE clause
        where_clause = ""
        if config.data_source.query and "where" in config.data_source.query:
            custom_where = config.data_source.query["where"]
            if custom_where:
                where_clause = f" WHERE {custom_where}"

        # Build ORDER BY clause
        if sort_column:
            # Validate sort column is in the column list
            if sort_column not in column_names:
                raise InvalidQueryConfigError(
                    f"Sort column '{sort_column}' not in table columns"
                )
            order_by_col = self._quote_identifier(sort_column)
        elif config.display and config.display.default_sort:
            order_by_col = self._quote_identifier(config.display.default_sort)
        else:
            # Use first column as default
            order_by_col = self._quote_identifier(column_names[0])

        # Validate sort order
        if sort_order.lower() not in ("asc", "desc"):
            sort_order = "desc"

        order_by = f"{order_by_col} {sort_order.upper()}"

        # Build LIMIT and OFFSET for pagination
        page_size = config.display.pagination if config.display else 25
        offset = (page - 1) * page_size

        # Apply limit from config if provided
        limit = page_size
        if config.data_source.query and "limit" in config.data_source.query:
            config_limit = config.data_source.query["limit"]
            if isinstance(config_limit, int):
                # Use config limit but respect pagination
                limit = min(config_limit, page_size)

        # Construct full query
        query = f"SELECT {select_clause} FROM {table}"
        query += where_clause
        query += f" ORDER BY {order_by}"
        query += f" LIMIT {limit} OFFSET {offset}"

        params: dict[str, Any] = {}
        return query, params

    def build_query(
        self,
        config: PanelConfig,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any]]:
        """Build a SQL query for any panel type.

        Args:
            config: Panel configuration
            date_from: Optional start date for time-based filtering
            date_to: Optional end date for time-based filtering
            **kwargs: Additional panel-specific parameters (sort_column, sort_order, page)

        Returns:
            Tuple of (SQL query string, parameters dict)

        Raises:
            QueryBuilderError: If query cannot be built
        """
        if isinstance(config, TimeSeriesPanelConfig):
            return self.build_time_series_query(config, date_from, date_to)
        elif isinstance(config, KPIPanelConfig):
            return self.build_kpi_query(config)
        elif isinstance(config, HealthStatusPanelConfig):
            return self.build_health_status_query(config)
        elif isinstance(config, TablePanelConfig):
            return self.build_table_query(
                config,
                sort_column=kwargs.get("sort_column"),
                sort_order=kwargs.get("sort_order", "desc"),
                page=kwargs.get("page", 1),
            )
        else:
            raise QueryBuilderError(f"Unsupported panel type: {type(config)}")


# Singleton instance
def get_query_builder() -> QueryBuilder:
    """Get the singleton QueryBuilder instance.

    Returns:
        QueryBuilder instance
    """
    return QueryBuilder()
