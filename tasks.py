from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)


# ============================================================
# TWILIO SETUP (WhatsApp & SMS)
# ============================================================
def get_twilio_client():
    """Get Twilio client instance"""
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def format_phone_number(phone):
    """Format phone number to Twilio format"""
    phone = phone.replace(' ', '').replace('-', '').replace('+', '')
    
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif not phone.startswith('254'):
        phone = '254' + phone
    
    return '+' + phone


# ============================================================
# EMAIL NOTIFICATIONS
# ============================================================
@shared_task(bind=True, max_retries=3)
def send_html_email(self, subject, template_name, context, recipient_email):
    """Send HTML email with template"""
    try:
        # Render template
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email]
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
        
        logger.info(f"HTML email sent to {recipient_email}")
        
    except Exception as exc:
        logger.error(f"Failed to send HTML email: {str(exc)}")
        self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_plain_email(self, subject, message, recipient_email):
    """Send plain text email"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        logger.info(f"Plain email sent to {recipient_email}")
        
    except Exception as exc:
        logger.error(f"Failed to send email: {str(exc)}")
        self.retry(exc=exc, countdown=60)


# ============================================================
# WHATSAPP NOTIFICATIONS
# ============================================================
@shared_task(bind=True, max_retries=3)
def send_whatsapp_message(self, phone_number, message_text):
    """Send WhatsApp message via Twilio"""
    try:
        if not all([
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_PHONE_NUMBER
        ]):
            logger.warning("Twilio credentials not configured")
            return
        
        client = get_twilio_client()
        phone = format_phone_number(phone_number)
        
        message = client.messages.create(
            body=message_text,
            from_=f'whatsapp:{settings.TWILIO_PHONE_NUMBER}',
            to=f'whatsapp:{phone}'
        )
        
        logger.info(f"WhatsApp message sent to {phone}: {message.sid}")
        return message.sid
        
    except Exception as exc:
        logger.error(f"Failed to send WhatsApp: {str(exc)}")
        self.retry(exc=exc, countdown=120)


# ============================================================
# SMS NOTIFICATIONS
# ============================================================
@shared_task(bind=True, max_retries=3)
def send_sms_message(self, phone_number, message_text):
    """Send SMS via Twilio"""
    try:
        if not all([
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_PHONE_NUMBER
        ]):
            logger.warning("Twilio credentials not configured")
            return
        
        client = get_twilio_client()
        phone = format_phone_number(phone_number)
        
        message = client.messages.create(
            body=message_text,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone
        )
        
        logger.info(f"SMS sent to {phone}: {message.sid}")
        return message.sid
        
    except Exception as exc:
        logger.error(f"Failed to send SMS: {str(exc)}")
        self.retry(exc=exc, countdown=120)


# ============================================================
# ORDER NOTIFICATIONS
# ============================================================
@shared_task
def notify_order_placed(order_id):
    """Notify customer order was placed"""
    try:
        from apps.orders.models import Order
        order = Order.objects.get(id=order_id)
        
        subject = f"Order Placed - {order.order_id}"
        message = f"""
Hello {order.customer.first_name},

Thank you for placing your order!

Order ID: {order.order_id}
Total: KES {order.total_amount}
Items: {order.get_item_count()}

Delivery to: {order.delivery_address}, {order.delivery_city}

You can track your order here:
https://joankkufarm.co.ke/orders/{order.order_id}

We'll notify you once your order is ready for dispatch.

Best regards,
Joan Kuku Farm Team
        """
        
        # Send via email
        send_plain_email.delay(
            subject=subject,
            message=message,
            recipient_email=order.customer.email
        )
        
        # Send via WhatsApp
        whatsapp_msg = f"""✅ Order Confirmed!

Order: {order.order_id}
Total: KES {order.total_amount}
Items: {order.get_item_count()}

Track here: https://joankkufarm.co.ke/orders/{order.order_id}

Thank you for choosing Joan Kuku Farm!"""
        
        send_whatsapp_message.delay(
            phone_number=order.delivery_phone,
            message_text=whatsapp_msg
        )
        
        logger.info(f"Order placed notification sent for {order.order_id}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as e:
        logger.error(f"Error sending order placed notification: {str(e)}")


@shared_task
def notify_order_shipped(order_id):
    """Notify customer order shipped"""
    try:
        from apps.orders.models import Order
        order = Order.objects.get(id=order_id)
        
        subject = f"Order Shipped - {order.order_id}"
        message = f"""
