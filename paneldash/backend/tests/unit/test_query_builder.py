"""Unit tests for SQL query builder service."""

from datetime import datetime

import pytest

from app.schemas.config import (
    HealthStatusDataSource,
    HealthStatusDisplay,
    HealthStatusMapping,
    HealthStatusPanelConfig,
    KPIDataSource,
    KPIDisplay,
    KPIPanelConfig,
    PanelType,
    TableColumn,
    TableDataSource,
    TableDisplay,
    TablePanelConfig,
    TimeSeriesDataSource,
    TimeSeriesPanelConfig,
)
from app.services.query_builder import (
    InvalidQueryConfigError,
    QueryBuilder,
    SQLInjectionError,
)


@pytest.fixture
def query_builder() -> QueryBuilder:
    """Create a QueryBuilder instance for testing."""
    return QueryBuilder()


class TestIdentifierValidation:
    """Test SQL identifier validation and quoting."""

    def test_valid_identifiers(self, query_builder: QueryBuilder) -> None:
        """Test that valid identifiers are accepted."""
        valid_ids = ["table_name", "column1", "_private", "CamelCase", "snake_case_123"]
        for identifier in valid_ids:
            # Should not raise
            result = query_builder._validate_identifier(identifier)
            assert result == identifier

    def test_invalid_identifiers_raise_error(self, query_builder: QueryBuilder) -> None:
        """Test that invalid identifiers raise SQLInjectionError."""
        invalid_ids = [
            "table-name",  # Hyphen
            "1table",  # Starts with number
            "table.name",  # Dot
            "table; DROP TABLE users;",  # SQL injection attempt
            "table/*comment*/",  # Comment injection
            "table name",  # Space
        ]
        for identifier in invalid_ids:
            with pytest.raises(SQLInjectionError):
                query_builder._validate_identifier(identifier)

    def test_quote_identifier(self, query_builder: QueryBuilder) -> None:
        """Test identifier quoting."""
        assert query_builder._quote_identifier("table_name") == '"table_name"'
        assert query_builder._quote_identifier("column_1") == '"column_1"'


class TestTimeSeriesQuery:
    """Test time series query building."""

    def test_basic_time_series_query(self, query_builder: QueryBuilder) -> None:
        """Test building a basic time series query."""
        config = TimeSeriesPanelConfig(
            type=PanelType.TIMESERIES,
            title="CPU Usage",
            data_source=TimeSeriesDataSource(
                table="metrics",
                columns={"timestamp": "recorded_at", "value": "cpu_percent"},
            ),
        )

        query, params = query_builder.build_time_series_query(config)

        assert '"metrics"' in query
        assert '"recorded_at" AS timestamp' in query
        assert '"cpu_percent" AS value' in query
        assert 'ORDER BY "recorded_at" ASC' in query
        assert params == {}

    def test_time_series_with_series_label(self, query_builder: QueryBuilder) -> None:
        """Test time series query with series label for multiple lines."""
        config = TimeSeriesPanelConfig(
            type=PanelType.TIMESERIES,
            title="CPU Usage by Server",
            data_source=TimeSeriesDataSource(
                table="metrics",
                columns={
                    "timestamp": "recorded_at",
                    "value": "cpu_percent",
                    "series_label": "server_name",
                },
            ),
        )

        query, params = query_builder.build_time_series_query(config)

        assert '"server_name" AS series_label' in query
        assert params == {}

    def test_time_series_with_date_range(self, query_builder: QueryBuilder) -> None:
        """Test time series query with date range filtering."""
        config = TimeSeriesPanelConfig(
            type=PanelType.TIMESERIES,
            title="CPU Usage",
            data_source=TimeSeriesDataSource(
                table="metrics",
                columns={"timestamp": "recorded_at", "value": "cpu_percent"},
            ),
        )

        date_from = datetime(2024, 1, 1, 0, 0, 0)
        date_to = datetime(2024, 1, 31, 23, 59, 59)

        query, params = query_builder.build_time_series_query(
            config, date_from=date_from, date_to=date_to
        )

        assert '"recorded_at" >= %(date_from)s' in query
        assert '"recorded_at" <= %(date_to)s' in query
        assert params["date_from"] == date_from
        assert params["date_to"] == date_to

    def test_time_series_with_custom_where(self, query_builder: QueryBuilder) -> None:
        """Test time series query with custom WHERE clause."""
        config = TimeSeriesPanelConfig(
            type=PanelType.TIMESERIES,
            title="CPU Usage",
            data_source=TimeSeriesDataSource(
                table="metrics",
                columns={"timestamp": "recorded_at", "value": "cpu_percent"},
                query={"where": "metric_type = 'cpu'"},
            ),
        )

        query, params = query_builder.build_time_series_query(config)

        assert "WHERE (metric_type = 'cpu')" in query

    def test_time_series_missing_columns_raises_error(
        self, query_builder: QueryBuilder
    ) -> None:
        """Test that missing required columns raise error."""
        # Missing 'value' column
        config = TimeSeriesPanelConfig(
            type=PanelType.TIMESERIES,
            title="Invalid",
            data_source=TimeSeriesDataSource(
                table="metrics",
                columns={"timestamp": "recorded_at"},  # Missing 'value'
            ),
        )

        with pytest.raises(InvalidQueryConfigError, match="must have 'timestamp' and 'value'"):
            query_builder.build_time_series_query(config)


