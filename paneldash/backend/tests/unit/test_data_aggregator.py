"""Unit tests for data aggregation service."""

from datetime import datetime, timedelta

import pytest

from app.services.data_aggregator import (
    BucketSize,
    DataAggregationStrategy,
    DataAggregator,
)


@pytest.fixture
def aggregator() -> DataAggregator:
    """Create a DataAggregator instance for testing."""
    return DataAggregator()


@pytest.fixture
def strategy() -> DataAggregationStrategy:
    """Create a DataAggregationStrategy instance for testing."""
    return DataAggregationStrategy()


class TestBucketSizeStrategy:
    """Test bucket size determination based on date range."""

    def test_no_aggregation_for_short_range(
        self, strategy: DataAggregationStrategy
    ) -> None:
        """Test that ranges ≤ 8 hours get no aggregation."""
        now = datetime(2024, 1, 1, 12, 0, 0)

        # 1 hour - no aggregation
        date_from = now
        date_to = now + timedelta(hours=1)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.NONE

        # 8 hours - no aggregation
        date_from = now
        date_to = now + timedelta(hours=8)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.NONE

        # 4 hours - no aggregation
        date_from = now
        date_to = now + timedelta(hours=4)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.NONE

    def test_minute_buckets_for_one_day(
        self, strategy: DataAggregationStrategy
    ) -> None:
        """Test that ranges ≤ 1 day get 1-minute buckets."""
        now = datetime(2024, 1, 1, 0, 0, 0)

        # 9 hours - 1 minute buckets
        date_from = now
        date_to = now + timedelta(hours=9)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.MINUTE

        # 24 hours - 1 minute buckets
        date_from = now
        date_to = now + timedelta(days=1)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.MINUTE

        # 23 hours - 1 minute buckets
        date_from = now
        date_to = now + timedelta(hours=23)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.MINUTE

    def test_ten_minute_buckets_for_four_days(
        self, strategy: DataAggregationStrategy
    ) -> None:
        """Test that ranges ≤ 4 days get 10-minute buckets."""
        now = datetime(2024, 1, 1, 0, 0, 0)

        # 2 days - 10 minute buckets
        date_from = now
        date_to = now + timedelta(days=2)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.TEN_MINUTES

        # 4 days - 10 minute buckets
        date_from = now
        date_to = now + timedelta(days=4)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.TEN_MINUTES

        # 3.5 days - 10 minute buckets
        date_from = now
        date_to = now + timedelta(days=3, hours=12)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.TEN_MINUTES

    def test_hour_buckets_for_long_range(
        self, strategy: DataAggregationStrategy
    ) -> None:
        """Test that ranges > 4 days get 1-hour buckets."""
        now = datetime(2024, 1, 1, 0, 0, 0)

        # 5 days - 1 hour buckets
        date_from = now
        date_to = now + timedelta(days=5)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.HOUR

        # 7 days - 1 hour buckets
        date_from = now
        date_to = now + timedelta(days=7)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.HOUR

        # 30 days - 1 hour buckets
        date_from = now
        date_to = now + timedelta(days=30)
        assert strategy.get_bucket_size(date_from, date_to) == BucketSize.HOUR

    def test_disable_aggregation_flag(
        self, strategy: DataAggregationStrategy
    ) -> None:
        """Test that disable_aggregation flag forces no aggregation."""
        now = datetime(2024, 1, 1, 0, 0, 0)

        # Large range that would normally get hour buckets
        date_from = now
        date_to = now + timedelta(days=30)

        # Without flag - should get hour buckets
        assert strategy.get_bucket_size(date_from, date_to, False) == BucketSize.HOUR

        # With flag - should get no aggregation
        assert (
            strategy.get_bucket_size(date_from, date_to, True) == BucketSize.NONE
        )


