# Video & Media Processing System

import os
from django.db import models
from django.core.files.storage import default_storage
import logging

logger = logging.getLogger('media')

# ============================================================
# MEDIA MODELS
# ============================================================

class MediaAsset(models.Model):
    """Store media assets"""
    TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('audio', 'Audio'),
    ]
    
    STATUS_CHOICES = [
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]
    
    # Basic info
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    asset_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # File
    original_file = models.FileField(upload_to='media/%Y/%m/%d/')
    file_size = models.BigIntegerField()  # In bytes
    file_hash = models.CharField(max_length=64, unique=True)  # SHA256
    
    # Processing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    processing_started = models.DateTimeField(null=True, blank=True)
    processing_completed = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    duration = models.IntegerField(null=True, blank=True)  # For videos, in seconds
    width = models.IntegerField(null=True, blank=True)  # For images/videos
    height = models.IntegerField(null=True, blank=True)  # For images/videos
    
    # CDN
    cdn_url = models.URLField(blank=True)
    cdn_key = models.CharField(max_length=255, blank=True)
    
    # Tracking
    uploaded_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'media_asset'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['asset_type', 'status']),
            models.Index(fields=['created_at']),
        ]


class ProcessedMedia(models.Model):
    """Processed versions of media"""
    original = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name='processed')
    
    # Format
    format_type = models.CharField(max_length=20)  # webp, mp4, thumbnail, etc
    quality = models.CharField(max_length=20, default='high')  # low, medium, high
    
    # File
    processed_file = models.FileField(upload_to='media/processed/%Y/%m/%d/')
    file_size = models.BigIntegerField()
    
    # CDN
    cdn_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'processed_media'
        unique_together = ['original', 'format_type', 'quality']


class ImageVariant(models.Model):
    """Image variants (thumbnails, different sizes)"""
    original = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name='variants')
    
    # Size
    width = models.IntegerField()
    height = models.IntegerField()
    name = models.CharField(max_length=50)  # thumbnail, medium, large, etc
    
    # File
    file = models.ImageField(upload_to='media/variants/%Y/%m/%d/')
    cdn_url = models.URLField(blank=True)
    
    class Meta:
        db_table = 'image_variant'
        unique_together = ['original', 'name']


# ============================================================
# MEDIA PROCESSING ENGINE
# ============================================================

