from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Analytics sections
    path('orders/', views.OrdersAnalyticsView.as_view(), name='orders_analytics'),
    path('revenue/', views.RevenueAnalyticsView.as_view(), name='revenue_analytics'),
    path('products/', views.ProductsAnalyticsView.as_view(), name='products_analytics'),
    path('customers/', views.CustomersAnalyticsView.as_view(), name='customers_analytics'),
    
    # Reports
    path('sales-report/', views.SalesReportView.as_view(), name='sales_report'),
]