class TestAggregationSQL:
    """Test SQL generation for aggregation."""

    def test_no_aggregation_sql(self, aggregator: DataAggregator) -> None:
        """Test SQL generation with no aggregation."""
        sql = aggregator.get_aggregation_sql(
            '"timestamp"', '"value"', BucketSize.NONE
        )

        assert '"timestamp" AS timestamp' in sql
        assert '"value" AS value' in sql
        assert "AVG" not in sql
        assert "date_trunc" not in sql

    def test_no_aggregation_sql_with_series_label(
        self, aggregator: DataAggregator
    ) -> None:
        """Test SQL generation with no aggregation and series label."""
        sql = aggregator.get_aggregation_sql(
            '"timestamp"', '"value"', BucketSize.NONE, '"server"'
        )

        assert '"timestamp" AS timestamp' in sql
        assert '"value" AS value' in sql
        assert '"server" AS series_label' in sql

    def test_minute_bucket_sql(self, aggregator: DataAggregator) -> None:
        """Test SQL generation for 1-minute buckets."""
        sql = aggregator.get_aggregation_sql(
            '"timestamp"', '"value"', BucketSize.MINUTE
        )

        assert "date_trunc('minute', \"timestamp\")" in sql
        assert "AVG(\"value\") AS value" in sql
        assert "AS timestamp" in sql

    def test_ten_minute_bucket_sql(self, aggregator: DataAggregator) -> None:
        """Test SQL generation for 10-minute buckets."""
        sql = aggregator.get_aggregation_sql(
            '"timestamp"', '"value"', BucketSize.TEN_MINUTES
        )

        assert "date_trunc('minute', \"timestamp\")" in sql
        assert "EXTRACT(minute FROM \"timestamp\")::int % 10" in sql
        assert "interval '1 minute'" in sql
        assert "AVG(\"value\") AS value" in sql

    def test_hour_bucket_sql(self, aggregator: DataAggregator) -> None:
        """Test SQL generation for 1-hour buckets."""
        sql = aggregator.get_aggregation_sql(
            '"timestamp"', '"value"', BucketSize.HOUR
        )

        assert "date_trunc('hour', \"timestamp\")" in sql
        assert "AVG(\"value\") AS value" in sql

    def test_aggregation_sql_with_series_label(
        self, aggregator: DataAggregator
    ) -> None:
        """Test SQL generation with series label for multiple series."""
        sql = aggregator.get_aggregation_sql(
            '"timestamp"', '"value"', BucketSize.HOUR, '"server"'
        )

        assert "date_trunc('hour', \"timestamp\")" in sql
        assert "AVG(\"value\") AS value" in sql
        assert '"server" AS series_label' in sql

    def test_unsupported_bucket_size_raises_error(
        self, aggregator: DataAggregator
    ) -> None:
        """Test that unsupported bucket sizes raise ValueError."""
        # Create an invalid bucket size (this shouldn't happen in practice)
        invalid_size = "invalid"

        with pytest.raises(ValueError, match="Unsupported bucket size"):
            aggregator.get_aggregation_sql('"timestamp"', '"value"', invalid_size)  # type: ignore


class TestGroupByClause:
    """Test GROUP BY clause generation."""

    def test_no_group_by_for_no_aggregation(
        self, aggregator: DataAggregator
    ) -> None:
        """Test that no GROUP BY is generated when no aggregation."""
        group_by = aggregator.get_group_by_clause(BucketSize.NONE)
        assert group_by == ""

    def test_group_by_timestamp_only(self, aggregator: DataAggregator) -> None:
        """Test GROUP BY with timestamp only."""
        group_by = aggregator.get_group_by_clause(BucketSize.MINUTE, False)
        assert group_by == "GROUP BY timestamp"

    def test_group_by_with_series_label(self, aggregator: DataAggregator) -> None:
        """Test GROUP BY with timestamp and series label."""
        group_by = aggregator.get_group_by_clause(BucketSize.HOUR, True)
        assert group_by == "GROUP BY timestamp, series_label"

    def test_group_by_for_all_bucket_sizes(self, aggregator: DataAggregator) -> None:
        """Test that GROUP BY is generated for all non-none bucket sizes."""
        assert aggregator.get_group_by_clause(BucketSize.MINUTE, False) != ""
        assert aggregator.get_group_by_clause(BucketSize.TEN_MINUTES, False) != ""
        assert aggregator.get_group_by_clause(BucketSize.HOUR, False) != ""


