"""Sensor health monitoring and statistics."""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SensorHealth:
    """Track sensor read success/failure and provide health statistics."""
    
    def __init__(self):
        self.sensors: Dict[str, Dict[str, Any]] = {}
        self.total_reads = 0
        self.successful_reads = 0
        self.failed_reads = 0
        self.last_update = None
    
    def record_sensor(self, sensor_id: str, value: Any, success: bool = True):
        """Record a sensor reading."""
        if sensor_id not in self.sensors:
            self.sensors[sensor_id] = {
                'total': 0,
                'success': 0,
                'failed': 0,
                'last_value': None,
                'last_success': None,
                'last_failure': None,
                'value_type': None
            }
        
        sensor = self.sensors[sensor_id]
        sensor['total'] += 1
        
        if success and value is not None:
            sensor['success'] += 1
            sensor['last_value'] = value
            sensor['last_success'] = datetime.now()
            sensor['value_type'] = type(value).__name__
            self.successful_reads += 1
        else:
            sensor['failed'] += 1
            sensor['last_failure'] = datetime.now()
            self.failed_reads += 1
        
        self.total_reads += 1
        self.last_update = datetime.now()
    
    def get_sensor_health(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        """Get health statistics for a specific sensor."""
        if sensor_id not in self.sensors:
            return None
        
        sensor = self.sensors[sensor_id]
        success_rate = (sensor['success'] / sensor['total'] * 100) if sensor['total'] > 0 else 0
        
        return {
            'sensor_id': sensor_id,
            'total_reads': sensor['total'],
            'successful': sensor['success'],
            'failed': sensor['failed'],
            'success_rate': round(success_rate, 2),
            'last_value': sensor['last_value'],
            'value_type': sensor['value_type'],
            'last_success': sensor['last_success'],
            'last_failure': sensor['last_failure'],
            'status': 'healthy' if success_rate >= 95 else 'degraded' if success_rate >= 80 else 'unhealthy'
        }
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall health statistics."""
        success_rate = (self.successful_reads / self.total_reads * 100) if self.total_reads > 0 else 0
        
        healthy_sensors = sum(1 for s in self.sensors.values() if (s['success'] / s['total'] * 100) >= 95)
        degraded_sensors = sum(1 for s in self.sensors.values() if 80 <= (s['success'] / s['total'] * 100) < 95)
        unhealthy_sensors = sum(1 for s in self.sensors.values() if (s['success'] / s['total'] * 100) < 80)
        
        return {
            'total_sensors': len(self.sensors),
            'total_reads': self.total_reads,
            'successful_reads': self.successful_reads,
            'failed_reads': self.failed_reads,
            'overall_success_rate': round(success_rate, 2),
            'healthy_sensors': healthy_sensors,
            'degraded_sensors': degraded_sensors,
            'unhealthy_sensors': unhealthy_sensors,
            'last_update': self.last_update
        }
    
    def get_summary(self) -> str:
        """Get a formatted summary of sensor health."""
        overall = self.get_overall_health()
        
        lines = [
            "\n" + "="*60,
            "SENSOR HEALTH DASHBOARD",
            "="*60,
            f"Total Sensors: {overall['total_sensors']}",
            f"Total Reads: {overall['total_reads']}",
            f"Success Rate: {overall['overall_success_rate']}%",
            f"",
            f"Sensor Status:",
            f"  ✓ Healthy (≥95%): {overall['healthy_sensors']}",
            f"  ⚠ Degraded (80-95%): {overall['degraded_sensors']}",
            f"  ✗ Unhealthy (<80%): {overall['unhealthy_sensors']}",
            f"",
            f"Last Update: {overall['last_update'].strftime('%Y-%m-%d %H:%M:%S') if overall['last_update'] else 'Never'}",
            "="*60
        ]
        
        # Add problematic sensors
        if overall['degraded_sensors'] > 0 or overall['unhealthy_sensors'] > 0:
            lines.append("\nProblematic Sensors:")
            for sensor_id, data in sorted(self.sensors.items()):
                success_rate = (data['success'] / data['total'] * 100) if data['total'] > 0 else 0
                if success_rate < 95:
                    status_icon = "⚠" if success_rate >= 80 else "✗"
                    lines.append(f"  {status_icon} {sensor_id}: {success_rate:.1f}% ({data['success']}/{data['total']})")
        
        # Add sensor type breakdown
        type_counts = {}
        for sensor_id, data in self.sensors.items():
            vtype = data['value_type'] or 'None'
            type_counts[vtype] = type_counts.get(vtype, 0) + 1
        
        if type_counts:
            lines.append("\nSensor Value Types:")
            for vtype, count in sorted(type_counts.items()):
                lines.append(f"  {vtype}: {count}")
        
        lines.append("="*60 + "\n")
        
        return "\n".join(lines)
    
    def get_detailed_report(self) -> str:
        """Get a detailed report of all sensors."""
        lines = [
            "\n" + "="*80,
            "DETAILED SENSOR REPORT",
            "="*80,
            ""
        ]
        
        for sensor_id in sorted(self.sensors.keys()):
            health = self.get_sensor_health(sensor_id)
            if not health:
                continue
            
            status_icon = "✓" if health['status'] == 'healthy' else "⚠" if health['status'] == 'degraded' else "✗"
            
            lines.extend([
                f"{status_icon} {sensor_id}",
                f"  Status: {health['status'].upper()}",
                f"  Success Rate: {health['success_rate']}%",
                f"  Reads: {health['successful']}/{health['total_reads']} successful",
                f"  Last Value: {health['last_value']} ({health['value_type']})",
                f"  Last Success: {health['last_success'].strftime('%Y-%m-%d %H:%M:%S') if health['last_success'] else 'Never'}",
                ""
            ])
        
        lines.append("="*80 + "\n")
        
        return "\n".join(lines)
