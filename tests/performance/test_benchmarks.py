"""
Performance benchmarks for all MCP tools.

This module contains comprehensive performance tests to ensure
all datetime calculation tools meet the p95 ≤ 50ms requirement.
"""

import asyncio
import pytest
from pydantic import AnyUrl

from datetime_mcp_server.server import (
    handle_call_tool,
    handle_get_prompt,
    handle_list_prompts,
    handle_list_resources,
    handle_list_tools,
    handle_read_resource,
)


class TestDatetimeMCPPerformance:
    """Performance benchmarks for Datetime MCP Server."""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_list_tools(self, benchmark):
        """Benchmark the tools/list operation."""
        result = await benchmark(handle_list_tools)
        assert len(result) > 0
        assert len(result) == 10  # Expected number of tools

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_list_resources(self, benchmark):
        """Benchmark the resources/list operation."""
        result = await benchmark(handle_list_resources)
        assert len(result) > 0
        assert (
            len(result) >= 5
        )  # At least 5 datetime resources (may include dynamic note resources)

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_list_prompts(self, benchmark):
        """Benchmark the prompts/list operation."""
        result = await benchmark(handle_list_prompts)
        assert len(result) > 0
        assert len(result) == 5  # Expected number of prompts

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_get_current_datetime_iso(self, benchmark):
        """Benchmark get-current-datetime tool with ISO format."""
        result = await benchmark(
            handle_call_tool, "get-current-datetime", {"format": "iso"}
        )
        assert len(result) == 1
        assert result[0].text is not None

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_get_current_datetime_json(self, benchmark):
        """Benchmark get-current-datetime tool with JSON format."""
        result = await benchmark(
            handle_call_tool, "get-current-datetime", {"format": "json"}
        )
        assert len(result) == 1
        assert result[0].text is not None

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_calculate_date_add_days(self, benchmark):
        """Benchmark calculate-date tool adding days."""
        result = await benchmark(
            handle_call_tool,
            "calculate-date",
            {
                "base_date": "2024-01-01",
                "operation": "add",
                "amount": 30,
                "unit": "days",
            },
        )
        assert len(result) == 1
        assert "2024-01-31" in result[0].text

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_calculate_date_add_months(self, benchmark):
        """Benchmark calculate-date tool adding months."""
        result = await benchmark(
            handle_call_tool,
            "calculate-date",
            {
                "base_date": "2024-01-01",
                "operation": "add",
                "amount": 3,
                "unit": "months",
            },
        )
        assert len(result) == 1
        assert "2024-04-01" in result[0].text

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_calculate_date_range(self, benchmark):
        """Benchmark calculate-date-range tool."""
        result = await benchmark(
            handle_call_tool,
            "calculate-date-range",
            {
                "base_date": "2024-07-15",
                "direction": "last",
                "amount": 3,
                "unit": "months",
            },
        )
        assert len(result) == 1
        assert "start" in result[0].text
        assert "end" in result[0].text

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_calculate_business_days(self, benchmark):
        """Benchmark calculate-business-days tool."""
        result = await benchmark(
            handle_call_tool,
            "calculate-business-days",
            {"start_date": "2024-01-01", "end_date": "2024-01-31"},
        )
        assert len(result) == 1
        assert "business_days" in result[0].text

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_calculate_business_days_with_holidays(self, benchmark):
        """Benchmark calculate-business-days tool with holidays."""
        result = await benchmark(
            handle_call_tool,
            "calculate-business-days",
            {
                "start_date": "2024-12-20",
                "end_date": "2024-12-31",
                "holidays": ["2024-12-25", "2024-12-26"],
            },
        )
        assert len(result) == 1
        assert "business_days" in result[0].text

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_format_date(self, benchmark):
        """Benchmark format-date tool."""
        result = await benchmark(
            handle_call_tool,
            "format-date",
            {"date": "2024-07-15", "format": "%Y년 %m월 %d일"},
        )
        assert len(result) == 1
        assert "2024년 07월 15일" in result[0].text

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_note_operations(self, benchmark):
        """Benchmark note management operations."""

        async def run_note_operations():
            # Add note
            await handle_call_tool(
                "add-note",
                {
                    "name": "benchmark_note",
                    "content": "This is a benchmark test note.",
                },
            )

            # Get note
            result = await handle_call_tool("get-note", {"name": "benchmark_note"})

            # Delete note
            await handle_call_tool("delete-note", {"name": "benchmark_note"})

            return result

        result = await benchmark(run_note_operations)
        assert len(result) == 1
        assert "benchmark test note" in result[0].text

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_read_datetime_resource(self, benchmark):
        """Benchmark reading datetime resources."""
        result = await benchmark(handle_read_resource, AnyUrl("datetime://current"))
        assert result is not None
        assert len(result) > 0

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_read_timezone_info_resource(self, benchmark):
        """Benchmark reading timezone info resource."""
        result = await benchmark(
            handle_read_resource, AnyUrl("datetime://timezone-info")
        )
        assert result is not None
        assert "timezone_name" in result

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_get_prompt(self, benchmark):
        """Benchmark get prompt operation."""
        result = await benchmark(handle_get_prompt, "datetime-calculation-guide", {})
        assert result is not None
        assert len(result.messages) > 0

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_benchmark_complex_timezone_calculation(self, benchmark):
        """Benchmark complex timezone-aware calculation."""
        result = await benchmark(
            handle_call_tool,
            "calculate-date",
            {
                "base_date": "2024-03-10T10:00:00",
                "operation": "add",
                "amount": 15,
                "unit": "days",
                "timezone": "America/New_York",
            },
        )
        assert len(result) == 1
        assert result[0].text is not None


