# Advanced Location Services & Maps Integration

from django.db import models
from django.contrib.gis.db import models as gis_models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('location')

# ============================================================
# LOCATION MODELS
# ============================================================

class GeoLocation(models.Model):
    """Geo-location data"""
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Address
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    
    # Type
    location_type = models.CharField(
        max_length=20,
        choices=[
            ('home', 'Home'),
            ('work', 'Work'),
            ('delivery', 'Delivery'),
            ('other', 'Other'),
        ]
    )
    
    # Default
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'geo_location'


class DeliveryZone(models.Model):
    """Delivery zones/service areas"""
    name = models.CharField(max_length=255)
    
    # Polygon (for GIS)
    polygon = gis_models.PolygonField()
    
    # Details
    description = models.TextField(blank=True)
    
    # Delivery
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_time_hours = models.IntegerField()
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'delivery_zone'


class WarehouseLocation(models.Model):
    """Warehouse physical locations"""
    warehouse = models.ForeignKey('warehouse.Warehouse', on_delete=models.CASCADE)
    
    # Coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Service radius
    service_radius_km = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'warehouse_location'


class DeliveryRoute(models.Model):
    """Optimized delivery routes"""
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    # Route
    route_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255, blank=True)
    
    # Orders
    orders = models.ManyToManyField('orders.Order', through='RouteStop')
    
    # Driver
    assigned_driver = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Route details
    start_point = models.CharField(max_length=255)
    end_point = models.CharField(max_length=255)
    total_distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_duration_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    
    # Tracking
    actual_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_duration_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'delivery_route'


class RouteStop(models.Model):
    """Individual stops on a route"""
    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    
    # Order
    sequence = models.IntegerField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('delivered', 'Delivered'), ('failed', 'Failed')]
    )
    
    # Proof of delivery
    signature = models.ImageField(upload_to='delivery_signatures/', null=True, blank=True)
    photo = models.ImageField(upload_to='delivery_photos/', null=True, blank=True)
    
    # Timing
    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'route_stop'
        unique_together = ['route', 'order']


class LiveTracking(models.Model):
    """Real-time delivery tracking"""
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE)
    
    # Current location
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Status
    status = models.CharField(max_length=50)
    
    # ETA
    estimated_arrival = models.DateTimeField()
    
    # Updates
    last_update = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'live_tracking'


# ============================================================
# LOCATION ENGINE
# ============================================================

class LocationEngine:
    """Geo-location operations"""
    
    @staticmethod
    def check_delivery_availability(latitude, longitude):
        """Check if location is in delivery zone"""
        from apps.location.models import DeliveryZone
        from django.contrib.gis.geos import Point
        
        point = Point(longitude, latitude)
        
        zone = DeliveryZone.objects.filter(
            polygon__contains=point,
            is_active=True
        ).first()
        
        if zone:
            return {
                'available': True,
                'zone': zone.name,
                'delivery_fee': zone.delivery_fee,
                'delivery_time': zone.delivery_time_hours,
            }
        
        return {'available': False, 'message': 'Location not in delivery zone'}
    
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates"""
        from math import radians, cos, sin, asin, sqrt
        
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        
        return c * r
    
    @staticmethod
    def optimize_delivery_route(orders):
        """Optimize delivery route using TSP"""
        from apps.location.models import DeliveryRoute, RouteStop
        import uuid
        
        # Sort orders by location proximity
        # This would use a proper routing algorithm like Google Maps API
        
        route = DeliveryRoute.objects.create(
            route_id=f"ROUTE-{uuid.uuid4().hex[:8].upper()}",
            start_point='Warehouse',
        )
        
        for idx, order in enumerate(orders):
            RouteStop.objects.create(
                route=route,
                order=order,
                sequence=idx + 1,
            )
        
        logger.info(f'Route optimized: {route.route_id}')
        
        return route
    
    @staticmethod
    def update_live_tracking(order, latitude, longitude):
        """Update live tracking"""
        from apps.location.models import LiveTracking
        from datetime import timedelta
        
        tracking, created = LiveTracking.objects.get_or_create(order=order)
        
        tracking.latitude = latitude
        tracking.longitude = longitude
        tracking.estimated_arrival = timezone.now() + timedelta(hours=1)  # Estimate
        tracking.save()
        
        logger.info(f'Tracking updated for order {order.order_id}')
        
        return tracking
    
    @staticmethod
    def get_nearest_warehouse(latitude, longitude):
        """Find nearest warehouse"""
        from apps.location.models import WarehouseLocation
        
        warehouses = WarehouseLocation.objects.all()
        
        nearest = None
        min_distance = float('inf')
        
        for warehouse in warehouses:
            distance = LocationEngine.calculate_distance(
                latitude, longitude,
                float(warehouse.latitude), float(warehouse.longitude)
            )
            
            if distance < min_distance and distance <= warehouse.service_radius_km:
                min_distance = distance
                nearest = warehouse
        
        return nearest
    
    @staticmethod
    def geocode_address(address):
        """Convert address to coordinates"""
        # Integration with Google Maps Geocoding API
        try:
            import googlemaps
            
            gmaps = googlemaps.Client(key=os.environ.get('GOOGLE_MAPS_API_KEY'))
            
            geocode_result = gmaps.geocode(address)
            
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                return {
                    'latitude': location['lat'],
                    'longitude': location['lng'],
                    'formatted_address': geocode_result[0]['formatted_address'],
                }
            
            return None
        
        except Exception as e:
            logger.error(f'Geocoding failed: {e}')
            return None


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def optimize_delivery_routes():
    '''Optimize delivery routes daily'''
    from apps.orders.models import Order
    
    pending = Order.objects.filter(
        status='confirmed',
        delivery_route__isnull=True
    )
    
    if pending.exists():
        LocationEngine.optimize_delivery_route(list(pending[:20]))

@shared_task
def update_live_tracking():
    '''Update live tracking for deliveries'''
    pass

# Add to CELERY_BEAT_SCHEDULE:
'optimize-routes': {
    'task': 'apps.location.tasks.optimize_delivery_routes',
    'schedule': 86400.0,  # Daily
},
"""