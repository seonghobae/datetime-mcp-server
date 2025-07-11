#!/usr/bin/env python3
"""
MCP Server Stress Test

This script sends continuous requests to the datetime MCP server to:
- Simulate real-world usage patterns
- Test server stability under load
- Identify potential memory leaks or resource issues
- Trigger edge cases that might cause server termination
"""

import asyncio
import json
import subprocess
import time
import random
from datetime import datetime, timedelta
from pathlib import Path

class MCPStressTester:
    def __init__(self, duration=600, request_interval=0.5):
        self.duration = duration
        self.request_interval = request_interval
        self.server_process = None
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.start_time = time.time()
        self.active = False
        
    def start_server(self):
        """Start the MCP server"""
        print(f"[{datetime.now()}] 🚀 Starting MCP server for stress testing...")
        
        # Use package-level execution to avoid RuntimeWarning
        self.server_process = subprocess.Popen(
            ["uv", "run", "python", "-m", "datetime_mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"[{datetime.now()}] Server started with PID: {self.server_process.pid}")
        
        # Give server time to initialize
        time.sleep(2)
        return self.server_process.pid
    
    async def send_mcp_request(self, method, params=None):
        """Send an MCP request to the server"""
        if not self.server_process or self.server_process.poll() is not None:
            return False, "Server not running"
        
        request = {
            "jsonrpc": "2.0",
            "id": self.total_requests + 1,
            "method": method,
            "params": params or {}
        }
        
        try:
            # Send request
            request_json = json.dumps(request) + '\n'
            self.server_process.stdin.write(request_json)
            self.server_process.stdin.flush()
            
            # Wait for response (with timeout)
            response_line = await asyncio.wait_for(
                asyncio.to_thread(self.server_process.stdout.readline),
                timeout=5.0
            )
            
            if response_line:
                response = json.loads(response_line.strip())
                return True, response
            else:
                return False, "No response"
                
        except asyncio.TimeoutError:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)
    
    def generate_test_requests(self):
        """Generate various test requests to stress different parts of the server"""
        requests = [
            # Resource requests
            ("resources/list", {}),
            ("resources/read", {"uri": "datetime://current"}),
            ("resources/read", {"uri": "datetime://today"}),
            ("resources/read", {"uri": "datetime://time"}),
            ("resources/read", {"uri": "datetime://timezone-info"}),
            
            # Tool requests - original tools
            ("tools/call", {
                "name": "get-current-time",
                "arguments": {"format": random.choice(["iso", "readable", "unix", "rfc3339"])}
            }),
            ("tools/call", {
                "name": "format-date", 
                "arguments": {
                    "date": "2024-07-15",
                    "format": random.choice(["%Y-%m-%d", "%B %d, %Y", "%Y/%m/%d %H:%M:%S"])
                }
            }),
            
            # Note management requests
            ("tools/call", {
                "name": "add-note",
                "arguments": {
                    "name": f"stress_test_{random.randint(1000, 9999)}",
                    "content": f"Stress test note created at {datetime.now()}"
                }
            }),
            ("tools/call", {"name": "list-notes", "arguments": {}}),
            
            # Enhanced datetime tools
            ("tools/call", {
                "name": "get-current-datetime",
                "arguments": {
                    "format": random.choice(["iso", "json", "custom"]),
                    "timezone": random.choice(["UTC", "America/New_York", "Asia/Tokyo", "Europe/London"])
                }
            }),
            ("tools/call", {
                "name": "calculate-date",
                "arguments": {
                    "base_date": "2024-07-15",
                    "operation": random.choice(["add", "subtract"]),
                    "amount": random.randint(1, 100),
                    "unit": random.choice(["days", "weeks", "months", "years"])
                }
            }),
            ("tools/call", {
                "name": "calculate-date-range",
                "arguments": {
                    "base_date": "2024-07-15",
                    "direction": random.choice(["last", "next"]),
                    "amount": random.randint(1, 12),
                    "unit": random.choice(["days", "weeks", "months"])
                }
            }),
            ("tools/call", {
                "name": "calculate-business-days",
                "arguments": {
                    "start_date": "2024-07-01",
                    "end_date": "2024-07-31",
                    "holidays": ["2024-07-04"]
                }
            }),
            
            # Prompt requests
            ("prompts/list", {}),
            ("prompts/get", {"name": "datetime-calculation-guide", "arguments": {}}),
        ]
        
        return random.choice(requests)
    
    async def run_stress_test(self):
        """Run the main stress test loop"""
        print(f"[{datetime.now()}] 🔥 Starting stress test for {self.duration} seconds...")
        print(f"[{datetime.now()}] Request interval: {self.request_interval} seconds")
        
        # Start server
        pid = self.start_server()
        
        self.active = True
        
        try:
            while self.active and (time.time() - self.start_time) < self.duration:
                if self.server_process.poll() is not None:
                    print(f"[{datetime.now()}] ❌ SERVER TERMINATED! Exit code: {self.server_process.poll()}")
                    break
                
                # Generate and send request
                method, params = self.generate_test_requests()
                self.total_requests += 1
                
                success, response = await self.send_mcp_request(method, params)
                
                if success:
                    self.successful_requests += 1
                    if self.total_requests % 50 == 0:  # Log every 50th request
                        print(f"[{datetime.now()}] ✅ Request #{self.total_requests}: {method} - Success")
                else:
                    self.failed_requests += 1
                    print(f"[{datetime.now()}] ❌ Request #{self.total_requests}: {method} - Failed: {response}")
                
                # Wait before next request
                await asyncio.sleep(self.request_interval)
                
        except KeyboardInterrupt:
            print(f"[{datetime.now()}] 🛑 Stress test interrupted by user")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up and report results"""
        print(f"[{datetime.now()}] 🧹 Cleaning up stress test...")
        
        self.active = False
        
        # Terminate server
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
        
        # Report results
        duration = time.time() - self.start_time
        print(f"\n[{datetime.now()}] 📊 STRESS TEST RESULTS")
        print("=" * 50)
        print(f"Duration: {duration:.1f} seconds")
        print(f"Total Requests: {self.total_requests}")
        print(f"Successful: {self.successful_requests}")
        print(f"Failed: {self.failed_requests}")
        print(f"Success Rate: {(self.successful_requests/self.total_requests*100):.1f}%" if self.total_requests > 0 else "N/A")
        print(f"Requests per Second: {(self.total_requests/duration):.2f}")
        
        if self.failed_requests > 0:
            print(f"⚠️ {self.failed_requests} requests failed - investigate server stability")
        
        if self.server_process and self.server_process.poll() is not None:
            print(f"⚠️ Server terminated with exit code: {self.server_process.poll()}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Stress test the datetime MCP server")
    parser.add_argument("--duration", type=int, default=600,
                       help="Test duration in seconds (default: 600)")
    parser.add_argument("--interval", type=float, default=0.5,
                       help="Request interval in seconds (default: 0.5)")
    
    args = parser.parse_args()
    
    tester = MCPStressTester(duration=args.duration, request_interval=args.interval)
    await tester.run_stress_test()

if __name__ == "__main__":
    asyncio.run(main()) 