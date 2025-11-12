# Panel Data API Implementation Specification

## Overview

This document provides implementation specifications for completing the four panel data handler functions in `paneldash/backend/app/api/v1/panels.py`. Currently, all four handlers return mock/test data. This spec explains how to complete each implementation by connecting to tenant databases and executing real queries.

## Current State

**File:** `paneldash/backend/app/api/v1/panels.py`

All four panel data handlers currently return hardcoded test data:
- `_get_timeseries_data()` (lines 170-234)
- `_get_kpi_data()` (lines 237-287)
- `_get_health_status_data()` (lines 290-346)
- `_get_table_data()` (lines 349-405)

Mock data locations:
- **Timeseries**: Lines 196-207 (hardcoded timestamps and values)
- **KPI**: Lines 254-281 (hardcoded value 75.3)
- **Health Status**: Lines 307-335 (dummy services array)
- **Table**: Lines 377-405 (fabricated log entries)

## Architecture Overview

### Multi-Tenant Database Architecture

The application uses a **multi-tenant architecture** with separate databases:

1. **Central Database**: Stores users, tenants, and access control mappings
   - Models: `User`, `Tenant`, `UserTenant` (see `app/models/central.py`)
   - Accessed via: `get_central_db()` dependency

2. **Tenant Databases**: Each tenant has its own PostgreSQL database
   - Connection info stored in `Tenant` model (database_host, database_name, database_user, etc.)
   - Database URL computed via `tenant.database_url` property
   - Accessed via: `db_manager.get_tenant_session(database_url)`

### Reusable Backend Components

The following services are already implemented and should be reused:

1. **DatabaseManager** (`app/database.py`)
   - `get_tenant_session(database_url)`: Returns async context manager for tenant DB session
   - Handles connection pooling and lifecycle

2. **QueryBuilder** (`app/services/query_builder.py`)
   - Already generates SQL queries from panel configs
   - Methods: `build_time_series_query()`, `build_kpi_query()`, `build_health_status_query()`, `build_table_query()`
   - Returns parameterized queries safe from SQL injection

3. **DataAggregator** (`app/services/data_aggregator.py`)
   - Handles time-based bucketing for time series data
   - Methods: `should_aggregate()`, `get_bucket_interval()`, `get_aggregation_sql()`

4. **Tenant Model** (`app/models/central.py:33-64`)
   - Property `database_url` (line 58-64): Constructs connection string
   - Already passed to the endpoint via tenant lookup

---

## Handler 1: Time Series Data

### File Location
`paneldash/backend/app/api/v1/panels.py:170-234`

### Current Implementation
Returns mock data (lines 196-207):
```python
mock_data = {
    "series": [
        {
            "timestamps": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
            "values": [45.2, 52.1],
            "label": "server-1",
        }
    ],
    "query_executed": query,
}
```

### Implementation Steps

1. **Import required dependencies** (add to top of file):
   ```python
   from app.database import db_manager
   ```

2. **Get tenant database connection** (replace mock data section):
   - Retrieve tenant object from central DB (already done in main `get_panel_data()` function)
   - Access tenant database using `db_manager.get_tenant_session(tenant.database_url)`

3. **Execute the query**:
   - Use the already-built query and params from `query_builder.build_time_series_query()`
   - Execute using SQLAlchemy's async session
   - Handle potential database connection errors

4. **Transform results to expected format**:
   - Group by series_label if present
   - Format timestamps as ISO 8601 strings
   - Convert Decimal/numeric types to float for JSON serialization

5. **Apply aggregation** (if needed):
   - Use `DataAggregator` to determine if aggregation should be applied
   - Modify query with aggregation SQL if needed
   - Include aggregation info in response

### Complete Implementation

Replace lines 193-207 with:

```python
async def _get_timeseries_data(
    panel_id: str,
    config: TimeSeriesPanelConfig,
    date_from: datetime | None,
    date_to: datetime | None,
    disable_aggregation: bool,
    query_builder: QueryBuilder,
    aggregator: DataAggregator,
    tenant: Tenant,  # ADD THIS PARAMETER
) -> PanelDataResponse:
    """Get time series panel data."""

    # Build query
    query, params = query_builder.build_time_series_query(config, date_from, date_to)

    # Execute query against tenant database
    async with db_manager.get_tenant_session(tenant.database_url) as session:
        from sqlalchemy import text

        result = await session.execute(text(query), params)
        rows = result.fetchall()

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
```

### Update Main Endpoint

Update the call to `_get_timeseries_data()` at line 146 to pass the tenant object:

