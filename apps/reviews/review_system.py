# Review & Rating System - Verified Reviews with Moderation

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('reviews')

# ============================================================
# REVIEW MODELS
# ============================================================

class ProductReview(models.Model):
    """Product reviews and ratings"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('flagged', 'Flagged for Review'),
    ]
    
    # Review info
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Content
    title = models.CharField(max_length=255)
    content = models.TextField()
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Review aspects
    value_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Value for money rating"
    )
    quality_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Product quality rating"
    )
    delivery_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Delivery experience rating"
    )
    
    # Verification
    verified_purchase = models.BooleanField(default=False)
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Moderation
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    
    # Engagement
    helpful_count = models.IntegerField(default=0)
    unhelpful_count = models.IntegerField(default=0)
    
    # Media
    images = models.JSONField(default=list)  # URLs to review images
    
    # Metadata
    language = models.CharField(max_length=10, default='en')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_review'
        ordering = ['-created_at']
        unique_together = ['product', 'customer', 'order']
        indexes = [
            models.Index(fields=['product', 'status']),
            models.Index(fields=['customer']),
            models.Index(fields=['-created_at']),
        ]


class ReviewHelpfulness(models.Model):
    """Track review helpfulness votes"""
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='helpfulness_votes')
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    helpful = models.BooleanField()  # True = helpful, False = unhelpful
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_helpfulness'
        unique_together = ['review', 'user']


class ReviewResponse(models.Model):
    """Seller responses to reviews"""
    review = models.OneToOneField(ProductReview, on_delete=models.CASCADE, related_name='response')
    
    # Response
    content = models.TextField()
    respondent = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'review_response'


class ReviewModeration(models.Model):
    """Track review moderation actions"""
    ACTION_CHOICES = [
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('flagged', 'Flagged'),
        ('edited', 'Edited'),
    ]
    
    REASON_CHOICES = [
        ('spam', 'Spam'),
        ('inappropriate', 'Inappropriate Content'),
        ('fake', 'Likely Fake Review'),
        ('offensive', 'Offensive Language'),
        ('unrelated', 'Unrelated to Product'),
        ('duplicates', 'Duplicate Review'),
        ('other', 'Other'),
    ]
    
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='moderation_history')
    
    # Action
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes = models.TextField(blank=True)
    
    # Moderator
    moderator = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_moderation'
        ordering = ['-created_at']


class ReviewSummary(models.Model):
    """Cached review statistics"""
    product = models.OneToOneField('products.Product', on_delete=models.CASCADE)
    
    # Ratings
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_reviews = models.IntegerField(default=0)
    
    # Rating distribution
    five_star_count = models.IntegerField(default=0)
    four_star_count = models.IntegerField(default=0)
    three_star_count = models.IntegerField(default=0)
    two_star_count = models.IntegerField(default=0)
    one_star_count = models.IntegerField(default=0)
    
    # Aspect ratings
    avg_value_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    avg_quality_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    avg_delivery_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Verified purchases
    verified_purchase_count = models.IntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'review_summary'


# ============================================================
# REVIEW MANAGER
# ============================================================

class ReviewManager:
    """Manage product reviews"""
    
    @staticmethod
    def create_review(product, customer, title, content, rating, order=None, images=None):
        """Create new review"""
        
        # Check if customer can review this product
        if not ReviewManager.can_review(product, customer, order):
            raise ValueError('Customer cannot review this product')
        
        review = ProductReview.objects.create(
            product=product,
            customer=customer,
            title=title,
            content=content,
            rating=rating,
            order=order,
            verified_purchase=order is not None,
            images=images or [],
        )
        
        # Update review summary
        ReviewManager.update_review_summary(product)
        
        logger.info(f'Review created for product {product.id}')
        
        return review
    
    @staticmethod
    def can_review(product, customer, order=None):
        """Check if customer can review product"""
        
        # Check for existing review
        if ProductReview.objects.filter(product=product, customer=customer).exists():
            return False
        
        # Check if customer purchased product
        if order:
            return order.customer == customer and order.status == 'delivered'
        
        return True
    
    @staticmethod
    def approve_review(review, moderator=None):
        """Approve pending review"""
        review.status = 'approved'
        review.save()
        
        ReviewModeration.objects.create(
            review=review,
            action='approved',
            reason='manual',
            moderator=moderator,
        )
        
        ReviewManager.update_review_summary(review.product)
        logger.info(f'Review {review.id} approved')
    
    @staticmethod
    def reject_review(review, reason, moderator=None):
        """Reject review"""
        review.status = 'rejected'
        review.rejection_reason = reason
        review.save()
        
        ReviewModeration.objects.create(
            review=review,
            action='rejected',
            reason=reason,
            moderator=moderator,
        )
        
        logger.info(f'Review {review.id} rejected: {reason}')
    
    @staticmethod
    def flag_review(review, reason):
        """Flag review for manual review"""
        review.status = 'flagged'
        review.save()
        
        ReviewModeration.objects.create(
            review=review,
            action='flagged',
            reason=reason,
        )
        
        logger.warning(f'Review {review.id} flagged: {reason}')
    
    @staticmethod
    def update_review_summary(product):
        """Update cached review statistics"""
        from django.db.models import Avg, Count, Q
        
        reviews = product.reviews.filter(status='approved')
        
        if not reviews.exists():
            return
        
        summary, created = ReviewSummary.objects.get_or_create(product=product)
        
        summary.total_reviews = reviews.count()
        summary.average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        
        # Count by rating
        summary.five_star_count = reviews.filter(rating=5).count()
        summary.four_star_count = reviews.filter(rating=4).count()
        summary.three_star_count = reviews.filter(rating=3).count()
        summary.two_star_count = reviews.filter(rating=2).count()
        summary.one_star_count = reviews.filter(rating=1).count()
        
        # Aspect ratings
        summary.avg_value_rating = reviews.filter(value_rating__isnull=False).aggregate(Avg('value_rating'))['value_rating__avg'] or 0
        summary.avg_quality_rating = reviews.filter(quality_rating__isnull=False).aggregate(Avg('quality_rating'))['quality_rating__avg'] or 0
        summary.avg_delivery_rating = reviews.filter(delivery_rating__isnull=False).aggregate(Avg('delivery_rating'))['delivery_rating__avg'] or 0
        
        summary.verified_purchase_count = reviews.filter(verified_purchase=True).count()
        
        summary.save()
        
        # Update product rating
        product.rating = summary.average_rating
        product.save()
    
    @staticmethod
    def detect_fake_reviews():
        """Detect potentially fake reviews"""
        pending_reviews = ProductReview.objects.filter(status='pending')
        
        for review in pending_reviews:
            score = 0
            
            # Check for short content
            if len(review.content) < 20:
                score += 2
            
            # Check for generic content
            generic_phrases = ['great product', 'recommend', 'good quality', 'fast delivery']
            if any(phrase in review.content.lower() for phrase in generic_phrases):
                score += 1
            
            # Check rating distribution
            if review.rating == 5 and not review.verified_purchase:
                score += 2
            
            # Check reviewer history
            reviewer_reviews = ProductReview.objects.filter(customer=review.customer, status='approved')
            if reviewer_reviews.count() > 50 and reviewer_reviews.filter(rating__gte=4).count() > 45:
                score += 3  # Likely professional reviewer
            
            if score >= 4:
                ReviewManager.flag_review(review, 'likely_fake')


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def auto_approve_verified_reviews():
    '''Auto-approve reviews from verified purchases'''
    from apps.reviews.models import ProductReview
    
    pending = ProductReview.objects.filter(
        status='pending',
        verified_purchase=True,
        created_at__gte=timezone.now() - timedelta(days=7)
    )
    
    for review in pending:
        ReviewManager.approve_review(review)

@shared_task
def detect_fake_reviews_task():
    '''Detect and flag potential fake reviews'''
    ReviewManager.detect_fake_reviews()

@shared_task
def send_review_requests():
    '''Send review request emails after delivery'''
    from apps.orders.models import Order
    
    # Orders delivered 3 days ago
    target_date = (timezone.now() - timedelta(days=3)).date()
    
    orders = Order.objects.filter(
        status='delivered',
        delivered_at__date=target_date
    )
    
    for order in orders:
        # Send review request email
        pass

# Add to CELERY_BEAT_SCHEDULE:
'auto-approve-verified-reviews': {
    'task': 'apps.reviews.tasks.auto_approve_verified_reviews',
    'schedule': 86400.0,  # Daily
},
'detect-fake-reviews': {
    'task': 'apps.reviews.tasks.detect_fake_reviews_task',
    'schedule': 3600.0,  # Hourly
},
'send-review-requests': {
    'task': 'apps.reviews.tasks.send_review_requests',
    'schedule': 86400.0,  # Daily
},
"""