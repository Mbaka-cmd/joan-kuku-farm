# Advanced SEO & Performance Optimization System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('seo')

# ============================================================
# SEO MODELS
# ============================================================

class SEOMetadata(models.Model):
    """SEO metadata for content"""
    CONTENT_TYPE = [
        ('product', 'Product'),
        ('category', 'Category'),
        ('blog', 'Blog Post'),
        ('page', 'Page'),
    ]
    
    content_type = models.CharField(max_length=50, choices=CONTENT_TYPE)
    content_id = models.IntegerField()
    
    # Meta
    title = models.CharField(max_length=60)  # SEO title
    description = models.CharField(max_length=160)  # Meta description
    keywords = models.CharField(max_length=255, blank=True)
    
    # Slug
    slug = models.SlugField(unique=True)
    
    # Open Graph
    og_title = models.CharField(max_length=255, blank=True)
    og_description = models.CharField(max_length=255, blank=True)
    og_image = models.ImageField(upload_to='og_images/', null=True, blank=True)
    
    # Structured Data
    structured_data = models.JSONField(default=dict)
    
    # Canonical
    canonical_url = models.URLField(blank=True)
    
    # Robots
    index = models.BooleanField(default=True)
    follow = models.BooleanField(default=True)
    
    # Updated
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seo_metadata'
        unique_together = ['content_type', 'content_id']


class SEOPerformance(models.Model):
    """Track SEO performance"""
    metadata = models.OneToOneField(SEOMetadata, on_delete=models.CASCADE)
    
    # Rankings
    keyword = models.CharField(max_length=255)
    current_rank = models.IntegerField(null=True, blank=True)
    previous_rank = models.IntegerField(null=True, blank=True)
    
    # Metrics
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    ctr = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    
    # Authority
    domain_authority = models.IntegerField(null=True, blank=True)
    page_authority = models.IntegerField(null=True, blank=True)
    backlinks = models.IntegerField(default=0)
    
    # Traffic
    organic_traffic = models.IntegerField(default=0)
    organic_conversion = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seo_performance'


class PageSpeedMetric(models.Model):
    """Page speed and performance metrics"""
    page_url = models.CharField(max_length=500)
    
    # Core Web Vitals
    lcp = models.IntegerField()  # Largest Contentful Paint (ms)
    fid = models.IntegerField()  # First Input Delay (ms)
    cls = models.DecimalField(max_digits=4, decimal_places=2)  # Cumulative Layout Shift
    
    # Performance
    load_time = models.IntegerField()  # ms
    first_paint = models.IntegerField()  # ms
    first_contentful_paint = models.IntegerField()  # ms
    
    # Optimization
    page_size = models.IntegerField()  # KB
    requests = models.IntegerField()
    
    # Score
    performance_score = models.IntegerField()  # 0-100
    seo_score = models.IntegerField()  # 0-100
    accessibility_score = models.IntegerField()  # 0-100
    best_practices_score = models.IntegerField()  # 0-100
    
    tested_at = models.DateTimeField()
    
    class Meta:
        db_table = 'page_speed_metric'
        indexes = [
            models.Index(fields=['page_url', '-tested_at']),
        ]


class CacheStrategy(models.Model):
    """Cache strategy configuration"""
    CACHE_TYPE = [
        ('browser', 'Browser Cache'),
        ('cdn', 'CDN Cache'),
        ('server', 'Server Cache'),
        ('db', 'Database Cache'),
    ]
    
    path = models.CharField(max_length=500)
    cache_type = models.CharField(max_length=20, choices=CACHE_TYPE)
    
    # Duration
    ttl = models.IntegerField()  # seconds
    
    # Rules
    rules = models.JSONField(default=dict)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'cache_strategy'


# ============================================================
# SEO ENGINE
# ============================================================