Hello {order.customer.first_name},

Your order is on the way!

Order ID: {order.order_id}
Tracking Number: {order.tracking_number or 'Coming soon'}

Delivery to: {order.delivery_address}, {order.delivery_city}

Track your order: https://joankkufarm.co.ke/orders/{order.order_id}

Expected delivery in 1-3 business days.

Best regards,
Joan Kuku Farm Team
        """
        
        send_plain_email.delay(
            subject=subject,
            message=message,
            recipient_email=order.customer.email
        )
        
        whatsapp_msg = f"""🚚 Your Order is On the Way!

Order: {order.order_id}
Tracking: {order.tracking_number or 'TBA'}

Track here: https://joankkufarm.co.ke/orders/{order.order_id}

Expected in 1-3 days. Thank you!"""
        
        send_whatsapp_message.delay(
            phone_number=order.delivery_phone,
            message_text=whatsapp_msg
        )
        
        logger.info(f"Order shipped notification sent for {order.order_id}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as e:
        logger.error(f"Error sending order shipped notification: {str(e)}")


@shared_task
def notify_order_delivered(order_id):
    """Notify customer order delivered"""
    try:
        from apps.orders.models import Order
        order = Order.objects.get(id=order_id)
        
        subject = f"Order Delivered - {order.order_id}"
        message = f"""
Hello {order.customer.first_name},

Your order has been delivered!

Order ID: {order.order_id}
Items: {order.get_item_count()}
Total: KES {order.total_amount}

Please leave a review: https://joankkufarm.co.ke/orders/{order.order_id}/review/

Thank you for choosing Joan Kuku Farm. We look forward to serving you again!

Best regards,
Joan Kuku Farm Team
        """
        
        send_plain_email.delay(
            subject=subject,
            message=message,
            recipient_email=order.customer.email
        )
        
        whatsapp_msg = f"""📦 Your Order Delivered!

Order: {order.order_id}

