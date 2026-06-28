# Social Media Integration - Sharing, Cross-posting, Analytics

from django.db import models
from django.utils import timezone
import logging

logger = logging.getLogger('social')

# ============================================================
# SOCIAL MEDIA MODELS
# ============================================================

class SocialMediaAccount(models.Model):
    """Connected social media accounts"""
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter/X'),
        ('instagram', 'Instagram'),
        ('tiktok', 'TikTok'),
        ('linkedin', 'LinkedIn'),
        ('youtube', 'YouTube'),
    ]
    
    business = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    
    # Account info
    account_name = models.CharField(max_length=255)
    account_id = models.CharField(max_length=255, unique=True)
    
    # Credentials
    access_token = models.CharField(max_length=500)
    refresh_token = models.CharField(max_length=500, blank=True)
    token_expires = models.DateTimeField(null=True, blank=True)
    
    # Permissions
    permissions = models.JSONField(default=list)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    
    connected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_media_account'
        unique_together = ['business', 'platform', 'account_id']


class SocialPost(models.Model):
    """Posts shared to social media"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('posted', 'Posted'),
        ('failed', 'Failed'),
    ]
    
    # Content
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='social_posts/', blank=True)
    
    # Reference
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Posting
    account = models.ForeignKey(SocialMediaAccount, on_delete=models.CASCADE)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    posted_time = models.DateTimeField(null=True, blank=True)
    
    # Platform-specific
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    platform_post_id = models.CharField(max_length=255, blank=True, unique=True)
    platform_url = models.URLField(blank=True)
    
    # Analytics
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_post'
        ordering = ['-created_at']


class SocialMediaAnalytics(models.Model):
    """Analytics for social media accounts"""
    account = models.OneToOneField(SocialMediaAccount, on_delete=models.CASCADE)
    
    # Engagement
    total_followers = models.IntegerField(default=0)
    total_posts = models.IntegerField(default=0)
    avg_engagement_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Growth
    followers_today = models.IntegerField(default=0)
    followers_week = models.IntegerField(default=0)
    followers_month = models.IntegerField(default=0)
    
    # Performance
    best_posting_time = models.TimeField(null=True, blank=True)
    best_content_type = models.CharField(max_length=50, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_media_analytics'


class SocialMediaComment(models.Model):
    """Comments on social posts"""
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='comments')
    
    # Comment info
    platform_comment_id = models.CharField(max_length=255, unique=True)
    author_name = models.CharField(max_length=255)
    author_id = models.CharField(max_length=255)
    content = models.TextField()
    
    # Engagement
    likes = models.IntegerField(default=0)
    replies_count = models.IntegerField(default=0)
    
    # Response
    replied = models.BooleanField(default=False)
    response_content = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_media_comment'


# ============================================================
# SOCIAL MEDIA MANAGER
# ============================================================

class SocialMediaManager:
    """Manage social media posting"""
    
    @staticmethod
    def post_to_facebook(account, content, image=None, scheduled_time=None):
        """Post to Facebook"""
        import facebook
        
        try:
            graph = facebook.GraphAPI(account.access_token)
            
            if scheduled_time:
                # Schedule post
                graph.put_object(
                    'me/feed',
                    message=content,
                    image=image,
                    published=False,
                    scheduled_publish_time=int(scheduled_time.timestamp())
                )
            else:
                # Post immediately
                result = graph.put_object(
                    'me/feed',
                    message=content,
                )
                
                return result.get('id')
        
        except Exception as e:
            logger.error(f'Facebook post failed: {e}')
            return None
    
    @staticmethod
    def post_to_twitter(account, content, image=None):
        """Post to Twitter/X"""
        import tweepy
        
        try:
            auth = tweepy.OAuthHandler(
                'TWITTER_API_KEY',
                'TWITTER_API_SECRET'
            )
            auth.set_access_token(account.access_token, account.refresh_token)
            
            api = tweepy.API(auth)
            
            if image:
                # Upload image
                media = api.media_upload(image)
                tweet = api.update_status(content, media_ids=[media.media_id])
            else:
                tweet = api.update_status(content)
            
            return tweet.id_str
        
        except Exception as e:
            logger.error(f'Twitter post failed: {e}')
            return None
    
    @staticmethod
    def post_to_instagram(account, content, image):
        """Post to Instagram"""
        import instagrapi
        
        try:
            cl = instagrapi.Client()
            cl.login(account.account_name, account.access_token)
            
            result = cl.photo_upload(image, caption=content)
            return result.id
        
        except Exception as e:
            logger.error(f'Instagram post failed: {e}')
            return None
    
    @staticmethod
    def post_to_tiktok(account, content, video):
        """Post to TikTok"""
        try:
            # TikTok API is more restrictive
            # Use TikTok Business Account API
            import requests
            
            url = 'https://open-api.tiktok.com/v1/post/publish/'
            
            headers = {
                'Authorization': f'Bearer {account.access_token}',
                'Content-Type': 'application/json',
            }
            
            data = {
                'video_title': content,
                'video_id': video,  # Must be uploaded first
            }
            
            response = requests.post(url, json=data, headers=headers)
            return response.json().get('data', {}).get('publish_id')
        
        except Exception as e:
            logger.error(f'TikTok post failed: {e}')
            return None
    
    @staticmethod
    def sync_analytics(account):
        """Sync analytics from platform"""
        try:
            if account.platform == 'facebook':
                SocialMediaManager._sync_facebook_analytics(account)
            elif account.platform == 'twitter':
                SocialMediaManager._sync_twitter_analytics(account)
            elif account.platform == 'instagram':
                SocialMediaManager._sync_instagram_analytics(account)
            
            account.last_synced = timezone.now()
            account.save()
        
        except Exception as e:
            logger.error(f'Analytics sync failed: {e}')
    
    @staticmethod
    def _sync_facebook_analytics(account):
        """Sync Facebook analytics"""
        import facebook
        
        graph = facebook.GraphAPI(account.access_token)
        
        # Get page insights
        insights = graph.get_objects(
            ids='me/insights',
            fields='name,values'
        )
        
        # Update analytics
        analytics, created = SocialMediaAnalytics.objects.get_or_create(account=account)
        
        for insight in insights.get('me', []):
            if insight['name'] == 'page_fans':
                analytics.total_followers = insight['values'][0]['value']
            elif insight['name'] == 'page_posts':
                analytics.total_posts = insight['values'][0]['value']
        
        analytics.save()
    
    @staticmethod
    def get_engagement_metrics(post):
        """Calculate engagement metrics"""
        total_interactions = post.likes + post.comments + post.shares
        
        if post.impressions > 0:
            engagement_rate = (total_interactions / post.impressions) * 100
        else:
            engagement_rate = 0
        
        return {
            'total_interactions': total_interactions,
            'engagement_rate': engagement_rate,
            'ctr': (post.clicks / post.impressions * 100) if post.impressions > 0 else 0,
        }


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def publish_scheduled_posts():
    '''Publish scheduled social posts'''
    from apps.social.models import SocialPost
    
    posts = SocialPost.objects.filter(
        status='scheduled',
        scheduled_time__lte=timezone.now()
    )
    
    for post in posts:
        try:
            post_id = SocialMediaManager.post_to_social(post.account, post.content, post.image)
            
            if post_id:
                post.status = 'posted'
                post.platform_post_id = post_id
                post.posted_time = timezone.now()
            else:
                post.status = 'failed'
            
            post.save()
        except Exception as e:
            post.status = 'failed'
            post.save()
            logger.error(f'Failed to publish post {post.id}: {e}')

@shared_task
def sync_social_analytics():
    '''Sync analytics from all connected accounts'''
    from apps.social.models import SocialMediaAccount
    
    accounts = SocialMediaAccount.objects.filter(is_active=True)
    
    for account in accounts:
        SocialMediaManager.sync_analytics(account)

# Add to CELERY_BEAT_SCHEDULE:
'publish-scheduled-posts': {
    'task': 'apps.social.tasks.publish_scheduled_posts',
    'schedule': 300.0,  # Every 5 minutes
},
'sync-social-analytics': {
    'task': 'apps.social.tasks.sync_social_analytics',
    'schedule': 3600.0,  # Hourly
},
"""

# ============================================================
# SHARING UTILITIES
# ============================================================

class ShareGenerator:
    """Generate share URLs and buttons"""
    
    @staticmethod
    def get_facebook_share_url(url, quote=None):
        """Generate Facebook share URL"""
        params = f"u={url}"
        if quote:
            params += f"&quote={quote}"
        return f"https://www.facebook.com/sharer/sharer.php?{params}"
    
    @staticmethod
    def get_twitter_share_url(url, text=None, hashtags=None):
        """Generate Twitter share URL"""
        params = f"url={url}"
        if text:
            params += f"&text={text}"
        if hashtags:
            params += f"&hashtags={','.join(hashtags)}"
        return f"https://twitter.com/intent/tweet?{params}"
    
    @staticmethod
    def get_linkedin_share_url(url, title=None):
        """Generate LinkedIn share URL"""
        params = f"url={url}"
        if title:
            params += f"&title={title}"
        return f"https://www.linkedin.com/sharing/share-offsite/?{params}"
    
    @staticmethod
    def get_whatsapp_share_url(url, text=None):
        """Generate WhatsApp share URL"""
        params = f"text={text or url}"
        return f"https://wa.me/?{params}"