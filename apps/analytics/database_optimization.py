# Database Optimization & Indexing Guide

from django.db import models, connection
from django.db.models import Index, F
import logging

logger = logging.getLogger('database')

# ============================================================
# OPTIMIZED MODELS WITH INDEXES
# ============================================================

class OptimizedModels:
    """Models with proper indexing"""
    
    """
    Example: Product Model with Indexes
    
    class Product(models.Model):
        # Fields
        name = models.CharField(max_length=255, db_index=True)
        sku = models.CharField(max_length=50, db_index=True, unique=True)
        category = models.ForeignKey(Category, db_index=True)
        price = models.DecimalField(max_digits=10, decimal_places=2)
        stock = models.IntegerField(db_index=True)
        is_active = models.BooleanField(db_index=True, default=True)
        is_featured = models.BooleanField(db_index=True, default=False)
        created_at = models.DateTimeField(auto_now_add=True, db_index=True)
        updated_at = models.DateTimeField(auto_now=True)
        
        class Meta:
            db_table = 'products'
            indexes = [
                # Single column indexes
                Index(fields=['name']),
                Index(fields=['sku']),
                Index(fields=['category']),
                Index(fields=['-created_at']),  # Descending
                
                # Composite indexes (search frequent combinations)
                Index(fields=['category', 'is_active']),
                Index(fields=['is_featured', '-created_at']),
                Index(fields=['name', 'category']),
                
                # Conditional indexes (for filtered queries)
                Index(
                    fields=['created_at'],
                    condition=Q(is_active=True),
                    name='idx_active_products_created'
                ),
            ]
    """
    pass


# ============================================================
# INDEX STRATEGIES
# ============================================================

class IndexStrategies:
    """Index optimization strategies"""
    
    @staticmethod
    def single_column_index():
        """Index frequently filtered columns"""
        """
        CREATE INDEX idx_product_name ON products(name);
        CREATE INDEX idx_product_sku ON products(sku);
        CREATE INDEX idx_product_category ON products(category_id);
        CREATE INDEX idx_order_status ON orders(status);
        CREATE INDEX idx_order_created ON orders(created_at);
        """
        pass
    
    @staticmethod
    def composite_index():
        """Index for queries filtering on multiple columns"""
        """
        For query: SELECT * FROM products 
        WHERE category_id = 1 AND is_active = true
        
        CREATE INDEX idx_product_category_active 
        ON products(category_id, is_active);
        
        Order matters! Put most selective column first.
        """
        pass
    
    @staticmethod
    def partial_index():
        """Index only subset of rows"""
        """
        For query: SELECT * FROM products 
        WHERE is_active = true AND created_at > NOW() - INTERVAL '30 days'
        
        CREATE INDEX idx_active_recent_products 
        ON products(created_at) 
        WHERE is_active = true;
        
        Benefits:
        - Smaller index
        - Faster writes
        - Faster lookups
        """
        pass
    
    @staticmethod
    def unique_index():
        """Enforce uniqueness"""
        """
        CREATE UNIQUE INDEX idx_product_sku_unique ON products(sku);
        
        Or in Django:
        class Product(models.Model):
            sku = models.CharField(max_length=50, unique=True)
        """
        pass
    
    @staticmethod
    def full_text_search_index():
        """Index for text search"""
        """
        CREATE INDEX idx_product_search 
        ON products USING GIN(to_tsvector('english', name || ' ' || description));
        
        Query:
        SELECT * FROM products 
        WHERE to_tsvector('english', name || ' ' || description) 
        @@ plainto_tsquery('english', 'search term');
        """
        pass
    
    @staticmethod
    def expression_index():
        """Index on expression"""
        """
        For query: WHERE UPPER(name) = 'PRODUCT NAME'
        
        CREATE INDEX idx_product_name_upper ON products(UPPER(name));
        
        Or in Django:
        from django.db.models import F
        from django.db.models.functions import Upper
        
        Index(
            fields=[Upper('name')],
            name='idx_product_name_upper'
        )
        """
        pass
    
    @staticmethod
    def multi_column_where():
        """Covering index for better performance"""
        """
        For query: SELECT id, name, price FROM products 
        WHERE category_id = 1 AND is_active = true
        
        CREATE INDEX idx_product_covering 
        ON products(category_id, is_active) 
        INCLUDE (id, name, price);
        
        Index covers entire query (no table lookup needed)
        """
        pass


# ============================================================
# QUERY ANALYSIS & OPTIMIZATION
# ============================================================

