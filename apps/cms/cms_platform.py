# Content Management System (CMS) Platform

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('cms')

# ============================================================
# CMS MODELS
# ============================================================

class BlogPost(models.Model):
    """Blog posts"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    # Content
    title = models.CharField(max_length=500)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    excerpt = models.CharField(max_length=500, blank=True)
    
    # Image
    featured_image = models.ImageField(upload_to='blog_images/%Y/%m/')
    
    # Author
    author = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    # Categories
    category = models.CharField(max_length=100)
    tags = models.JSONField(default=list)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # SEO
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=255, blank=True)
    
    # Stats
    views = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    
    # Dates
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'blog_post'
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['status', '-published_at']),
        ]


class Page(models.Model):
    """Static pages"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]
    
    title = models.CharField(max_length=500)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    
    # Template
    template = models.CharField(max_length=100, default='default')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Parent (for hierarchy)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    
    # Display
    show_in_menu = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'page'
        ordering = ['order']


class BlogComment(models.Model):
    """Blog comments"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    
    # Author
    author = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.CASCADE)
    author_name = models.CharField(max_length=255)
    author_email = models.EmailField()
    
    # Comment
    content = models.TextField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Threading
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    
    # Spam
    is_spam = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'blog_comment'
        ordering = ['created_at']


class MediaLibrary(models.Model):
    """Media management"""
    FILE_TYPE = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('audio', 'Audio'),
    ]
    
    title = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE)
    
    # File
    file = models.FileField(upload_to='media/%Y/%m/')
    
    # Image specific
    is_image = models.BooleanField(default=False)
    image_width = models.IntegerField(null=True, blank=True)
    image_height = models.IntegerField(null=True, blank=True)
    
    # Metadata
    alt_text = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    
    # Usage
    used_in = models.JSONField(default=list)  # Posts using this media
    
    uploaded_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'media_library'
        ordering = ['-created_at']


class ContentBlock(models.Model):
    """Reusable content blocks"""
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    
    # Template
    template = models.CharField(max_length=100, blank=True)
    
    # Used in pages
    pages = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'content_block'


# ============================================================
# CMS ENGINE
# ============================================================

class CMSEngine:
    """Content management operations"""
    
    @staticmethod
    def publish_post(post):
        """Publish blog post"""
        post.status = 'published'
        post.published_at = timezone.now()
        post.save()
        
        logger.info(f'Post published: {post.title}')
        
        return post
    
    @staticmethod
    def approve_comment(comment):
        """Approve blog comment"""
        comment.status = 'approved'
        comment.save()
        
        # Send notification to post author
        logger.info(f'Comment approved on: {comment.post.title}')
    
    @staticmethod
    def detect_spam(comment):
        """Detect spam comments"""
        # Simple spam detection
        spam_words = ['viagra', 'casino', 'lottery', 'click here']
        
        content = comment.content.lower()
        
        for word in spam_words:
            if word in content:
                return True
        
        # Check for excessive links
        link_count = content.count('http')
        if link_count > 3:
            return True
        
        return False
    
    @staticmethod
    def get_blog_sidebar():
        """Get blog sidebar data"""
        from apps.cms.models import BlogPost
        
        recent_posts = BlogPost.objects.filter(
            status='published'
        ).order_by('-published_at')[:5]
        
        # Tags
        all_posts = BlogPost.objects.filter(status='published')
        tags = {}
        
        for post in all_posts:
            for tag in post.tags:
                tags[tag] = tags.get(tag, 0) + 1
        
        return {
            'recent_posts': recent_posts,
            'tags': sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10],
        }
    
    @staticmethod
    def render_post(post):
        """Render blog post with formatting"""
        import markdown
        
        # Convert markdown to HTML
        html_content = markdown.markdown(post.content)
        
        return html_content
    
    @staticmethod
    def get_reading_time(content):
        """Estimate reading time"""
        words = len(content.split())
        reading_time = max(1, words // 200)  # 200 words per minute
        
        return reading_time


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def moderate_pending_comments():
    '''Moderate pending comments'''
    from apps.cms.models import BlogComment, CMSEngine
    
    pending = BlogComment.objects.filter(status='pending')
    
    for comment in pending:
        if CMSEngine.detect_spam(comment):
            comment.is_spam = True
            comment.status = 'rejected'
        else:
            CMSEngine.approve_comment(comment)
        
        comment.save()

@shared_task
def cleanup_old_drafts():
    '''Delete old draft posts'''
    from apps.cms.models import BlogPost
    
    cutoff = timezone.now() - timedelta(days=90)
    
    BlogPost.objects.filter(
        status='draft',
        updated_at__lt=cutoff
    ).delete()

# Add to CELERY_BEAT_SCHEDULE:
'moderate-comments': {
    'task': 'apps.cms.tasks.moderate_pending_comments',
    'schedule': 3600.0,  # Hourly
},
'cleanup-drafts': {
    'task': 'apps.cms.tasks.cleanup_old_drafts',
    'schedule': 604800.0,  # Weekly
},
"""