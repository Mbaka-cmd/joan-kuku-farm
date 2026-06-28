from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import CustomUser, UserPreferences


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer"""
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'address', 'city', 'county', 'postal_code',
            'is_verified', 'email_verified', 'phone_verified',
            'profile_picture', 'bio', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_verified']


class RegisterSerializer(serializers.ModelSerializer):
    """Registration serializer"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = CustomUser
        fields = [
            'email', 'phone_number', 'first_name', 'last_name',
            'password', 'password_confirm', 'address', 'city', 'county'
        ]
    
    def validate(self, data):
        """Validate passwords match"""
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password': 'Passwords do not match'})
        return data
    
    def validate_email(self, value):
        """Check email uniqueness"""
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email is already registered')
        return value
    
    def validate_phone_number(self, value):
        """Check phone uniqueness"""
        if CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError('This phone number is already registered')
        return value
    
    def create(self, validated_data):
        """Create user with hashed password"""
        user = CustomUser.objects.create_user(
            username=validated_data['email'].split('@')[0],
            email=validated_data['email'],
            phone_number=validated_data['phone_number'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            address=validated_data.get('address', ''),
            city=validated_data.get('city', 'Nairobi'),
            county=validated_data.get('county', ''),
            password=validated_data['password']
        )
        
        # Create default preferences
        UserPreferences.objects.create(user=user)
        
        return user


class LoginSerializer(serializers.Serializer):
    """Login serializer"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        """Authenticate user"""
        try:
            user = CustomUser.objects.get(email=data['email'])
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError('Invalid email or password')
        
        if not user.check_password(data['password']):
            raise serializers.ValidationError('Invalid email or password')
        
        data['user'] = user
        return data


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Update user profile"""
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'phone_number', 'address',
            'city', 'county', 'postal_code', 'profile_picture', 'bio'
        ]
    
    def validate_phone_number(self, value):
        """Check phone uniqueness (excluding current user)"""
        user = self.instance
        if CustomUser.objects.filter(phone_number=value).exclude(id=user.id).exists():
            raise serializers.ValidationError('This phone number is already in use')
        return value


class UserPreferencesSerializer(serializers.ModelSerializer):
    """User notification preferences"""
    
    class Meta:
        model = UserPreferences
        fields = [
            'receive_order_updates', 'receive_promotions', 'receive_newsletters',
            'preferred_notification', 'is_public_profile', 'allow_marketing'
        ]


class UserProfileDetailSerializer(serializers.ModelSerializer):
    """Detailed user profile with preferences"""
    preferences = UserPreferencesSerializer(read_only=True)
    total_orders = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'address', 'city', 'county', 'postal_code',
            'is_verified', 'email_verified', 'phone_verified',
            'profile_picture', 'bio', 'preferences',
            'total_orders', 'total_spent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'is_verified']
    
    def get_total_orders(self, obj):
        """Get user's total orders"""
        return obj.get_total_orders()
    
    def get_total_spent(self, obj):
        """Get user's total spending"""
        return float(obj.get_total_spent())


class PasswordChangeSerializer(serializers.Serializer):
    """Change password"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    def validate(self, data):
        """Validate passwords"""
        user = self.context['request'].user
        
        if not user.check_password(data['old_password']):
            raise serializers.ValidationError({'old_password': 'Incorrect password'})
        
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({'new_password': 'Passwords do not match'})
        
        return data
    
    def save(self):
        """Update password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user