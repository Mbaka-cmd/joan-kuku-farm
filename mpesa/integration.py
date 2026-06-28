import base64
import requests
import logging
from datetime import datetime
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class MPesaIntegration:
    """Handle M-Pesa API interactions"""
    
    @staticmethod
    def get_access_token():
        """Get M-Pesa OAuth access token"""
        try:
            url = settings.MPESA_ACCESS_TOKEN_URL
            
            response = requests.get(
                url,
                auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data.get('access_token')
        
        except requests.RequestException as exc:
            logger.error(f"Failed to get M-Pesa access token: {str(exc)}")
            raise
    
    @staticmethod
    def initiate_payment(phone_number, amount, order_id):
        """Initiate M-Pesa STK Push"""
        try:
            access_token = MPesaIntegration.get_access_token()
            
            # Generate timestamp and password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = base64.b64encode(
                f"{settings.MPESA_BUSINESS_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
            ).decode()
            
            # Prepare payload
            payload = {
                "BusinessShortCode": settings.MPESA_BUSINESS_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": int(phone_number),
                "PartyB": settings.MPESA_BUSINESS_SHORTCODE,
                "PhoneNumber": int(phone_number),
                "CallBackURL": "https://yourdomain.com/api/payments/mpesa/callback/",
                "AccountReference": order_id,
                "TransactionDesc": f"JKF Order {order_id}",
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                settings.MPESA_STK_PUSH_URL,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"M-Pesa STK Push initiated for order {order_id}: {data}")
            
            return {
                'success': data.get('ResponseCode') == '0',
                'checkout_request_id': data.get('CheckoutRequestID'),
                'merchant_request_id': data.get('MerchantRequestID'),
                'response_code': data.get('ResponseCode'),
                'response_description': data.get('ResponseDescription'),
                'raw_response': data
            }
        
        except requests.RequestException as exc:
            logger.error(f"M-Pesa STK Push failed: {str(exc)}")
            return {
                'success': False,
                'error': str(exc)
            }
    
    @staticmethod
    def query_transaction_status(transaction_id):
        """Query the status of a transaction"""
        try:
            access_token = MPesaIntegration.get_access_token()
            
            payload = {
                "Initiator": "testapi",
                "SecurityCredential": settings.MPESA_SECURITY_CREDENTIAL,
                "CommandID": "TransactionStatusQuery",
                "TransactionID": transaction_id,
                "PartyA": settings.MPESA_BUSINESS_SHORTCODE,
                "IdentifierType": "4",
                "ResultURL": "https://yourdomain.com/api/payments/result/",
                "QueueTimeOutURL": "https://yourdomain.com/api/payments/timeout/",
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                settings.MPESA_QUERY_URL,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data
        
        except requests.RequestException as exc:
            logger.error(f"M-Pesa transaction query failed: {str(exc)}")
            return None
    
    @staticmethod
    def initiate_refund(transaction_id, amount, order_id):
        """Refund a transaction"""
        try:
            access_token = MPesaIntegration.get_access_token()
            
            # Generate timestamp and password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            payload = {
                "Initiator": "testapi",
                "SecurityCredential": settings.MPESA_SECURITY_CREDENTIAL,
                "CommandID": "Refund",
                "TransactionID": transaction_id,
                "Amount": int(amount),
                "ReceiverParty": settings.MPESA_BUSINESS_SHORTCODE,
                "RecieverIdentifierType": "4",
                "Remarks": f"Refund for order {order_id}",
                "QueueTimeOutURL": "https://yourdomain.com/api/payments/refund-timeout/",
                "ResultURL": "https://yourdomain.com/api/payments/refund-result/",
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                "https://api.safaricom.co.ke/mpesa/refund/v1/request",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"M-Pesa refund initiated: {data}")
            
            return {
                'success': data.get('ResponseCode') == '0',
                'response': data
            }
        
        except requests.RequestException as exc:
            logger.error(f"M-Pesa refund failed: {str(exc)}")
            return {
                'success': False,
                'error': str(exc)
            }


class MPesaCallbackHandler:
    """Handle M-Pesa callbacks"""
    
    @staticmethod
    def handle_stk_callback(body):
        """Handle STK Push callback"""
        try:
            from apps.payments.models import Payment, MpesaTransaction
            from apps.orders.models import Order
            
            callback_data = body.get('Body', {}).get('stkCallback', {})
            
            result_code = callback_data.get('ResultCode')
            checkout_request_id = callback_data.get('CheckoutRequestID')
            merchant_request_id = callback_data.get('MerchantRequestID')
            
            # Find payment by checkout request ID
            try:
                mpesa_tx = MpesaTransaction.objects.get(
                    checkout_request_id=checkout_request_id
                )
                payment = mpesa_tx.payment
                order = payment.order
            except MpesaTransaction.DoesNotExist:
                logger.error(f"M-Pesa transaction not found: {checkout_request_id}")
                return False
            
            # Process callback
            if result_code == 0:  # Success
                callback_metadata = callback_data.get('CallbackMetadata', {})
                item_list = callback_metadata.get('Item', [])
                
                # Extract details
                mpesa_receipt = None
                transaction_date = None
                phone_number = None
                
                for item in item_list:
                    item_name = item.get('Name')
                    item_value = item.get('Value')
                    
                    if item_name == 'MpesaReceiptNumber':
                        mpesa_receipt = item_value
                    elif item_name == 'TransactionDate':
                        transaction_date = datetime.strptime(
                            str(item_value), '%Y%m%d%H%M%S'
                        )
                    elif item_name == 'PhoneNumber':
                        phone_number = item_value
                
                # Update payment
                payment.status = 'completed'
                payment.mark_as_completed()
                
                # Update M-Pesa transaction
                mpesa_tx.status = 'success'
                mpesa_tx.mpesa_receipt_number = mpesa_receipt
                mpesa_tx.transaction_date = transaction_date
                mpesa_tx.response_code = '0'
                mpesa_tx.response_description = 'Transaction successful'
                mpesa_tx.save()
                
                # Update order
                order.is_paid = True
                order.status = 'confirmed'
                order.save()
                
                logger.info(f"Payment successful for order {order.order_id}")
                
                # Trigger confirmation
                from apps.orders.tasks import send_order_confirmation
                send_order_confirmation.delay(order.id)
                
                return True
            
            else:  # Failed
                payment.status = 'failed'
                payment.save()
                
                mpesa_tx.status = 'failed'
                mpesa_tx.response_code = str(result_code)
                mpesa_tx.response_description = callback_data.get(
                    'ResultDesc',
                    'Transaction failed'
                )
                mpesa_tx.save()
                
                logger.warning(
                    f"Payment failed for order {order.order_id}: {mpesa_tx.response_description}"
                )
                
                return False
        
        except Exception as exc:
            logger.error(f"Error handling M-Pesa callback: {str(exc)}")
            return False