<!-- Order Confirmation Email Template -->
<!-- Usage: render_to_string('emails/order_confirmation.html', context) -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #3b82f6; color: white; padding: 20px; text-align: center; }
        .content { background: #f9fafb; padding: 20px; margin: 10px 0; }
        .section { margin: 20px 0; }
        .order-items { width: 100%; border-collapse: collapse; }
        .order-items th { background: #e5e7eb; padding: 10px; text-align: left; }
        .order-items td { padding: 10px; border-bottom: 1px solid #e5e7eb; }
        .footer { text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }
        .button { 
            display: inline-block; 
            background: #3b82f6; 
            color: white; 
            padding: 10px 20px; 
            text-decoration: none; 
            border-radius: 5px; 
        }
        .status-badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 12px;
        }
        .status-pending { background: #fef3c7; color: #92400e; }
        .status-confirmed { background: #dbeafe; color: #1e40af; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>Joan Kuku Farm</h1>
            <p>Order Confirmation</p>
        </div>

        <!-- Welcome -->
        <div class="content">
            <h2>Hello {{ first_name }} {{ last_name }},</h2>
            <p>Thank you for your order! We're excited to serve you with fresh, quality poultry products.</p>
        </div>

        <!-- Order Details -->
        <div class="section">
            <h3>Order Details</h3>
            <div class="content">
                <p><strong>Order ID:</strong> {{ order_id }}</p>
                <p><strong>Order Date:</strong> {{ created_at|date:"F j, Y" }}</p>
                <p><strong>Status:</strong> <span class="status-badge status-confirmed">{{ status }}</span></p>
            </div>
        </div>

        <!-- Items -->
        <div class="section">
            <h3>Items Ordered</h3>
            <table class="order-items">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Quantity</th>
                        <th>Unit Price</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in items %}
                    <tr>
                        <td>{{ item.product_name }}</td>
                        <td>{{ item.quantity }}</td>
                        <td>KES {{ item.unit_price }}</td>
                        <td>KES {{ item.subtotal }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Totals -->
        <div class="section">
            <div class="content">
                <p><strong>Subtotal:</strong> KES {{ subtotal }}</p>
                <p><strong>Tax:</strong> KES {{ tax_amount }}</p>
                <p><strong>Discount:</strong> -KES {{ discount_amount }}</p>
                <h3>Total: KES {{ total_amount }}</h3>
            </div>
        </div>

        <!-- Delivery Info -->
        <div class="section">
            <h3>Delivery Information</h3>
            <div class="content">
                <p><strong>Recipient:</strong> {{ first_name }} {{ last_name }}</p>
                <p><strong>Phone:</strong> {{ delivery_phone }}</p>
                <p><strong>Address:</strong> {{ delivery_address }}</p>
                <p><strong>City:</strong> {{ delivery_city }}, {{ delivery_county }}</p>
            </div>
        </div>

        <!-- Payment Info -->
        <div class="section">
            <h3>Payment Method</h3>
            <div class="content">
                <p><strong>Method:</strong> {{ payment_method|upper }}</p>
                {% if payment_status == 'pending' %}
                <p><strong style="color: #ef4444;">Action Required:</strong> Your payment is pending. Please complete the payment to confirm your order.</p>
                {% else %}
                <p><strong style="color: #16a34a;">✓ Payment Received</strong></p>
                {% endif %}
            </div>
        </div>

        <!-- Next Steps -->
        <div class="section">
            <div class="content">
                <h3>What's Next?</h3>
                <ul>
                    <li>Order confirmation sent to your email</li>
                    <li>We'll prepare your items</li>
                    <li>You'll receive a tracking number via SMS/email</li>
                    <li>Delivery within 24-48 hours</li>
                </ul>
            </div>
        </div>

        <!-- Track Order -->
        <div class="section" style="text-align: center;">
            <a href="{{ track_url }}" class="button">Track Your Order</a>
        </div>

        <!-- Support -->
        <div class="content">
            <h3>Need Help?</h3>
            <p>Contact us at any time:</p>
            <p>
                <strong>Phone:</strong> 0726306005<br>
                <strong>Email:</strong> joanwapolly@gmail.com<br>
                <strong>Available:</strong> Mon-Fri 8am-5pm EAT
            </p>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>&copy; 2024 Joan Kuku Farm. All rights reserved.</p>
            <p>Nairobi, Kenya | Fresh Poultry Products</p>
        </div>
    </div>
</body>
</html>

---

<!-- Payment Confirmation Email Template -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .success { background: #d1fae5; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0; }
        .header { background: #10b981; color: white; padding: 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✓ Payment Confirmed</h1>
        </div>

        <div class="success">
            <h2>Your payment has been received successfully!</h2>
        </div>

        <div style="padding: 20px;">
            <h3>Payment Details</h3>
            <p><strong>Order ID:</strong> {{ order_id }}</p>
            <p><strong>Amount:</strong> KES {{ amount }}</p>
            <p><strong>Method:</strong> {{ payment_method|upper }}</p>
            <p><strong>Transaction ID:</strong> {{ transaction_id }}</p>
            <p><strong>Date:</strong> {{ payment_date|date:"F j, Y H:i" }}</p>

            <h3>Next Steps</h3>
            <ul>
                <li>Your order is now confirmed</li>
                <li>We're preparing your items</li>
                <li>You'll receive tracking information soon</li>
            </ul>

            <p>Thank you for your business!</p>
        </div>
    </div>
</body>
</html>

---

<!-- Shipment Notification Email Template -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .tracking-box { background: #eff6ff; border: 2px dashed #3b82f6; padding: 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📦 Your Order is On The Way!</h1>

        <p>Hi {{ first_name }},</p>

        <p>Great news! Your order has been shipped and is on its way to you.</p>

        <div class="tracking-box">
            <h3>Tracking Number</h3>
            <p style="font-size: 24px; font-weight: bold;">{{ tracking_number }}</p>
            <p>Use this number to track your delivery status</p>
        </div>

        <h3>Delivery Details</h3>
        <p>
            <strong>Recipient:</strong> {{ first_name }} {{ last_name }}<br>
            <strong>Address:</strong> {{ delivery_address }}, {{ delivery_city }}<br>
            <strong>Expected Delivery:</strong> {{ expected_delivery_date|date:"F j, Y" }}<br>
            <strong>Contact:</strong> {{ delivery_phone }}
        </p>

        <h3>Order Summary</h3>
        <p>
            <strong>Order ID:</strong> {{ order_id }}<br>
            <strong>Total Amount:</strong> KES {{ total_amount }}<br>
            <strong>Items:</strong> {{ item_count }} item(s)
        </p>

        <p>Track your delivery in real-time or contact us for any questions!</p>
    </div>
</body>
</html>

---

<!-- Password Reset Email Template -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .warning { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; }
        .button { 
            display: inline-block; 
            background: #3b82f6; 
            color: white; 
            padding: 10px 20px; 
            text-decoration: none; 
            border-radius: 5px; 
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Reset Your Password</h1>

        <p>Hi {{ first_name }},</p>

        <p>We received a request to reset your password. Click the button below to proceed:</p>

        <p style="text-align: center; margin: 30px 0;">
            <a href="{{ reset_link }}" class="button">Reset Password</a>
        </p>

        <p>Or copy this link: {{ reset_link }}</p>

        <div class="warning">
            <p><strong>⚠️ Security Notice:</strong></p>
            <p>This link will expire in {{ expiration_hours }} hours. If you didn't request this, please ignore this email.</p>
        </div>

        <p>Questions? Contact us at joanwapolly@gmail.com</p>
    </div>
</body>
</html>

---

<!-- Email Verification Template -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .code-box { 
            background: #f3f4f6; 
            border: 2px dashed #d1d5db; 
            padding: 20px; 
            text-align: center; 
            font-size: 32px; 
            letter-spacing: 5px; 
            font-weight: bold;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Verify Your Email</h1>

        <p>Hi {{ first_name }},</p>

        <p>Welcome to Joan Kuku Farm! Please use the code below to verify your email address:</p>

        <div class="code-box">
            {{ verification_code }}
        </div>

        <p>This code expires in {{ expiration_minutes }} minutes.</p>

        <p>If you didn't create this account, please ignore this email.</p>
    </div>
</body>
</html>

---

<!-- Low Stock Alert (Admin) -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .alert { background: #fee2e2; border-left: 4px solid #ef4444; padding: 15px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th { background: #f3f4f6; padding: 10px; text-align: left; }
        td { padding: 10px; border-bottom: 1px solid #e5e7eb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠️ Low Stock Alert</h1>

        <div class="alert">
            <p>The following products are running low on stock:</p>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Product</th>
                    <th>Current Stock</th>
                    <th>Minimum Stock</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for product in low_stock_products %}
                <tr>
                    <td>{{ product.name }}</td>
                    <td>{{ product.stock }}</td>
                    <td>{{ product.min_stock }}</td>
                    <td>{% if product.stock == 0 %}🔴 OUT{% else %}🟡 LOW{% endif %}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <p>Please reorder these items as soon as possible.</p>

        <p>Go to admin panel: <a href="{{ admin_url }}">Manage Products</a></p>
    </div>
</body>
</html>

---

<!-- Daily Sales Summary (Admin) -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .card { background: #f9fafb; border: 1px solid #e5e7eb; padding: 15px; margin: 10px 0; }
        .number { font-size: 24px; font-weight: bold; color: #3b82f6; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Daily Sales Summary</h1>
        <p>{{ summary_date|date:"F j, Y" }}</p>

        <div class="card">
            <p>Total Orders</p>
            <p class="number">{{ total_orders }}</p>
        </div>

        <div class="card">
            <p>Total Revenue</p>
            <p class="number">KES {{ total_revenue }}</p>
        </div>

        <div class="card">
            <p>Top Selling Product</p>
            <p class="number">{{ top_product.name }}</p>
            <p>{{ top_product.order_count }} orders</p>
        </div>

        <div class="card">
            <p>Order Status Breakdown</p>
            <ul>
                <li>✓ Delivered: {{ delivered_count }}</li>
                <li>📦 In Transit: {{ in_transit_count }}</li>
                <li>🔄 Processing: {{ processing_count }}</li>
                <li>⏳ Pending: {{ pending_count }}</li>
            </ul>
        </div>

        <p>View full dashboard: <a href="{{ dashboard_url }}">Analytics Dashboard</a></p>
    </div>
</body>
</html>

---

<!-- Python Helper to Send Emails -->

"""
# apps/notifications/email.py

from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

def send_order_confirmation(order):
    '''Send order confirmation email'''
    context = {
        'order_id': order.order_id,
        'first_name': order.customer.first_name,
        'last_name': order.customer.last_name,
        'items': order.orderitem_set.all(),
        'subtotal': order.subtotal,
        'tax_amount': order.tax_amount,
        'discount_amount': order.discount_amount,
        'total_amount': order.total_amount,
        'created_at': order.created_at,
        'status': order.status,
        'delivery_phone': order.delivery_phone,
        'delivery_address': order.delivery_address,
        'delivery_city': order.delivery_city,
        'delivery_county': order.delivery_county,
        'payment_method': order.payment_method,
        'payment_status': order.payment.status if hasattr(order, 'payment') else 'pending',
        'track_url': f'{settings.FRONTEND_URL}/orders/{order.id}',
    }
    
    subject = f'Order Confirmation - {order.order_id}'
    html = render_to_string('emails/order_confirmation.html', context)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.customer.email],
    )
    email.attach_alternative(html, 'text/html')
    email.send()

def send_payment_confirmation(payment):
    '''Send payment confirmation email'''
    context = {
        'order_id': payment.order.order_id,
        'first_name': payment.order.customer.first_name,
        'amount': payment.amount,
        'payment_method': payment.method,
        'transaction_id': payment.transaction_id,
        'payment_date': payment.created_at,
    }
    
    subject = f'Payment Received - {payment.order.order_id}'
    html = render_to_string('emails/payment_confirmation.html', context)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[payment.order.customer.email],
    )
    email.attach_alternative(html, 'text/html')
    email.send()
"""