class TestKPIQuery:
    """Test KPI query building."""

    def test_basic_kpi_query(self, query_builder: QueryBuilder) -> None:
        """Test building a basic KPI query."""
        config = KPIPanelConfig(
            type=PanelType.KPI,
            title="Memory Usage",
            data_source=KPIDataSource(
                table="metrics",
                columns={"value": "memory_percent"},
                query="WHERE metric_type = 'memory' ORDER BY recorded_at DESC LIMIT 1",
            ),
            display=KPIDisplay(unit="%"),
        )

        query, params = query_builder.build_kpi_query(config)

        assert 'SELECT "memory_percent" AS value FROM "metrics"' in query
        assert "WHERE metric_type = 'memory'" in query
        assert "ORDER BY recorded_at DESC LIMIT 1" in query
        assert params == {}

    def test_kpi_missing_value_column_raises_error(
        self, query_builder: QueryBuilder
    ) -> None:
        """Test that missing value column raises error."""
        config = KPIPanelConfig(
            type=PanelType.KPI,
            title="Invalid",
            data_source=KPIDataSource(
                table="metrics",
                columns={},  # Missing 'value'
            ),
            display=KPIDisplay(),
        )

        with pytest.raises(InvalidQueryConfigError, match="must have 'value' column"):
            query_builder.build_kpi_query(config)


class TestHealthStatusQuery:
    """Test health status query building."""

    def test_basic_health_status_query(self, query_builder: QueryBuilder) -> None:
        """Test building a basic health status query."""
        config = HealthStatusPanelConfig(
            type=PanelType.HEALTH_STATUS,
            title="Service Health",
            data_source=HealthStatusDataSource(
                table="service_status",
                columns={"service_name": "name", "status_value": "status"},
            ),
            display=HealthStatusDisplay(
                status_mapping={
                    0: HealthStatusMapping(color="#10B981", label="Healthy"),
                    1: HealthStatusMapping(color="#EF4444", label="Down"),
                }
            ),
        )

        query, params = query_builder.build_health_status_query(config)

        assert 'SELECT "name" AS service_name, "status" AS status_value' in query
        assert 'FROM "service_status"' in query
        assert params == {}

    def test_health_status_missing_columns_raises_error(
        self, query_builder: QueryBuilder
    ) -> None:
        """Test that missing required columns raise error."""
        config = HealthStatusPanelConfig(
            type=PanelType.HEALTH_STATUS,
            title="Invalid",
            data_source=HealthStatusDataSource(
                table="service_status",
                columns={"service_name": "name"},  # Missing 'status_value'
            ),
            display=HealthStatusDisplay(status_mapping={}),
        )

        with pytest.raises(
            InvalidQueryConfigError,
            match="must have 'service_name' and 'status_value'",
        ):
            query_builder.build_health_status_query(config)


