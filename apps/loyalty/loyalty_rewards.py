# Customer Loyalty & Rewards System

from django.db import models
from django.db.models import Sum, Count
from datetime import datetime, timedelta
from decimal import Decimal

# ============================================================
# LOYALTY MODELS
# ============================================================

class LoyaltyProgram(models.Model):
    """Loyalty program configuration"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('paused', 'Paused'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Points configuration
    points_per_ksh = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        help_text="Points earned per 1 KES spent"
    )
    
    # Tiers
    has_tiers = models.BooleanField(default=True)
    
    # Redemption
    points_expiry_days = models.IntegerField(default=365)  # 1 year
    min_points_to_redeem = models.IntegerField(default=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'loyalty_program'


class LoyaltyTier(models.Model):
    """Loyalty program tiers (Bronze, Silver, Gold, Platinum)"""
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name='tiers')
    
    name = models.CharField(max_length=100)  # Bronze, Silver, Gold, Platinum
    level = models.IntegerField()  # 1, 2, 3, 4
    
    # Requirements
    min_points_required = models.IntegerField()
    min_annual_spend = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Benefits
    points_multiplier = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        help_text="Multiply earned points by this factor"
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    free_shipping = models.BooleanField(default=False)
    birthday_bonus_points = models.IntegerField(default=0)
    
    # Color/Badge
    color = models.CharField(max_length=20, default='#999999')
    badge_emoji = models.CharField(max_length=10, default='⭐')
    
    class Meta:
        db_table = 'loyalty_tier'
        ordering = ['level']


class CustomerLoyaltyAccount(models.Model):
    """Loyalty account for each customer"""
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE)
    
    # Points
    total_points = models.IntegerField(default=0)
    available_points = models.IntegerField(default=0)
    redeemed_points = models.IntegerField(default=0)
    
    # Tier
    current_tier = models.ForeignKey(LoyaltyTier, null=True, blank=True, on_delete=models.SET_NULL)
    tier_achieved_date = models.DateTimeField(null=True, blank=True)
    
    # Spending
    lifetime_spending = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_spending = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Tracking
    joined_date = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'loyalty_account'


class LoyaltyPoints(models.Model):
    """Transaction log for loyalty points"""
    ACTION_CHOICES = [
        ('earn', 'Earned'),
        ('redeem', 'Redeemed'),
        ('expire', 'Expired'),
        ('bonus', 'Bonus'),
        ('adjustment', 'Adjustment'),
        ('referral', 'Referral'),
    ]
    
    account = models.ForeignKey(CustomerLoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    points = models.IntegerField()
    
    # References
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    reward = models.ForeignKey('LoyaltyReward', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Metadata
    description = models.CharField(max_length=255, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'loyalty_points'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
        ]


class LoyaltyReward(models.Model):
    """Rewards customers can redeem"""
    REWARD_TYPE_CHOICES = [
        ('discount', 'Discount Coupon'),
        ('free_product', 'Free Product'),
        ('free_shipping', 'Free Shipping'),
        ('exclusive_access', 'Exclusive Access'),
        ('cash_back', 'Cash Back'),
    ]
    
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name='rewards')
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    reward_type = models.CharField(max_length=20, choices=REWARD_TYPE_CHOICES)
    
    # Cost in points
    points_required = models.IntegerField()
    
    # Reward details
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Availability
    is_active = models.BooleanField(default=True)
    max_redemptions = models.IntegerField(null=True, blank=True)  # Null = unlimited
    current_redemptions = models.IntegerField(default=0)
    
    # Validity
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Tier restrictions
    min_tier = models.ForeignKey(
        LoyaltyTier,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Minimum tier required to redeem"
    )
    
    class Meta:
        db_table = 'loyalty_reward'
        ordering = ['points_required']


class RedemptionRecord(models.Model):
    """Track reward redemptions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('claimed', 'Claimed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    account = models.ForeignKey(CustomerLoyaltyAccount, on_delete=models.CASCADE)
    reward = models.ForeignKey(LoyaltyReward, on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Coupon code
    coupon_code = models.CharField(max_length=50, unique=True)
    coupon_expiry = models.DateTimeField()
    claimed_at = models.DateTimeField(null=True, blank=True)
    
    # Order reference
    used_in_order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'redemption_record'
        ordering = ['-created_at']


class ReferralProgram(models.Model):
    """Customer referral tracking"""
    referrer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='referrals_given')
    referred_user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='referrals_received')
    
    # Bonuses
    referrer_bonus_points = models.IntegerField(default=500)
    referred_bonus_points = models.IntegerField(default=250)
    
    # Tracking
    referral_code = models.CharField(max_length=50, unique=True)
    referred_at = models.DateTimeField(auto_now_add=True)
    first_purchase_at = models.DateTimeField(null=True, blank=True)
    bonus_awarded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'referral_program'


