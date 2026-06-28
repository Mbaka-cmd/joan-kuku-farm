# Advanced Analytics & Business Intelligence

from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value, DecimalField
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from datetime import datetime, timedelta
from decimal import Decimal
import json

# ============================================================
# ANALYTICS QUERIES
# ============================================================

class BusinessAnalytics:
    """Advanced business analytics"""
    
    @staticmethod
    def get_sales_metrics(start_date=None, end_date=None):
        """Get comprehensive sales metrics"""
        from apps.orders.models import Order
        
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        orders = Order.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        metrics = orders.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            avg_order_value=Avg('total_amount'),
            total_items=Sum('orderitem__quantity'),
        )
        
        # Status breakdown
        status_breakdown = orders.values('status').annotate(
            count=Count('id'),
            revenue=Sum('total_amount')
        ).order_by('status')
        
        # Payment method breakdown
        payment_breakdown = orders.values('payment_method').annotate(
            count=Count('id'),
            revenue=Sum('total_amount')
        ).order_by('payment_method')
        
        return {
            **metrics,
            'status_breakdown': list(status_breakdown),
            'payment_breakdown': list(payment_breakdown),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            }
        }
    
    @staticmethod
    def get_product_analytics():
        """Get product performance metrics"""
        from apps.products.models import Product
        from apps.orders.models import OrderItem
        
        products = Product.objects.annotate(
            total_orders=Count('orderitem'),
            total_quantity_sold=Sum('orderitem__quantity'),
            total_revenue=Sum(
                F('orderitem__quantity') * F('orderitem__unit_price'),
                output_field=DecimalField()
            ),
            avg_rating=Avg('productreview__rating'),
        ).filter(
            total_orders__gt=0
        ).order_by('-total_revenue')[:20]
        
        return [{
            'id': p.id,
            'name': p.name,
            'total_orders': p.total_orders,
            'total_quantity': p.total_quantity_sold,
            'total_revenue': str(p.total_revenue),
            'avg_rating': float(p.avg_rating) if p.avg_rating else 0,
            'current_stock': p.stock,
        } for p in products]
    
    @staticmethod
    def get_customer_analytics():
        """Get customer behavior metrics"""
        from apps.users.models import CustomUser
        from apps.orders.models import Order
        
        # Total customers
        total_customers = CustomUser.objects.filter(is_verified=True).count()
        
        # New customers this month
        month_ago = datetime.now() - timedelta(days=30)
        new_customers = CustomUser.objects.filter(
            date_joined__gte=month_ago
        ).count()
        
        # Customer segments
        customer_segments = Order.objects.values('customer').annotate(
            order_count=Count('id'),
            total_spend=Sum('total_amount'),
        ).order_by('-total_spend')
        
        # Segment classification
        high_value = 0
        regular = 0
        at_risk = 0
        
        today = datetime.now().date()
        
        for segment in customer_segments:
            spend = float(segment['total_spend'])
            orders = segment['order_count']
            
            if spend > 10000 and orders >= 5:
                high_value += 1
            elif orders >= 2:
                regular += 1
            elif (today - Order.objects.filter(
                customer_id=segment['customer']
            ).last().created_at.date()).days > 90:
                at_risk += 1
        
        return {
            'total_customers': total_customers,
            'new_customers_month': new_customers,
            'segments': {
                'high_value': high_value,
                'regular': regular,
                'at_risk': at_risk,
                'inactive': total_customers - high_value - regular - at_risk,
            }
        }
    
    @staticmethod
    def get_cohort_analysis(cohort_month):
        """Analyze customer cohorts"""
        from apps.users.models import CustomUser
        from apps.orders.models import Order
        
        # Get customers who joined in cohort month
        cohort_start = datetime(cohort_month.year, cohort_month.month, 1)
        if cohort_month.month == 12:
            cohort_end = datetime(cohort_month.year + 1, 1, 1)
        else:
            cohort_end = datetime(cohort_month.year, cohort_month.month + 1, 1)
        
        cohort_users = CustomUser.objects.filter(
            date_joined__range=[cohort_start, cohort_end]
        )
        
        # Track retention over months
        retention = []
        for months_ago in range(12):
            check_date = datetime.now() - timedelta(days=30*months_ago)
            retained = Order.objects.filter(
                customer__in=cohort_users,
                created_at__month=check_date.month,
                created_at__year=check_date.year,
            ).distinct('customer').count()
            
            retention.append({
                'month': months_ago,
                'retained': retained,
                'retention_rate': (retained / cohort_users.count() * 100) if cohort_users.count() > 0 else 0,
            })
        
        return {
            'cohort_month': cohort_month.isoformat(),
            'cohort_size': cohort_users.count(),
            'retention_data': retention,
        }
    
    @staticmethod
    def get_daily_trend(metric='revenue', days=30):
        """Get daily trend data"""
        from apps.orders.models import Order
        
        start_date = datetime.now() - timedelta(days=days)
        
        if metric == 'revenue':
            trend = Order.objects.filter(
                created_at__gte=start_date
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                revenue=Sum('total_amount')
            ).order_by('date')
        
        elif metric == 'orders':
            trend = Order.objects.filter(
                created_at__gte=start_date
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                orders=Count('id')
            ).order_by('date')
        
        else:
            trend = []
        
        return list(trend)
    
    @staticmethod
    def get_monthly_comparison(months=12):
        """Compare metrics across months"""
        from apps.orders.models import Order
        
        comparison = Order.objects.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            revenue=Sum('total_amount'),
            orders=Count('id'),
            avg_order_value=Avg('total_amount'),
        ).order_by('-month')[:months]
        
        return list(comparison)
    
    @staticmethod
    def get_geographic_distribution():
        """Analyze sales by location"""
        from apps.orders.models import Order
        
        distribution = Order.objects.values(
            'delivery_city',
            'delivery_county'
        ).annotate(
            orders=Count('id'),
            revenue=Sum('total_amount'),
            avg_order_value=Avg('total_amount'),
        ).order_by('-revenue')
        
        return list(distribution)
    
    @staticmethod
    def get_forecast_vs_actual(month):
        """Compare forecast vs actual sales"""
        from apps.inventory.models import InventoryForecast
        from apps.orders.models import Order
        
        start_date = datetime(month.year, month.month, 1)
        if month.month == 12:
            end_date = datetime(month.year + 1, 1, 1)
        else:
            end_date = datetime(month.year, month.month + 1, 1)
        
        actual_orders = Order.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        comparison_data = []
        for forecast in InventoryForecast.objects.all():
            actual = actual_orders.filter(
                orderitem__product=forecast.product
            ).aggregate(
                quantity=Sum('orderitem__quantity')
            )['quantity'] or 0
            
            forecasted = int(float(forecast.monthly_average_sales))
            variance = actual - forecasted
            variance_pct = (variance / forecasted * 100) if forecasted > 0 else 0
            
            comparison_data.append({
                'product': forecast.product.name,
                'forecasted': forecasted,
                'actual': actual,
                'variance': variance,
                'variance_pct': variance_pct,
                'accuracy': 100 - abs(variance_pct),
            })
        
        return comparison_data


