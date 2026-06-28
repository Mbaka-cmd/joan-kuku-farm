from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class DashboardView(views.APIView):
    """
    Main dashboard with all stats
    GET /api/analytics/dashboard/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get dashboard data"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from apps.orders.models import Order
        from apps.payments.models import Payment
        from apps.products.models import Product
        from apps.users.models import CustomUser
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Key Metrics
        total_orders = Order.objects.count()
        total_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        total_customers = CustomUser.objects.filter(is_verified=True).count()
        total_products = Product.objects.filter(is_active=True).count()
        
        # Today's metrics
        today_orders = Order.objects.filter(created_at__date=today).count()
        today_revenue = Payment.objects.filter(
            status='completed',
            completed_at__date=today
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Orders trend (last 7 days)
        orders_trend = []
        for i in range(7, 0, -1):
            date = today - timedelta(days=i)
            count = Order.objects.filter(created_at__date=date).count()
            revenue = Payment.objects.filter(
                status='completed',
                completed_at__date=date
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            orders_trend.append({
                'date': str(date),
                'orders': count,
                'revenue': float(revenue)
            })
        
        # Revenue trend (last 30 days)
        revenue_trend = []
        for i in range(30, 0, -1):
            date = today - timedelta(days=i)
            revenue = Payment.objects.filter(
                status='completed',
                completed_at__date=date
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            revenue_trend.append({
                'date': str(date),
                'revenue': float(revenue)
            })
        
        # Order status breakdown
        status_breakdown = Order.objects.values('status').annotate(
            count=Count('id')
        )
        
        # Top products
        top_products = Product.objects.annotate(
            order_count=Count('orderitem')
        ).filter(
            is_active=True,
            order_count__gt=0
        ).order_by('-order_count')[:5]
        
        top_products_data = [{
            'id': p.id,
            'name': p.name,
            'orders': p.order_count,
            'price': str(p.price),
            'stock': p.stock
        } for p in top_products]
        
        # Recent orders
        recent_orders = Order.objects.all().order_by('-created_at')[:10]
        recent_orders_data = [{
            'order_id': o.order_id,
            'customer': o.customer.get_full_name(),
            'amount': str(o.total_amount),
            'status': o.status,
            'created_at': o.created_at
        } for o in recent_orders]
        
        return Response({
            'summary': {
                'total_orders': total_orders,
                'total_revenue': float(total_revenue),
                'total_customers': total_customers,
                'total_products': total_products,
                'today_orders': today_orders,
                'today_revenue': float(today_revenue)
            },
            'trends': {
                'orders_7_days': orders_trend,
                'revenue_30_days': revenue_trend
            },
            'breakdown': {
                'order_status': list(status_breakdown)
            },
            'top_products': top_products_data,
            'recent_orders': recent_orders_data
        }, status=status.HTTP_200_OK)


class OrdersAnalyticsView(views.APIView):
    """
    Orders analytics and trends
    GET /api/analytics/orders/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get orders analytics"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from apps.orders.models import Order
        
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)
        
        # Total orders
        total = Order.objects.count()
        paid = Order.objects.filter(is_paid=True).count()
        unpaid = Order.objects.filter(is_paid=False).count()
        
        # Status breakdown
        statuses = {
            'pending': Order.objects.filter(status='pending').count(),
            'confirmed': Order.objects.filter(status='confirmed').count(),
            'processing': Order.objects.filter(status='processing').count(),
            'in_transit': Order.objects.filter(status='in_transit').count(),
            'delivered': Order.objects.filter(status='delivered').count(),
            'cancelled': Order.objects.filter(status='cancelled').count(),
        }
        
        # Average order value
        avg_order_value = Order.objects.filter(
            is_paid=True
        ).aggregate(Avg('total_amount'))['total_amount__avg'] or 0
        
        # Orders by date (last 30 days)
        daily_orders = []
        for i in range(30, 0, -1):
            date = today - timedelta(days=i)
            count = Order.objects.filter(created_at__date=date).count()
            daily_orders.append({
                'date': str(date),
                'count': count
            })
        
        # Payment method breakdown
        payment_methods = Order.objects.values('payment_method').annotate(
            count=Count('id')
        )
        
        return Response({
            'total': total,
            'paid': paid,
            'unpaid': unpaid,
            'status_breakdown': statuses,
            'average_value': float(avg_order_value),
            'daily_orders': daily_orders,
            'payment_methods': list(payment_methods)
        }, status=status.HTTP_200_OK)