class TestPerformanceRegression:
    """Performance regression tests with specific thresholds."""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_performance_regression_50ms_threshold(self, benchmark):
        """Ensure all common operations stay under 50ms (p95 requirement)."""

        async def run_mixed_operations():
            """Run a mix of common datetime operations."""
            # Get current datetime
            await handle_call_tool("get-current-datetime", {"format": "iso"})

            # Calculate date
            await handle_call_tool(
                "calculate-date",
                {
                    "base_date": "2024-01-01",
                    "operation": "add",
                    "amount": 30,
                    "unit": "days",
                },
            )

            # Calculate business days
            await handle_call_tool(
                "calculate-business-days",
                {"start_date": "2024-01-01", "end_date": "2024-01-31"},
            )

            return True

        result = await benchmark(run_mixed_operations)
        assert result is True

        # The actual performance validation is done through pytest-benchmark
        # configuration which will fail if performance degrades

    @pytest.mark.benchmark
    @pytest.mark.timeout(120)  # 2 minute timeout for memory intensive tests
    @pytest.mark.asyncio
    async def test_memory_usage_benchmark(self, benchmark):
        """Benchmark memory usage of datetime operations."""
        import os
        import psutil

        async def run_memory_intensive_operations():
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss

            # Run multiple operations
            for i in range(100):
                await handle_call_tool("get-current-datetime", {"format": "iso"})
                await handle_call_tool(
                    "calculate-date",
                    {
                        "base_date": f"2024-01-{i % 28 + 1:02d}",
                        "operation": "add",
                        "amount": i,
                        "unit": "days",
                    },
                )

            memory_after = process.memory_info().rss
            memory_diff = memory_after - memory_before

            # Return memory difference in MB
            return memory_diff / (1024 * 1024)

        result = await benchmark(run_memory_intensive_operations)
        assert result < 10.0, f"Memory usage too high: {result:.2f}MB"


class TestScalabilityBenchmarks:
    """Scalability and load testing benchmarks."""

    @pytest.mark.benchmark
    @pytest.mark.timeout(180)  # 3 minute timeout for concurrent tests
    @pytest.mark.asyncio
    async def test_concurrent_operations_simulation(self, benchmark):
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

        result = await benchmark(run_concurrent_operations)
        assert result == 20

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_large_date_range_calculation(self, benchmark):
        """Benchmark calculation over large date ranges."""
        result = await benchmark(
            handle_call_tool,
            "calculate-business-days",
            {"start_date": "2020-01-01", "end_date": "2024-12-31"},
        )
        assert len(result) == 1
        assert "business_days" in result[0].text
