from rest_framework import viewsets, status, generics, views, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .models import Order, OrderItem, OrderStatusHistory, OrderCancellation
from .serializers import (
    OrderListSerializer,
    OrderDetailSerializer,
    OrderCreateSerializer,
    OrderUpdateSerializer,
    OrderTrackingSerializer,
    OrderCancellationCreateSerializer,
    OrderCancellationSerializer,
)
from .permissions import CanManageOrders
from .tasks import send_order_confirmation, update_order_status

logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Order ViewSet
    GET /api/orders/ - List user's orders
    POST /api/orders/ - Create new order
    GET /api/orders/<id>/ - Get order details
    PUT /api/orders/<id>/ - Update order
    """
    permission_classes = [IsAuthenticated, CanManageOrders]
    lookup_field = 'id'
    
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'is_paid', 'payment_method']
    ordering_fields = ['created_at', 'total_amount', 'status']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use different serializer based on action"""
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action == 'retrieve':
            return OrderDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return OrderUpdateSerializer
        elif self.action == 'track':
            return OrderTrackingSerializer
        return OrderListSerializer
    
    def get_queryset(self):
        """Return orders based on user role"""
        user = self.request.user
        
        if user.is_staff:
            # Admins see all orders
            return Order.objects.all()
        
        # Regular users see only their orders
        return Order.objects.filter(customer=user)
    
    def create(self, request, *args, **kwargs):
        """Create new order"""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        
        # Send confirmation email/WhatsApp
        send_order_confirmation.delay(order.id)
        
        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Update order details (delivery info, etc.)"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Only allow updating certain fields for non-admin users
        if not request.user.is_staff:
            # Users can only update delivery details on pending orders
            if instance.status not in ['pending', 'confirmed']:
                return Response({
                    'error': 'Cannot update order in current status'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(
            OrderDetailSerializer(instance).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def track(self, request, pk=None):
        """Track order status and shipping"""
        order = self.get_object()
        serializer = OrderTrackingSerializer(order)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm order (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        order = self.get_object()
        
        if order.status != 'pending':
            return Response({
                'error': f'Cannot confirm order in {order.status} status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not order.is_paid:
            return Response({
                'error': 'Order must be paid before confirmation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        order.status = 'confirmed'
        order.save()
        
        OrderStatusHistory.objects.create(
            order=order,
            from_status='pending',
            to_status='confirmed',
            reason='Order confirmed by admin',
            changed_by=request.user
        )
        
        # Send notification
        update_order_status.delay(order.id, 'confirmed')
        
        return Response({
            'order': OrderDetailSerializer(order).data,
            'message': 'Order confirmed successfully'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Mark order as processing (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        order = self.get_object()
        
        if order.status not in ['confirmed', 'pending']:
            return Response({
                'error': f'Cannot process order in {order.status} status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        order.status = 'processing'
        order.save()
        
        OrderStatusHistory.objects.create(
            order=order,
            from_status=order.status,
            to_status='processing',
            reason=request.data.get('reason', 'Processing'),
            changed_by=request.user
        )
        
        update_order_status.delay(order.id, 'processing')
        
        return Response({
            'order': OrderDetailSerializer(order).data,
            'message': 'Order marked as processing'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """Mark order as shipped (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        order = self.get_object()
        tracking_number = request.data.get('tracking_number')
        
        if order.status not in ['processing', 'confirmed']:
            return Response({
                'error': f'Cannot ship order in {order.status} status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from django.utils import timezone
        
        order.status = 'in_transit'
        order.shipped_date = timezone.now()
        order.tracking_number = tracking_number
        order.save()
        
        OrderStatusHistory.objects.create(
            order=order,
            from_status='processing',
            to_status='in_transit',
            reason=f'Shipped with tracking: {tracking_number}',
            changed_by=request.user
        )
        
        update_order_status.delay(order.id, 'in_transit')
        
        return Response({
            'order': OrderDetailSerializer(order).data,
            'message': 'Order marked as shipped'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def deliver(self, request, pk=None):
        """Mark order as delivered (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        order = self.get_object()
        
        if order.status not in ['in_transit', 'processing']:
            return Response({
                'error': f'Cannot mark as delivered in {order.status} status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from django.utils import timezone
        
        order.status = 'delivered'
        order.delivered_date = timezone.now()
        order.save()
        
        OrderStatusHistory.objects.create(
            order=order,
            from_status='in_transit',
            to_status='delivered',
            reason='Order delivered',
            changed_by=request.user
        )
        
        # Send delivery confirmation
        from .tasks import send_delivery_confirmation
        send_delivery_confirmation.delay(order.id)
        
        return Response({
            'order': OrderDetailSerializer(order).data,
            'message': 'Order marked as delivered'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel order"""
        order = self.get_object()
        
        # Check if user can cancel
        if not request.user.is_staff and request.user != order.customer:
            return Response({
                'error': 'You can only cancel your own orders'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if not order.can_be_cancelled():
            return Response({
                'error': f'Cannot cancel order in {order.status} status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        reason = request.data.get('reason', 'Cancelled by customer')
        details = request.data.get('details', '')
        
        order.status = 'cancelled'
        order.save()
        
        # Create cancellation record
        OrderCancellation.objects.create(
            order=order,
            reason=reason,
            details=details,
            refund_amount=order.total_amount if order.is_paid else 0,
            cancelled_by=request.user
        )
        
        # Release reserved stock
        for item in order.items.all():
            item.product.reserved_quantity -= item.quantity
            item.product.save()
        
        logger.info(f"Order {order.order_id} cancelled by {request.user}")
        
        return Response({
            'order': OrderDetailSerializer(order).data,
            'message': 'Order cancelled successfully'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """Get current user's orders"""
        orders = Order.objects.filter(customer=request.user).order_by('-created_at')
        
        # Pagination
        page = request.query_params.get('page', 1)
        limit = request.query_params.get('limit', 10)
        
        start = (int(page) - 1) * int(limit)
        end = start + int(limit)
        
        total = orders.count()
        orders = orders[start:end]
        
        serializer = OrderListSerializer(orders, many=True)
        
        return Response({
            'total': total,
            'page': page,
            'limit': limit,
            'results': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending orders (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        orders = Order.objects.filter(status='pending').order_by('created_at')
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unpaid(self, request):
        """Get unpaid orders (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        orders = Order.objects.filter(is_paid=False).order_by('created_at')
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get order statistics (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Today's stats
        today_orders = Order.objects.filter(created_at__date=today)
        today_revenue = today_orders.filter(is_paid=True).aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0
        
        # Week stats
        week_orders = Order.objects.filter(created_at__date__gte=week_ago)
        week_revenue = week_orders.filter(is_paid=True).aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0
        
        # Month stats
        month_orders = Order.objects.filter(created_at__date__gte=month_ago)
        month_revenue = month_orders.filter(is_paid=True).aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0
        
        # Total stats
        total_orders = Order.objects.count()
        paid_orders = Order.objects.filter(is_paid=True).count()
        total_revenue = Order.objects.filter(is_paid=True).aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0
        
        # Status breakdown
        status_breakdown = Order.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        return Response({
            'today': {
                'orders': today_orders.count(),
                'revenue': float(today_revenue)
            },
            'week': {
                'orders': week_orders.count(),
                'revenue': float(week_revenue)
            },
            'month': {
                'orders': month_orders.count(),
                'revenue': float(month_revenue)
            },
            'total': {
                'orders': total_orders,
                'paid_orders': paid_orders,
                'revenue': float(total_revenue)
            },
            'status_breakdown': list(status_breakdown)
        }, status=status.HTTP_200_OK)


class OrderTrackingView(generics.RetrieveAPIView):
    """
    Track order by order_id
    GET /api/orders/track/<order_id>/
    """
    serializer_class = OrderTrackingSerializer
    permission_classes = [AllowAny]
    lookup_field = 'order_id'
    
    def get_queryset(self):
        """Get order by order_id"""
        return Order.objects.all()


class CancelOrderView(views.APIView):
    """
    Cancel specific order
    POST /api/orders/cancel/<order_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, order_id):
        """Cancel order by ID"""
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        if not request.user.is_staff and request.user != order.customer:
            return Response({
                'error': 'You can only cancel your own orders'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if not order.can_be_cancelled():
            return Response({
                'error': f'Cannot cancel order in {order.status} status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        order.status = 'cancelled'
        order.save()
        
        OrderCancellation.objects.create(
            order=order,
            reason=request.data.get('reason', 'Cancelled'),
            refund_amount=order.total_amount if order.is_paid else 0,
            cancelled_by=request.user
        )
        
        return Response({
            'order': OrderDetailSerializer(order).data,
            'message': 'Order cancelled'
        }, status=status.HTTP_200_OK)