```python
if isinstance(panel_config, TimeSeriesPanelConfig):
    return await _get_timeseries_data(
        panel_id,
        panel_config,
        date_from,
        date_to,
        disable_aggregation,
        query_builder,
        aggregator,
        tenant,  # ADD THIS
    )
```

### Positive Test Cases

**Test 1: Successful timeseries data retrieval**
- **Setup**:
  - Create tenant with test database
  - Create `metrics` table with columns: `recorded_at` (timestamp), `cpu_percent` (float), `server_name` (text)
  - Insert test data: 10 records over 2-hour period with varying values
  - Create user with access to tenant
- **Request**:
  ```
  GET /api/v1/panels/cpu_usage/data?tenant_id=test_tenant&date_from=2024-01-01T00:00:00Z&date_to=2024-01-01T02:00:00Z
  ```
- **Expected Result**:
  - Status 200
  - Response contains `series` array with timestamps and values
  - Data matches inserted test records
  - `aggregation_info.applied = false` (2-hour range, no aggregation needed)

**Test 2: Timeseries with aggregation**
- **Setup**: Same as Test 1, but insert 1000 records over 10-day period
- **Request**:
  ```
  GET /api/v1/panels/cpu_usage/data?tenant_id=test_tenant&date_from=2024-01-01T00:00:00Z&date_to=2024-01-11T00:00:00Z
  ```
- **Expected Result**:
  - Status 200
  - `aggregation_info.applied = true`
  - `aggregation_info.bucket_interval = "1 hour"`
  - Data is aggregated into hourly buckets

**Test 3: Multiple series (with series_label)**
- **Setup**: Insert data with different `server_name` values
- **Request**:
  ```
  GET /api/v1/panels/cpu_usage/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - Response contains multiple series in `series` array
  - Each series has different `label` value

### Negative Test Cases

**Test 1: Tenant database connection failure**
- **Setup**:
  - Create tenant with invalid database credentials
  - Create user with access to tenant
- **Request**:
  ```
  GET /api/v1/panels/cpu_usage/data?tenant_id=invalid_db_tenant
  ```
- **Expected Result**:
  - Status 500 or 503
  - Error message indicates database connection failure
  - Does not expose credentials in error message

**Test 2: Table does not exist in tenant database**
- **Setup**:
  - Create tenant with valid database but empty schema
  - Panel config references non-existent table `metrics`
- **Request**:
  ```
  GET /api/v1/panels/cpu_usage/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 500
  - Error message indicates table not found
  - Does not expose internal schema details

**Test 3: Empty result set**
- **Setup**:
  - Create tenant with valid database and table
  - Table has no data matching date range
- **Request**:
  ```
  GET /api/v1/panels/cpu_usage/data?tenant_id=test_tenant&date_from=2099-01-01T00:00:00Z
  ```
- **Expected Result**:
  - Status 200
  - Response contains empty `series` array
  - No error, gracefully handles no data

---

## Handler 2: KPI Data

### File Location
`paneldash/backend/app/api/v1/panels.py:237-287`

### Current Implementation
Returns mock value (lines 253-281):
```python
# Mock data (in real implementation, query tenant database)
mock_value = 75.3
```

### Implementation Steps

1. **Get tenant database connection**
2. **Execute KPI query** (returns single value)
3. **Extract scalar value** from result
4. **Apply threshold logic** (already implemented, lines 257-272)

### Complete Implementation

Replace lines 250-281 with:

```python
async def _get_kpi_data(
    panel_id: str,
    config: KPIPanelConfig,
    query_builder: QueryBuilder,
    tenant: Tenant,  # ADD THIS PARAMETER
) -> PanelDataResponse:
    """Get KPI panel data."""

    # Build query
    query, params = query_builder.build_kpi_query(config)

    # Execute query against tenant database
    async with db_manager.get_tenant_session(tenant.database_url) as session:
        from sqlalchemy import text

        result = await session.execute(text(query), params)
        row = result.fetchone()

    # Extract value (default to None if no result)
    value = None
    if row is not None:
        row_dict = row._mapping
        value = float(row_dict["value"]) if row_dict["value"] is not None else None

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
```

### Update Main Endpoint

Update the call at line 156:

```python
elif isinstance(panel_config, KPIPanelConfig):
    return await _get_kpi_data(panel_id, panel_config, query_builder, tenant)  # ADD tenant
```

### Positive Test Cases

**Test 1: Successful KPI retrieval with threshold**
- **Setup**:
  - Create `metrics` table with `cpu_percent` column
  - Insert record: `cpu_percent = 85.7`
  - Panel config has thresholds: 50 (warning), 80 (critical)
