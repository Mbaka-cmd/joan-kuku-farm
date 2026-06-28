from rest_framework import serializers
from .models import Payment, PaymentRefund, MpesaTransaction, PaymentLog


class PaymentSerializer(serializers.ModelSerializer):
    """Payment serializer"""
    order_id = serializers.CharField(source='order.order_id', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'order_id', 'amount', 'method', 'status',
            'transaction_id', 'payment_reference', 'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'order_id', 'transaction_id', 'created_at', 'completed_at'
        ]


class MpesaTransactionSerializer(serializers.ModelSerializer):
    """M-Pesa transaction serializer"""
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    
    class Meta:
        model = MpesaTransaction
        fields = [
            'id', 'checkout_request_id', 'merchant_request_id',
            'phone_number', 'amount', 'status', 'payment_status',
            'mpesa_receipt_number', 'response_description',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'checkout_request_id', 'merchant_request_id',
            'mpesa_receipt_number', 'response_description',
            'created_at', 'updated_at', 'payment_status'
        ]


class InitiateMpesaPaymentSerializer(serializers.Serializer):
    """Initiate M-Pesa payment"""
    order_id = serializers.IntegerField()
    phone_number = serializers.CharField(max_length=20)
    
    def validate_phone_number(self, value):
        """Validate Kenyan phone number"""
        # Accept formats: 254712345678, +254712345678, 0712345678, 712345678
        import re
        
        # Remove common formatting
        phone = value.replace(' ', '').replace('-', '').replace('+', '')
        
        # If starts with 0, convert to 254
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        
        # If doesn't start with 254, add it
        if not phone.startswith('254'):
            phone = '254' + phone
        
        # Validate length and format
        if not re.match(r'^254\d{9}$', phone):
            raise serializers.ValidationError(
                'Invalid phone number. Use format: 0712345678 or +254712345678'
            )
        
        return phone
    
    def validate_order_id(self, value):
        """Check order exists and is unpaid"""
        from apps.orders.models import Order
        
        try:
            order = Order.objects.get(id=value)
        except Order.DoesNotExist:
            raise serializers.ValidationError('Order not found')
        
        if order.is_paid:
            raise serializers.ValidationError('Order is already paid')
        
        return value


class MpesaCallbackSerializer(serializers.Serializer):
    """Handle M-Pesa STK callback"""
    Body = serializers.JSONField()
    
    def validate_Body(self, value):
        """Validate callback structure"""
        if 'stkCallback' not in value:
            raise serializers.ValidationError('Invalid callback structure')
        
        callback = value['stkCallback']
        required_fields = ['ResultCode', 'CheckoutRequestID']
        
        for field in required_fields:
            if field not in callback:
                raise serializers.ValidationError(f'Missing {field} in callback')
        
        return value


class PaymentRefundSerializer(serializers.ModelSerializer):
    """Payment refund serializer"""
    order_id = serializers.CharField(source='payment.order.order_id', read_only=True)
    
    class Meta:
        model = PaymentRefund
        fields = [
            'id', 'order_id', 'amount', 'reason', 'status',
            'refund_transaction_id', 'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'order_id', 'refund_transaction_id',
            'created_at', 'completed_at'
        ]


class InitiateRefundSerializer(serializers.Serializer):
    """Request refund"""
    payment_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField(max_length=200)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_payment_id(self, value):
        """Check payment exists"""
        try:
            payment = Payment.objects.get(id=value)
        except Payment.DoesNotExist:
            raise serializers.ValidationError('Payment not found')
        
        if payment.status != 'completed':
            raise serializers.ValidationError('Only completed payments can be refunded')
        
        return value
    
    def validate(self, data):
        """Validate refund amount"""
        payment = Payment.objects.get(id=data['payment_id'])
        
        # Get total refunded amount
        total_refunded = PaymentRefund.objects.filter(
            payment=payment,
            status__in=['processing', 'completed']
        ).aggregate(
            models.Sum('amount')
        )['amount__sum'] or 0
        
        if data['amount'] + total_refunded > payment.amount:
            raise serializers.ValidationError(
                f'Refund amount exceeds available {payment.amount}'
            )
        
        return data


class PaymentStatusSerializer(serializers.ModelSerializer):
    """Check payment status"""
    order_id = serializers.CharField(source='order.order_id', read_only=True)
    order_status = serializers.CharField(source='order.status', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'order_id', 'amount', 'method', 'status', 'order_status',
            'transaction_id', 'completed_at'
        ]
        read_only_fields = fields


class PaymentLogSerializer(serializers.ModelSerializer):
    """Payment log for debugging"""
    
    class Meta:
        model = PaymentLog
        fields = ['level', 'message', 'data', 'created_at']
        read_only_fields = fields


class PaymentHistorySerializer(serializers.ModelSerializer):
    """Payment history with logs"""
    logs = PaymentLogSerializer(many=True, read_only=True)
    refunds = PaymentRefundSerializer(many=True, read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'amount', 'method', 'status',
            'transaction_id', 'created_at', 'completed_at',
            'logs', 'refunds'
        ]
        read_only_fields = fields


# Import models for validation
from django.db import models
from .models import Payment