# ============================================================
# CUSTOM REPORTS
# ============================================================

class CustomReportGenerator:
    """Generate custom business reports"""
    
    @staticmethod
    def generate_executive_summary(start_date, end_date):
        """Generate executive summary report"""
        from apps.orders.models import Order
        
        orders = Order.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        report = {
            'report_title': 'Executive Summary',
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'kpis': {
                'total_revenue': float(orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
                'total_orders': orders.count(),
                'avg_order_value': float(orders.aggregate(Avg('total_amount'))['total_amount__avg'] or 0),
                'total_items_sold': orders.aggregate(Sum('orderitem__quantity'))['orderitem__quantity__sum'] or 0,
            },
            'highlights': [],
            'recommendations': [],
        }
        
        return report
    
    @staticmethod
    def generate_performance_report(product_id, start_date, end_date):
        """Generate detailed product performance report"""
        from apps.products.models import Product
        from apps.orders.models import OrderItem
        
        product = Product.objects.get(id=product_id)
        
        sales = OrderItem.objects.filter(
            product=product,
            order__created_at__range=[start_date, end_date]
        )
        
        metrics = sales.aggregate(
            total_sold=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('unit_price'), output_field=DecimalField()),
            avg_price=Avg('unit_price'),
            order_count=Count('order', distinct=True),
        )
        
        return {
            'product_name': product.name,
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'metrics': metrics,
            'inventory_status': {
                'current_stock': product.stock,
                'min_stock': product.min_stock,
                'status': 'in_stock' if product.stock > 0 else 'out_of_stock',
            }
        }
    
    @staticmethod
    def export_to_csv(data, filename):
        """Export data to CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    @staticmethod
    def export_to_json(data, filename):
        """Export data to JSON"""
        return json.dumps(data, indent=2, default=str)


# ============================================================
# DASHBOARD SERIALIZERS
# ============================================================

"""
from rest_framework import serializers

class SalesMetricsSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    avg_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)

class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]
    
    @action(detail=False)
    def sales_metrics(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        metrics = BusinessAnalytics.get_sales_metrics(
            start_date=datetime.fromisoformat(start_date) if start_date else None,
            end_date=datetime.fromisoformat(end_date) if end_date else None,
        )
        
        return Response(metrics)
    
    @action(detail=False)
    def product_analytics(self, request):
        data = BusinessAnalytics.get_product_analytics()
        return Response(data)
    
    @action(detail=False)
    def customer_analytics(self, request):
        data = BusinessAnalytics.get_customer_analytics()
        return Response(data)
    
    @action(detail=False)
    def custom_report(self, request):
        start_date = datetime.fromisoformat(request.query_params.get('start_date'))
        end_date = datetime.fromisoformat(request.query_params.get('end_date'))
        
        report = CustomReportGenerator.generate_executive_summary(start_date, end_date)
        return Response(report)
"""