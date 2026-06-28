# apps/core/management/commands/seed_database.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
import random

from apps.products.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate database with test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of test users to create'
        )
        parser.add_argument(
            '--orders',
            type=int,
            default=20,
            help='Number of test orders to create'
        )

    def handle(self, *args, **options):
        self.stdout.write('🌱 Seeding database...\n')

        # Create categories
        self.create_categories()
        
        # Create products
        self.create_products()
        
        # Create test users
        self.create_users(options['users'])
        
        # Create orders
        self.create_orders(options['orders'])
        
        self.stdout.write(self.style.SUCCESS('\n✅ Database seeding complete!'))

    def create_categories(self):
        """Create product categories"""
        self.stdout.write('📁 Creating categories...')
        
        categories_data = [
            {
                'name': 'Eggs',
                'slug': 'eggs',
                'description': 'Fresh farm eggs',
            },
            {
                'name': 'Broilers',
                'slug': 'broilers',
                'description': 'Healthy broiler chickens',
            },
            {
                'name': 'Layers',
                'slug': 'layers',
                'description': 'Layer hens for egg production',
            },
            {
                'name': 'Chicks',
                'slug': 'chicks',
                'description': 'Day-old and starter chicks',
            },
            {
                'name': 'Roosters',
                'slug': 'roosters',
                'description': 'Roosters and breeding males',
            },
        ]
        
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults=cat_data
            )
            if created:
                self.stdout.write(f'  ✓ Created category: {category.name}')

    def create_products(self):
        """Create test products"""
        self.stdout.write('🐔 Creating products...')
        
        products_data = [
            # Eggs
            {
                'category_slug': 'eggs',
                'SKU': 'EGG-FRESH-01',
                'name': 'Fresh Farm Eggs',
                'slug': 'fresh-farm-eggs',
                'description': 'Daily collected fresh eggs from our farm',
                'price': 15.00,
                'unit': 'per egg',
                'stock': 1000,
                'is_featured': True,
            },
            {
                'category_slug': 'eggs',
                'SKU': 'EGG-BULK-30',
                'name': 'Eggs - 30 Pack',
                'slug': 'eggs-30-pack',
                'description': 'Bulk pack of 30 fresh eggs',
                'price': 400.00,
                'unit': 'per carton',
                'stock': 50,
                'is_featured': True,
            },
            # Broilers
            {
                'category_slug': 'broilers',
                'SKU': 'BRL-2KG-01',
                'name': 'Broilers - 2kg',
                'slug': 'broilers-2kg',
                'description': 'Healthy 2kg broiler chickens, ready to cook',
                'price': 650.00,
                'unit': 'per bird',
                'stock': 100,
                'is_featured': True,
            },
            {
                'category_slug': 'broilers',
                'SKU': 'BRL-3KG-01',
                'name': 'Broilers - 3kg',
                'slug': 'broilers-3kg',
                'description': 'Premium 3kg broiler chickens',
                'price': 900.00,
                'unit': 'per bird',
                'stock': 50,
                'is_featured': False,
            },
            # Layers
            {
                'category_slug': 'layers',
                'SKU': 'LAY-HEN-01',
                'name': 'Layer Hens',
                'slug': 'layer-hens',
                'description': 'Productive layer hens for egg production',
                'price': 700.00,
                'unit': 'per bird',
                'stock': 30,
                'is_featured': False,
            },
            # Chicks
            {
                'category_slug': 'chicks',
                'SKU': 'CHK-DOL-01',
                'name': 'Day-Old Chicks',
                'slug': 'day-old-chicks',
                'description': 'Day-old chicks for rearing',
                'price': 50.00,
                'unit': 'per chick',
                'stock': 500,
                'is_featured': True,
            },
            {
                'category_slug': 'chicks',
                'SKU': 'CHK-KNJ-01',
                'name': 'Kienyeji Chicks',
                'slug': 'kienyeji-chicks',
                'description': 'Indigenous Kienyeji chicken chicks',
                'price': 100.00,
                'unit': 'per chick',
                'stock': 200,
                'is_featured': False,
            },
            # Roosters
            {
                'category_slug': 'roosters',
                'SKU': 'ROOSTER-01',
                'name': 'Roosters',
                'slug': 'roosters',
                'description': 'Healthy roosters for breeding',
                'price': 1500.00,
                'unit': 'per bird',
                'stock': 20,
                'is_featured': False,
            },
            {
                'category_slug': 'roosters',
                'SKU': 'ROOSTER-KNJ',
                'name': 'Kienyeji Roosters',
                'slug': 'kienyeji-roosters',
                'description': 'Indigenous Kienyeji roosters',
                'price': 1200.00,
                'unit': 'per bird',
                'stock': 15,
                'is_featured': False,
            },
        ]
        
        for prod_data in products_data:
            category = Category.objects.get(slug=prod_data.pop('category_slug'))
            
            product, created = Product.objects.get_or_create(
                SKU=prod_data['SKU'],
                defaults={**prod_data, 'category': category}
            )
            if created:
                self.stdout.write(f'  ✓ Created product: {product.name}')

    def create_users(self, count):
        """Create test users"""
        self.stdout.write(f'👥 Creating {count} test users...')
        
        first_names = ['John', 'Jane', 'Peter', 'Mary', 'James', 'Patricia', 'Robert', 'Jennifer']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']
        cities = ['Nairobi', 'Mombasa', 'Nakuru', 'Kisumu', 'Thika']
        counties = ['Nairobi County', 'Coastal County', 'Rift Valley County', 'Nyanza County']
        
        for i in range(count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            email = f'{first_name.lower()}.{last_name.lower()}{i}@example.com'
            phone = f'0{random.randint(7,9)}{random.randint(10000000, 99999999)}'
            
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email.split('@')[0],
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone_number': phone,
                    'address': f'{random.randint(1, 999)} Main Street',
                    'city': random.choice(cities),
                    'county': random.choice(counties),
                    'email_verified': True,
                    'phone_verified': True,
                    'is_verified': True,
                }
            )
            
            if created:
                user.set_password('testpass123')
                user.save()
                self.stdout.write(f'  ✓ Created user: {user.email}')

    def create_orders(self, count):
        """Create test orders with items and payments"""
        self.stdout.write(f'📦 Creating {count} test orders...')
        
        users = User.objects.all()
        products = Product.objects.all()
        statuses = ['pending', 'confirmed', 'processing', 'in_transit', 'delivered']
        payment_methods = ['mpesa', 'bank', 'cod']
        
        for i in range(count):
            user = random.choice(users)
            num_items = random.randint(1, 4)
            
            # Create order
            order = Order.objects.create(
                customer=user,
                delivery_phone=user.phone_number,
                delivery_address=user.address,
                delivery_city=user.city,
                delivery_county=user.county,
                status=random.choice(statuses),
                payment_method=random.choice(payment_methods),
            )
            
            # Add items
            subtotal = 0
            for _ in range(num_items):
                product = random.choice(products)
                quantity = random.randint(1, 10)
                unit_price = float(product.price)
                item_total = unit_price * quantity
                subtotal += item_total
                
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                )
            
            # Calculate totals
            tax = subtotal * 0.16  # 16% VAT
            discount = 0
            if subtotal > 5000:
                discount = subtotal * 0.05  # 5% discount for orders > 5000
            
            total = subtotal + tax - discount
            
            order.subtotal = subtotal
            order.tax_amount = tax
            order.discount_amount = discount
            order.total_amount = total
            
            # Mark as paid if not pending
            if order.status != 'pending':
                order.is_paid = True
            
            order.save()
            
            # Create payment if order is paid
            if order.is_paid:
                Payment.objects.create(
                    order=order,
                    method=order.payment_method,
                    amount=total,
                    status='completed',
                    transaction_id=f'MPR{random.randint(10000000, 99999999)}',
                )
            
            self.stdout.write(f'  ✓ Created order: {order.order_id}')
        
        self.stdout.write(f'  ✓ Created {count} orders with items and payments')

    def clear_data(self):
        """Delete all test data"""
        self.stdout.write('🗑️  Clearing test data...')
        
        Order.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        User.objects.filter(email__contains='example.com').delete()
        
        self.stdout.write(self.style.SUCCESS('✅ Test data cleared!'))