class RevenueAnalyticsView(views.APIView):
    """
    Revenue analytics
    GET /api/analytics/revenue/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get revenue analytics"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from apps.payments.models import Payment
        from apps.orders.models import Order
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Total revenue
        total_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # By period
        today_revenue = Payment.objects.filter(
            status='completed',
            completed_at__date=today
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        week_revenue = Payment.objects.filter(
            status='completed',
            completed_at__date__gte=week_ago
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        month_revenue = Payment.objects.filter(
            status='completed',
            completed_at__date__gte=month_ago
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # By payment method
        by_method = Payment.objects.filter(
            status='completed'
        ).values('method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Daily revenue
        daily_revenue = []
        for i in range(30, 0, -1):
            date = today - timedelta(days=i)
            revenue = Payment.objects.filter(
                status='completed',
                completed_at__date=date
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            daily_revenue.append({
                'date': str(date),
                'revenue': float(revenue)
            })
        
        return Response({
            'total': float(total_revenue),
            'by_period': {
                'today': float(today_revenue),
                'week': float(week_revenue),
                'month': float(month_revenue)
            },
            'by_method': list(by_method),
            'daily': daily_revenue
        }, status=status.HTTP_200_OK)


class ProductsAnalyticsView(views.APIView):
    """
    Products analytics
    GET /api/analytics/products/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get products analytics"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from apps.products.models import Product, Category
        from apps.orders.models import OrderItem
        
        # Total products
        total = Product.objects.filter(is_active=True).count()
        low_stock = Product.objects.filter(
            is_active=True,
            stock__lte=10
        ).count()
        out_of_stock = Product.objects.filter(
            is_active=True,
            stock=0
        ).count()
        
        # Top products by orders
        top_products = Product.objects.annotate(
            order_count=Count('orderitem')
        ).filter(
            is_active=True,
            order_count__gt=0
        ).order_by('-order_count')[:10]
        
        top_products_data = [{
            'name': p.name,
            'orders': p.order_count,
            'price': str(p.price),
            'stock': p.stock
        } for p in top_products]
        
        # Top products by revenue
        top_revenue = OrderItem.objects.values('product__name').annotate(
            total=Sum('subtotal'),
            count=Count('id')
        ).order_by('-total')[:10]
        
        # By category
        by_category = Category.objects.annotate(
            product_count=Count('products'),
            active_products=Count('products', filter=Q(products__is_active=True))
        ).values('name', 'product_count', 'active_products')
        
        return Response({
            'total': total,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'top_by_orders': top_products_data,
            'top_by_revenue': list(top_revenue),
            'by_category': list(by_category)
        }, status=status.HTTP_200_OK)


class CustomersAnalyticsView(views.APIView):
    """
    Customer analytics
    GET /api/analytics/customers/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get customer analytics"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from apps.users.models import CustomUser
        from apps.orders.models import Order
        from apps.payments.models import Payment
        
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)
        week_ago = today - timedelta(days=7)
        
        # Total customers
        total = CustomUser.objects.filter(is_verified=True).count()
        new_month = CustomUser.objects.filter(
            created_at__date__gte=month_ago,
            is_verified=True
        ).count()
        new_week = CustomUser.objects.filter(
            created_at__date__gte=week_ago,
            is_verified=True
        ).count()
        
        # Email verified
        email_verified = CustomUser.objects.filter(email_verified=True).count()
        phone_verified = CustomUser.objects.filter(phone_verified=True).count()
        
        # Top customers by spending
        top_customers = CustomUser.objects.annotate(
            total_spent=Sum('orders__total_amount', filter=Q(orders__is_paid=True)),
            order_count=Count('orders')
        ).filter(
            total_spent__isnull=False
        ).order_by('-total_spent')[:10]
        
        top_customers_data = [{
            'name': c.get_full_name(),
            'email': c.email,
            'spent': float(c.total_spent or 0),
            'orders': c.order_count
        } for c in top_customers]
        
        # Customer retention
        repeat_customers = CustomUser.objects.annotate(
            order_count=Count('orders')
        ).filter(
            order_count__gt=1
        ).count()
        
        return Response({
            'total': total,
            'new_month': new_month,
            'new_week': new_week,
            'email_verified': email_verified,
            'phone_verified': phone_verified,
            'repeat_customers': repeat_customers,
            'top_customers': top_customers_data
        }, status=status.HTTP_200_OK)


class SalesReportView(views.APIView):
    """
    Comprehensive sales report
    GET /api/analytics/sales-report/
    Query params:
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get sales report"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from apps.orders.models import Order
        from apps.payments.models import Payment
        
        # Get date range from query params
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date and end_date:
            from datetime import datetime
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            today = timezone.now().date()
            start = today - timedelta(days=30)
            end = today
        
        # Query data
        orders = Order.objects.filter(
            created_at__date__gte=start,
            created_at__date__lte=end
        )
        
        payments = Payment.objects.filter(
            status='completed',
            completed_at__date__gte=start,
            completed_at__date__lte=end
        )
        
        # Calculate metrics
        total_orders = orders.count()
        total_paid_orders = orders.filter(is_paid=True).count()
        total_revenue = payments.aggregate(Sum('amount'))['amount__sum'] or 0
        average_order = total_revenue / total_orders if total_orders > 0 else 0
        
        # By status
        by_status = orders.values('status').annotate(
            count=Count('id')
        )
        
        # By payment method
        by_method = orders.values('payment_method').annotate(
            count=Count('id'),
            revenue=Sum('total_amount', filter=Q(is_paid=True))
        )
        
        return Response({
            'period': {
                'start': str(start),
                'end': str(end)
            },
            'summary': {
                'total_orders': total_orders,
                'paid_orders': total_paid_orders,
                'total_revenue': float(total_revenue),
                'average_order_value': float(average_order)
            },
            'by_status': list(by_status),
            'by_payment_method': list(by_method)
        }, status=status.HTTP_200_OK)