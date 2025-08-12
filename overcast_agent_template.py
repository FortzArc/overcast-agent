#!/usr/bin/env python3
"""
STREAMING LOG FORWARDER - Configurable Template
==========================================

This version reads configuration from environment variables or .env file
for seamless integration with the Overcast GUI installer.

Based on senior engineer's chat guidance:
1. python app.py > /app.log & (background execution)
2. tail -f /app.log | send-command external-endpoint (streaming)
3. Real-time log forwarding with system metrics

CRITICAL: This streams logs in REAL-TIME, not polling!

Configuration via environment variables:
- OVERCAST_API_KEY (required)
- OVERCAST_CUSTOMER_NAME (optional - derived from API key if not set)
- OVERCAST_DASHBOARD_URL (optional - defaults to production)
- OVERCAST_LOG_FILE (optional - defaults to /app.log)
"""

import os
import sys
import json
import uuid
import time
import psutil
import subprocess
import requests
import hashlib
from datetime import datetime
from threading import Thread
from typing import Dict, Any, Optional
import signal

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, use os.environ directly
    pass

class SystemMetricsCollector:
    """Collects comprehensive system metrics like cosmed_ai_processor.py"""
    
    @staticmethod
    def get_accurate_container_cpu_usage():
        """Get accurate container CPU usage using cgroup metrics"""
        try:
            with open("/sys/fs/cgroup/cpu/cpuacct.usage", "r") as f:
                usage1 = int(f.read())
            time.sleep(1)
            with open("/sys/fs/cgroup/cpu/cpuacct.usage", "r") as f:
                usage2 = int(f.read())

            delta = usage2 - usage1
            cpu_percent = (delta / 1e9) * 100  # Convert nanoseconds to seconds, then to percent
            return cpu_percent
        except Exception as e:
            print(f"⚠️  Error getting accurate container CPU usage: {e}")
            return None

    @staticmethod
    def get_accurate_container_cpu_usage_v2():
        """Get accurate container CPU usage using modern cgroup v2 metrics"""
        try:
            with open("/sys/fs/cgroup/cpu.stat", "r") as f:
                lines = f.readlines()
            usage_usec_1 = int([line for line in lines if line.startswith("usage_usec")][0].split()[1])
            time.sleep(1)
            with open("/sys/fs/cgroup/cpu.stat", "r") as f:
                lines = f.readlines()
            usage_usec_2 = int([line for line in lines if line.startswith("usage_usec")][0].split()[1])
            delta_usec = usage_usec_2 - usage_usec_1

            return delta_usec / 1e4  # convert to percent-ish (100% = 1 core)
        except Exception as e:
            print(f"❌ Error getting CPU usage v2: {e}")
            return None

    @staticmethod
    def get_accurate_container_memory_usage():
        """Get accurate container memory usage using cgroup metrics"""
        try:
            with open("/sys/fs/cgroup/memory/memory.usage_in_bytes", "r") as f:
                used = int(f.read())
            with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
                limit = int(f.read())

            mem_percent = (used / limit) * 100
            return mem_percent, used, limit
        except Exception as e:
            print(f"⚠️  Error getting accurate container memory usage: {e}")
            return None, None, None

    @staticmethod
    def get_accurate_container_memory_usage_v2():
        """Get accurate container memory usage using modern cgroup v2 metrics"""
        try:
            with open("/sys/fs/cgroup/memory.current", "r") as f:
                used = int(f.read())
            with open("/sys/fs/cgroup/memory.max", "r") as f:
                limit = int(f.read())
            if limit == 0 or limit >= 9223372036854771712:  # Unlimited or placeholder
                limit = used  # prevent div by zero or nonsense
            percent = (used / limit) * 100
            return percent, used, limit
        except Exception as e:
            print(f"❌ Error getting memory usage v2: {e}")
            return None, None, None

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Get comprehensive system metrics for incident context with container awareness"""
        try:
            print(" SYSTEM METRICS COLLECTOR: Starting metrics collection...")
            
            # Check if we're in a container environment
            container_metrics = SystemMetricsCollector._get_container_metrics()
            is_container = container_metrics is not None
            
            print(f" Container detected: {is_container}")
            if is_container:
                print(f"   📦 Container Memory Limit: {container_metrics.get('memory_limit', 'Unknown')} bytes")
                print(f"   📦 Container CPU Limit: {container_metrics.get('cpu_limit', 'Unknown')} cores")
            
            # CPU metrics
            print("  Collecting CPU metrics...")
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            
            # Try accurate container CPU metrics with v2 priority
            accurate_cpu_percent = None
            cpu_source = "psutil"
            if is_container:
                # Try cgroup v2 first (most modern)
                accurate_cpu_percent = SystemMetricsCollector.get_accurate_container_cpu_usage_v2()
                if accurate_cpu_percent is not None:
                    print(f"   ✅ Accurate Container CPU Usage (v2): {accurate_cpu_percent:.2f}%")
                    effective_cpu_percent = accurate_cpu_percent
                    cpu_source = "cgroup_v2"
                else:
                    # Fallback to cgroup v1
                    accurate_cpu_percent = SystemMetricsCollector.get_accurate_container_cpu_usage()
                    if accurate_cpu_percent is not None:
                        print(f"   ✅ Accurate Container CPU Usage (v1): {accurate_cpu_percent:.2f}%")
                        effective_cpu_percent = accurate_cpu_percent
                        cpu_source = "cgroup_v1"
                    else:
                        # Fallback to docker stats or psutil
                        if container_metrics.get('cpu_percent'):
                            effective_cpu_percent = container_metrics['cpu_percent']
                            print(f"   ✅ CPU Percent (docker stats): {effective_cpu_percent}%")
                            cpu_source = "docker_stats"
                        else:
                            effective_cpu_percent = cpu_percent
                            print(f"   ✅ CPU Percent (psutil): {effective_cpu_percent}%")
                            cpu_source = "psutil"
            else:
                effective_cpu_percent = cpu_percent
                print(f"   ✅ CPU Percent (host): {effective_cpu_percent}%")
                cpu_source = "host_psutil"
            
            # Use container CPU limits if available
            if is_container and container_metrics.get('cpu_limit'):
                effective_cpu_count = container_metrics['cpu_limit']
                print(f"   ✅ CPU Count (container): {effective_cpu_count} cores")
            else:
                effective_cpu_count = cpu_count
                print(f"   ✅ CPU Count (host): {effective_cpu_count} cores")
            print(f"   ✅ Load Average: {load_avg}")
            
            # Memory metrics
            print("💾 Collecting memory metrics...")
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Try accurate container memory metrics with v2 priority
            accurate_mem_percent = None
            accurate_mem_used = None
            accurate_mem_limit = None
            memory_source = "psutil"
            
            if is_container:
                # Try cgroup v2 first (most modern)
                accurate_mem_percent, accurate_mem_used, accurate_mem_limit = SystemMetricsCollector.get_accurate_container_memory_usage_v2()
                if accurate_mem_percent is not None:
                    print(f"   ✅ Memory Usage (v2): {accurate_mem_percent:.2f}% ({accurate_mem_used / 1e6:.2f}MB / {accurate_mem_limit / 1e6:.2f}MB)")
                    effective_memory_percent = accurate_mem_percent
                    effective_memory_total = accurate_mem_limit
                    effective_memory_used = accurate_mem_used
                    memory_source = "cgroup_v2"
                else:
                    # Fallback to cgroup v1
                    accurate_mem_percent, accurate_mem_used, accurate_mem_limit = SystemMetricsCollector.get_accurate_container_memory_usage()
                    if accurate_mem_percent is not None:
                        print(f"   ✅ Accurate Container Memory Usage (v1): {accurate_mem_percent:.2f}% ({accurate_mem_used / 1e6:.2f}MB / {accurate_mem_limit / 1e6:.2f}MB)")
                        effective_memory_percent = accurate_mem_percent
                        effective_memory_total = accurate_mem_limit
                        effective_memory_used = accurate_mem_used
                        memory_source = "cgroup_v1"
                    else:
                        # Fallback to existing logic
                        if container_metrics.get('memory_percent'):
                            effective_memory_percent = container_metrics['memory_percent']
                            effective_memory_total = container_metrics.get('memory_total', memory.total)
                            effective_memory_used = container_metrics.get('memory_used', memory.used)
                            
                            print(f"   ✅ Memory Total (docker stats): {effective_memory_total} bytes")
                            print(f"   ✅ Memory Used (docker stats): {effective_memory_used} bytes")
                            print(f"   ✅ Memory Percent (docker stats): {effective_memory_percent:.1f}%")
                            memory_source = "docker_stats"
                        elif container_metrics.get('memory_limit'):
                            # Fallback to cgroup limits
                            container_memory_limit = container_metrics['memory_limit']
                            container_memory_used = min(memory.used, container_memory_limit)
                            container_memory_percent = (container_memory_used / container_memory_limit) * 100
                            
                            print(f"   ✅ Memory Total (cgroup): {container_memory_limit} bytes")
                            print(f"   ✅ Memory Used (cgroup): {container_memory_used} bytes")
                            print(f"   ✅ Memory Percent (cgroup): {container_memory_percent:.1f}%")
                            
                            effective_memory_total = container_memory_limit
                            effective_memory_used = container_memory_used
                            effective_memory_percent = container_memory_percent
                            memory_source = "cgroup_legacy"
                        else:
                            print(f"   ✅ Memory Total (host): {memory.total} bytes")
                            print(f"   ✅ Memory Used (host): {memory.used} bytes")
                            print(f"   ✅ Memory Percent (host): {memory.percent}%")
                            
                            effective_memory_total = memory.total
                            effective_memory_used = memory.used
                            effective_memory_percent = memory.percent
                            memory_source = "host_psutil"
            else:
                print(f"   ✅ Memory Total (host): {memory.total} bytes")
                print(f"   ✅ Memory Used (host): {memory.used} bytes")
                print(f"   ✅ Memory Percent (host): {memory.percent}%")
                
                effective_memory_total = memory.total
                effective_memory_used = memory.used
                effective_memory_percent = memory.percent
                memory_source = "host_psutil"
            
            print(f"   ✅ Swap Percent: {swap.percent}%")
            
            # Disk metrics
            print("💿 Collecting disk metrics...")
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            print(f"   ✅ Disk Total: {disk.total} bytes")
            print(f"   ✅ Disk Used: {disk.used} bytes")
            print(f"   ✅ Disk Percent: {(disk.used / disk.total) * 100:.1f}%")
            
            # Network metrics
            print("🌐 Collecting network metrics...")
            network_io = psutil.net_io_counters()
            network_connections = len(psutil.net_connections())
            
            print(f"   ✅ Network Bytes Sent: {network_io.bytes_sent} bytes")
            print(f"   ✅ Network Bytes Recv: {network_io.bytes_recv} bytes")
            print(f"   ✅ Network Connections: {network_connections}")
            
            # Process metrics
            print("🔢 Collecting process metrics...")
            process_count = len(psutil.pids())
            
            print(f"   ✅ Process Count: {process_count}")
            
            # System info
            print("⏱️  Collecting system info...")
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            
            print(f"   ✅ System Uptime: {uptime / 3600:.1f} hours")
            print(f"   ✅ Boot Time: {boot_time}")
            
            metrics_data = {
                'cpu': {
                    'percent': effective_cpu_percent,
                    'count': effective_cpu_count,
                    'load_average': list(load_avg),
                    'is_container': is_container,
                    'accurate_container_usage': accurate_cpu_percent,
                    'source': cpu_source
                },
                'memory': {
                    'total': effective_memory_total,
                    'available': memory.available,
                    'percent': effective_memory_percent,
                    'used': effective_memory_used,
                    'is_container': is_container,
                    'accurate_container_usage': accurate_mem_percent,
                    'accurate_container_used': accurate_mem_used,
                    'accurate_container_limit': accurate_mem_limit,
                    'source': memory_source
                },
                'swap': {
                    'total': swap.total,
                    'used': swap.used,
                    'percent': swap.percent
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100,
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0
                },
                'network': {
                    'bytes_sent': network_io.bytes_sent,
                    'bytes_recv': network_io.bytes_recv,
                    'connections': network_connections
                },
                'system': {
                    'process_count': process_count,
                    'uptime_seconds': uptime,
                    'boot_time': boot_time,
                    'is_container': is_container
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            print("✅ SYSTEM METRICS COLLECTOR: All metrics collected successfully!")
            print(f"📊 Final CPU Percent: {metrics_data['cpu']['percent']}%")
            print(f"📊 Final Memory Percent: {metrics_data['memory']['percent']:.1f}%")
            print(f"📊 Final Disk Percent: {metrics_data['disk']['percent']:.1f}%")
            print(f"🐳 Container Mode: {is_container}")
            if is_container:
                print(f"🐳 CPU Source: {cpu_source}")
                print(f"🐳 Memory Source: {memory_source}")
            
            return metrics_data
            
        except Exception as e:
            print(f"❌ Error collecting system metrics: {e}")
            print(f"❌ Exception type: {type(e).__name__}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def _get_container_metrics() -> Optional[Dict[str, Any]]:
        """Detect container environment and get container-specific metrics using docker stats"""
        try:
            container_metrics = {}
            
            # Check for Docker container
            if os.path.exists('/.dockerenv'):
                print("🐳 Docker container detected")
                container_metrics['type'] = 'docker'
                
                # Try to get container stats using docker stats command
                try:
                    import subprocess
                    import re
                    
                    # Get current container ID
                    container_id = None
                    try:
                        with open('/proc/self/cgroup', 'r') as f:
                            for line in f:
                                if 'docker' in line:
                                    container_id = line.strip().split('/')[-1]
                                    break
                    except:
                        pass
                    
                    if container_id:
                        print(f"   📦 Container ID: {container_id}")
                        
                        # Run docker stats command
                        try:
                            result = subprocess.run(
                                ['docker', 'stats', '--no-stream', '--format', 'table {{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}'],
                                capture_output=True, text=True, timeout=5
                            )
                            
                            if result.returncode == 0 and result.stdout:
                                lines = result.stdout.strip().split('\n')
                                if len(lines) > 1:  # Skip header line
                                    stats_line = lines[1]  # Get the actual stats
                                    parts = stats_line.split('\t')
                                    
                                    if len(parts) >= 5:
                                        # Parse CPU percentage
                                        cpu_percent_str = parts[0].strip()
                                        if cpu_percent_str.endswith('%'):
                                            cpu_percent = float(cpu_percent_str[:-1])
                                            container_metrics['cpu_percent'] = cpu_percent
                                            print(f"   📦 Docker CPU Usage: {cpu_percent}%")
                                        
                                        # Parse memory usage
                                        mem_usage_str = parts[1].strip()
                                        mem_percent_str = parts[2].strip()
                                        
                                        # Parse memory usage (e.g., "1.2GiB / 2GiB")
                                        mem_match = re.match(r'([\d.]+)([KMGT]i?B)\s*/\s*([\d.]+)([KMGT]i?B)', mem_usage_str)
                                        if mem_match:
                                            used_val, used_unit, total_val, total_unit = mem_match.groups()
                                            used_bytes = SystemMetricsCollector._parse_memory_value(float(used_val), used_unit)
                                            total_bytes = SystemMetricsCollector._parse_memory_value(float(total_val), total_unit)
                                            
                                            container_metrics['memory_used'] = used_bytes
                                            container_metrics['memory_total'] = total_bytes
                                            print(f"   📦 Docker Memory: {used_bytes} / {total_bytes} bytes")
                                        
                                        # Parse memory percentage
                                        if mem_percent_str.endswith('%'):
                                            mem_percent = float(mem_percent_str[:-1])
                                            container_metrics['memory_percent'] = mem_percent
                                            print(f"   📦 Docker Memory Usage: {mem_percent}%")
                                        
                                        # Parse network I/O
                                        net_io_str = parts[3].strip()
                                        net_match = re.match(r'([\d.]+)([KMGT]i?B)\s*/\s*([\d.]+)([KMGT]i?B)', net_io_str)
                                        if net_match:
                                            sent_val, sent_unit, recv_val, recv_unit = net_match.groups()
                                            bytes_sent = SystemMetricsCollector._parse_memory_value(float(sent_val), sent_unit)
                                            bytes_recv = SystemMetricsCollector._parse_memory_value(float(recv_val), recv_unit)
                                            
                                            container_metrics['network_bytes_sent'] = bytes_sent
                                            container_metrics['network_bytes_recv'] = bytes_recv
                                            print(f"   📦 Docker Network: {bytes_sent} sent / {bytes_recv} received")
                                        
                                        # Parse block I/O
                                        block_io_str = parts[4].strip()
                                        block_match = re.match(r'([\d.]+)([KMGT]i?B)\s*/\s*([\d.]+)([KMGT]i?B)', block_io_str)
                                        if block_match:
                                            read_val, read_unit, write_val, write_unit = block_match.groups()
                                            bytes_read = SystemMetricsCollector._parse_memory_value(float(read_val), read_unit)
                                            bytes_written = SystemMetricsCollector._parse_memory_value(float(write_val), write_unit)
                                            
                                            container_metrics['disk_bytes_read'] = bytes_read
                                            container_metrics['disk_bytes_written'] = bytes_written
                                            print(f"   📦 Docker Disk I/O: {bytes_read} read / {bytes_written} written")
                                            
                        except subprocess.TimeoutExpired:
                            print("   ⚠️ Docker stats command timed out")
                        except FileNotFoundError:
                            print("   ⚠️ Docker command not found")
                        except Exception as e:
                            print(f"   ⚠️ Error running docker stats: {e}")
                            
                except Exception as e:
                    print(f"   ⚠️ Error getting docker stats: {e}")
                
                # Fallback to cgroup reading if docker stats fails
                if not container_metrics.get('cpu_percent'):
                    try:
                        with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
                            memory_limit = int(f.read().strip())
                            if memory_limit > 0 and memory_limit != 9223372036854771712:  # Unlimited
                                container_metrics['memory_limit'] = memory_limit
                                print(f"   📦 Docker Memory Limit (cgroup): {memory_limit} bytes")
                    except:
                        pass
                    
                    try:
                        with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as f:
                            cpu_quota = int(f.read().strip())
                        with open('/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as f:
                            cpu_period = int(f.read().strip())
                        
                        if cpu_quota > 0:
                            cpu_limit = cpu_quota / cpu_period
                            container_metrics['cpu_limit'] = cpu_limit
                            print(f"   📦 Docker CPU Limit (cgroup): {cpu_limit} cores")
                    except:
                        pass
            
            # Check for Kubernetes container
            elif os.path.exists('/var/run/secrets/kubernetes.io/'):
                print("☸️  Kubernetes container detected")
                container_metrics['type'] = 'kubernetes'
                
                # Try to read memory limit from cgroup
                try:
                    with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
                        memory_limit = int(f.read().strip())
                        if memory_limit > 0 and memory_limit != 9223372036854771712:  # Unlimited
                            container_metrics['memory_limit'] = memory_limit
                            print(f"   📦 K8s Memory Limit: {memory_limit} bytes")
                except:
                    pass
                
                # Try to read CPU limit from cgroup
                try:
                    with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as f:
                        cpu_quota = int(f.read().strip())
                    with open('/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as f:
                        cpu_period = int(f.read().strip())
                    
                    if cpu_quota > 0:
                        cpu_limit = cpu_quota / cpu_period
                        container_metrics['cpu_limit'] = cpu_limit
                        print(f"   📦 K8s CPU Limit: {cpu_limit} cores")
                except:
                    pass
            
            # Check for Railway container (Railway uses Docker)
            elif os.environ.get('RAILWAY_ENVIRONMENT'):
                print("🚂 Railway container detected")
                container_metrics['type'] = 'railway'
                
                # Railway typically provides memory limits via environment
                memory_limit_env = os.environ.get('RAILWAY_MEMORY_LIMIT')
                if memory_limit_env:
                    try:
                        memory_limit = int(memory_limit_env) * 1024 * 1024  # Convert MB to bytes
                        container_metrics['memory_limit'] = memory_limit
                        print(f"   📦 Railway Memory Limit: {memory_limit} bytes")
                    except:
                        pass
                
                # Railway CPU limits are usually fractional
                cpu_limit_env = os.environ.get('RAILWAY_CPU_LIMIT')
                if cpu_limit_env:
                    try:
                        cpu_limit = float(cpu_limit_env)
                        container_metrics['cpu_limit'] = cpu_limit
                        print(f"   📦 Railway CPU Limit: {cpu_limit} cores")
                    except:
                        pass
            
            # Check for Heroku container
            elif os.environ.get('DYNO'):
                print("🦊 Heroku container detected")
                container_metrics['type'] = 'heroku'
                
                # Heroku provides memory limits via environment
                memory_limit_env = os.environ.get('MEMORY_LIMIT')
                if memory_limit_env:
                    try:
                        # Parse Heroku memory format (e.g., "512M")
                        if memory_limit_env.endswith('M'):
                            memory_limit = int(memory_limit_env[:-1]) * 1024 * 1024
                        elif memory_limit_env.endswith('G'):
                            memory_limit = int(memory_limit_env[:-1]) * 1024 * 1024 * 1024
                        else:
                            memory_limit = int(memory_limit_env) * 1024 * 1024
                        
                        container_metrics['memory_limit'] = memory_limit
                        print(f"   📦 Heroku Memory Limit: {memory_limit} bytes")
                    except:
                        pass
            
            # Check for generic cgroup (other container runtimes)
            elif os.path.exists('/sys/fs/cgroup/'):
                print("📦 Generic container detected (cgroup found)")
                container_metrics['type'] = 'generic'
                
                # Try to read memory limit from cgroup
                try:
                    with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
                        memory_limit = int(f.read().strip())
                        if memory_limit > 0 and memory_limit != 9223372036854771712:  # Unlimited
                            container_metrics['memory_limit'] = memory_limit
                            print(f"   📦 Generic Memory Limit: {memory_limit} bytes")
                except:
                    pass
                
                # Try to read CPU limit from cgroup
                try:
                    with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as f:
                        cpu_quota = int(f.read().strip())
                    with open('/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as f:
                        cpu_period = int(f.read().strip())
                    
                    if cpu_quota > 0:
                        cpu_limit = cpu_quota / cpu_period
                        container_metrics['cpu_limit'] = cpu_limit
                        print(f"   📦 Generic CPU Limit: {cpu_limit} cores")
                except:
                    pass
            
            if container_metrics:
                return container_metrics
            else:
                print("🖥️  No container detected - using host metrics")
                return None
                
        except Exception as e:
            print(f"⚠️  Error detecting container: {e}")
            return None
    
    @staticmethod
    def _parse_memory_value(value: float, unit: str) -> int:
        """Parse memory value with unit (e.g., 1.5GiB -> bytes)"""
        unit = unit.upper()
        multipliers = {
            'B': 1,
            'KB': 1024,
            'KIB': 1024,
            'MB': 1024**2,
            'MIB': 1024**2,
            'GB': 1024**3,
            'GIB': 1024**3,
            'TB': 1024**4,
            'TIB': 1024**4
        }
        
        multiplier = multipliers.get(unit, 1)
        return int(value * multiplier)

class DashboardAPIClient:
    """API client for multi_tenant_ide_dashboard integration - embedded in forwarder"""
    
    def __init__(self, server_url: str, customer_name: str, api_key: str):
        self.server_url = server_url.rstrip('/')
        self.customer_name = customer_name
        self.api_key = api_key
        self.customer_id = None
        self.service_id = None
        
        # Initialize customer and service
        self._setup_customer_and_service()
        
    def _setup_customer_and_service(self):
        """Setup customer and service for log forwarding"""
        try:
            # Ensure customer exists
            self.customer_id = self._ensure_customer()
            # Ensure service exists
            self.service_id = self._ensure_service("StreamingLogService")
            print(f"🔗 Dashboard API ready: {self.customer_name} -> StreamingLogService")
            
        except Exception as e:
            print(f"❌ Failed to setup API client: {e}")
            # Use fallback IDs
            self.customer_id = str(uuid.uuid4())
            self.service_id = str(uuid.uuid4())
    
    def _ensure_customer(self) -> str:
        """Ensure customer exists in dashboard database"""
        try:
            # First try to get existing customer by API key
            get_response = requests.get(
                f"{self.server_url}/api/db/customer/check",
                params={"api_key": self.api_key},
                timeout=10
            )
            
            print(f"🔍 Customer Check: {get_response.status_code} - {get_response.text}")
            
            if get_response.status_code == 200:
                customer_data = get_response.json()
                if customer_data.get('exists'):
                    customer_id = customer_data.get('customer_id')
                    print(f"✅ Found existing customer: {self.customer_name} (ID: {customer_id})")
                    return customer_id
            
            # Customer doesn't exist, try to create
            customer_data = {
                "id": str(uuid.uuid4()),
                "name": self.customer_name,
                "api_key": self.api_key
            }
            
            response = requests.post(
                f"{self.server_url}/api/db/customer/create",
                json=customer_data,
                timeout=10
            )
            
            print(f"🔍 Customer Create: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                print(f"✅ Customer created: {self.customer_name}")
                return customer_data["id"]
            else:
                print(f"⚠️  Customer creation failed, using fallback ID")
                # Use consistent fallback ID
                return hashlib.md5(self.api_key.encode()).hexdigest()[:16]
                
        except Exception as e:
            print(f"❌ Error ensuring customer: {e}")
            return hashlib.md5(self.api_key.encode()).hexdigest()[:16]
    
    def _ensure_service(self, service_name: str) -> str:
        """Ensure service exists in dashboard database"""
        try:
            # Check if service already exists
            check_response = requests.get(
                f"{self.server_url}/api/db/service/check",
                params={"customer_id": self.customer_id, "name": service_name},
                timeout=10
            )
            
            print(f"🔍 Service Check: {check_response.status_code} - {check_response.text}")
            
            if check_response.status_code == 200:
                service_data = check_response.json()
                if service_data.get('exists'):
                    service_id = service_data.get('service_id')
                    print(f"✅ Found existing service: {service_name} (ID: {service_id})")
                    return service_id
            
            # Service doesn't exist, create it
            service_data = {
                "id": str(uuid.uuid4()),
                "customer_id": self.customer_id,
                "name": service_name,
                "status": "active"
            }
            
            response = requests.post(
                f"{self.server_url}/api/db/service/create",
                json=service_data,
                timeout=10
            )
            
            print(f"🔍 Service Create: {response.status_code} - {response.text}")
            if response.status_code == 200:
                print(f"✅ Service created: {service_name}")
                return service_data["id"]
            else:
                print(f"⚠️  Service creation failed, using fallback ID")
                return str(uuid.uuid4())
                
        except Exception as e:
            print(f"❌ Error ensuring service: {e}")
            return str(uuid.uuid4())
    
    def send_log_as_incident(self, log_line: str, system_metrics: Dict[str, Any]) -> bool:
        """Send log line as incident with system metrics - core streaming function"""
        try:
            # Create alert first
            alert_id = self._create_alert(log_line, system_metrics)
            
            # Create incident
            incident_id = self._create_incident(alert_id, log_line, system_metrics)
            
            # Store the log entry
            self._store_log_entry(log_line, system_metrics)
            
            # Store individual system metrics for dashboard queries
            self._store_system_metrics(system_metrics)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to send incident: {e}")
            return False
    
    def _create_alert(self, log_line: str, system_metrics: Dict[str, Any]) -> str:
        """Create alert for the log entry"""
        try:
            # Calculate severity based on log content
            severity = self._calculate_severity(log_line)
            
            alert_data = {
                "id": str(uuid.uuid4()),
                "customer_id": self.customer_id,
                "service_id": self.service_id,
                "timestamp": datetime.utcnow().isoformat(),
                "alert_text": log_line[:500],  # Truncate if too long
                "severity": severity,
                "status": "open",
                "fingerprint": hashlib.md5(f"{self.service_id}:{log_line}".encode()).hexdigest()[:16]
            }
            
            response = requests.post(
                f"{self.server_url}/api/db/alert/create",
                json=alert_data,
                timeout=10
            )
            
            print(f"🔍 Alert API: {response.status_code} - {response.text[:200]}")
            return alert_data["id"]
            
        except Exception as e:
            print(f"❌ Error creating alert: {e}")
            return str(uuid.uuid4())
    
    def _create_incident(self, alert_id: str, log_line: str, system_metrics: Dict[str, Any]) -> str:
        """Create incident with comprehensive system metrics"""
        try:
            incident_data = {
                "id": str(uuid.uuid4()),
                "customer_id": self.customer_id,
                "alert_id": alert_id,
                "summary": log_line[:200],  # Summary of log line
                "score": self._calculate_severity(log_line),
                "status": "open",
                "google_doc_url": None,
                "is_alert_sent": False
            }
            
            response = requests.post(
                f"{self.server_url}/api/db/incident/create",
                json=incident_data,
                timeout=10
            )
            
            print(f"🔍 Incident API: {response.status_code} - {response.text[:200]}")
            
            # Store comprehensive analysis with system metrics
            if response.status_code == 200:
                print(f"✅ Incident created successfully!")
                self._store_incident_analysis(incident_data["id"], {
                    'log_entry': log_line,
                    'system_metrics': system_metrics,
                    'processor': 'streaming_log_forwarder_v1',
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                print(f"❌ Incident creation failed: {response.status_code}")
            
            return incident_data["id"]
            
        except Exception as e:
            print(f"❌ Error creating incident: {e}")
            return str(uuid.uuid4())
    
    def _store_log_entry(self, log_line: str, system_metrics: Dict[str, Any]):
        """Store the actual log entry"""
        try:
            log_data = {
                "logs": [{
                    "id": str(uuid.uuid4()),
                    "customer_id": self.customer_id,
                    "service_id": self.service_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": self._extract_log_level(log_line),
                    "message": log_line,
                    "metadata": json.dumps({
                        'system_metrics': system_metrics,
                        'source': 'streaming_forwarder'
                    })
                }]
            }
            
            requests.post(
                f"{self.server_url}/api/db/logs/create",
                json=log_data,
                timeout=10
            )
            
        except Exception as e:
            print(f"❌ Error storing log entry: {e}")
    
    def _store_incident_analysis(self, incident_id: str, analysis_data: Dict[str, Any]):
        """Store incident analysis with system metrics"""
        try:
            analysis_record = {
                "id": str(uuid.uuid4()),
                "incident_id": incident_id,
                "analysis_data": json.dumps(analysis_data)
            }
            
            requests.post(
                f"{self.server_url}/api/db/incident/analysis/create",
                json=analysis_record,
                timeout=10
            )
            
        except Exception as e:
            print(f"❌ Error storing analysis: {e}")
    
    def _store_system_metrics(self, system_metrics: Dict[str, Any]):
        """Store individual system metrics for dashboard queries"""
        try:
            if system_metrics.get('error'):
                return  # Skip if metrics collection failed
            
            timestamp = datetime.utcnow().isoformat()
            metrics_to_send = []
            
            # CPU Metrics
            cpu_data = system_metrics.get('cpu', {})
            if cpu_data:
                metrics_to_send.extend([
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "cpu_percent",
                        "value": cpu_data.get('percent', 0),
                        "unit": "%",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "cpu_count",
                        "value": cpu_data.get('count', 0),
                        "unit": "cores",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "load_average_1m",
                        "value": cpu_data.get('load_average', [0, 0, 0])[0],
                        "unit": "avg",
                        "category": "system"
                    }
                ])
            
            # Memory Metrics
            memory_data = system_metrics.get('memory', {})
            if memory_data:
                metrics_to_send.extend([
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "memory_percent",
                        "value": memory_data.get('percent', 0),
                        "unit": "%",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "memory_used_mb",
                        "value": round(memory_data.get('used', 0) / (1024*1024), 2),
                        "unit": "MB",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "memory_available_mb",
                        "value": round(memory_data.get('available', 0) / (1024*1024), 2),
                        "unit": "MB",
                        "category": "system"
                    }
                ])
            
            # Disk Metrics
            disk_data = system_metrics.get('disk', {})
            if disk_data:
                metrics_to_send.extend([
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "disk_percent",
                        "value": disk_data.get('percent', 0),
                        "unit": "%",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "disk_used_gb",
                        "value": round(disk_data.get('used', 0) / (1024*1024*1024), 2),
                        "unit": "GB",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "disk_free_gb",
                        "value": round(disk_data.get('free', 0) / (1024*1024*1024), 2),
                        "unit": "GB",
                        "category": "system"
                    }
                ])
            
            # Network Metrics
            network_data = system_metrics.get('network', {})
            if network_data:
                metrics_to_send.extend([
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "network_bytes_sent",
                        "value": network_data.get('bytes_sent', 0),
                        "unit": "bytes",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "network_bytes_recv",
                        "value": network_data.get('bytes_recv', 0),
                        "unit": "bytes",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "network_connections",
                        "value": network_data.get('connections', 0),
                        "unit": "count",
                        "category": "system"
                    }
                ])
            
            # System Process Metrics
            system_data = system_metrics.get('system', {})
            if system_data:
                metrics_to_send.extend([
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "process_count",
                        "value": system_data.get('process_count', 0),
                        "unit": "count",
                        "category": "system"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "customer_id": self.customer_id,
                        "service_id": self.service_id,
                        "timestamp": timestamp,
                        "name": "uptime_hours",
                        "value": round(system_data.get('uptime_seconds', 0) / 3600, 2),
                        "unit": "hours",
                        "category": "system"
                    }
                ])
            
            # Send all metrics in batch
            if metrics_to_send:
                response = requests.post(
                    f"{self.server_url}/api/db/metrics/create",
                    json={"metrics": metrics_to_send},
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"✅ Stored {len(metrics_to_send)} system metrics")
                else:
                    print(f"⚠️  Metrics storage response: {response.status_code} - {response.text[:100]}")
            
        except Exception as e:
            print(f"❌ Error storing system metrics: {e}")
    
    def _calculate_severity(self, log_line: str) -> float:
        """Calculate severity score based on log content"""
        log_lower = log_line.lower()
        
        if any(word in log_lower for word in ['error', 'exception', 'failed', 'critical']):
            return 8.0
        elif any(word in log_lower for word in ['warning', 'warn', 'timeout']):
            return 5.0
        elif any(word in log_lower for word in ['info', 'debug']):
            return 2.0
        else:
            return 3.0
    
    def _extract_log_level(self, log_line: str) -> str:
        """Extract log level from log line"""
        log_lower = log_line.lower()
        
        if 'error' in log_lower or 'exception' in log_lower:
            return 'ERROR'
        elif 'warning' in log_lower or 'warn' in log_lower:
            return 'WARNING'
        elif 'info' in log_lower:
            return 'INFO'
        elif 'debug' in log_lower:
            return 'DEBUG'
        else:
            return 'INFO'

class StreamingLogForwarder:
    """Real-time log streaming forwarder - implements chat screenshot architecture"""
    
    def __init__(self, log_file_path: str, dashboard_url: str, customer_name: str, api_key: str):
        self.log_file_path = log_file_path
        self.api_client = DashboardAPIClient(dashboard_url, customer_name, api_key)
        self.metrics_collector = SystemMetricsCollector()
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Send test incident on startup
        self._send_test_incident()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def _send_test_incident(self):
        """Send a test incident to verify API connectivity"""
        print("🧪 Sending test incident to verify API connection...")
        
        test_log = "TEST INCIDENT: Log forwarder startup verification - this is a test message"
        print("🔍 Getting test system metrics...")
        test_metrics = self.metrics_collector.get_system_metrics()
        
        # Verify metrics were collected
        if 'error' in test_metrics:
            print(f"❌ Test metrics collection failed: {test_metrics['error']}")
        else:
            print(f"✅ Test metrics collected successfully:")
            print(f"   CPU: {test_metrics.get('cpu', {}).get('percent', 'N/A')}%")
            print(f"   Memory: {test_metrics.get('memory', {}).get('percent', 'N/A')}%")
            print(f"   Disk: {test_metrics.get('disk', {}).get('percent', 'N/A'):.1f}%")
        
        success = self.api_client.send_log_as_incident(test_log, test_metrics)
        
        if success:
            print("✅ Test incident sent successfully! API connection working.")
        else:
            print("❌ Test incident failed! Check API connection and credentials.")
        
        print("-" * 60)
    
    def stream_logs(self):
        """Stream logs using tail -f approach from chat screenshot"""
        print(f"🚀 Starting real-time log streaming from {self.log_file_path}")
        print(f"📡 Streaming to dashboard with system metrics")
        
        try:
            # Use tail -f to stream logs in real-time (chat screenshot approach)
            process = subprocess.Popen(
                ['tail', '-f', self.log_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Process each line as it comes (real-time streaming)
            while self.running:
                line = process.stdout.readline()
                
                if line:
                    line = line.strip()
                    if line:  # Only process non-empty lines
                        # Get current system metrics
                        print(f"📡 LOG FORWARDER: Getting system metrics for log line: {line[:50]}...")
                        system_metrics = self.metrics_collector.get_system_metrics()
                        
                        # Check if metrics were collected successfully
                        if 'error' in system_metrics:
                            print(f"❌ LOG FORWARDER: Failed to collect metrics: {system_metrics['error']}")
                        else:
                            print(f"✅ LOG FORWARDER: Successfully collected metrics - CPU: {system_metrics.get('cpu', {}).get('percent', 'N/A')}%")
                        
                        # Send to dashboard
                        success = self.api_client.send_log_as_incident(line, system_metrics)
                        
                        if success:
                            print(f"✅ Streamed: {line[:100]}...")
                        else:
                            print(f"❌ Failed to stream: {line[:50]}...")
                
                # Check if process is still running
                if process.poll() is not None:
                    break
                    
        except FileNotFoundError:
            print(f"❌ Log file not found: {self.log_file_path}")
            print("💡 Make sure your app is running with: python app.py > /app.log &")
        except Exception as e:
            print(f"❌ Streaming error: {e}")
        finally:
            if 'process' in locals():
                process.terminate()
            print("🏁 Log streaming stopped")

def main():
    """Main function - now reads configuration from environment variables"""
    # Configuration from environment variables with defaults
    LOG_FILE_PATH = os.getenv('OVERCAST_LOG_FILE', '/app.log')
    DASHBOARD_URL = os.getenv('OVERCAST_DASHBOARD_URL', 'https://dashboard.overcastsre.com')
    API_KEY = os.getenv('OVERCAST_API_KEY', 'default-key')
    
    # Customer name is optional - will derive from API key if not provided
    CUSTOMER_NAME = os.getenv('OVERCAST_CUSTOMER_NAME')
    if not CUSTOMER_NAME:
        # Generate customer name from API key for consistency
        import hashlib
        CUSTOMER_NAME = f"Customer-{hashlib.md5(API_KEY.encode()).hexdigest()[:8]}"
    
    # Validate required configuration
    if not API_KEY or API_KEY == 'default-key':
        print("❌ OVERCAST_API_KEY environment variable is required!")
        print("💡 Set it in your .env file or environment variables")
        sys.exit(1)
    
    print("=" * 60)
    print("   STREAMING LOG FORWARDER - CONFIGURABLE")
    print("=" * 60)
    print(f"📁 Log file: {LOG_FILE_PATH}")
    print(f"🌐 Dashboard: {DASHBOARD_URL}")
    print(f"👤 Customer: {CUSTOMER_NAME}")
    print(f"🔑 API Key: {API_KEY[:8]}...")
    print("=" * 60)
    
    # Create and start forwarder
    forwarder = StreamingLogForwarder(
        log_file_path=LOG_FILE_PATH,
        dashboard_url=DASHBOARD_URL, 
        customer_name=CUSTOMER_NAME,
        api_key=API_KEY
    )
    
    # Start streaming (this will run until interrupted)
    forwarder.stream_logs()

if __name__ == "__main__":
    main() 