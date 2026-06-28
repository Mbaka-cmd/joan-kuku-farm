# This script should be run after organizing files manually
# Or use this as a reference for your file movements

# STEP 1: Move config files
Move-Item -Path "settings.py" -Destination "config/settings.py" -Force
Move-Item -Path "urls.py" -Destination "config/urls.py" -Force
Move-Item -Path "wsgi.py" -Destination "config/wsgi.py" -Force
Move-Item -Path "asgi.py" -Destination "config/asgi.py" -Force
Move-Item -Path "celery.py" -Destination "config/celery.py" -Force
Move-Item -Path "api_versioning.py" -Destination "config/api_versioning.py" -Force

# STEP 2: Move app-specific files (Users)
Move-Item -Path "permissions.py" -Destination "apps/users/permissions.py" -Force
Move-Item -Path "localization.py" -Destination "apps/users/localization.py" -Force
Move-Item -Path "advanced_auth.py" -Destination "apps/users/advanced_auth.py" -Force

# STEP 3: Move Products app
Move-Item -Path "filters.py" -Destination "apps/products/filters.py" -Force
Move-Item -Path "advanced_search.py" -Destination "apps/search/advanced_search.py" -Force

# STEP 4: Move Payments
Move-Item -Path "payment_getaway_hub.py" -Destination "apps/payments/payment_gateway_hub.py" -Force

# STEP 5: Move Analytics
Move-Item -Path "advanced_analytics.py" -Destination "apps/analytics/advanced_analytics.py" -Force
Move-Item -Path "advanced_reporting.py" -Destination "apps/analytics/advanced_reporting.py" -Force
Move-Item -Path "bi_dashboard.py" -Destination "apps/bi/bi_dashboard.py" -Force
Move-Item -Path "data_warehouse.py" -Destination "apps/data_warehouse/data_warehouse.py" -Force
Move-Item -Path "ab_testing.py" -Destination "apps/analytics/ab_testing.py" -Force
Move-Item -Path "perfomance_optimization.py" -Destination "apps/analytics/performance_optimization.py" -Force

# STEP 6: Move ML/AI
Move-Item -Path "ml_engine.py" -Destination "apps/ml/ml_engine.py" -Force
Move-Item -Path "inventory_forecasting.py" -Destination "apps/ml/inventory_forecasting.py" -Force
Move-Item -Path "fraud_detection.py" -Destination "apps/fraud/fraud_detection.py" -Force
Move-Item -Path "churn_retention.py" -Destination "apps/churn/churn_retention.py" -Force
Move-Item -Path "recommendation_engine.py" -Destination "apps/recommendations/recommendation_engine.py" -Force
Move-Item -Path "personalization.py" -Destination "apps/personalization/personalization.py" -Force
Move-Item -Path "clv_optimization.py" -Destination "apps/clv/clv_optimization.py" -Force

# STEP 7: Move Marketplace
Move-Item -Path "multi_vendor.py" -Destination "apps/marketplace/multi_vendor.py" -Force

# STEP 8: Move Warehouse
Move-Item -Path "warehouse_management.py" -Destination "apps/warehouse/warehouse_management.py" -Force

# STEP 9: Move CDP
Move-Item -Path "cdp_platform.py" -Destination "apps/cdp/cdp_platform.py" -Force

# STEP 10: Move Content & Media
Move-Item -Path "cms_platform.py" -Destination "apps/cms/cms_platform.py" -Force
Move-Item -Path "video_platform.py" -Destination "apps/video/video_platform.py" -Force
Move-Item -Path "media_processing.py" -Destination "apps/media/media_processing.py" -Force
Move-Item -Path "seo_perfomance.py" -Destination "apps/seo/seo_performance.py" -Force

# STEP 11: Move Advanced Features
Move-Item -Path "business_automation.py" -Destination "apps/automation/business_automation.py" -Force
Move-Item -Path "dynamic_pricing.py" -Destination "apps/pricing/dynamic_pricing.py" -Force
Move-Item -Path "subscription_system.py" -Destination "apps/subscriptions/subscription_system.py" -Force
Move-Item -Path "loyalty_rewards.py" -Destination "apps/loyalty/loyalty_rewards.py" -Force
Move-Item -Path "affilliate_system.py" -Destination "apps/affiliate/affiliate_system.py" -Force
Move-Item -Path "returns_system.py" -Destination "apps/returns/returns_system.py" -Force
Move-Item -Path "bulk_operations.py" -Destination "apps/bulk_operations/bulk_operations.py" -Force
Move-Item -Path "gift_cards.py" -Destination "apps/giftcards/gift_cards.py" -Force
Move-Item -Path "review_system.py" -Destination "apps/reviews/review_system.py" -Force
Move-Item -Path "customer_support.py" -Destination "apps/support/customer_support.py" -Force
Move-Item -Path "compliance_system.py" -Destination "apps/compliance/compliance_system.py" -Force
Move-Item -Path "queue_system.py" -Destination "apps/queues/queue_system.py" -Force
Move-Item -Path "email_automation.py" -Destination "apps/email_marketing/email_automation.py" -Force
Move-Item -Path "supply_chain.py" -Destination "apps/supply_chain/supply_chain.py" -Force
Move-Item -Path "social_media_integration.py" -Destination "apps/social/social_media_integration.py" -Force
Move-Item -Path "inventory_optimization.py" -Destination "apps/inventory/inventory_optimization.py" -Force

# STEP 12: Move Security & Location
Move-Item -Path "advanced_security.py" -Destination "apps/security/advanced_security.py" -Force
Move-Item -Path "security_hardening.py" -Destination "apps/security/security_hardening.py" -Force
Move-Item -Path "location_services.py" -Destination "apps/location/location_services.py" -Force

# STEP 13: Move IoT & Blockchain
Move-Item -Path "iot_intengration.py" -Destination "apps/iot/iot_integration.py" -Force
Move-Item -Path "blockchain_crypto.py" -Destination "apps/blockchain/blockchain_crypto.py" -Force

# STEP 14: Move Analytics
Move-Item -Path "user_behavior_analytics.py" -Destination "apps/analytics/user_behavior_analytics.py" -Force

# STEP 15: Move Tests
Move-Item -Path "conftest.py" -Destination "tests/conftest.py" -Force

# STEP 16: Move Frontend
New-Item -ItemType Directory -Path "frontend/src" -Force
Move-Item -Path "app.jsx" -Destination "frontend/src/app.jsx" -Force

# STEP 17: Move Docs
New-Item -ItemType Directory -Path "docs/api" -Force
Move-Item -Path "collection.JSON" -Destination "docs/api/postman_collection.json" -Force

# STEP 18: Move Scripts
New-Item -ItemType Directory -Path "scripts" -Force
Move-Item -Path "seed_database.py" -Destination "scripts/seed_database.py" -Force

# STEP 19: Move CI/CD
New-Item -ItemType Directory -Path ".github/workflows" -Force
Move-Item -Path "github_actions.YML" -Destination ".github/workflows/tests.yml" -Force

Write-Host "✓ All files organized successfully!" -ForegroundColor Green