# ============================================================
# LOYALTY MANAGER
# ============================================================

class LoyaltyManager:
    """Manage loyalty points and rewards"""
    
    @staticmethod
    def award_points_for_order(order):
        """Award loyalty points for order"""
        try:
            account = CustomerLoyaltyAccount.objects.get(user=order.customer)
        except CustomerLoyaltyAccount.DoesNotExist:
            return None
        
        if account.program.status != 'active':
            return None
        
        # Calculate points
        base_points = int(float(order.total_amount) * float(account.program.points_per_ksh))
        
        # Apply tier multiplier
        multiplier = Decimal(1.0)
        if account.current_tier:
            multiplier = account.current_tier.points_multiplier
        
        total_points = int(base_points * float(multiplier))
        
        # Award points
        LoyaltyPoints.objects.create(
            account=account,
            action='earn',
            points=total_points,
            order=order,
            description=f'Points earned for order {order.order_id}',
            expiry_date=datetime.now().date() + timedelta(days=account.program.points_expiry_days),
        )
        
        # Update account
        account.total_points += total_points
        account.available_points += total_points
        account.lifetime_spending += order.total_amount
        account.annual_spending += order.total_amount
        account.last_activity = datetime.now()
        account.save()
        
        # Check tier upgrade
        LoyaltyManager.check_tier_upgrade(account)
        
        return total_points
    
    @staticmethod
    def check_tier_upgrade(account):
        """Check if customer should be upgraded to higher tier"""
        if not account.program.has_tiers:
            return
        
        # Get next tier
        next_tier = account.program.tiers.filter(
            level__gt=(account.current_tier.level if account.current_tier else 0)
        ).order_by('level').first()
        
        if next_tier and account.total_points >= next_tier.min_points_required:
            account.current_tier = next_tier
            account.tier_achieved_date = datetime.now()
            account.save()
            
            # Send notification
            LoyaltyManager.notify_tier_upgrade(account, next_tier)
    
    @staticmethod
    def notify_tier_upgrade(account, tier):
        """Send tier upgrade notification"""
        # TODO: Send email/SMS notification
        pass
    
    @staticmethod
    def redeem_reward(account, reward):
        """Redeem a reward"""
        if account.available_points < reward.points_required:
            raise ValueError('Insufficient points')
        
        if not reward.is_active:
            raise ValueError('Reward not available')
        
        if reward.max_redemptions and reward.current_redemptions >= reward.max_redemptions:
            raise ValueError('Reward limit reached')
        
        # Generate coupon code
        import secrets
        coupon_code = secrets.token_urlsafe(8).upper()
        
        # Create redemption record
        redemption = RedemptionRecord.objects.create(
            account=account,
            reward=reward,
            coupon_code=coupon_code,
            coupon_expiry=datetime.now() + timedelta(days=30),
        )
        
        # Deduct points
        account.available_points -= reward.points_required
        account.redeemed_points += reward.points_required
        account.save()
        
        # Log transaction
        LoyaltyPoints.objects.create(
            account=account,
            action='redeem',
            points=-reward.points_required,
            reward=reward,
            description=f'Redeemed: {reward.name}',
        )
        
        # Update reward count
        reward.current_redemptions += 1
        reward.save()
        
        return redemption
    
    @staticmethod
    def clean_expired_points():
        """Remove expired loyalty points"""
        expired = LoyaltyPoints.objects.filter(
            expiry_date__lt=datetime.now().date(),
            action='earn'
        )
        
        for transaction in expired:
            transaction.account.available_points -= transaction.points
            transaction.account.total_points -= transaction.points
            transaction.action = 'expire'
            transaction.save()
            transaction.account.save()
    
    @staticmethod
    def apply_referral_bonus(referrer, referred_user):
        """Award referral bonuses"""
        try:
            referrer_account = CustomerLoyaltyAccount.objects.get(user=referrer)
            referred_account = CustomerLoyaltyAccount.objects.get(user=referred_user)
        except CustomerLoyaltyAccount.DoesNotExist:
            return None
        
        # Award referrer bonus
        LoyaltyPoints.objects.create(
            account=referrer_account,
            action='referral',
            points=500,
            description=f'Referral bonus for {referred_user.email}',
        )
        
        # Award referred user bonus
        LoyaltyPoints.objects.create(
            account=referred_account,
            action='bonus',
            points=250,
            description='Referral sign-up bonus',
        )
        
        # Update accounts
        referrer_account.available_points += 500
        referred_account.available_points += 250
        referrer_account.save()
        referred_account.save()


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def clean_expired_points():
    '''Clean up expired points daily'''
    LoyaltyManager.clean_expired_points()
    return 'Expired points cleaned'

