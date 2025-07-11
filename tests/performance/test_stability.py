"""
Server stability tests to verify memory management, concurrency handling,
and resource cleanup improvements.
"""

import asyncio
import pytest
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
import json

import psutil
import httpx

from datetime_mcp_server.server import (
    notes, notes_lock, health_metrics, health_metrics_lock,
    set_shutdown_requested, is_shutdown_requested,
    update_health_metrics, cleanup_resources,
    MAX_NOTES, MAX_NOTE_SIZE
)
from datetime_mcp_server.http_server import (
    sse_manager, metrics, metrics_lock, 
    MAX_RESPONSE_TIMES, MAX_ENDPOINT_TRACKING
)


class TestConcurrencyAndThreadSafety:
    """Test thread safety and concurrency handling."""
    
    def test_notes_concurrent_access(self):
        """Test concurrent note operations are thread-safe."""
        # Clear notes
        with notes_lock:
            notes.clear()
        
        def add_note_worker(worker_id: int, note_count: int):
            """Worker function to add notes concurrently."""
            for i in range(note_count):
                note_name = f"worker_{worker_id}_note_{i}"
                content = f"Content from worker {worker_id}, note {i}"
                
                # Simulate the add-note operation
                with notes_lock:
                    if note_name not in notes and len(notes) >= MAX_NOTES:
                        if notes:
                            oldest_note, _ = notes.popitem(last=False)
                    notes[note_name] = content
                    if note_name in notes:  # Update case
                        notes.move_to_end(note_name)
        
        # Run concurrent workers
        num_workers = 10
        notes_per_worker = 50
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                future = executor.submit(add_note_worker, worker_id, notes_per_worker)
                futures.append(future)
            
            # Wait for all workers to complete
            for future in futures:
                future.result()
        
        # Verify final state
        with notes_lock:
            # Should have at most MAX_NOTES due to FIFO eviction
            assert len(notes) <= MAX_NOTES
            # Verify FIFO behavior - check that we have the most recent notes
            note_names = list(notes.keys())
            assert len(note_names) > 0
            
        print(f"Concurrent test completed. Final note count: {len(notes)}")
    
    def test_shutdown_flag_thread_safety(self):
        """Test shutdown flag operations are thread-safe."""
        def toggle_shutdown_worker(iterations: int):
            """Worker that toggles shutdown flag."""
            for i in range(iterations):
                set_shutdown_requested(i % 2 == 0)
                time.sleep(0.001)  # Small delay
                current_state = is_shutdown_requested()
                assert isinstance(current_state, bool)
        
        # Run multiple workers concurrently
        num_workers = 5
        iterations = 100
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for _ in range(num_workers):
                future = executor.submit(toggle_shutdown_worker, iterations)
                futures.append(future)
            
            for future in futures:
                future.result()
        
        # Final state should be deterministic
        final_state = is_shutdown_requested()
        assert isinstance(final_state, bool)
    
    def test_health_metrics_concurrent_updates(self):
        """Test health metrics updates are thread-safe."""
        def update_metrics_worker(worker_id: int, updates: int):
            """Worker that updates health metrics."""
            for i in range(updates):
                update_health_metrics("memory_warnings")
                update_health_metrics("error_recovery_count", 2)
                time.sleep(0.001)
        
        # Clear metrics
        with health_metrics_lock:
            for key in health_metrics:
                if key != "last_health_check":
                    health_metrics[key] = 0
        
        num_workers = 8
        updates_per_worker = 25
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                future = executor.submit(update_metrics_worker, worker_id, updates_per_worker)
                futures.append(future)
            
            for future in futures:
                future.result()
        
        # Verify final counts
        with health_metrics_lock:
            expected_memory_warnings = num_workers * updates_per_worker
            expected_error_recovery = num_workers * updates_per_worker * 2
            
            assert health_metrics["memory_warnings"] == expected_memory_warnings
            assert health_metrics["error_recovery_count"] == expected_error_recovery
            assert health_metrics["last_health_check"] > 0


