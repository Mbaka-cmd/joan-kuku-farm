# Video Management & Streaming Platform

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('video')

# ============================================================
# VIDEO MODELS
# ============================================================

class Video(models.Model):
    """Video management"""
    STATUS_CHOICES = [
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]
    
    # Video
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    
    # File
    video_file = models.FileField(upload_to='videos/%Y/%m/')
    duration = models.IntegerField(null=True, blank=True)  # seconds
    
    # Thumbnail
    thumbnail = models.ImageField(upload_to='video_thumbnails/', null=True, blank=True)
    
    # Streaming
    hls_url = models.URLField(blank=True)  # For HLS streaming
    dash_url = models.URLField(blank=True)  # For DASH streaming
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    
    # Stats
    views = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    
    # Owner
    owner = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Accessibility
    is_public = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'video'
        ordering = ['-created_at']


class VideoQuality(models.Model):
    """Video quality variants"""
    QUALITY_CHOICES = [
        ('360p', '360p'),
        ('480p', '480p'),
        ('720p', '720p'),
        ('1080p', '1080p'),
        ('4k', '4K'),
    ]
    
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    
    quality = models.CharField(max_length=10, choices=QUALITY_CHOICES)
    
    # File
    file_url = models.URLField()
    bitrate = models.IntegerField()  # kbps
    file_size = models.IntegerField()  # MB
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'video_quality'
        unique_together = ['video', 'quality']


class VideoAnalytics(models.Model):
    """Video analytics"""
    video = models.OneToOneField(Video, on_delete=models.CASCADE)
    
    # Engagement
    total_views = models.IntegerField(default=0)
    unique_viewers = models.IntegerField(default=0)
    avg_watch_time = models.IntegerField(default=0)  # seconds
    
    # Quality
    most_watched_quality = models.CharField(max_length=10, blank=True)
    
    # Device
    mobile_views = models.IntegerField(default=0)
    desktop_views = models.IntegerField(default=0)
    
    # Geography
    top_countries = models.JSONField(default=dict)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'video_analytics'


class VideoPlaylist(models.Model):
    """Video playlists"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    owner = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Videos
    videos = models.ManyToManyField(Video, through='PlaylistVideo')
    
    is_public = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'video_playlist'


class PlaylistVideo(models.Model):
    """Videos in playlist"""
    playlist = models.ForeignKey(VideoPlaylist, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    
    order = models.IntegerField()
    
    class Meta:
        db_table = 'playlist_video'
        unique_together = ['playlist', 'video']


class VideoSubtitle(models.Model):
    """Video subtitles/captions"""
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('sw', 'Swahili'),
    ]
    
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    
    # File
    vtt_file = models.FileField(upload_to='subtitles/')
    
    is_auto_generated = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'video_subtitle'
        unique_together = ['video', 'language']


# ============================================================
# VIDEO ENGINE
# ============================================================

class VideoEngine:
    """Video operations"""
    
    @staticmethod
    def process_video(video_id):
        """Process uploaded video"""
        from apps.video.models import Video, VideoQuality
        import subprocess
        
        video = Video.objects.get(id=video_id)
        
        video.status = 'processing'
        video.save()
        
        try:
            # Get video info
            duration = VideoEngine.get_video_duration(video.video_file.path)
            video.duration = duration
            
            # Generate thumbnail
            VideoEngine.generate_thumbnail(video)
            
            # Encode variants
            qualities = ['360p', '480p', '720p', '1080p']
            
            for quality in qualities:
                VideoEngine.encode_quality(video, quality)
            
            # Generate HLS streams
            VideoEngine.generate_hls_stream(video)
            
            video.status = 'ready'
            logger.info(f'Video processed: {video.title}')
        
        except Exception as e:
            video.status = 'failed'
            logger.error(f'Video processing failed: {e}')
        
        video.save()
    
    @staticmethod
    def get_video_duration(file_path):
        """Get video duration"""
        import subprocess
        
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1:noprint_sections=1', file_path],
                capture_output=True,
                text=True
            )
            
            return int(float(result.stdout.strip()))
        
        except Exception as e:
            logger.error(f'Duration detection failed: {e}')
            return 0
    
    @staticmethod
    def generate_thumbnail(video):
        """Generate video thumbnail"""
        import subprocess
        from PIL import Image
        import os
        
        try:
            # Extract frame at 5 seconds
            thumbnail_path = f'/tmp/thumb_{video.id}.jpg'
            
            subprocess.run([
                'ffmpeg', '-i', video.video_file.path,
                '-ss', '00:00:05',
                '-vframes', '1',
                '-vf', 'scale=320:-1',
                thumbnail_path
            ], capture_output=True)
            
            # Save thumbnail
            with open(thumbnail_path, 'rb') as f:
                video.thumbnail.save(f'thumb_{video.id}.jpg', f)
            
            os.remove(thumbnail_path)
        
        except Exception as e:
            logger.error(f'Thumbnail generation failed: {e}')
    
    @staticmethod
    def encode_quality(video, quality):
        """Encode video to specific quality"""
        from apps.video.models import VideoQuality
        
        quality_settings = {
            '360p': {'bitrate': '500k', 'scale': '640:360'},
            '480p': {'bitrate': '1500k', 'scale': '854:480'},
            '720p': {'bitrate': '3000k', 'scale': '1280:720'},
            '1080p': {'bitrate': '5000k', 'scale': '1920:1080'},
        }
        
        settings = quality_settings.get(quality)
        
        try:
            output_file = f'/tmp/{video.id}_{quality}.mp4'
            
            # This would encode using FFmpeg
            logger.info(f'Encoding {quality} for video: {video.title}')
            
            # Create quality record
            VideoQuality.objects.create(
                video=video,
                quality=quality,
                file_url=f'/media/videos/{video.id}/{quality}.mp4',
                bitrate=int(settings['bitrate'].rstrip('k')),
                file_size=100,  # placeholder
            )
        
        except Exception as e:
            logger.error(f'Encoding failed: {e}')
    
    @staticmethod
    def generate_hls_stream(video):
        """Generate HLS stream for adaptive bitrate"""
        try:
            logger.info(f'Generating HLS stream for: {video.title}')
            
            video.hls_url = f'/media/videos/{video.id}/stream.m3u8'
            video.save()
        
        except Exception as e:
            logger.error(f'HLS generation failed: {e}')
    
    @staticmethod
    def track_view(video, user=None, watch_time=0):
        """Track video view"""
        from apps.video.models import VideoAnalytics
        
        video.views += 1
        video.save()
        
        try:
            analytics = VideoAnalytics.objects.get(video=video)
            analytics.total_views += 1
            analytics.avg_watch_time = (analytics.avg_watch_time + watch_time) // 2
            analytics.save()
        except:
            pass


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def process_uploaded_video(video_id):
    '''Process uploaded video'''
    VideoEngine.process_video(video_id)

@shared_task
def cleanup_processed_videos():
    '''Clean up temporary video files'''
    import os
    import shutil
    
    tmp_dir = '/tmp/'
    for file in os.listdir(tmp_dir):
        if file.startswith('thumb_') or file.endswith('.mp4'):
            try:
                os.remove(os.path.join(tmp_dir, file))
            except:
                pass

# Add to CELERY_BEAT_SCHEDULE:
'cleanup-videos': {
    'task': 'apps.video.tasks.cleanup_processed_videos',
    'schedule': 86400.0,  # Daily
},
"""