# AI-Powered Recommendation Engine - Collaborative Filtering & ML

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging
import numpy as np

logger = logging.getLogger('recommendations')

# ============================================================
# RECOMMENDATION MODELS
# ============================================================

class UserProductInteraction(models.Model):
    """Track user-product interactions"""
    INTERACTION_TYPE_CHOICES = [
        ('view', 'Viewed'),
        ('add_cart', 'Added to Cart'),
        ('purchase', 'Purchased'),
        ('review', 'Reviewed'),
        ('wishlist', 'Added to Wishlist'),
    ]
    
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPE_CHOICES)
    
    # Weight/score
    weight = models.FloatField(default=1.0)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_product_interaction'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'product']),
            models.Index(fields=['user', 'interaction_type']),
        ]


class Recommendation(models.Model):
    """Generated recommendations"""
    ALGORITHM_CHOICES = [
        ('collaborative', 'Collaborative Filtering'),
        ('content', 'Content-Based'),
        ('hybrid', 'Hybrid'),
        ('trending', 'Trending'),
        ('seasonal', 'Seasonal'),
    ]
    
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    # Algorithm
    algorithm = models.CharField(max_length=20, choices=ALGORITHM_CHOICES)
    
    # Score
    score = models.FloatField()  # 0-1
    
    # Context
    reason = models.CharField(max_length=255)  # "Users who bought X also bought Y"
    
    # Tracking
    clicked = models.BooleanField(default=False)
    purchased = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'recommendation'
        ordering = ['-score']
        unique_together = ['user', 'product', 'algorithm']


class SimilarProduct(models.Model):
    """Cached similar products"""
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='similar_products')
    similar_product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='+')
    
    # Similarity score
    similarity_score = models.FloatField()  # 0-1
    
    # Reason
    reason = models.CharField(max_length=100)  # category, price_range, reviews, etc
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'similar_product'
        unique_together = ['product', 'similar_product']


class RecommendationFeedback(models.Model):
    """Track recommendation feedback"""
    FEEDBACK_CHOICES = [
        ('relevant', 'Relevant'),
        ('irrelevant', 'Irrelevant'),
        ('already_own', 'Already Own'),
        ('not_interested', 'Not Interested'),
    ]
    
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    feedback = models.CharField(max_length=20, choices=FEEDBACK_CHOICES)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'recommendation_feedback'
        unique_together = ['recommendation', 'user']


# ============================================================
# RECOMMENDATION ENGINE
# ============================================================