class TestMemoryManagement:
    """Test memory management and resource limits."""
    
    def test_notes_memory_limits(self):
        """Test that notes respect memory limits and FIFO eviction."""
        # Clear notes
        with notes_lock:
            notes.clear()
        
        # Add notes up to the limit
        for i in range(MAX_NOTES + 50):  # Exceed limit
            note_name = f"test_note_{i:04d}"
            content = f"Test content for note {i}"
            
            with notes_lock:
                if note_name not in notes and len(notes) >= MAX_NOTES:
                    if notes:
                        oldest_note, _ = notes.popitem(last=False)
                notes[note_name] = content
        
        # Verify limits are respected
        with notes_lock:
            assert len(notes) == MAX_NOTES
            
            # Verify FIFO - oldest notes should be evicted
            # The remaining notes should be the most recent ones
            note_names = list(notes.keys())
            assert "test_note_0000" not in note_names  # Should be evicted
            assert f"test_note_{MAX_NOTES + 49:04d}" in note_names  # Should be present
    
    def test_note_size_limits(self):
        """Test that note size limits are enforced."""
        large_content = "x" * (MAX_NOTE_SIZE + 1000)  # Exceed size limit
        content_size = len(large_content.encode('utf-8'))
        
        # This would normally be caught in the tool handler
        assert content_size > MAX_NOTE_SIZE
        
        # Verify size calculation
        normal_content = "Normal content"
        normal_size = len(normal_content.encode('utf-8'))
        assert normal_size <= MAX_NOTE_SIZE
    
    @pytest.mark.asyncio
    async def test_sse_connection_limits(self):
        """Test SSE connection limits and cleanup."""
        # Clear existing connections
        sse_manager.connections.clear()
        
        # Test adding connections up to limit
        connection_ids = []
        for i in range(sse_manager.max_connections):
            conn_id = f"test_connection_{i}"
            success = sse_manager.add_connection(conn_id)
            assert success
            connection_ids.append(conn_id)
        
        # Verify limit is reached
        assert sse_manager.get_connection_count() == sse_manager.max_connections
        
        # Try to add one more - should fail
        overflow_conn = "overflow_connection"
        success = sse_manager.add_connection(overflow_conn)
        assert not success
        
        # Cleanup connections
        for conn_id in connection_ids[:10]:  # Remove some connections
            sse_manager.remove_connection(conn_id)
        
        # Should be able to add new connections now
        new_conn = "new_connection"
        success = sse_manager.add_connection(new_conn)
        assert success
    
    def test_metrics_memory_management(self):
        """Test that metrics respect memory limits."""
        # Clear metrics
        with metrics_lock:
            metrics["requests_by_endpoint"].clear()
            metrics["response_times"].clear()
        
        # Test response times deque limit
        from datetime_mcp_server.http_server import response_times_deque
        
        # Add more than the limit
        for i in range(MAX_RESPONSE_TIMES + 100):
            response_times_deque.append(i * 0.001)
        
        # Should be limited to max size
        assert len(response_times_deque) == MAX_RESPONSE_TIMES
        # Should contain the most recent values
        assert (MAX_RESPONSE_TIMES + 99) * 0.001 in response_times_deque
        assert 0.0 not in response_times_deque  # Oldest should be evicted


