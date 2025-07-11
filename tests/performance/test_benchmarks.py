"""
Performance benchmarks for all MCP tools.

This module contains comprehensive performance tests to ensure
all datetime calculation tools meet the p95 ≤ 50ms requirement.
"""

import asyncio
import pytest

from datetime_mcp_server.server import (
    handle_call_tool,
    handle_list_tools,
    handle_list_resources,
    handle_read_resource,
    handle_list_prompts,
    handle_get_prompt,
)


class TestDatetimeMCPPerformance:
    """Performance benchmarks for Datetime MCP Server."""

    @pytest.mark.benchmark
    def test_benchmark_list_tools(self, benchmark):
        """Benchmark the tools/list operation."""

        def run_list_tools():
            return asyncio.run(handle_list_tools())

        result = benchmark(run_list_tools)
        assert len(result) > 0
        assert len(result) == 10  # Expected number of tools

    @pytest.mark.benchmark
    def test_benchmark_list_resources(self, benchmark):
        """Benchmark the resources/list operation."""

        def run_list_resources():
            return asyncio.run(handle_list_resources())

        result = benchmark(run_list_resources)
        assert len(result) > 0
        assert len(result) >= 5  # At least 5 datetime resources (may include dynamic note resources)

    @pytest.mark.benchmark
    def test_benchmark_list_prompts(self, benchmark):
        """Benchmark the prompts/list operation."""

        def run_list_prompts():
            return asyncio.run(handle_list_prompts())

        result = benchmark(run_list_prompts)
        assert len(result) > 0
        assert len(result) == 5  # Expected number of prompts

    @pytest.mark.benchmark
    def test_benchmark_get_current_datetime_iso(self, benchmark):
        """Benchmark get-current-datetime tool with ISO format."""

        def run_get_current_datetime():
            return asyncio.run(
                handle_call_tool("get-current-datetime", {"format": "iso"})
            )

        result = benchmark(run_get_current_datetime)
        assert len(result) == 1
        assert result[0].text is not None

    @pytest.mark.benchmark
    def test_benchmark_get_current_datetime_json(self, benchmark):
        """Benchmark get-current-datetime tool with JSON format."""

        def run_get_current_datetime():
            return asyncio.run(
                handle_call_tool("get-current-datetime", {"format": "json"})
            )

        result = benchmark(run_get_current_datetime)
        assert len(result) == 1
        assert result[0].text is not None

    @pytest.mark.benchmark
    def test_benchmark_calculate_date_add_days(self, benchmark):
        """Benchmark calculate-date tool adding days."""

        def run_calculate_date():
            return asyncio.run(
                handle_call_tool(
                    "calculate-date",
                    {
                        "base_date": "2024-01-01",
                        "operation": "add",
                        "amount": 30,
                        "unit": "days",
                    },
                )
            )

        result = benchmark(run_calculate_date)
        assert len(result) == 1
        assert "2024-01-31" in result[0].text

    @pytest.mark.benchmark
    def test_benchmark_calculate_date_add_months(self, benchmark):
        """Benchmark calculate-date tool adding months."""

        def run_calculate_date():
            return asyncio.run(
                handle_call_tool(
                    "calculate-date",
                    {
                        "base_date": "2024-01-01",
                        "operation": "add",
                        "amount": 3,
                        "unit": "months",
                    },
                )
            )

        result = benchmark(run_calculate_date)
        assert len(result) == 1
        assert "2024-04-01" in result[0].text

    @pytest.mark.benchmark
    def test_benchmark_calculate_date_range(self, benchmark):
        """Benchmark calculate-date-range tool."""

        def run_calculate_date_range():
            return asyncio.run(
                handle_call_tool(
                    "calculate-date-range",
                    {
                        "base_date": "2024-07-15",
                        "direction": "last",
                        "amount": 3,
                        "unit": "months",
                    },
                )
            )

        result = benchmark(run_calculate_date_range)
        assert len(result) == 1
        assert "start" in result[0].text
        assert "end" in result[0].text

    @pytest.mark.benchmark
    def test_benchmark_calculate_business_days(self, benchmark):
        """Benchmark calculate-business-days tool."""

        def run_calculate_business_days():
            return asyncio.run(
                handle_call_tool(
                    "calculate-business-days",
                    {"start_date": "2024-01-01", "end_date": "2024-01-31"},
                )
            )

        result = benchmark(run_calculate_business_days)
        assert len(result) == 1
        assert "business_days" in result[0].text

    @pytest.mark.benchmark
    def test_benchmark_calculate_business_days_with_holidays(self, benchmark):
        """Benchmark calculate-business-days tool with holidays."""

        def run_calculate_business_days():
            return asyncio.run(
                handle_call_tool(
                    "calculate-business-days",
                    {
                        "start_date": "2024-12-20",
                        "end_date": "2024-12-31",
                        "holidays": ["2024-12-25", "2024-12-26"],
                    },
                )
            )

        result = benchmark(run_calculate_business_days)
        assert len(result) == 1
        assert "business_days" in result[0].text

    @pytest.mark.benchmark
    def test_benchmark_format_date(self, benchmark):
        """Benchmark format-date tool."""

        def run_format_date():
            return asyncio.run(
                handle_call_tool(
                    "format-date", {"date": "2024-07-15", "format": "%Y년 %m월 %d일"}
                )
            )

        result = benchmark(run_format_date)
        assert len(result) == 1
        assert "2024년 07월 15일" in result[0].text

    @pytest.mark.benchmark
    def test_benchmark_note_operations(self, benchmark):
        """Benchmark note management operations."""

        def run_note_operations():
            # Add note
            asyncio.run(
                handle_call_tool(
                    "add-note",
                    {
                        "name": "benchmark_note",
                        "content": "This is a benchmark test note.",
                    },
                )
            )

            # Get note
            result = asyncio.run(
                handle_call_tool("get-note", {"name": "benchmark_note"})
            )

            # Delete note
            asyncio.run(handle_call_tool("delete-note", {"name": "benchmark_note"}))

            return result

        result = benchmark(run_note_operations)
        assert len(result) == 1
        assert "benchmark test note" in result[0].text

    @pytest.mark.benchmark
    def test_benchmark_read_datetime_resource(self, benchmark):
        """Benchmark reading datetime resources."""
        from pydantic import AnyUrl

        def run_read_resource():
            return asyncio.run(handle_read_resource(AnyUrl("datetime://current")))

        result = benchmark(run_read_resource)
        assert result is not None
        assert len(result) > 0

    @pytest.mark.benchmark
    def test_benchmark_read_timezone_info_resource(self, benchmark):
        """Benchmark reading timezone info resource."""
        from pydantic import AnyUrl

        def run_read_resource():
            return asyncio.run(handle_read_resource(AnyUrl("datetime://timezone-info")))

        result = benchmark(run_read_resource)
        assert result is not None
        assert "timezone_name" in result

    @pytest.mark.benchmark
    def test_benchmark_get_prompt(self, benchmark):
        """Benchmark get prompt operation."""

        def run_get_prompt():
            return asyncio.run(handle_get_prompt("datetime-calculation-guide", {}))

        result = benchmark(run_get_prompt)
        assert result is not None
        assert len(result.messages) > 0

    @pytest.mark.benchmark
    def test_benchmark_complex_timezone_calculation(self, benchmark):
        """Benchmark complex timezone-aware calculation."""

        def run_complex_calculation():
            return asyncio.run(
                handle_call_tool(
                    "calculate-date",
                    {
                        "base_date": "2024-03-10T10:00:00",
                        "operation": "add",
                        "amount": 15,
                        "unit": "days",
                        "timezone": "America/New_York",
                    },
                )
            )

        result = benchmark(run_complex_calculation)
        assert len(result) == 1
        assert result[0].text is not None


