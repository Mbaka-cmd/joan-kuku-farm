from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusHistory, OrderCancellation
from apps.products.models import Product


class OrderItemSerializer(serializers.ModelSerializer):
    """Order item serializer"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_unit = serializers.CharField(source='product.unit', read_only=True)
    product_image = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_name', 'product_unit', 'product_image',
            'quantity', 'unit_price', 'subtotal', 'created_at'
        ]
        read_only_fields = ['id', 'subtotal', 'created_at', 'product_name', 'product_unit']
    
    def get_product_image(self, obj):
        if obj.product.image:
            return obj.product.image.url
        return None


class OrderItemCreateSerializer(serializers.Serializer):
    """Create order items"""
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    
    def validate_product_id(self, value):
        """Check product exists and is active"""
        try:
            product = Product.objects.get(id=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError('Product not found or inactive')
        return value
    
    def validate(self, data):
        """Validate product can fulfill order"""
        product = Product.objects.get(id=data['product_id'])
        
        if not product.can_fulfill_order(data['quantity']):
            raise serializers.ValidationError(
                f'Only {product.get_available_stock()} units available'
            )
        return data


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """Order status history"""
    changed_by_name = serializers.CharField(
        source='changed_by.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = OrderStatusHistory
        fields = [
            'from_status', 'to_status', 'reason', 'changed_by_name', 'created_at'
        ]
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    """Order list serializer"""
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    item_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display_verbose', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_id', 'customer_name', 'total_amount', 'status',
            'status_display', 'item_count', 'is_paid', 'created_at'
        ]
        read_only_fields = fields
    
    def get_item_count(self, obj):
        return obj.get_item_count()


class OrderDetailSerializer(serializers.ModelSerializer):
    """Order detail serializer"""
    items = OrderItemSerializer(many=True, read_only=True)
    customer = serializers.SerializerMethodField()
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    cancellation = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display_verbose', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_id', 'customer', 'items', 'subtotal', 'tax',
            'discount', 'total_amount', 'status', 'status_display',
            'is_paid', 'payment_method', 'notes',
            'delivery_phone', 'delivery_address', 'delivery_city',
            'delivery_county', 'delivery_postal_code', 'delivery_instructions',
            'shipped_date', 'delivered_date', 'tracking_number',
            'status_history', 'cancellation', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order_id', 'subtotal', 'items', 'status_history',
            'shipped_date', 'delivered_date', 'created_at', 'updated_at'
        ]
    
    def get_customer(self, obj):
        """Get customer basic info"""
        user = obj.customer
        return {
            'id': user.id,
            'name': user.get_full_name(),
            'phone': user.phone_number,
            'email': user.email
        }
    
    def get_cancellation(self, obj):
        """Get cancellation details if exists"""
        if hasattr(obj, 'cancellation'):
            return {
                'reason': obj.cancellation.reason,
                'refund_amount': str(obj.cancellation.refund_amount),
                'refund_status': obj.cancellation.refund_status,
                'created_at': obj.cancellation.created_at
            }
        return None


class OrderCreateSerializer(serializers.Serializer):
    """Create new order"""
    items = OrderItemCreateSerializer(many=True, min_length=1)
    delivery_phone = serializers.CharField(max_length=20)
    delivery_address = serializers.CharField()
    delivery_city = serializers.CharField(max_length=100)
    delivery_county = serializers.CharField(max_length=100, required=False)
    delivery_postal_code = serializers.CharField(max_length=20, required=False)
    delivery_instructions = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=['mpesa', 'card', 'bank_transfer', 'cash_on_delivery'],
        default='mpesa'
    )
    
    def create(self, validated_data):
        """Create order with items"""
        user = self.context['request'].user
        items_data = validated_data.pop('items')
        
        # Calculate totals
        subtotal = 0
        order_items = []
        
        for item_data in items_data:
            product = Product.objects.get(id=item_data['product_id'])
            quantity = item_data['quantity']
            unit_price = product.price
            item_subtotal = unit_price * quantity
            subtotal += item_subtotal
            
            order_items.append({
                'product': product,
                'quantity': quantity,
                'unit_price': unit_price,
                'subtotal': item_subtotal
            })
        
        # Create order
        order = Order.objects.create(
            customer=user,
            subtotal=subtotal,
            total_amount=subtotal,
            delivery_phone=validated_data['delivery_phone'],
            delivery_address=validated_data['delivery_address'],
            delivery_city=validated_data['delivery_city'],
            delivery_county=validated_data.get('delivery_county', ''),
            delivery_postal_code=validated_data.get('delivery_postal_code', ''),
            delivery_instructions=validated_data.get('delivery_instructions', ''),
            notes=validated_data.get('notes', ''),
            payment_method=validated_data['payment_method']
        )
        
        # Create order items and reserve stock
        for item in order_items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                subtotal=item['subtotal']
            )
            
            # Reserve stock
            item['product'].reserved_quantity += item['quantity']
            item['product'].save()
        
        return order


class OrderUpdateSerializer(serializers.ModelSerializer):
    """Update order details"""
    
    class Meta:
        model = Order
        fields = [
            'delivery_phone', 'delivery_address', 'delivery_city',
            'delivery_county', 'delivery_postal_code',
            'delivery_instructions', 'notes'
        ]


class OrderTrackingSerializer(serializers.ModelSerializer):
    """Order tracking serializer"""
    status_display = serializers.CharField(source='get_status_display_verbose', read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'order_id', 'status', 'status_display', 'item_count',
            'total_amount', 'delivery_address', 'delivery_city',
            'tracking_number', 'shipped_date', 'delivered_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_item_count(self, obj):
        return obj.get_item_count()


class OrderCancellationSerializer(serializers.ModelSerializer):
    """Order cancellation"""
    
    class Meta:
        model = OrderCancellation
        fields = ['reason', 'details', 'refund_status', 'created_at']
        read_only_fields = ['refund_status', 'created_at']


class OrderCancellationCreateSerializer(serializers.Serializer):
    """Request order cancellation"""
    reason = serializers.CharField(max_length=200)
    details = serializers.CharField(required=False, allow_blank=True)