from rest_framework import viewsets, status, generics, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
import logging

from .models import Payment, PaymentRefund, MpesaTransaction, PaymentLog
from .serializers import (
    PaymentSerializer,
    MpesaTransactionSerializer,
    InitiateMpesaPaymentSerializer,
    MpesaCallbackSerializer,
    PaymentStatusSerializer,
    PaymentRefundSerializer,
    InitiateRefundSerializer,
    PaymentHistorySerializer,
)
from .mpesa_integration import MPesaIntegration, MPesaCallbackHandler
from apps.orders.models import Order
from apps.orders.tasks import send_order_confirmation

logger = logging.getLogger(__name__)


class InitiateMpesaPaymentView(views.APIView):
    """
    Initiate M-Pesa STK Push payment
    POST /api/payments/mpesa/initiate/
    Body: {
        "order_id": 1,
        "phone_number": "0712345678"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Start M-Pesa payment"""
        serializer = InitiateMpesaPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order_id = serializer.validated_data['order_id']
        phone_number = serializer.validated_data['phone_number']
        
        try:
            order = Order.objects.get(id=order_id)
            
            # Check user permission
            if order.customer != request.user:
                return Response({
                    'error': 'You can only pay for your own orders'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Initiate M-Pesa payment
            mpesa_response = MPesaIntegration.initiate_payment(
                phone_number=phone_number,
                amount=order.total_amount,
                order_id=order.order_id
            )
            
            if not mpesa_response.get('success'):
                return Response({
                    'error': mpesa_response.get('error', 'Payment initiation failed'),
                    'details': mpesa_response
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create payment record
            payment = Payment.objects.create(
                order=order,
                amount=order.total_amount,
                method='mpesa',
                status='pending',
                transaction_id=mpesa_response.get('checkout_request_id', 'PENDING'),
                payment_data=mpesa_response
            )
            
            # Create M-Pesa transaction record
            MpesaTransaction.objects.create(
                payment=payment,
                checkout_request_id=mpesa_response.get('checkout_request_id'),
                merchant_request_id=mpesa_response.get('merchant_request_id'),
                phone_number=phone_number,
                amount=order.total_amount,
                status='pending',
                response_code=mpesa_response.get('response_code'),
                response_description=mpesa_response.get('response_description'),
                raw_response=mpesa_response
            )
            
            # Log payment attempt
            PaymentLog.objects.create(
                payment=payment,
                level='info',
                message='M-Pesa STK Push initiated',
                data={'phone': phone_number, 'amount': str(order.total_amount)}
            )
            
            logger.info(f"M-Pesa payment initiated for order {order.order_id}")
            
            return Response({
                'success': True,
                'message': 'Check your phone for M-Pesa prompt',
                'checkout_request_id': mpesa_response.get('checkout_request_id'),
                'payment_id': payment.id
            }, status=status.HTTP_200_OK)
        
        except Order.DoesNotExist:
            return Response({
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"M-Pesa initiation error: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(views.APIView):
    """
    M-Pesa STK Push callback endpoint
    This is called by M-Pesa after payment attempt
    POST /api/payments/mpesa/callback/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Handle M-Pesa callback"""
        try:
            body = request.data
            
            logger.info(f"M-Pesa callback received: {body}")
            
            # Validate callback format
            serializer = MpesaCallbackSerializer(data=body)
            serializer.is_valid(raise_exception=True)
            
            # Process callback
            success = MPesaCallbackHandler.handle_stk_callback(body)
            
            if success:
                logger.info("M-Pesa callback processed successfully")
                return Response({'status': 'success'}, status=status.HTTP_200_OK)
            else:
                logger.warning("M-Pesa callback processing failed")
                return Response({'status': 'error'}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"M-Pesa callback error: {str(e)}")
            # Always return 200 to M-Pesa to prevent retries
            return Response({'status': 'error'}, status=status.HTTP_200_OK)


class MpesaStatusView(views.APIView):
    """
    Check M-Pesa payment status
    GET /api/payments/mpesa/status/<checkout_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, checkout_id):
        """Get M-Pesa transaction status"""
        try:
            mpesa_tx = MpesaTransaction.objects.get(checkout_request_id=checkout_id)
            
            # Check permission
            if mpesa_tx.payment.order.customer != request.user:
                return Response({
                    'error': 'Unauthorized'
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = MpesaTransactionSerializer(mpesa_tx)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except MpesaTransaction.DoesNotExist:
            return Response({
                'error': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PaymentStatusView(views.APIView):
    """
    Check payment status
    GET /api/payments/status/<order_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, order_id):
        """Get payment status for order"""
        try:
            order = Order.objects.get(id=order_id)
            
            # Check permission
            if order.customer != request.user and not request.user.is_staff:
                return Response({
                    'error': 'Unauthorized'
                }, status=status.HTTP_403_FORBIDDEN)
            
            try:
                payment = order.payment
                serializer = PaymentStatusSerializer(payment)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Payment.DoesNotExist:
                return Response({
                    'error': 'No payment found for this order'
                }, status=status.HTTP_404_NOT_FOUND)
        
        except Order.DoesNotExist:
            return Response({
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PaymentHistoryView(generics.RetrieveAPIView):
    """
    Get payment history and logs for an order
    GET /api/payments/history/<order_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, order_id):
        """Get payment history"""
        try:
            order = Order.objects.get(id=order_id)
            
            # Check permission
            if order.customer != request.user and not request.user.is_staff:
                return Response({
                    'error': 'Unauthorized'
                }, status=status.HTTP_403_FORBIDDEN)
            
            try:
                payment = order.payment
                serializer = PaymentHistorySerializer(payment)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Payment.DoesNotExist:
                return Response({
                    'error': 'No payment found for this order'
                }, status=status.HTTP_404_NOT_FOUND)
        
        except Order.DoesNotExist:
            return Response({
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)


class InitiateRefundView(views.APIView):
    """
    Request refund for paid order
    POST /api/payments/refund/initiate/
    Body: {
        "payment_id": 1,
        "amount": 100.00,
        "reason": "Customer requested refund"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Initiate refund"""
        serializer = InitiateRefundSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        payment_id = serializer.validated_data['payment_id']
        amount = serializer.validated_data['amount']
        reason = serializer.validated_data['reason']
        notes = serializer.validated_data.get('notes', '')
        
        try:
            payment = Payment.objects.get(id=payment_id)
            
            # Check permission
            if payment.order.customer != request.user and not request.user.is_staff:
                return Response({
                    'error': 'Unauthorized'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Create refund record
            refund = PaymentRefund.objects.create(
                payment=payment,
                amount=amount,
                reason=reason,
                notes=notes,
                initiated_by=request.user,
                status='pending'
            )
            
            # Log refund
            PaymentLog.objects.create(
                payment=payment,
                level='info',
                message=f'Refund of KES {amount} initiated',
                data={'reason': reason, 'notes': notes}
            )
            
            logger.info(f"Refund initiated for payment {payment.id}: KES {amount}")
            
            return Response({
                'refund': PaymentRefundSerializer(refund).data,
                'message': 'Refund initiated. Admin will process it shortly.'
            }, status=status.HTTP_201_CREATED)
        
        except Payment.DoesNotExist:
            return Response({
                'error': 'Payment not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Refund initiation error: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RefundStatusView(views.APIView):
    """
    Check refund status
    GET /api/payments/refund/status/<refund_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, refund_id):
        """Get refund status"""
        try:
            refund = PaymentRefund.objects.get(id=refund_id)
            
            # Check permission
            if refund.payment.order.customer != request.user and not request.user.is_staff:
                return Response({
                    'error': 'Unauthorized'
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = PaymentRefundSerializer(refund)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except PaymentRefund.DoesNotExist:
            return Response({
                'error': 'Refund not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PaymentListView(generics.ListAPIView):
    """
    List all payments (admin only)
    GET /api/payments/
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only admins can list all payments"""
        if not self.request.user.is_staff:
            # Users can see their own payments
            return Payment.objects.filter(order__customer=self.request.user)
        return Payment.objects.all()


class PaymentStatisticsView(views.APIView):
    """
    Payment statistics (admin only)
    GET /api/payments/statistics/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get payment statistics"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from django.db.models import Count, Sum, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        # Status breakdown
        status_stats = Payment.objects.values('status').annotate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        # Method breakdown
        method_stats = Payment.objects.values('method').annotate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        # M-Pesa specific
        mpesa_transactions = MpesaTransaction.objects.all()
        mpesa_success = mpesa_transactions.filter(status='success').count()
        mpesa_failed = mpesa_transactions.filter(status='failed').count()
        
        # Today's revenue
        today = timezone.now().date()
        today_revenue = Payment.objects.filter(
            status='completed',
            completed_at__date=today
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Week's revenue
        week_ago = today - timedelta(days=7)
        week_revenue = Payment.objects.filter(
            status='completed',
            completed_at__date__gte=week_ago
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Month's revenue
        month_ago = today - timedelta(days=30)
        month_revenue = Payment.objects.filter(
            status='completed',
            completed_at__date__gte=month_ago
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Total revenue
        total_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return Response({
            'status_breakdown': list(status_stats),
            'method_breakdown': list(method_stats),
            'mpesa': {
                'total': mpesa_transactions.count(),
                'successful': mpesa_success,
                'failed': mpesa_failed
            },
            'revenue': {
                'today': float(today_revenue),
                'week': float(week_revenue),
                'month': float(month_revenue),
                'total': float(total_revenue)
            }
        }, status=status.HTTP_200_OK)