- **Request**:
  ```
  GET /api/v1/panels/cpu_kpi/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - `data.value = 85.7`
  - `threshold_status = "critical"`
  - Correct threshold color applied

**Test 2: KPI with aggregation query**
- **Setup**:
  - Insert 100 records with varying values
  - Panel config query: `ORDER BY recorded_at DESC LIMIT 1`
- **Request**:
  ```
  GET /api/v1/panels/latest_cpu/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - Returns most recent value only
  - Correctly applies ORDER BY and LIMIT

### Negative Test Cases

**Test 1: Query returns no rows**
- **Setup**:
  - Empty table or WHERE clause that matches nothing
- **Request**:
  ```
  GET /api/v1/panels/cpu_kpi/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - `data.value = null`
  - Threshold status remains "good" (default)

**Test 2: Query returns NULL value**
- **Setup**:
  - Table has row but value column is NULL
- **Request**:
  ```
  GET /api/v1/panels/cpu_kpi/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - `data.value = null`
  - Gracefully handles NULL without error

---

## Handler 3: Health Status Data

### File Location
`paneldash/backend/app/api/v1/panels.py:290-346`

### Current Implementation
Returns mock services (lines 306-335):
```python
# Mock data (in real implementation, query tenant database)
mock_services = [
    {"service_name": "api", "status_value": 0},
    {"service_name": "database", "status_value": 0},
    {"service_name": "cache", "status_value": 1},
]
```

### Implementation Steps

1. **Get tenant database connection**
2. **Execute health status query**
3. **Transform rows to services list**
4. **Apply status mapping** (already implemented, lines 314-335)

### Complete Implementation

Replace lines 303-340 with:

```python
async def _get_health_status_data(
    panel_id: str,
    config: HealthStatusPanelConfig,
    query_builder: QueryBuilder,
    tenant: Tenant,  # ADD THIS PARAMETER
) -> PanelDataResponse:
    """Get health status panel data."""

    # Build query
    query, params = query_builder.build_health_status_query(config)

    # Execute query against tenant database
    async with db_manager.get_tenant_session(tenant.database_url) as session:
        from sqlalchemy import text

        result = await session.execute(text(query), params)
        rows = result.fetchall()

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

    return PanelDataResponse(
        panel_id=panel_id,
        panel_type=PanelType.HEALTH_STATUS,
        data=data,
    )
```

### Update Main Endpoint

Update the call at line 158:

```python
elif isinstance(panel_config, HealthStatusPanelConfig):
    return await _get_health_status_data(panel_id, panel_config, query_builder, tenant)  # ADD tenant
```

### Positive Test Cases

**Test 1: Successful health status retrieval**
- **Setup**:
  - Create `health_status` table with `name` (text), `status` (int)
  - Insert 3 services: api (0), database (0), cache (1)
  - Panel config maps: 0→healthy, 1→degraded, 2→down
- **Request**:
  ```
  GET /api/v1/panels/system_health/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - Returns 3 services with correct labels and colors
  - api: healthy/green, database: healthy/green, cache: degraded/yellow

**Test 2: Status value not in mapping**
- **Setup**:
  - Insert service with status value 99 (not in config mapping)
- **Request**:
  ```
  GET /api/v1/panels/system_health/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - Service shows `status_label: "unknown"`, `status_color: "#6B7280"`
  - Does not crash, handles gracefully

### Negative Test Cases

**Test 1: Empty health status table**
- **Setup**:
  - Table exists but has no rows
- **Request**:
  ```
  GET /api/v1/panels/system_health/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - Returns empty `services` array
  - No error

**Test 2: NULL status value**
- **Setup**:
  - Insert row with NULL in status_value column
- **Request**:
  ```
  GET /api/v1/panels/system_health/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 500 or gracefully skip row
  - Should handle NULL without crash (consider adding validation)

---

## Handler 4: Table Data

### File Location
`paneldash/backend/app/api/v1/panels.py:349-405`

### Current Implementation
Returns mock rows (lines 375-405):
```python
# Mock data (in real implementation, query tenant database)
page_size = config.display.pagination if config.display else 25
mock_rows = [
    {"timestamp": "2024-01-01T12:00:00Z", "message": "Error in API", "severity": "ERROR"},
    {"timestamp": "2024-01-01T11:30:00Z", "message": "DB connection lost", "severity": "CRITICAL"},
]
```

### Implementation Steps

1. **Get tenant database connection**
2. **Execute table query with pagination**
3. **Execute count query** for total rows (needed for pagination metadata)
4. **Transform results to row list**
5. **Build pagination metadata**

### Complete Implementation

Replace lines 370-399 with:

```python
async def _get_table_data(
    panel_id: str,
    config: TablePanelConfig,
    sort_column: str | None,
    sort_order: str,
    page: int,
    query_builder: QueryBuilder,
    tenant: Tenant,  # ADD THIS PARAMETER
) -> PanelDataResponse:
    """Get table panel data."""

    # Build query
    query, params = query_builder.build_table_query(
        config, sort_column, sort_order, page
    )

    # Execute query against tenant database
    async with db_manager.get_tenant_session(tenant.database_url) as session:
        from sqlalchemy import text

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

    return PanelDataResponse(
        panel_id=panel_id,
        panel_type=PanelType.TABLE,
        data=data,
    )
```

### Update Main Endpoint

Update the call at line 160:

```python
elif isinstance(panel_config, TablePanelConfig):
    return await _get_table_data(
        panel_id, panel_config, sort_column, sort_order, page, query_builder, tenant  # ADD tenant
    )
```

### Positive Test Cases

**Test 1: Successful table data retrieval with pagination**
- **Setup**:
  - Create `logs` table with columns: timestamp, message, severity
  - Insert 50 test records
  - Page size = 25
- **Request**:
  ```
  GET /api/v1/panels/error_logs/data?tenant_id=test_tenant&page=1
  ```
- **Expected Result**:
  - Status 200
  - Returns 25 rows (first page)
  - `pagination.total_rows = 50`
  - `pagination.total_pages = 2`
  - `pagination.current_page = 1`

**Test 2: Table with sorting**
- **Setup**:
  - Insert records with different timestamps
- **Request**:
  ```
  GET /api/v1/panels/error_logs/data?tenant_id=test_tenant&sort_column=timestamp&sort_order=desc
  ```
- **Expected Result**:
  - Status 200
  - Rows ordered by timestamp descending
  - Most recent record first

**Test 3: Last page (partial results)**
- **Setup**:
  - 50 records, page size 25
- **Request**:
  ```
  GET /api/v1/panels/error_logs/data?tenant_id=test_tenant&page=2
  ```
- **Expected Result**:
  - Status 200
  - Returns 25 rows (records 26-50)
  - `pagination.current_page = 2`

### Negative Test Cases

**Test 1: Page number out of bounds**
- **Setup**:
  - 10 total records, page size 25
- **Request**:
  ```
  GET /api/v1/panels/error_logs/data?tenant_id=test_tenant&page=5
  ```
- **Expected Result**:
  - Status 200
  - Returns empty rows array
  - `pagination.total_pages = 1`
  - Does not error

**Test 2: Invalid sort column**
- **Setup**:
  - Table has columns: timestamp, message, severity
- **Request**:
  ```
  GET /api/v1/panels/error_logs/data?tenant_id=test_tenant&sort_column=nonexistent
  ```
- **Expected Result**:
  - Status 400 or 422
  - Error message indicates invalid sort column
  - (Note: query_builder already validates this at line 280-283)

**Test 3: Empty table**
- **Setup**:
  - Table exists but has no rows
- **Request**:
  ```
  GET /api/v1/panels/error_logs/data?tenant_id=test_tenant
  ```
- **Expected Result**:
  - Status 200
  - Returns empty rows array
  - `pagination.total_rows = 0`
  - `pagination.total_pages = 0`

---

## Common Error Handling

All four handlers should implement consistent error handling:

### Database Connection Errors

```python
try:
    async with db_manager.get_tenant_session(tenant.database_url) as session:
        # ... execute queries
except Exception as e:
    raise HTTPException(
        status_code=503,
        detail=f"Failed to connect to tenant database: {str(e)}",
    )
```

### Query Execution Errors

```python
try:
    result = await session.execute(text(query), params)
except Exception as e:
    raise HTTPException(
        status_code=500,
        detail=f"Database query failed: {str(e)}",
    )
```

### Recommendations

1. **Wrap database operations** in try-except blocks
2. **Use specific HTTP status codes**:
   - 503: Database connection failures
   - 500: Query execution errors
   - 404: Panel or tenant not found
   - 403: Access denied
3. **Log errors** for debugging (add logging)
4. **Sanitize error messages** - don't expose credentials or internal schema
5. **Add request timeout** for tenant database queries

---

## Testing Strategy

### Unit Tests

Location: `paneldash/backend/tests/unit/`

- Test query builder functions (already exists: `test_query_builder.py`)
- Test data aggregator logic (already exists: `test_data_aggregator.py`)

### Integration Tests

Location: `paneldash/backend/tests/integration/test_panels_api.py`

The file already has test stubs. Update them to:

1. **Create real tenant databases** for testing (not mocked)
2. **Insert test data** using SQLAlchemy
3. **Execute actual API requests** (not mocking dependencies)
4. **Verify response data** matches inserted data