class MediaProcessor:
    """Process media files"""
    
    @staticmethod
    def calculate_file_hash(file):
        """Calculate SHA256 hash of file"""
        import hashlib
        
        file.seek(0)
        hash_sha256 = hashlib.sha256()
        
        for chunk in file.chunks():
            hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    @staticmethod
    def process_image(media_asset):
        """Process image"""
        from PIL import Image
        import io
        
        try:
            # Open image
            img = Image.open(media_asset.original_file)
            
            # Store dimensions
            media_asset.width = img.width
            media_asset.height = img.height
            
            # Create variants
            variants = [
                {'name': 'thumbnail', 'size': (150, 150)},
                {'name': 'medium', 'size': (500, 500)},
                {'name': 'large', 'size': (1000, 1000)},
            ]
            
            for variant in variants:
                img_copy = img.copy()
                img_copy.thumbnail(variant['size'], Image.Resampling.LANCZOS)
                
                # Save to buffer
                buffer = io.BytesIO()
                img_copy.save(buffer, format='WebP', quality=85)
                buffer.seek(0)
                
                # Create variant
                from django.core.files.base import ContentFile
                ImageVariant.objects.create(
                    original=media_asset,
                    width=img_copy.width,
                    height=img_copy.height,
                    name=variant['name'],
                    file=ContentFile(buffer.read(), name=f"{media_asset.id}_{variant['name']}.webp")
                )
            
            # Convert to WebP
            buffer = io.BytesIO()
            img.save(buffer, format='WebP', quality=90)
            buffer.seek(0)
            
            ProcessedMedia.objects.create(
                original=media_asset,
                format_type='webp',
                quality='high',
                processed_file=ContentFile(buffer.read(), name=f"{media_asset.id}.webp"),
                file_size=buffer.tell()
            )
            
            media_asset.status = 'ready'
            logger.info(f'Image processed: {media_asset.id}')
            
        except Exception as e:
            media_asset.status = 'failed'
            logger.error(f'Image processing failed: {e}')
    
    @staticmethod
    def process_video(media_asset):
        """Process video using FFmpeg"""
        import subprocess
        
        try:
            # Get video info
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_format', '-show_streams',
                '-of', 'json',
                str(media_asset.original_file.path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            info = json.loads(result.stdout)
            
            # Store duration and dimensions
            stream = info['streams'][0]
            media_asset.duration = int(float(info['format']['duration']))
            media_asset.width = stream.get('width')
            media_asset.height = stream.get('height')
            
            # Create MP4 version
            output_path = f"/tmp/{media_asset.id}.mp4"
            cmd = [
                'ffmpeg', '-i', str(media_asset.original_file.path),
                '-c:v', 'libx264', '-crf', '23',
                '-c:a', 'aac', '-b:a', '128k',
                '-movflags', 'faststart',
                output_path
            ]
            
            subprocess.run(cmd, check=True)
            
            # Save processed video
            with open(output_path, 'rb') as f:
                ProcessedMedia.objects.create(
                    original=media_asset,
                    format_type='mp4',
                    quality='high',
                    processed_file=ContentFile(f.read(), name=f"{media_asset.id}.mp4"),
                    file_size=os.path.getsize(output_path)
                )
            
            # Create thumbnail
            thumbnail_path = f"/tmp/{media_asset.id}_thumb.jpg"
            cmd = [
                'ffmpeg', '-i', str(media_asset.original_file.path),
                '-ss', '00:00:05', '-vframes', '1',
                thumbnail_path
            ]
            
            subprocess.run(cmd, check=True)
            
            media_asset.status = 'ready'
            logger.info(f'Video processed: {media_asset.id}')
            
        except Exception as e:
            media_asset.status = 'failed'
            logger.error(f'Video processing failed: {e}')


# ============================================================
# CDN INTEGRATION
# ============================================================

class CDNManager:
    """Manage CDN uploads"""
    
    @staticmethod
    def upload_to_cdn(media_asset):
        """Upload media to CDN"""
        import boto3
        from django.conf import settings
        
        if not settings.AWS_STORAGE_BUCKET_NAME:
            return
        
        try:
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
            
            # Upload original
            key = f"media/{media_asset.id}/{media_asset.original_file.name}"
            s3.upload_file(
                media_asset.original_file.path,
                settings.AWS_STORAGE_BUCKET_NAME,
                key,
                ExtraArgs={
                    'ContentType': media_asset.original_file.content_type,
                    'CacheControl': 'max-age=31536000',
                }
            )
            
            media_asset.cdn_key = key
            media_asset.cdn_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{key}"
            media_asset.save()
            
            # Upload processed versions
            for processed in media_asset.processed.all():
                key = f"media/{media_asset.id}/processed/{processed.format_type}/{processed.processed_file.name}"
                s3.upload_file(
                    processed.processed_file.path,
                    settings.AWS_STORAGE_BUCKET_NAME,
                    key,
                )
                
                processed.cdn_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{key}"
                processed.save()
            
            logger.info(f'Uploaded to CDN: {media_asset.id}')
            
        except Exception as e:
            logger.error(f'CDN upload failed: {e}')
    
    @staticmethod
    def delete_from_cdn(media_asset):
        """Delete media from CDN"""
        import boto3
        from django.conf import settings
        
        try:
            s3 = boto3.client('s3')
            
            # Delete original
            if media_asset.cdn_key:
                s3.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=media_asset.cdn_key
                )
            
            # Delete processed versions
            for processed in media_asset.processed.all():
                s3.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=processed.cdn_url.split('/')[-1]
                )
            
            logger.info(f'Deleted from CDN: {media_asset.id}')
            
        except Exception as e:
            logger.error(f'CDN deletion failed: {e}')


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def process_media_task(media_id):
    '''Process uploaded media'''
    from apps.media.models import MediaAsset
    
    media = MediaAsset.objects.get(id=media_id)
    
    if media.asset_type == 'image':
        MediaProcessor.process_image(media)
    elif media.asset_type == 'video':
        MediaProcessor.process_video(media)
    
    media.save()
    
    # Upload to CDN
    CDNManager.upload_to_cdn(media)

@shared_task
def cleanup_old_media():
    '''Delete old unused media'''
    from apps.media.models import MediaAsset
    from datetime import timedelta
    from django.utils import timezone
    
    cutoff = timezone.now() - timedelta(days=90)
    old_media = MediaAsset.objects.filter(created_at__lt=cutoff)
    
    for media in old_media:
        CDNManager.delete_from_cdn(media)
        media.delete()

# Add to CELERY_BEAT_SCHEDULE:
'cleanup-media': {
    'task': 'apps.media.tasks.cleanup_old_media',
    'schedule': 604800.0,  # Weekly
},
"""

# ============================================================
# SETTINGS.PY ADDITIONS
# ============================================================

"""
Add to requirements.txt:
Pillow==10.0.0
boto3==1.28.0
ffmpeg-python==0.2.1

Add to settings.py:

# AWS S3 / CloudFront
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

# Media Processing
MEDIA_PROCESSING = {
    'MAX_FILE_SIZE': 5 * 1024 * 1024 * 1024,  # 5GB
    'ALLOWED_IMAGE_TYPES': ['image/jpeg', 'image/png', 'image/webp'],
    'ALLOWED_VIDEO_TYPES': ['video/mp4', 'video/quicktime'],
}

# FFmpeg
FFMPEG_BINARY = '/usr/bin/ffmpeg'
FFPROBE_BINARY = '/usr/bin/ffprobe'
"""