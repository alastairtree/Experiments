"""Service for time-based data aggregation with bucket strategies."""

from datetime import datetime, timedelta
from enum import Enum


class BucketSize(str, Enum):
    """Time bucket sizes for aggregation."""

    NONE = "none"  # No aggregation
    MINUTE = "1 minute"
    TEN_MINUTES = "10 minutes"
    HOUR = "1 hour"


class DataAggregationStrategy:
    """Strategy for determining time bucket size based on date range."""

    @staticmethod
    def get_bucket_size(
        date_from: datetime, date_to: datetime, disable_aggregation: bool = False
    ) -> BucketSize:
        """Determine the appropriate bucket size for a date range.

        Aggregation Rules:
        - ≤ 8 hours: No aggregation (return all data points)
        - ≤ 1 day: 1 minute buckets
        - ≤ 4 days: 10 minute buckets
        - > 4 days: 1 hour buckets

        Args:
            date_from: Start date
            date_to: End date
            disable_aggregation: If True, force no aggregation

        Returns:
            BucketSize enum value
        """
        if disable_aggregation:
            return BucketSize.NONE

        time_range = date_to - date_from

        # ≤ 8 hours: No aggregation
        if time_range <= timedelta(hours=8):
            return BucketSize.NONE

        # ≤ 1 day: 1 minute buckets
        if time_range <= timedelta(days=1):
            return BucketSize.MINUTE

        # ≤ 4 days: 10 minute buckets
        if time_range <= timedelta(days=4):
            return BucketSize.TEN_MINUTES

        # > 4 days: 1 hour buckets
        return BucketSize.HOUR


class DataAggregator:
    """Handles time-based aggregation logic for panel data queries."""

    def __init__(self) -> None:
        """Initialize the data aggregator."""
        self.strategy = DataAggregationStrategy()

    def get_aggregation_sql(
        self,
        timestamp_column: str,
        value_column: str,
        bucket_size: BucketSize,
        series_label_column: str | None = None,
    ) -> str:
        """Generate SQL aggregation clause for time-based bucketing.

        Args:
            timestamp_column: Name of the timestamp column (already quoted)
            value_column: Name of the value column (already quoted)
            bucket_size: Bucket size to use for aggregation
            series_label_column: Optional series label column (already quoted)

        Returns:
            SQL SELECT clause with aggregation

        Examples:
            For 10-minute buckets:
            ```sql
            date_trunc('minute', "timestamp") -
            (EXTRACT(minute FROM "timestamp")::int % 10) * interval '1 minute' as bucket,
            AVG("value") as value
            ```

            For 1-hour buckets:
            ```sql
            date_trunc('hour', "timestamp") as bucket,
            AVG("value") as value
            ```
        """
        if bucket_size == BucketSize.NONE:
            # No aggregation - return raw columns
            parts = [
                f"{timestamp_column} AS timestamp",
                f"{value_column} AS value",
            ]
            if series_label_column:
                parts.append(f"{series_label_column} AS series_label")
            return ", ".join(parts)

        # Generate bucket expression based on size
        if bucket_size == BucketSize.MINUTE:
            bucket_expr = f"date_trunc('minute', {timestamp_column})"
        elif bucket_size == BucketSize.TEN_MINUTES:
            bucket_expr = (
                f"date_trunc('minute', {timestamp_column}) - "
                f"(EXTRACT(minute FROM {timestamp_column})::int % 10) * interval '1 minute'"
            )
        elif bucket_size == BucketSize.HOUR:
            bucket_expr = f"date_trunc('hour', {timestamp_column})"
        else:
            raise ValueError(f"Unsupported bucket size: {bucket_size}")

        # Build aggregation SELECT clause
        parts = [
            f"{bucket_expr} AS timestamp",
            f"AVG({value_column}) AS value",
        ]

        if series_label_column:
            # Include series label in selection and grouping
            parts.append(f"{series_label_column} AS series_label")

        return ", ".join(parts)

    def get_group_by_clause(
        self, bucket_size: BucketSize, has_series_label: bool = False
    ) -> str:
        """Generate SQL GROUP BY clause for aggregation.

        Args:
            bucket_size: Bucket size being used
            has_series_label: Whether query includes series label

        Returns:
            GROUP BY clause or empty string if no aggregation
        """
        if bucket_size == BucketSize.NONE:
            return ""

        group_by_parts = ["timestamp"]
        if has_series_label:
            group_by_parts.append("series_label")

        return "GROUP BY " + ", ".join(group_by_parts)

    def build_aggregated_query(
        self,
        base_query: str,
        timestamp_column: str,
        value_column: str,
        date_from: datetime,
        date_to: datetime,
        series_label_column: str | None = None,
        disable_aggregation: bool = False,
    ) -> str:
        """Build a complete aggregated query from a base query.

        Args:
            base_query: Base SELECT query without aggregation
            timestamp_column: Timestamp column name (quoted)
            value_column: Value column name (quoted)
            date_from: Start date
            date_to: End date
            series_label_column: Optional series label column (quoted)
            disable_aggregation: Force no aggregation

        Returns:
            Complete SQL query with aggregation applied
        """
        # Determine bucket size
        bucket_size = self.strategy.get_bucket_size(
            date_from, date_to, disable_aggregation
        )

        if bucket_size == BucketSize.NONE:
            # No aggregation needed - return original query
            return base_query

        # Modify query to use aggregation
        # This replaces the SELECT columns with aggregated versions
        # and adds GROUP BY clause

        # Note: This is a simplified implementation
        # In production, you might use SQL parsing libraries
        # For now, this provides the aggregation logic that can be
        # integrated into the query builder

        select_clause = self.get_aggregation_sql(
            timestamp_column, value_column, bucket_size, series_label_column
        )

        group_by_clause = self.get_group_by_clause(
            bucket_size, has_series_label=series_label_column is not None
        )

        # Return the aggregation components
        # Actual integration happens in query_builder
        return f"{select_clause}|{group_by_clause}"

    def should_aggregate(
        self, date_from: datetime, date_to: datetime, disable_aggregation: bool = False
    ) -> bool:
        """Check if aggregation should be applied for a date range.

        Args:
            date_from: Start date
            date_to: End date
            disable_aggregation: Force no aggregation

        Returns:
            True if aggregation should be applied
        """
        bucket_size = self.strategy.get_bucket_size(
            date_from, date_to, disable_aggregation
        )
        return bucket_size != BucketSize.NONE

    def get_bucket_interval(
        self, date_from: datetime, date_to: datetime, disable_aggregation: bool = False
    ) -> str:
        """Get the bucket interval description for a date range.

        Args:
            date_from: Start date
            date_to: End date
            disable_aggregation: Force no aggregation

        Returns:
            Human-readable bucket interval (e.g., "1 minute", "10 minutes")
        """
        bucket_size = self.strategy.get_bucket_size(
            date_from, date_to, disable_aggregation
        )
        if bucket_size == BucketSize.NONE:
            return "No aggregation"
        return str(bucket_size.value)


# Singleton instance
def get_data_aggregator() -> DataAggregator:
    """Get the singleton DataAggregator instance.

    Returns:
        DataAggregator instance
    """
    return DataAggregator()