### Test Database Setup

Use the existing test infrastructure:

```python
@pytest.fixture
async def tenant_with_data(db_session: AsyncSession) -> Tenant:
    """Create tenant with populated database."""
    # Create tenant
    tenant = Tenant(
        tenant_id="test_tenant",
        database_name="test_metrics_db",
        database_host="localhost",
        # ...
    )
    db_session.add(tenant)
    await db_session.commit()

    # Connect to tenant database and create tables
    async with db_manager.get_tenant_session(tenant.database_url) as tenant_session:
        await tenant_session.execute(text("""
            CREATE TABLE IF NOT EXISTS metrics (
                recorded_at TIMESTAMP,
                cpu_percent FLOAT,
                server_name TEXT
            )
        """))
        await tenant_session.commit()

        # Insert test data
        # ...

    return tenant
```

---

## Migration Plan

### Phase 1: Implement (1-2 days)
1. Add database connection to all 4 handlers
2. Update function signatures (add `tenant` parameter)
3. Update all call sites in main endpoint
4. Add error handling

### Phase 2: Test (1 day)
1. Write integration tests with real databases
2. Test all positive scenarios
3. Test all negative scenarios
4. Verify error messages are appropriate

### Phase 3: Deploy (1 day)
1. Code review
2. Run full test suite
3. Deploy to staging
4. Manual QA testing
5. Deploy to production

---

## Dependencies

### Required Imports

Add to `paneldash/backend/app/api/v1/panels.py`:

```python
from sqlalchemy import text  # For raw SQL execution
from app.database import db_manager  # For tenant database access
```

### No New External Dependencies

All required libraries already in use:
- SQLAlchemy (async)
- asyncpg (PostgreSQL driver)
- FastAPI
- Pydantic

---

## Security Considerations

1. **SQL Injection Prevention**
   - QueryBuilder already uses parameterized queries
   - Never concatenate user input into SQL strings
   - Validate identifiers using `_validate_identifier()`

2. **Database Credentials**
   - Never expose credentials in error messages
   - Use connection pooling (already implemented in DatabaseManager)
   - Consider encrypting tenant database credentials in central DB

3. **Access Control**
   - Tenant access already verified in main `get_panel_data()` function
   - Don't bypass this check in handlers

4. **Resource Limits**
   - Add query timeouts (e.g., 30 seconds)
   - Consider row limits for large tables
   - Monitor connection pool exhaustion

---

## Performance Considerations

1. **Connection Pooling**
   - DatabaseManager already implements pooling (pool_size=5, max_overflow=10)
   - Reuses connections across requests

2. **Query Optimization**
   - Ensure tenant databases have proper indexes on:
     - Timestamp columns (for time series and tables)
     - Status columns (for health status)
     - Columns used in WHERE/ORDER BY clauses

3. **Pagination**
   - Table handler already limits results via pagination
   - Consider caching count queries if table is large

4. **Aggregation**
   - Time series aggregation reduces data transfer
   - Use database-side aggregation (AVG, SUM) rather than fetching all rows

---

## Rollback Plan

If issues arise after deployment:

1. **Feature Flag**: Add config setting to enable/disable real queries
   ```python
   if settings.use_real_panel_data:
       # Execute real query
   else:
       # Return mock data (current implementation)
   ```

2. **Gradual Rollout**: Enable for specific tenants first

3. **Monitoring**: Track query times and error rates

---

## Acceptance Criteria

Implementation is complete when:

- ✅ All 4 handlers execute real database queries
- ✅ All positive test cases pass
- ✅ All negative test cases pass
- ✅ Error handling implemented
- ✅ No regression in existing tests
- ✅ Code review approved
- ✅ Documentation updated

---

## Questions/Clarifications Needed

Before starting implementation, clarify:

1. **Tenant Database Schema**: Do we have migrations for tenant databases? Or does each tenant manage their own schema?
2. **Error Logging**: What logging framework should we use? (structlog, standard logging?)
3. **Monitoring**: Should we add metrics/tracing for query performance?
4. **Timeout Values**: What's the appropriate timeout for tenant database queries?

---

## Contact

For questions about this spec, contact the backend team.

**File Author**: Claude Code
**Date**: 2025-11-12
**Related Files**:
- `paneldash/backend/app/api/v1/panels.py` (implementation target)
- `paneldash/backend/app/database.py` (database manager)
- `paneldash/backend/app/services/query_builder.py` (query generation)
- `paneldash/backend/app/services/data_aggregator.py` (aggregation logic)
- `paneldash/backend/tests/integration/test_panels_api.py` (integration tests)