class QueryAnalysis:
    """Analyze and optimize queries"""
    
    @staticmethod
    def explain_query():
        """Analyze query execution plan"""
        """
        EXPLAIN ANALYZE
        SELECT p.id, p.name, c.category 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = true
        ORDER BY p.created_at DESC
        LIMIT 20;
        
        Look for:
        - Sequential Scan (bad, use index)
        - Index Scan (good)
        - Join type efficiency
        - Row estimates vs actual
        """
        pass
    
    @staticmethod
    def find_slow_queries():
        """Find slow running queries"""
        """
        Enable query logging:
        
        log_min_duration_statement = 1000  # Log queries > 1 second
        log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
        
        Then analyze slow-query.log for patterns
        """
        pass
    
    @staticmethod
    def analyze_table_stats():
        """Update table statistics"""
        """
        ANALYZE table_name;
        
        This updates row counts and distribution stats
        used by query planner
        
        Run after large data changes
        """
        pass
    
    @staticmethod
    def find_unused_indexes():
        """Find indexes not being used"""
        """
        SELECT schemaname, tablename, indexname, idx_scan
        FROM pg_stat_user_indexes
        WHERE idx_scan = 0
        ORDER BY pg_relation_size(indexrelid) DESC;
        
        Drop unused indexes:
        DROP INDEX CONCURRENTLY idx_name;
        """
        pass
    
    @staticmethod
    def find_missing_indexes():
        """Identify missing indexes"""
        """
        Query pg_stat_user_tables for sequential scans:
        
        SELECT schemaname, tablename, seq_scan, seq_tup_read, idx_scan
        FROM pg_stat_user_tables
        WHERE seq_scan - idx_scan > 0
        ORDER BY seq_tup_read DESC;
        
        High sequential scans = missing index opportunity
        """
        pass


# ============================================================
# TABLE OPTIMIZATION
# ============================================================

class TableOptimization:
    """Optimize table structure"""
    
    @staticmethod
    def vacuum_and_analyze():
        """Clean up and analyze tables"""
        """
        VACUUM ANALYZE products;
        
        VACUUM:
        - Removes dead rows
        - Reclaims space
        - Updates visibility map
        
        ANALYZE:
        - Updates statistics
        - Helps query planner
        
        Regular maintenance:
        autovacuum = on
        autovacuum_naptime = '1min'
        """
        pass
    
    @staticmethod
    def partition_large_tables():
        """Partition tables for performance"""
        """
        Partition orders by date:
        
        CREATE TABLE orders_2024 PARTITION OF orders
        FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
        
        Benefits:
        - Faster queries
        - Easier maintenance
        - Parallel queries
        """
        pass
    
    @staticmethod
    def denormalization_strategy():
        """Strategically denormalize for performance"""
        """
        Instead of:
        SELECT o.id, o.total, c.name, c.email
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        
        Store denormalized data:
        ALTER TABLE orders ADD COLUMN customer_name VARCHAR(255);
        ALTER TABLE orders ADD COLUMN customer_email VARCHAR(255);
        
        Tradeoff: Faster reads, slower writes, storage overhead
        """
        pass


# ============================================================
# CONNECTION POOLING
# ============================================================

class ConnectionPooling:
    """Optimize database connections"""
    
    """
    Use pgBouncer for connection pooling:
    
    # pgbouncer.ini
    [databases]
    mydb = host=localhost port=5432 dbname=mydb
    
    [pgbouncer]
    pool_mode = transaction
    max_client_conn = 1000
    default_pool_size = 25
    
    Django settings:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': 'localhost',  # pgBouncer
            'PORT': 6432,  # pgBouncer port
            'CONN_MAX_AGE': 600,
            'OPTIONS': {
                'connect_timeout': 10,
                'options': '-c default_transaction_isolation=read_committed'
            }
        }
    }
    """
    pass


# ============================================================
# BACKUP & RECOVERY
# ============================================================

class BackupRecovery:
    """Backup and recovery strategies"""
    
    @staticmethod
    def full_backup():
        """Create full database backup"""
        """
        pg_dump -U postgres -h localhost mydb > backup.sql
        
        Or binary format:
        pg_dump -Fc -U postgres -h localhost mydb > backup.dump
        """
        pass
    
    @staticmethod
    def continuous_archiving():
        """Setup WAL archiving for PITR"""
        """
        postgresql.conf:
        
        wal_level = replica
        archive_mode = on
        archive_command = 'cp %p /backup/wal_archive/%f'
        archive_timeout = 300
        
        Recovery:
        restore_command = 'cp /backup/wal_archive/%f %p'
        """
        pass
    
    @staticmethod
    def restore_from_backup():
        """Restore database from backup"""
        """
        psql -U postgres -h localhost mydb < backup.sql
        
        Or from binary backup:
        pg_restore -d mydb backup.dump
        """
        pass


# ============================================================
# MONITORING & MAINTENANCE
# ============================================================