class SEOEngine:
    """SEO operations"""
    
    @staticmethod
    def generate_sitemap():
        """Generate XML sitemap"""
        from apps.products.models import Product
        from apps.seo.models import SEOMetadata
        
        sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        
        # Products
        products = Product.objects.filter(is_active=True)
        
        for product in products:
            try:
                seo = SEOMetadata.objects.get(content_type='product', content_id=product.id)
                url = f"https://joankkfarm.com/product/{seo.slug}/"
            except:
                url = f"https://joankkfarm.com/product/{product.id}/"
            
            sitemap += f'  <url>\n'
            sitemap += f'    <loc>{url}</loc>\n'
            sitemap += f'    <lastmod>{product.updated_at.isoformat()}</lastmod>\n'
            sitemap += f'    <priority>0.8</priority>\n'
            sitemap += f'  </url>\n'
        
        sitemap += '</urlset>'
        
        return sitemap
    
    @staticmethod
    def optimize_product_seo(product):
        """Optimize product SEO"""
        from apps.seo.models import SEOMetadata
        
        seo, created = SEOMetadata.objects.get_or_create(
            content_type='product',
            content_id=product.id
        )
        
        # Generate title
        seo.title = f"{product.name} | Buy Online at Joan Kuku Farm"
        
        # Generate description
        seo.description = f"Buy {product.name}. High quality poultry products delivered to your door. Affordable prices, fast delivery."
        
        # Generate keywords
        seo.keywords = f"{product.name}, {product.category.name}, buy online, delivery"
        
        # Generate slug
        import re
        slug = re.sub(r'[^\w\s-]', '', product.name.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        seo.slug = slug
        
        # Structured data
        seo.structured_data = {
            '@context': 'https://schema.org',
            '@type': 'Product',
            'name': product.name,
            'description': product.description,
            'price': str(product.price),
            'priceCurrency': 'KES',
            'image': product.image_url,
            'rating': {
                '@type': 'AggregateRating',
                'ratingValue': str(product.rating or 0),
                'reviewCount': product.review_count,
            },
        }
        
        seo.save()
        
        logger.info(f'SEO optimized for product: {product.name}')
        
        return seo
    
    @staticmethod
    def test_page_speed(url):
        """Test page speed using PageSpeed Insights API"""
        import requests
        from apps.seo.models import PageSpeedMetric
        
        api_key = os.environ.get('GOOGLE_PAGESPEED_KEY')
        
        try:
            response = requests.get(
                f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params={
                    'url': url,
                    'key': api_key,
                }
            )
            
            data = response.json()
            
            core_web_vitals = data['lighthouseResult']['audits']['metrics']['details']['items'][0]
            
            metric = PageSpeedMetric.objects.create(
                page_url=url,
                lcp=int(core_web_vitals.get('largestContentfulPaint', 0)),
                fid=int(core_web_vitals.get('firstInputDelay', 0)),
                cls=float(core_web_vitals.get('cumulativeLayoutShift', 0)),
                load_time=int(core_web_vitals.get('speedIndex', 0)),
                performance_score=data['lighthouseResult']['categories']['performance']['score'] * 100,
                seo_score=data['lighthouseResult']['categories']['seo']['score'] * 100,
                accessibility_score=data['lighthouseResult']['categories']['accessibility']['score'] * 100,
                best_practices_score=data['lighthouseResult']['categories']['best-practices']['score'] * 100,
                tested_at=timezone.now(),
            )
            
            return metric
        
        except Exception as e:
            logger.error(f'Page speed test failed: {e}')
            return None
    
    @staticmethod
    def generate_robots_txt():
        """Generate robots.txt"""
        robots = "User-agent: *\n"
        robots += "Allow: /\n"
        robots += "Disallow: /admin/\n"
        robots += "Disallow: /api/\n"
        robots += "Disallow: /search/\n"
        robots += "\n"
        robots += "Sitemap: https://joankkfarm.com/sitemap.xml\n"
        
        return robots


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def optimize_all_seo():
    '''Optimize SEO for all products'''
    from apps.products.models import Product
    
    products = Product.objects.filter(is_active=True)
    
    for product in products:
        SEOEngine.optimize_product_seo(product)

@shared_task
def test_page_speeds():
    '''Test page speeds for key pages'''
    urls = [
        'https://joankkfarm.com/',
        'https://joankkfarm.com/products/',
    ]
    
    for url in urls:
        SEOEngine.test_page_speed(url)

# Add to CELERY_BEAT_SCHEDULE:
'optimize-seo': {
    'task': 'apps.seo.tasks.optimize_all_seo',
    'schedule': 604800.0,  # Weekly
},
'test-speeds': {
    'task': 'apps.seo.tasks.test_page_speeds',
    'schedule': 604800.0,  # Weekly
},
"""