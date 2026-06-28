# IoT Integration & Smart Device Management System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('iot')

# ============================================================
# IOT MODELS
# ============================================================

class IoTDevice(models.Model):
    """IoT device management"""
    DEVICE_TYPE = [
        ('temperature_sensor', 'Temperature Sensor'),
        ('humidity_sensor', 'Humidity Sensor'),
        ('scale', 'Smart Scale'),
        ('camera', 'Security Camera'),
        ('tracker', 'GPS Tracker'),
        ('smart_fridge', 'Smart Refrigerator'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]
    
    # Device
    device_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPE)
    
    # Connection
    api_key = models.CharField(max_length=255)
    webhook_url = models.URLField(blank=True)
    
    # Location
    warehouse = models.ForeignKey('warehouse.Warehouse', on_delete=models.CASCADE)
    location_details = models.CharField(max_length=255, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_heartbeat = models.DateTimeField()
    
    # Battery (for wireless devices)
    battery_level = models.IntegerField(null=True, blank=True)  # %
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'iot_device'


class IoTReading(models.Model):
    """IoT sensor readings"""
    device = models.ForeignKey(IoTDevice, on_delete=models.CASCADE)
    
    # Reading
    reading_type = models.CharField(max_length=100)  # temperature, humidity, weight
    value = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20)  # C, %, kg
    
    # Quality
    is_valid = models.BooleanField(default=True)
    quality_score = models.IntegerField(default=100)  # 0-100
    
    # Timestamp
    timestamp = models.DateTimeField()
    
    class Meta:
        db_table = 'iot_reading'
        indexes = [
            models.Index(fields=['device', '-timestamp']),
        ]


class IoTAlert(models.Model):
    """IoT alerts and anomalies"""
    ALERT_TYPE = [
        ('temperature_high', 'Temperature Too High'),
        ('temperature_low', 'Temperature Too Low'),
        ('humidity_high', 'Humidity Too High'),
        ('battery_low', 'Battery Low'),
        ('device_offline', 'Device Offline'),
        ('anomaly', 'Data Anomaly'),
    ]
    
    SEVERITY = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    device = models.ForeignKey(IoTDevice, on_delete=models.CASCADE)
    
    # Alert
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPE)
    severity = models.CharField(max_length=20, choices=SEVERITY)
    
    # Details
    message = models.TextField()
    reading = models.ForeignKey(IoTReading, null=True, blank=True, on_delete=models.SET_NULL)
    
    # Status
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'iot_alert'
        ordering = ['-severity', '-created_at']


class SmartRefrigerator(models.Model):
    """Smart refrigerator inventory tracking"""
    device = models.OneToOneField(IoTDevice, on_delete=models.CASCADE)
    
    # Inventory
    capacity = models.IntegerField()  # Liters
    current_load = models.IntegerField()  # %
    
    # Contents
    products = models.JSONField(default=list)  # List of products and quantities
    
    # Settings
    target_temperature = models.IntegerField(default=4)  # Celsius
    
    # Alerts
    low_stock_threshold = models.IntegerField(default=20)  # %
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'smart_refrigerator'


class TemperatureLog(models.Model):
    """Historical temperature logs"""
    warehouse = models.ForeignKey('warehouse.Warehouse', on_delete=models.CASCADE)
    
    # Temperature
    temperature = models.DecimalField(max_digits=5, decimal_places=2)
    humidity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Compliance
    is_within_range = models.BooleanField(default=True)
    
    timestamp = models.DateTimeField()
    
    class Meta:
        db_table = 'temperature_log'
        ordering = ['-timestamp']


# ============================================================
# IOT ENGINE
# ============================================================