class TestShouldAggregate:
    """Test aggregation decision logic."""

    def test_should_not_aggregate_short_range(
        self, aggregator: DataAggregator
    ) -> None:
        """Test that short ranges don't trigger aggregation."""
        now = datetime(2024, 1, 1, 12, 0, 0)
        date_from = now
        date_to = now + timedelta(hours=4)

        assert aggregator.should_aggregate(date_from, date_to) is False

    def test_should_aggregate_long_range(self, aggregator: DataAggregator) -> None:
        """Test that long ranges trigger aggregation."""
        now = datetime(2024, 1, 1, 0, 0, 0)
        date_from = now
        date_to = now + timedelta(days=7)

        assert aggregator.should_aggregate(date_from, date_to) is True

    def test_should_not_aggregate_when_disabled(
        self, aggregator: DataAggregator
    ) -> None:
        """Test that disable_aggregation flag prevents aggregation."""
        now = datetime(2024, 1, 1, 0, 0, 0)
        date_from = now
        date_to = now + timedelta(days=30)

        assert aggregator.should_aggregate(date_from, date_to, False) is True
        assert aggregator.should_aggregate(date_from, date_to, True) is False


class TestBucketInterval:
    """Test bucket interval description."""

    def test_no_aggregation_interval(self, aggregator: DataAggregator) -> None:
        """Test interval description for no aggregation."""
        now = datetime(2024, 1, 1, 12, 0, 0)
        date_from = now
        date_to = now + timedelta(hours=4)

        interval = aggregator.get_bucket_interval(date_from, date_to)
        assert interval == "No aggregation"

    def test_minute_interval(self, aggregator: DataAggregator) -> None:
        """Test interval description for minute buckets."""
        now = datetime(2024, 1, 1, 0, 0, 0)
        date_from = now
        date_to = now + timedelta(hours=12)

        interval = aggregator.get_bucket_interval(date_from, date_to)
        assert interval == "1 minute"

    def test_ten_minute_interval(self, aggregator: DataAggregator) -> None:
        """Test interval description for 10-minute buckets."""
        now = datetime(2024, 1, 1, 0, 0, 0)
        date_from = now
        date_to = now + timedelta(days=3)

        interval = aggregator.get_bucket_interval(date_from, date_to)
        assert interval == "10 minutes"

    def test_hour_interval(self, aggregator: DataAggregator) -> None:
        """Test interval description for hour buckets."""
        now = datetime(2024, 1, 1, 0, 0, 0)
        date_from = now
        date_to = now + timedelta(days=7)

        interval = aggregator.get_bucket_interval(date_from, date_to)
        assert interval == "1 hour"


class TestBuildAggregatedQuery:
    """Test complete aggregated query building."""

    def test_build_query_no_aggregation(self, aggregator: DataAggregator) -> None:
        """Test building query with no aggregation."""
        now = datetime(2024, 1, 1, 12, 0, 0)
        date_from = now
        date_to = now + timedelta(hours=4)

        base_query = 'SELECT "timestamp", "value" FROM metrics'

        result = aggregator.build_aggregated_query(
            base_query, '"timestamp"', '"value"', date_from, date_to
        )

        # Should return base query when no aggregation
        assert result == base_query

    def test_build_query_with_aggregation(self, aggregator: DataAggregator) -> None:
        """Test building query with aggregation."""
        now = datetime(2024, 1, 1, 0, 0, 0)
        date_from = now
        date_to = now + timedelta(days=7)

        base_query = 'SELECT "timestamp", "value" FROM metrics'

        result = aggregator.build_aggregated_query(
            base_query, '"timestamp"', '"value"', date_from, date_to
        )

        # Should include aggregation components
        assert "date_trunc('hour'" in result
        assert "AVG" in result
        assert "GROUP BY" in result

    def test_build_query_with_disable_flag(self, aggregator: DataAggregator) -> None:
        """Test that disable_aggregation flag prevents aggregation in query."""
        now = datetime(2024, 1, 1, 0, 0, 0)
        date_from = now
        date_to = now + timedelta(days=30)

        base_query = 'SELECT "timestamp", "value" FROM metrics'

        result = aggregator.build_aggregated_query(
            base_query,
            '"timestamp"',
            '"value"',
            date_from,
            date_to,
            disable_aggregation=True,
        )

        # Should return base query when aggregation disabled
        assert result == base_query