class RecommendationEngine:
    """Generate product recommendations"""
    
    @staticmethod
    def get_recommendations(user, limit=10, algorithm='hybrid'):
        """Get recommendations for user"""
        
        recommendations = Recommendation.objects.filter(user=user).order_by('-score')[:limit]
        
        if not recommendations.exists():
            # Generate new recommendations
            if algorithm == 'collaborative':
                recs = RecommendationEngine.collaborative_filtering(user, limit)
            elif algorithm == 'content':
                recs = RecommendationEngine.content_based(user, limit)
            elif algorithm == 'hybrid':
                recs = RecommendationEngine.hybrid_recommendations(user, limit)
            else:
                recs = RecommendationEngine.trending_products(user, limit)
            
            recommendations = recs
        
        return recommendations
    
    @staticmethod
    def collaborative_filtering(user, limit=10):
        """Collaborative filtering recommendations"""
        from apps.recommendations.models import UserProductInteraction, Recommendation
        
        # Get user's interactions
        user_interactions = UserProductInteraction.objects.filter(user=user).values_list('product_id', flat=True)
        
        # Find similar users (users who liked same products)
        similar_users = UserProductInteraction.objects.filter(
            product_id__in=user_interactions
        ).exclude(user=user).values('user').distinct()
        
        # Get products that similar users liked
        recommended_products = UserProductInteraction.objects.filter(
            user_id__in=similar_users
        ).exclude(
            product_id__in=user_interactions
        ).values('product_id').annotate(
            score=models.Sum('weight')
        ).order_by('-score')[:limit]
        
        recommendations = []
        for item in recommended_products:
            rec = Recommendation.objects.create(
                user=user,
                product_id=item['product_id'],
                algorithm='collaborative',
                score=min(item['score'] / 100, 1.0),
                reason='Similar users purchased this'
            )
            recommendations.append(rec)
        
        return recommendations
    
    @staticmethod
    def content_based(user, limit=10):
        """Content-based recommendations"""
        from apps.recommendations.models import UserProductInteraction, Recommendation, SimilarProduct
        
        # Get products user has interacted with
        user_products = UserProductInteraction.objects.filter(user=user).values_list('product_id', flat=True)
        
        # Get similar products
        similar_products = SimilarProduct.objects.filter(
            product_id__in=user_products
        ).exclude(
            similar_product_id__in=user_products
        ).values('similar_product_id').annotate(
            score=models.Avg('similarity_score')
        ).order_by('-score')[:limit]
        
        recommendations = []
        for item in similar_products:
            rec = Recommendation.objects.create(
                user=user,
                product_id=item['similar_product_id'],
                algorithm='content',
                score=item['score'],
                reason='Similar to products you viewed'
            )
            recommendations.append(rec)
        
        return recommendations
    
    @staticmethod
    def hybrid_recommendations(user, limit=10):
        """Hybrid approach combining multiple algorithms"""
        
        collab = RecommendationEngine.collaborative_filtering(user, limit)
        content = RecommendationEngine.content_based(user, limit)
        
        # Combine and deduplicate
        seen_products = set()
        recommendations = []
        
        for rec in collab + content:
            if rec.product_id not in seen_products:
                recommendations.append(rec)
                seen_products.add(rec.product_id)
                
                if len(recommendations) >= limit:
                    break
        
        return recommendations
    
    @staticmethod
    def trending_products(user, limit=10):
        """Trending products recommendations"""
        from apps.orders.models import Order, OrderItem
        from apps.recommendations.models import UserProductInteraction, Recommendation
        
        # Get trending products (high sales in last 30 days)
        cutoff = timezone.now() - timedelta(days=30)
        
        trending = OrderItem.objects.filter(
            order__created_at__gte=cutoff
        ).values('product_id').annotate(
            sales_count=models.Count('id')
        ).order_by('-sales_count')[:limit]
        
        user_products = UserProductInteraction.objects.filter(user=user).values_list('product_id', flat=True)
        
        recommendations = []
        for item in trending:
            if item['product_id'] not in user_products:
                rec = Recommendation.objects.create(
                    user=user,
                    product_id=item['product_id'],
                    algorithm='trending',
                    score=min(item['sales_count'] / 100, 1.0),
                    reason='Trending now'
                )
                recommendations.append(rec)
        
        return recommendations
    
    @staticmethod
    def track_interaction(user, product, interaction_type):
        """Track user-product interaction"""
        from apps.recommendations.models import UserProductInteraction
        
        # Weight different interaction types
        weights = {
            'view': 1.0,
            'add_cart': 2.0,
            'wishlist': 1.5,
            'review': 2.5,
            'purchase': 5.0,
        }
        
        weight = weights.get(interaction_type, 1.0)
        
        interaction, created = UserProductInteraction.objects.get_or_create(
            user=user,
            product=product,
            interaction_type=interaction_type,
            defaults={'weight': weight}
        )
        
        if not created:
            interaction.weight += weight
            interaction.save()
        
        # Regenerate recommendations
        RecommendationEngine.get_recommendations(user)
    
    @staticmethod
    def calculate_similar_products():
        """Calculate similarity between all products"""
        from apps.products.models import Product
        from apps.recommendations.models import SimilarProduct
        
        products = Product.objects.filter(is_active=True)
        
        for product in products:
            # Find similar products by category
            category_similar = Product.objects.filter(
                category=product.category,
                is_active=True
            ).exclude(id=product.id)[:5]
            
            for similar in category_similar:
                score = RecommendationEngine.calculate_similarity(product, similar)
                
                SimilarProduct.objects.update_or_create(
                    product=product,
                    similar_product=similar,
                    defaults={
                        'similarity_score': score,
                        'reason': 'Same category'
                    }
                )
    
    @staticmethod
    def calculate_similarity(product1, product2):
        """Calculate similarity between two products"""
        
        score = 0.0
        
        # Category similarity
        if product1.category == product2.category:
            score += 0.3
        
        # Price similarity (within 20%)
        price_diff = abs(product1.price - product2.price) / max(product1.price, product2.price)
        if price_diff < 0.2:
            score += 0.3
        
        # Rating similarity
        if abs(product1.rating - product2.rating) < 1.0:
            score += 0.2
        
        # Tag similarity
        tags1 = set(product1.tags.values_list('id', flat=True))
        tags2 = set(product2.tags.values_list('id', flat=True))
        if tags1 and tags2:
            similarity = len(tags1 & tags2) / len(tags1 | tags2)
            score += similarity * 0.2
        
        return min(score, 1.0)


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def generate_recommendations_batch():
    '''Generate recommendations for all active users'''
    from apps.users.models import CustomUser
    
    users = CustomUser.objects.filter(is_active=True, last_login__gte=timezone.now() - timedelta(days=30))
    
    for user in users:
        try:
            RecommendationEngine.get_recommendations(user, algorithm='hybrid')
        except Exception as e:
            logger.error(f'Failed to generate recommendations for {user.id}: {e}')

@shared_task
def calculate_product_similarities():
    '''Calculate similarity scores between products'''
    RecommendationEngine.calculate_similar_products()

@shared_task
def cleanup_old_interactions():
    '''Delete old user interactions'''
    from apps.recommendations.models import UserProductInteraction
    
    cutoff = timezone.now() - timedelta(days=365)
    UserProductInteraction.objects.filter(created_at__lt=cutoff).delete()

@shared_task
def optimize_recommendations():
    '''Optimize recommendation quality based on feedback'''
    from apps.recommendations.models import RecommendationFeedback
    
    # Analyze feedback and adjust algorithm weights
    feedback = RecommendationFeedback.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    )
    
    relevant_count = feedback.filter(feedback='relevant').count()
    total_count = feedback.count()
    
    if total_count > 0:
        accuracy = relevant_count / total_count
        logger.info(f'Recommendation accuracy: {accuracy:.2%}')

# Add to CELERY_BEAT_SCHEDULE:
'generate-recommendations': {
    'task': 'apps.recommendations.tasks.generate_recommendations_batch',
    'schedule': 86400.0,  # Daily
},
'calculate-similarities': {
    'task': 'apps.recommendations.tasks.calculate_product_similarities',
    'schedule': 604800.0,  # Weekly
},
'cleanup-interactions': {
    'task': 'apps.recommendations.tasks.cleanup_old_interactions',
    'schedule': 2592000.0,  # Monthly
},
'optimize-recommendations': {
    'task': 'apps.recommendations.tasks.optimize_recommendations',
    'schedule': 604800.0,  # Weekly
},
"""