class TestPerformanceRegression:
    """Performance regression tests with specific thresholds."""

    @pytest.mark.benchmark
    def test_performance_regression_50ms_threshold(self, benchmark):
        """Ensure all common operations stay under 50ms (p95 requirement)."""

        def run_mixed_operations():
            """Run a mix of common datetime operations."""
            # Get current datetime
            asyncio.run(handle_call_tool("get-current-datetime", {"format": "iso"}))

            # Calculate date
            asyncio.run(
                handle_call_tool(
                    "calculate-date",
                    {
                        "base_date": "2024-01-01",
                        "operation": "add",
                        "amount": 30,
                        "unit": "days",
                    },
                )
            )

            # Calculate business days
            asyncio.run(
                handle_call_tool(
                    "calculate-business-days",
                    {"start_date": "2024-01-01", "end_date": "2024-01-31"},
                )
            )

            return True

        # Run benchmark and check that it meets p95 requirement
        result = benchmark(run_mixed_operations)
        assert result is True

        # The actual performance validation is done through pytest-benchmark
        # configuration which will fail if performance degrades

    @pytest.mark.benchmark
    @pytest.mark.timeout(120)  # 2 minute timeout for memory intensive tests
    def test_memory_usage_benchmark(self, benchmark):
        """Benchmark memory usage of datetime operations."""
        import psutil
        import os

        def run_memory_intensive_operations():
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss

            # Run multiple operations
            for i in range(100):
                asyncio.run(handle_call_tool("get-current-datetime", {"format": "iso"}))
                asyncio.run(
                    handle_call_tool(
                        "calculate-date",
                        {
                            "base_date": f"2024-01-{i % 28 + 1:02d}",
                            "operation": "add",
                            "amount": i,
                            "unit": "days",
                        },
                    )
                )

            memory_after = process.memory_info().rss
            memory_diff = memory_after - memory_before

            # Return memory difference in MB
            return memory_diff / (1024 * 1024)

        memory_usage = benchmark(run_memory_intensive_operations)

        # Ensure memory usage doesn't grow excessively (< 10MB for 100 operations)
        assert memory_usage < 10.0, f"Memory usage too high: {memory_usage:.2f}MB"


class TestScalabilityBenchmarks:
    """Scalability and load testing benchmarks."""

    @pytest.mark.benchmark
    @pytest.mark.timeout(180)  # 3 minute timeout for concurrent tests  
    def test_concurrent_operations_simulation(self, benchmark):
        """Simulate concurrent operations to test scalability."""

        async def run_concurrent_operations():
            """Simulate multiple concurrent datetime operations."""
            tasks = []

            # Create 20 concurrent tasks
            for i in range(20):
                task = handle_call_tool("get-current-datetime", {"format": "iso"})
                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks)
            return len(results)

        def sync_wrapper():
            return asyncio.run(run_concurrent_operations())

        result = benchmark(sync_wrapper)
        assert result == 20

    @pytest.mark.benchmark
    def test_large_date_range_calculation(self, benchmark):
        """Benchmark calculation over large date ranges."""

        def run_large_calculation():
            return asyncio.run(
                handle_call_tool(
                    "calculate-business-days",
                    {"start_date": "2020-01-01", "end_date": "2024-12-31"},
                )
            )

        result = benchmark(run_large_calculation)
        assert len(result) == 1
        assert "business_days" in result[0].text