Thank you for shopping with us!
Rate our service: https://joankkufarm.co.ke/orders/{order.order_id}/review/"""
        
        send_whatsapp_message.delay(
            phone_number=order.delivery_phone,
            message_text=whatsapp_msg
        )
        
        logger.info(f"Order delivered notification sent for {order.order_id}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as e:
        logger.error(f"Error sending order delivered notification: {str(e)}")


@shared_task
def notify_order_cancelled(order_id):
    """Notify customer order cancelled"""
    try:
        from apps.orders.models import Order
        order = Order.objects.get(id=order_id)
        
        subject = f"Order Cancelled - {order.order_id}"
        message = f"""
Hello {order.customer.first_name},

Your order has been cancelled.

Order ID: {order.order_id}
Refund Amount: KES {order.total_amount if order.is_paid else 0}

The refund will be processed within 3-5 business days.

If you have questions, contact us:
📞 0726306005
📧 joanwapolly@gmail.com

Best regards,
Joan Kuku Farm Team
        """
        
        send_plain_email.delay(
            subject=subject,
            message=message,
            recipient_email=order.customer.email
        )
        
        whatsapp_msg = f"""❌ Order Cancelled

Order: {order.order_id}
Refund: KES {order.total_amount if order.is_paid else 0}

Refund in 3-5 days.
Contact: 0726306005"""
        
        send_whatsapp_message.delay(
            phone_number=order.delivery_phone,
            message_text=whatsapp_msg
        )
        
        logger.info(f"Order cancelled notification sent for {order.order_id}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as e:
        logger.error(f"Error sending order cancelled notification: {str(e)}")


# ============================================================
# PAYMENT NOTIFICATIONS
# ============================================================
@shared_task
def notify_payment_received(payment_id):
    """Notify order payment received"""
    try:
        from apps.payments.models import Payment
        payment = Payment.objects.get(id=payment_id)
        order = payment.order
        
        subject = f"Payment Received - {order.order_id}"
        message = f"""
Hello {order.customer.first_name},

Thank you! We received your payment.

Order ID: {order.order_id}
Amount: KES {payment.amount}
Method: {payment.get_method_display()}
Reference: {payment.transaction_id}

Your order is being prepared for shipment.

Best regards,
Joan Kuku Farm Team
        """
        
        send_plain_email.delay(
            subject=subject,
            message=message,
            recipient_email=order.customer.email
        )
        
        whatsapp_msg = f"""✅ Payment Received!

Order: {order.order_id}
Amount: KES {payment.amount}
Ref: {payment.transaction_id}

Preparing for shipment. Thank you!"""
        
        send_whatsapp_message.delay(
            phone_number=order.delivery_phone,
            message_text=whatsapp_msg
        )
        
        logger.info(f"Payment received notification sent for {order.order_id}")
        
    except Exception as e:
        logger.error(f"Error sending payment notification: {str(e)}")


@shared_task
def notify_payment_failed(payment_id):
    """Notify payment failed"""
    try:
        from apps.payments.models import Payment
        payment = Payment.objects.get(id=payment_id)
        order = payment.order
        
        subject = f"Payment Failed - {order.order_id}"
        message = f"""
Hello {order.customer.first_name},

Your payment attempt failed.

Order ID: {order.order_id}
Amount: KES {payment.amount}

Please try again: https://joankkufarm.co.ke/orders/{order.order_id}/pay/

If you need help, call us:
📞 0726306005

Best regards,
Joan Kuku Farm Team
        """
        
        send_plain_email.delay(
            subject=subject,
            message=message,
            recipient_email=order.customer.email
        )
        
        whatsapp_msg = f"""⚠️ Payment Failed

Order: {order.order_id}
Amount: KES {payment.amount}

Try again: https://joankkufarm.co.ke/orders/{order.order_id}/pay/

Need help? Call 0726306005"""
        
        send_whatsapp_message.delay(
            phone_number=order.delivery_phone,
            message_text=whatsapp_msg
        )
        
        logger.info(f"Payment failed notification sent for {order.order_id}")
        
    except Exception as e:
        logger.error(f"Error sending payment failed notification: {str(e)}")


# ============================================================
# PROMOTIONAL NOTIFICATIONS
# ============================================================
@shared_task
def send_promotional_message(customer_id, title, message):
    """Send promotional message to customer"""
    try:
        from apps.users.models import CustomUser
        customer = CustomUser.objects.get(id=customer_id)
        
        # Check preferences
        if not customer.preferences.receive_promotions:
            logger.info(f"Customer {customer.email} has opted out of promotions")
            return
        
        send_plain_email.delay(
            subject=title,
            message=message,
            recipient_email=customer.email
        )
        
        logger.info(f"Promotional message sent to {customer.email}")
        
    except CustomUser.DoesNotExist:
        logger.error(f"Customer {customer_id} not found")
    except Exception as e:
        logger.error(f"Error sending promotional message: {str(e)}")


@shared_task
def send_bulk_promotional_message(title, message, customer_ids=None):
    """Send promotional message to multiple customers"""
    try:
        from apps.users.models import CustomUser
        
        if customer_ids:
            customers = CustomUser.objects.filter(
                id__in=customer_ids,
                preferences__receive_promotions=True
            )
        else:
            customers = CustomUser.objects.filter(
                preferences__receive_promotions=True
            )
        
        count = 0
        for customer in customers:
            send_promotional_message.delay(
                customer_id=customer.id,
                title=title,
                message=message
            )
            count += 1
        
        logger.info(f"Promotional message queued for {count} customers")
        
    except Exception as e:
        logger.error(f"Error sending bulk promotional message: {str(e)}")


# ============================================================
# SUPPORT NOTIFICATIONS
# ============================================================
@shared_task
def notify_customer_support(order_id, subject, message):
    """Send customer support message"""
    try:
        from apps.orders.models import Order
        order = Order.objects.get(id=order_id)
        
        send_plain_email.delay(
            subject=subject,
            message=message,
            recipient_email=order.customer.email
        )
        
        logger.info(f"Support message sent for order {order.order_id}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as e:
        logger.error(f"Error sending support message: {str(e)}")