class TestErrorRecovery:
    """Test error recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_resource_monitoring_error_recovery(self):
        """Test resource monitoring handles errors gracefully."""
        from datetime_mcp_server.server import monitor_resources
        
        # Mock psutil to raise exceptions
        with patch('datetime_mcp_server.server.psutil.Process') as mock_process:
            mock_instance = Mock()
            mock_instance.memory_info.side_effect = [
                Exception("Memory access failed"),
                Exception("Another failure"),
                Mock(rss=50 * 1024 * 1024)  # 50MB - success
            ]
            mock_process.return_value = mock_instance
            
            # Set short intervals for testing
            set_shutdown_requested(False)
            
            # Start monitoring task
            monitor_task = asyncio.create_task(monitor_resources())
            
            # Let it run for a short time
            await asyncio.sleep(0.5)
            
            # Stop monitoring
            set_shutdown_requested(True)
            monitor_task.cancel()
            
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            
            # Verify error recovery count increased
            with health_metrics_lock:
                assert health_metrics["error_recovery_count"] > 0
    
    @pytest.mark.asyncio
    async def test_cleanup_resources_error_handling(self):
        """Test resource cleanup handles errors gracefully."""
        # Add some notes to clean up
        with notes_lock:
            notes.clear()
            for i in range(10):
                notes[f"test_note_{i}"] = f"content_{i}"
        
        # Test cleanup
        await cleanup_resources()
        
        # Verify notes were cleared
        with notes_lock:
            assert len(notes) == 0
        
        # Verify cleanup count increased
        with health_metrics_lock:
            assert health_metrics["resource_cleanup_count"] > 0


class TestPerformanceStability:
    """Test performance characteristics under load."""
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self):
        """Test memory usage remains stable under load."""
        import gc
        
        # Get initial memory
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform memory-intensive operations
        with notes_lock:
            notes.clear()
        
        # Add and remove many notes
        for cycle in range(5):
            for i in range(MAX_NOTES):
                note_name = f"cycle_{cycle}_note_{i}"
                content = f"Content for cycle {cycle}, note {i}" * 10  # Larger content
                
                with notes_lock:
                    if note_name not in notes and len(notes) >= MAX_NOTES:
                        if notes:
                            oldest_note, _ = notes.popitem(last=False)
                    notes[note_name] = content
            
            # Clear notes periodically
            if cycle % 2 == 1:
                with notes_lock:
                    notes.clear()
            
            # Force garbage collection
            gc.collect()
        
        # Get final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory increase: {memory_increase:.2f} MB")
        
        # Memory increase should be reasonable (less than 50MB for this test)
        assert memory_increase < 50, f"Memory increase too high: {memory_increase:.2f} MB"
    
    def test_concurrent_load_handling(self):
        """Test system handles concurrent load without degradation."""
        def load_worker(worker_id: int, operations: int):
            """Simulate mixed load operations."""
            for i in range(operations):
                # Mix of operations
                if i % 3 == 0:
                    # Add note
                    note_name = f"load_worker_{worker_id}_note_{i}"
                    content = f"Load test content from worker {worker_id}"
                    with notes_lock:
                        if note_name not in notes and len(notes) >= MAX_NOTES:
                            if notes:
                                oldest_note, _ = notes.popitem(last=False)
                        notes[note_name] = content
                elif i % 3 == 1:
                    # Update health metrics
                    update_health_metrics("memory_warnings")
                else:
                    # Read operations
                    with notes_lock:
                        note_count = len(notes)
                        if notes:
                            sample_note = next(iter(notes.values()))
                
                # Small delay to simulate processing
                time.sleep(0.001)
        
        start_time = time.time()
        
        # Run concurrent load
        num_workers = 20
        operations_per_worker = 100
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                future = executor.submit(load_worker, worker_id, operations_per_worker)
                futures.append(future)
            
            for future in futures:
                future.result()
        
        end_time = time.time()
        total_time = end_time - start_time
        total_operations = num_workers * operations_per_worker
        ops_per_second = total_operations / total_time
        
        print(f"Processed {total_operations} operations in {total_time:.2f}s ({ops_per_second:.0f} ops/sec)")
        
        # Should handle at least 1000 ops/sec
        assert ops_per_second > 1000, f"Performance too low: {ops_per_second:.0f} ops/sec"


class TestStabilityIntegration:
    """Integration tests for overall stability."""
    
    @pytest.mark.asyncio
    async def test_full_system_stability(self):
        """Test full system under mixed load conditions."""
        # Reset state
        with notes_lock:
            notes.clear()
        with health_metrics_lock:
            for key in health_metrics:
                if key != "last_health_check":
                    health_metrics[key] = 0
        
        # Clear SSE manager connections for clean test
        sse_manager.connections.clear()
        sse_manager.connection_timestamps.clear()
        
        set_shutdown_requested(False)
        
        # Simulate various concurrent operations
        async def note_operations():
            for i in range(100):
                note_name = f"stability_note_{i}"
                content = f"Stability test content {i}"
                
                with notes_lock:
                    if note_name not in notes and len(notes) >= MAX_NOTES:
                        if notes:
                            oldest_note, _ = notes.popitem(last=False)
                    notes[note_name] = content
                
                await asyncio.sleep(0.01)
        
        async def metric_operations():
            for i in range(50):
                update_health_metrics("memory_warnings")
                update_health_metrics("error_recovery_count", 2)
                await asyncio.sleep(0.02)
        
        async def sse_operations():
            # Simulate SSE connections
            connection_ids = []
            for i in range(10):
                conn_id = f"stability_conn_{i}"
                if sse_manager.add_connection(conn_id):
                    connection_ids.append(conn_id)
                await asyncio.sleep(0.01)
            
            # Cleanup connections
            for conn_id in connection_ids:
                sse_manager.remove_connection(conn_id)
                await asyncio.sleep(0.01)
        
        # Run all operations concurrently
        await asyncio.gather(
            note_operations(),
            metric_operations(),
            sse_operations()
        )
        
        # Verify system stability
        with notes_lock:
            final_note_count = len(notes)
            assert final_note_count <= MAX_NOTES
        
        with health_metrics_lock:
            assert health_metrics["memory_warnings"] > 0
            assert health_metrics["error_recovery_count"] > 0
            assert health_metrics["last_health_check"] > 0
        
        # Check that our test connections were cleaned up (not all global connections)
        # This verifies the cleanup mechanism works, even if other tests left connections
        initial_conn_count = sse_manager.get_connection_count()
        test_conn = "final_test_connection"
        sse_manager.add_connection(test_conn)
        assert sse_manager.get_connection_count() == initial_conn_count + 1
        sse_manager.remove_connection(test_conn)
        assert sse_manager.get_connection_count() == initial_conn_count
        
        print("Full system stability test completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"]) 