class DatabaseMonitoring:
    """Monitor database health"""
    
    @staticmethod
    def monitor_table_size():
        """Monitor table sizes"""
        """
        SELECT schemaname, tablename, 
               pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
        FROM pg_tables
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
        """
        pass
    
    @staticmethod
    def monitor_index_size():
        """Monitor index sizes"""
        """
        SELECT schemaname, tablename, indexname,
               pg_size_pretty(pg_relation_size(indexrelid)) AS size
        FROM pg_stat_user_indexes
        ORDER BY pg_relation_size(indexrelid) DESC;
        """
        pass
    
    @staticmethod
    def monitor_cache_hit_ratio():
        """Monitor cache effectiveness"""
        """
        SELECT 
            sum(heap_blks_read) as heap_read, 
            sum(heap_blks_hit) as heap_hit, 
            sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
        FROM pg_statio_user_tables;
        
        Ratio should be > 0.99 (99% of blocks in cache)
        """
        pass
    
    @staticmethod
    def monitor_connections():
        """Monitor active connections"""
        """
        SELECT datname, usename, count(*) 
        FROM pg_stat_activity 
        GROUP BY datname, usename;
        
        Check for:
        - Idle connections
        - Long-running queries
        - Connection leaks
        """
        pass
    
    @staticmethod
    def monitor_locks():
        """Monitor database locks"""
        """
        SELECT pid, usename, pg_blocking_pids(pid) as blocked_by,
               query as blocked_query
        FROM pg_stat_activity
        WHERE pg_blocking_pids(pid)::text != '{}';
        
        Identify:
        - Blocking queries
        - Long locks
        - Deadlocks
        """
        pass


# ============================================================
# DJANGO ORM OPTIMIZATION
# ============================================================

class DjangoORMOptimization:
    """Optimize Django ORM usage"""
    
    @staticmethod
    def use_select_related():
        """Reduce queries with select_related"""
        """
        from apps.orders.models import Order
        
        # Bad: N+1 queries
        orders = Order.objects.all()
        for order in orders:
            print(order.customer.name)
        
        # Good: 1 query with JOIN
        orders = Order.objects.select_related('customer')
        """
        pass
    
    @staticmethod
    def use_prefetch_related():
        """Optimize reverse relations with prefetch_related"""
        """
        # Bad: Multiple queries
        customers = Customer.objects.all()
        for customer in customers:
            orders = customer.order_set.all()
        
        # Good: 2 queries total
        from django.db.models import Prefetch
        customers = Customer.objects.prefetch_related('order_set')
        """
        pass
    
    @staticmethod
    def use_only_and_defer():
        """Load only needed fields"""
        """
        # Load specific fields
        products = Product.objects.only('id', 'name', 'price')
        
        # Defer large fields
        products = Product.objects.defer('description', 'image')
        """
        pass
    
    @staticmethod
    def use_aggregate():
        """Use database aggregation"""
        """
        from django.db.models import Sum, Avg, Count
        
        # Bad: Load all and calculate in Python
        total = sum(order.total_amount for order in Order.objects.all())
        
        # Good: Calculate in database
        total = Order.objects.aggregate(
            total=Sum('total_amount')
        )['total']
        """
        pass
    
    @staticmethod
    def use_values_list():
        """Return simple values instead of objects"""
        """
        # Returns dictionaries (lighter)
        products = Product.objects.values('id', 'name', 'price')
        
        # Returns tuples (lightest)
        products = Product.objects.values_list('id', 'name', 'price')
        """
        pass
    
    @staticmethod
    def batch_operations():
        """Batch database operations"""
        """
        # Bad: Multiple saves
        for product in products:
            product.stock -= 1
            product.save()
        
        # Good: Single update
        Product.objects.filter(stock__gt=0).update(stock=F('stock') - 1)
        
        # Good: Bulk create
        Product.objects.bulk_create(products_list)
        """
        pass


# ============================================================
# DATABASE OPTIMIZATION CHECKLIST
# ============================================================

"""
DATABASE OPTIMIZATION CHECKLIST:

Indexing:
☐ Add indexes to frequently filtered columns
☐ Use composite indexes for multi-column filters
☐ Add partial indexes for conditional queries
☐ Remove unused indexes
☐ Check index size
☐ Monitor index fragmentation

Query Optimization:
☐ Use select_related for FK relationships
☐ Use prefetch_related for reverse relations
☐ Use only() and defer() for large fields
☐ Use values() and values_list() where possible
☐ Use aggregate() in database
☐ Batch write operations
☐ EXPLAIN ANALYZE slow queries

Table Structure:
☐ Normalize data appropriately
☐ Use correct column types
☐ Set NOT NULL where applicable
☐ Use constraints properly
☐ Regular VACUUM ANALYZE
☐ Monitor table sizes

Connection & Performance:
☐ Use connection pooling (pgBouncer)
☐ Set connection timeout
☐ Monitor active connections
☐ Check cache hit ratio (target > 99%)
☐ Monitor slow queries
☐ Monitor locks and deadlocks

Maintenance:
☐ Regular backups
☐ Enable WAL archiving
☐ Monitor disk space
☐ Update statistics
☐ Rebuild indexes periodically
☐ Archive old data
"""