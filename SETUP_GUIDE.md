# Django Project Setup Guide for Joan Kuku Farm

## Step 1: Install Dependencies
pip install -r requirements.txt

## Step 2: Create Database
createdb joankkfarm
psql joankkfarm -c "CREATE EXTENSION postgis;"

## Step 3: Create Superuser
python manage.py createsuperuser

## Step 4: Run Migrations
python manage.py makemigrations
python manage.py migrate

## Step 5: Load Initial Data
python manage.py seed_database

## Step 6: Collect Static Files
python manage.py collectstatic --noinput

## Step 7: Create Cache Table
python manage.py createcachetable

## Step 8: Run Development Servers (in separate terminals)

# Terminal 1: Django Server
python manage.py runserver

# Terminal 2: Celery Worker
celery -A config worker -l info

# Terminal 3: Celery Beat (Scheduler)
celery -A config beat -l info

# Terminal 4: Redis Server
redis-server

## Step 9: Access Applications

- Admin: http://localhost:8000/admin/
- API Docs: http://localhost:8000/api/docs/
- API Schema: http://localhost:8000/api/schema/

## Environment Variables (.env)

Create a .env file with:

DEBUG=True
SECRET_KEY=your_secret_key_here
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgresql://user:password@localhost:5432/joankkfarm
REDIS_URL=redis://localhost:6379/0

# M-Pesa
MPESA_CONSUMER_KEY=your_key
MPESA_CONSUMER_SECRET=your_secret
MPESA_SHORTCODE=your_shortcode

# Stripe
STRIPE_SECRET_KEY=your_key
STRIPE_PUBLISHABLE_KEY=your_key

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_password

# AWS S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_STORAGE_BUCKET_NAME=your_bucket

# Twilio
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890

# Google Maps
GOOGLE_MAPS_API_KEY=your_key

## Troubleshooting

### Port Already in Use
netstat -ano | findstr :8000
taskkill /PID <PID> /F

### Database Connection Error
Check PostgreSQL is running: pg_isready -h localhost

### Redis Connection Error
Check Redis is running: redis-cli ping

### Permission Denied on Static Files
python manage.py collectstatic --clear --noinput

## Testing

Run all tests:
pytest

Run specific app tests:
pytest tests/test_orders.py

With coverage:
pytest --cov=apps

## Deployment Checklist

- [ ] Update DEBUG=False in settings
- [ ] Set ALLOWED_HOSTS correctly
- [ ] Use environment variables for secrets
- [ ] Run security checks: python manage.py check --deploy
- [ ] Set up SSL/TLS certificate
- [ ] Configure CORS properly
- [ ] Set up monitoring and logging
- [ ] Run load tests
- [ ] Backup database
- [ ] Set up CI/CD pipeline
