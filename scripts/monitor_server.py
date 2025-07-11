#!/usr/bin/env python3
"""
Server Stability Monitoring Script

This script monitors the datetime MCP server for stability issues:
- Memory usage tracking
- CPU utilization monitoring  
- Process lifecycle tracking
- Error detection and logging
- Resource leak detection
"""

import asyncio
import psutil
import time
import json
import signal
import sys
import subprocess
import threading
from datetime import datetime
from pathlib import Path

class ServerMonitor:
    def __init__(self, monitoring_duration=3600):  # Default 1 hour
        self.monitoring_duration = monitoring_duration
        self.server_process = None
        self.monitoring_active = False
        self.start_time = time.time()
        self.metrics = []
        self.log_file = Path("server_stability_log.json")
        
    def start_server(self):
        """Start the MCP server process"""
        print(f"[{datetime.now()}] Starting MCP server...")
        
        # Start server process using package-level execution to avoid RuntimeWarning
        self.server_process = subprocess.Popen(
            ["uv", "run", "python", "-m", "datetime_mcp_server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            preexec_fn=None
        )
        
        print(f"[{datetime.now()}] Server started with PID: {self.server_process.pid}")
        return self.server_process.pid
        
    def monitor_process(self, pid):
        """Monitor process metrics"""
        try:
            process = psutil.Process(pid)
            
            # Get memory info
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # Get CPU info
            cpu_percent = process.cpu_percent()
            
            # Get file descriptors (Unix only)
            try:
                num_fds = process.num_fds()
            except (AttributeError, psutil.AccessDenied):
                num_fds = -1
                
            # Get thread count
            num_threads = process.num_threads()
            
            # Get process status
            status = process.status()
            
            metric = {
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": time.time() - self.start_time,
                "memory_rss_mb": memory_info.rss / 1024 / 1024,
                "memory_vms_mb": memory_info.vms / 1024 / 1024, 
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
                "num_file_descriptors": num_fds,
                "num_threads": num_threads,
                "process_status": status,
                "is_running": process.is_running()
            }
            
            self.metrics.append(metric)
            return metric, True
            
        except psutil.NoSuchProcess:
            print(f"[{datetime.now()}] ❌ Process {pid} no longer exists!")
            return None, False
        except Exception as e:
            print(f"[{datetime.now()}] ⚠️ Error monitoring process: {e}")
            return None, True
    
    def monitor_server_lifecycle(self):
        """Monitor server output for errors and lifecycle events"""
        if not self.server_process:
            return
            
        def read_output(stream, name):
            for line in iter(stream.readline, ''):
                if line.strip():
                    print(f"[{datetime.now()}] {name}: {line.strip()}")
                    # Look for error patterns
                    if any(pattern in line.lower() for pattern in 
                           ['error', 'exception', 'traceback', 'fatal', 'critical']):
                        print(f"[{datetime.now()}] 🚨 ERROR DETECTED in {name}: {line.strip()}")
        
        # Start threads to read stdout and stderr
        if self.server_process.stdout:
            stdout_thread = threading.Thread(
                target=read_output, 
                args=(self.server_process.stdout, "STDOUT"),
                daemon=True
            )
            stdout_thread.start()
        
        if self.server_process.stderr:
            stderr_thread = threading.Thread(
                target=read_output,
                args=(self.server_process.stderr, "STDERR"), 
                daemon=True
            )
            stderr_thread.start()
    
    async def run_monitoring(self):
        """Main monitoring loop"""
        print(f"[{datetime.now()}] 🔍 Starting server monitoring for {self.monitoring_duration} seconds...")
        
        # Start the server
        pid = self.start_server()
        
        # Wait a moment for server to initialize
        await asyncio.sleep(2)
        
        # Start lifecycle monitoring
        self.monitor_server_lifecycle()
        
        self.monitoring_active = True
        monitor_interval = 5  # Monitor every 5 seconds
        
        try:
            while self.monitoring_active and (time.time() - self.start_time) < self.monitoring_duration:
                metric, process_alive = self.monitor_process(pid)
                
                if metric:
                    print(f"[{datetime.now()}] 📊 Memory: {metric['memory_rss_mb']:.1f}MB "
                          f"CPU: {metric['cpu_percent']:.1f}% "
                          f"Threads: {metric['num_threads']} "
                          f"FDs: {metric['num_file_descriptors']} "
                          f"Status: {metric['process_status']}")
                    
                    # Check for memory growth
                    if len(self.metrics) > 10:
                        recent_memory = [m['memory_rss_mb'] for m in self.metrics[-10:]]
                        if max(recent_memory) - min(recent_memory) > 10:  # 10MB growth
                            print(f"[{datetime.now()}] ⚠️ MEMORY GROWTH DETECTED: "
                                  f"{min(recent_memory):.1f}MB → {max(recent_memory):.1f}MB")
                
                if not process_alive:
                    print(f"[{datetime.now()}] ❌ SERVER TERMINATED UNEXPECTEDLY!")
                    break
                    
                await asyncio.sleep(monitor_interval)
                
        except KeyboardInterrupt:
            print(f"[{datetime.now()}] 🛑 Monitoring interrupted by user")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources and save results"""
        print(f"[{datetime.now()}] 🧹 Cleaning up...")
        
        self.monitoring_active = False
        
        # Terminate server process
        if self.server_process and self.server_process.poll() is None:
            print(f"[{datetime.now()}] Terminating server process...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[{datetime.now()}] Force killing server process...")
                self.server_process.kill()
        
        # Save metrics to file
        if self.metrics:
            self.save_metrics()
            self.analyze_metrics()
    
    def save_metrics(self):
        """Save collected metrics to JSON file"""
        data = {
            "monitoring_session": {
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "duration_seconds": time.time() - self.start_time,
                "total_samples": len(self.metrics)
            },
            "metrics": self.metrics
        }
        
        with open(self.log_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"[{datetime.now()}] 💾 Metrics saved to {self.log_file}")
    
    def analyze_metrics(self):
        """Analyze collected metrics for stability issues"""
        if not self.metrics:
            return
            
        print(f"\n[{datetime.now()}] 📈 STABILITY ANALYSIS")
        print("=" * 50)
        
        # Memory analysis
        memory_values = [m['memory_rss_mb'] for m in self.metrics]
        print(f"Memory Usage:")
        print(f"  Initial: {memory_values[0]:.1f}MB")
        print(f"  Final: {memory_values[-1]:.1f}MB") 
        print(f"  Peak: {max(memory_values):.1f}MB")
        print(f"  Growth: {memory_values[-1] - memory_values[0]:.1f}MB")
        
        # CPU analysis
        cpu_values = [m['cpu_percent'] for m in self.metrics if m['cpu_percent'] > 0]
        if cpu_values:
            print(f"CPU Usage:")
            print(f"  Average: {sum(cpu_values)/len(cpu_values):.1f}%")
            print(f"  Peak: {max(cpu_values):.1f}%")
        
        # Thread analysis
        thread_values = [m['num_threads'] for m in self.metrics]
        print(f"Thread Count:")
        print(f"  Initial: {thread_values[0]}")
        print(f"  Final: {thread_values[-1]}")
        print(f"  Peak: {max(thread_values)}")
        
        # File descriptor analysis
        fd_values = [m['num_file_descriptors'] for m in self.metrics if m['num_file_descriptors'] > 0]
        if fd_values:
            print(f"File Descriptors:")
            print(f"  Initial: {fd_values[0]}")
            print(f"  Final: {fd_values[-1]}")
            print(f"  Peak: {max(fd_values)}")
        
        # Stability assessment
        print(f"\nStability Assessment:")
        memory_growth = memory_values[-1] - memory_values[0]
        if memory_growth > 20:  # 20MB growth
            print(f"  ❌ MEMORY LEAK SUSPECTED: {memory_growth:.1f}MB growth")
        else:
            print(f"  ✅ Memory usage stable: {memory_growth:.1f}MB growth")
            
        thread_growth = thread_values[-1] - thread_values[0]
        if thread_growth > 5:
            print(f"  ⚠️ THREAD LEAK SUSPECTED: {thread_growth} threads created")
        else:
            print(f"  ✅ Thread count stable: {thread_growth} thread growth")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor datetime MCP server stability")
    parser.add_argument("--duration", type=int, default=300, 
                       help="Monitoring duration in seconds (default: 300)")
    parser.add_argument("--interval", type=int, default=5,
                       help="Monitoring interval in seconds (default: 5)")
    
    args = parser.parse_args()
    
    monitor = ServerMonitor(monitoring_duration=args.duration)
    
    # Set up signal handlers for clean shutdown
    def signal_handler(signum, frame):
        print(f"\n[{datetime.now()}] Received signal {signum}, shutting down...")
        monitor.monitoring_active = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await monitor.run_monitoring()

if __name__ == "__main__":
    asyncio.run(main()) 