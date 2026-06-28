from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_order_confirmation(self, order_id):
    """Send order confirmation via email and WhatsApp"""
    try:
        from apps.orders.models import Order
        
        order = Order.objects.get(id=order_id)
        
        # Prepare email content
        items_list = '\n'.join([
            f"• {item.product.name} x {item.quantity} = KES {item.subtotal}"
            for item in order.items.all()
        ])
        
        email_message = f"""
Dear {order.customer.first_name},

Thank you for your order with Joan Kuku Farm!

ORDER DETAILS
Order ID: {order.order_id}
Date: {order.created_at.strftime('%d %B %Y')}

ITEMS:
{items_list}

Total Amount: KES {order.total_amount}
Payment Status: {'Paid' if order.is_paid else 'Pending'}

DELIVERY TO:
{order.delivery_address}
{order.delivery_city}, {order.delivery_county}
Phone: {order.delivery_phone}

You will receive a WhatsApp update within 2 hours.

Track your order at: https://joankkufarm.co.ke/orders/{order.order_id}

Thank you for choosing Joan Kuku Farm!

Best regards,
Joan Kuku Farm Team
0726306005
        """
        
        # Send email
        send_mail(
            subject=f'Order Confirmation - {order.order_id}',
            message=email_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer.email],
            fail_silently=False,
        )
        
        logger.info(f"Order confirmation email sent for {order.order_id}")
        
        # Send WhatsApp
        send_whatsapp_notification.delay(
            order_id=order_id,
            message_type='order_confirmation'
        )
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as exc:
        logger.error(f"Error sending order confirmation: {str(exc)}")
        # Retry after 60 seconds
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def update_order_status(self, order_id, new_status, notes=''):
    """Update order status and notify customer"""
    try:
        from apps.orders.models import Order, OrderStatusHistory
        
        order = Order.objects.get(id=order_id)
        old_status = order.status
        
        # Update status
        order.status = new_status
        order.save()
        
        # Log status change
        OrderStatusHistory.objects.create(
            order=order,
            from_status=old_status,
            to_status=new_status,
            reason=notes
        )
        
        logger.info(f"Order {order.order_id} status updated: {old_status} → {new_status}")
        
        # Send notification
        send_status_update.delay(order_id, new_status)
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as exc:
        logger.error(f"Error updating order status: {str(exc)}")
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_status_update(self, order_id, status):
    """Notify customer of status change"""
    try:
        from apps.orders.models import Order
        
        order = Order.objects.get(id=order_id)
        
        status_messages = {
            'pending': '⏳ Your order is awaiting payment. Please complete payment to proceed.',
            'confirmed': '✅ Your order has been confirmed! We are preparing your items.',
            'processing': '📦 We are packing your order. It will ship soon.',
            'in_transit': '🚚 Your order is on the way! Track your delivery.',
            'delivered': '📍 Your order has been delivered. Thank you for choosing Joan Kuku Farm!',
            'cancelled': '❌ Your order has been cancelled. Refund will be processed shortly.',
        }
        
        message_text = status_messages.get(status, f'Order status: {order.get_status_display()}')
        
        # Send WhatsApp
        send_whatsapp_notification.delay(
            order_id=order_id,
            message_type='status_update',
            message=message_text
        )
        
        logger.info(f"Status update sent for {order.order_id}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as exc:
        logger.error(f"Error sending status update: {str(exc)}")
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_whatsapp_notification(self, order_id, message_type='order_confirmation', message=''):
    """Send WhatsApp notification"""
    try:
        from apps.orders.models import Order
        
        if not all([
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_PHONE_NUMBER
        ]):
            logger.warning("Twilio credentials not configured")
            return
        
        order = Order.objects.get(id=order_id)
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Format phone number
        phone = order.delivery_phone
        if not phone.startswith('+'):
            if phone.startswith('0'):
                phone = '+254' + phone[1:]
            else:
                phone = '+254' + phone
        
        # Send WhatsApp message
        client.messages.create(
            body=message or f"Order {order.order_id} confirmed! Total: KES {order.total_amount}",
            from_=f'whatsapp:{settings.TWILIO_PHONE_NUMBER}',
            to=f'whatsapp:{phone}'
        )
        
        logger.info(f"WhatsApp notification sent to {phone}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as exc:
        logger.error(f"Error sending WhatsApp: {str(exc)}")
        self.retry(exc=exc, countdown=120)


@shared_task
def send_low_stock_alert():
    """Check inventory and alert admin"""
    try:
        from apps.products.models import Product
        
        low_stock_products = Product.objects.filter(
            is_active=True,
            stock__lte=10
        )
        
        if low_stock_products.exists():
            message = "🔔 LOW STOCK ALERT\n\n"
            message += "The following products have low inventory:\n\n"
            
            for product in low_stock_products:
                message += f"• {product.name}: {product.get_available_stock()} units\n"
            
            message += "\nPlease restock these items soon."
            
            send_mail(
                subject='JKF - Low Stock Alert',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['joanwapolly@gmail.com'],
            )
            
            logger.info(f"Low stock alert sent for {low_stock_products.count()} products")
        
    except Exception as exc:
        logger.error(f"Error in low stock alert: {str(exc)}")


@shared_task
def send_unpaid_order_reminder():
    """Remind customers about unpaid orders"""
    try:
        from apps.orders.models import Order
        from django.utils import timezone
        from datetime import timedelta
        
        # Get orders pending payment for more than 2 hours
        two_hours_ago = timezone.now() - timedelta(hours=2)
        pending_orders = Order.objects.filter(
            is_paid=False,
            status='pending',
            created_at__lte=two_hours_ago
        )
        
        for order in pending_orders:
            send_mail(
                subject=f'Complete Payment for Order {order.order_id}',
                message=f"""Dear {order.customer.first_name},

Your order {order.order_id} is still pending payment.

Amount Due: KES {order.total_amount}

Please complete the payment to proceed with your order.

Pay here: https://joankkufarm.co.ke/orders/{order.order_id}/pay/

Best regards,
Joan Kuku Farm Team
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.customer.email],
            )
            
            logger.info(f"Payment reminder sent for {order.order_id}")
        
    except Exception as exc:
        logger.error(f"Error in payment reminder: {str(exc)}")


@shared_task
def send_delivery_confirmation(order_id):
    """Send delivery confirmation"""
    try:
        from apps.orders.models import Order
        
        order = Order.objects.get(id=order_id)
        
        message = f"""Dear {order.customer.first_name},

Your order {order.order_id} has been delivered!

Thank you for ordering from Joan Kuku Farm.

Would you like to leave a review?
https://joankkufarm.co.ke/orders/{order.order_id}/review/

Best regards,
Joan Kuku Farm Team
        """
        
        send_mail(
            subject=f'Order Delivered - {order.order_id}',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer.email],
        )
        
        logger.info(f"Delivery confirmation sent for {order.order_id}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as exc:
        logger.error(f"Error in delivery confirmation: {str(exc)}")