@shared_task
def process_annual_reset():
    '''Reset annual spending at year start'''
    from apps.loyalty.models import CustomerLoyaltyAccount
    
    today = datetime.now().date()
    if today.month == 1 and today.day == 1:
        CustomerLoyaltyAccount.objects.all().update(annual_spending=0)
    
    return 'Annual spending reset'

# Add to CELERY_BEAT_SCHEDULE:
'clean-expired-loyalty-points': {
    'task': 'apps.loyalty.tasks.clean_expired_points',
    'schedule': 86400.0,  # Daily
},
'process-annual-reset': {
    'task': 'apps.loyalty.tasks.process_annual_reset',
    'schedule': 86400.0,  # Daily
},
"""

# ============================================================
# API SERIALIZERS & VIEWS
# ============================================================

"""
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

class LoyaltyAccountSerializer(serializers.ModelSerializer):
    current_tier_name = serializers.CharField(source='current_tier.name', read_only=True)
    
    class Meta:
        model = CustomerLoyaltyAccount
        fields = [
            'total_points', 'available_points', 'current_tier_name',
            'lifetime_spending', 'annual_spending', 'joined_date'
        ]

class LoyaltyRewardSerializer(serializers.ModelSerializer):
    can_redeem = serializers.SerializerMethodField()
    
    def get_can_redeem(self, obj):
        request = self.context.get('request')
        if request:
            account = request.user.loyaltyaccount
            return account.available_points >= obj.points_required
        return False
    
    class Meta:
        model = LoyaltyReward
        fields = ['id', 'name', 'points_required', 'reward_type', 'can_redeem']

class LoyaltyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LoyaltyAccountSerializer
    
    @action(detail=False)
    def my_account(self, request):
        '''Get user's loyalty account'''
        account = request.user.loyaltyaccount
        serializer = self.serializer_class(account)
        return Response(serializer.data)
    
    @action(detail=False)
    def available_rewards(self, request):
        '''Get available rewards'''
        account = request.user.loyaltyaccount
        rewards = account.program.rewards.filter(is_active=True)
        serializer = LoyaltyRewardSerializer(
            rewards,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def redeem_reward(self, request):
        '''Redeem a reward'''
        reward_id = request.data.get('reward_id')
        account = request.user.loyaltyaccount
        reward = LoyaltyReward.objects.get(id=reward_id)
        
        redemption = LoyaltyManager.redeem_reward(account, reward)
        
        return Response({
            'coupon_code': redemption.coupon_code,
            'valid_until': redemption.coupon_expiry,
        })
"""