class TestTableQuery:
    """Test table query building."""

    def test_basic_table_query(self, query_builder: QueryBuilder) -> None:
        """Test building a basic table query."""
        config = TablePanelConfig(
            type=PanelType.TABLE,
            title="Error Logs",
            data_source=TableDataSource(
                table="logs",
                columns=[
                    TableColumn(name="timestamp", display="Time"),
                    TableColumn(name="message", display="Message"),
                    TableColumn(name="severity", display="Severity"),
                ],
            ),
            display=TableDisplay(pagination=25),
        )

        query, params = query_builder.build_table_query(config)

        assert 'SELECT "timestamp", "message", "severity" FROM "logs"' in query
        assert 'ORDER BY "timestamp" DESC' in query
        assert "LIMIT 25 OFFSET 0" in query
        assert params == {}

    def test_table_query_with_sorting(self, query_builder: QueryBuilder) -> None:
        """Test table query with custom sorting."""
        config = TablePanelConfig(
            type=PanelType.TABLE,
            title="Error Logs",
            data_source=TableDataSource(
                table="logs",
                columns=[
                    TableColumn(name="timestamp", display="Time"),
                    TableColumn(name="severity", display="Severity"),
                ],
            ),
            display=TableDisplay(default_sort="severity", default_sort_order="asc"),
        )

        query, params = query_builder.build_table_query(config, sort_column="severity", sort_order="asc")

        assert 'ORDER BY "severity" ASC' in query

    def test_table_query_with_pagination(self, query_builder: QueryBuilder) -> None:
        """Test table query with pagination."""
        config = TablePanelConfig(
            type=PanelType.TABLE,
            title="Error Logs",
            data_source=TableDataSource(
                table="logs",
                columns=[TableColumn(name="timestamp", display="Time")],
            ),
            display=TableDisplay(pagination=50),
        )

        # Page 1
        query, _ = query_builder.build_table_query(config, page=1)
        assert "LIMIT 50 OFFSET 0" in query

        # Page 2
        query, _ = query_builder.build_table_query(config, page=2)
        assert "LIMIT 50 OFFSET 50" in query

        # Page 3
        query, _ = query_builder.build_table_query(config, page=3)
        assert "LIMIT 50 OFFSET 100" in query

    def test_table_query_with_where_clause(self, query_builder: QueryBuilder) -> None:
        """Test table query with WHERE clause."""
        config = TablePanelConfig(
            type=PanelType.TABLE,
            title="Critical Errors",
            data_source=TableDataSource(
                table="logs",
                columns=[TableColumn(name="message", display="Message")],
                query={"where": "severity IN ('ERROR', 'CRITICAL')"},
            ),
            display=TableDisplay(),
        )

        query, params = query_builder.build_table_query(config)

        assert "WHERE severity IN ('ERROR', 'CRITICAL')" in query

    def test_table_invalid_sort_column_raises_error(
        self, query_builder: QueryBuilder
    ) -> None:
        """Test that invalid sort column raises error."""
        config = TablePanelConfig(
            type=PanelType.TABLE,
            title="Logs",
            data_source=TableDataSource(
                table="logs",
                columns=[TableColumn(name="message", display="Message")],
            ),
            display=TableDisplay(),
        )

        with pytest.raises(InvalidQueryConfigError, match="not in table columns"):
            query_builder.build_table_query(config, sort_column="invalid_column")

    def test_table_empty_columns_raises_error(
        self, query_builder: QueryBuilder
    ) -> None:
        """Test that empty columns list raises error."""
        config = TablePanelConfig(
            type=PanelType.TABLE,
            title="Invalid",
            data_source=TableDataSource(
                table="logs",
                columns=[],  # Empty columns
            ),
            display=TableDisplay(),
        )

        with pytest.raises(InvalidQueryConfigError, match="at least one column"):
            query_builder.build_table_query(config)


class TestBuildQueryGeneric:
    """Test the generic build_query method."""

    def test_build_query_dispatches_to_correct_method(
        self, query_builder: QueryBuilder
    ) -> None:
        """Test that build_query dispatches to the correct panel-specific method."""
        # Time series
        ts_config = TimeSeriesPanelConfig(
            type=PanelType.TIMESERIES,
            title="Test",
            data_source=TimeSeriesDataSource(
                table="metrics",
                columns={"timestamp": "t", "value": "v"},
            ),
        )
        query, _ = query_builder.build_query(ts_config)
        assert "metrics" in query

        # KPI
        kpi_config = KPIPanelConfig(
            type=PanelType.KPI,
            title="Test",
            data_source=KPIDataSource(table="metrics", columns={"value": "v"}),
            display=KPIDisplay(),
        )
        query, _ = query_builder.build_query(kpi_config)
        assert "metrics" in query

        # Health status
        health_config = HealthStatusPanelConfig(
            type=PanelType.HEALTH_STATUS,
            title="Test",
            data_source=HealthStatusDataSource(
                table="status",
                columns={"service_name": "name", "status_value": "status"},
            ),
            display=HealthStatusDisplay(status_mapping={}),
        )
        query, _ = query_builder.build_query(health_config)
        assert "status" in query

        # Table
        table_config = TablePanelConfig(
            type=PanelType.TABLE,
            title="Test",
            data_source=TableDataSource(
                table="logs",
                columns=[TableColumn(name="message", display="Message")],
            ),
            display=TableDisplay(),
        )
        query, _ = query_builder.build_query(table_config)
        assert "logs" in query