class IoTEngine:
    """IoT operations"""
    
    @staticmethod
    def register_device(device_id, device_type, warehouse_id):
        """Register new IoT device"""
        from apps.iot.models import IoTDevice
        import secrets
        
        device = IoTDevice.objects.create(
            device_id=device_id,
            name=f"{device_type} - {device_id}",
            device_type=device_type,
            warehouse_id=warehouse_id,
            api_key=secrets.token_urlsafe(32),
            last_heartbeat=timezone.now(),
        )
        
        logger.info(f'IoT device registered: {device_id}')
        
        return device
    
    @staticmethod
    def process_reading(device_id, reading_type, value, unit):
        """Process IoT reading"""
        from apps.iot.models import IoTDevice, IoTReading, IoTAlert
        
        try:
            device = IoTDevice.objects.get(device_id=device_id)
        except IoTDevice.DoesNotExist:
            logger.error(f'Device not found: {device_id}')
            return None
        
        # Create reading
        reading = IoTReading.objects.create(
            device=device,
            reading_type=reading_type,
            value=value,
            unit=unit,
            timestamp=timezone.now(),
        )
        
        # Check for anomalies
        if reading_type == 'temperature':
            if value > 25:
                IoTAlert.objects.create(
                    device=device,
                    alert_type='temperature_high',
                    severity='warning',
                    message=f'Temperature: {value}°C',
                    reading=reading,
                )
            elif value < 2:
                IoTAlert.objects.create(
                    device=device,
                    alert_type='temperature_low',
                    severity='critical',
                    message=f'Temperature: {value}°C',
                    reading=reading,
                )
        
        # Update device heartbeat
        device.last_heartbeat = timezone.now()
        device.status = 'active'
        device.save()
        
        logger.debug(f'Reading processed: {device_id} - {reading_type}: {value}{unit}')
        
        return reading
    
    @staticmethod
    def check_device_health():
        """Check health of all IoT devices"""
        from apps.iot.models import IoTDevice, IoTAlert
        
        devices = IoTDevice.objects.filter(status='active')
        
        for device in devices:
            # Check last heartbeat
            time_since_heartbeat = (timezone.now() - device.last_heartbeat).total_seconds()
            
            if time_since_heartbeat > 3600:  # 1 hour
                device.status = 'inactive'
                device.save()
                
                IoTAlert.objects.create(
                    device=device,
                    alert_type='device_offline',
                    severity='critical',
                    message=f'Device offline for {time_since_heartbeat} seconds',
                )
                
                logger.warning(f'Device offline: {device.device_id}')
    
    @staticmethod
    def analyze_temperature_trends(warehouse_id):
        """Analyze temperature trends"""
        from apps.iot.models import TemperatureLog
        from django.db.models import Avg
        
        # Last 24 hours
        logs = TemperatureLog.objects.filter(
            warehouse_id=warehouse_id,
            timestamp__gte=timezone.now() - timedelta(hours=24)
        )
        
        if logs.exists():
            avg_temp = logs.aggregate(Avg('temperature'))['temperature__avg']
            min_temp = logs.aggregate(models.Min('temperature'))['temperature__min']
            max_temp = logs.aggregate(models.Max('temperature'))['temperature__max']
            
            return {
                'avg_temperature': avg_temp,
                'min_temperature': min_temp,
                'max_temperature': max_temp,
                'readings_count': logs.count(),
            }
        
        return None
    
    @staticmethod
    def update_smart_fridge_inventory(device_id, products):
        """Update smart refrigerator inventory"""
        from apps.iot.models import SmartRefrigerator
        
        try:
            fridge = SmartRefrigerator.objects.get(device__device_id=device_id)
            fridge.products = products
            fridge.save()
            
            logger.info(f'Fridge inventory updated: {device_id}')
        
        except SmartRefrigerator.DoesNotExist:
            logger.error(f'Smart fridge not found: {device_id}')


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def check_iot_device_health():
    '''Check health of all IoT devices'''
    IoTEngine.check_device_health()

@shared_task
def process_iot_alerts():
    '''Process pending IoT alerts'''
    from apps.iot.models import IoTAlert
    
    critical = IoTAlert.objects.filter(
        severity='critical',
        is_acknowledged=False
    )
    
    for alert in critical:
        # Send notification
        pass

# Add to CELERY_BEAT_SCHEDULE:
'check-iot-health': {
    'task': 'apps.iot.tasks.check_iot_device_health',
    'schedule': 600.0,  # Every 10 minutes
},
'process-alerts': {
    'task': 'apps.iot.tasks.process_iot_alerts',
    'schedule': 300.0,  # Every 5 minutes
},
"""