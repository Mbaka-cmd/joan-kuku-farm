# Machine Learning Engine - Model Training & Inference

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging
import pickle
import joblib

logger = logging.getLogger('ml')

# ============================================================
# ML MODELS
# ============================================================

class MLModel(models.Model):
    """Trained machine learning models"""
    MODEL_TYPE_CHOICES = [
        ('recommendation', 'Recommendation'),
        ('demand_forecast', 'Demand Forecast'),
        ('churn_prediction', 'Churn Prediction'),
        ('fraud_detection', 'Fraud Detection'),
        ('price_optimization', 'Price Optimization'),
        ('customer_segmentation', 'Customer Segmentation'),
    ]
    
    MODEL_STATUS = [
        ('training', 'Training'),
        ('validated', 'Validated'),
        ('deployed', 'Deployed'),
        ('archived', 'Archived'),
    ]
    
    # Model info
    name = models.CharField(max_length=255)
    model_type = models.CharField(max_length=30, choices=MODEL_TYPE_CHOICES)
    version = models.CharField(max_length=20)
    
    # Files
    model_file = models.FileField(upload_to='ml_models/%Y/%m/%d/')
    
    # Performance
    accuracy = models.DecimalField(max_digits=5, decimal_places=4)  # 0-1
    precision = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    recall = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    f1_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    # Training info
    training_samples = models.IntegerField()
    training_features = models.IntegerField()
    training_completed = models.DateTimeField()
    
    # Status
    status = models.CharField(max_length=20, choices=MODEL_STATUS, default='training')
    is_active = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ml_model'
        ordering = ['-created_at']
        unique_together = ['model_type', 'version']


class ModelPrediction(models.Model):
    """Store model predictions"""
    model = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    
    # Prediction
    prediction = models.JSONField()
    confidence = models.DecimalField(max_digits=5, decimal_places=4)
    
    # Input
    input_data = models.JSONField()
    
    # Reference
    user = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Validation
    actual_value = models.JSONField(null=True, blank=True)
    was_correct = models.BooleanField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'model_prediction'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model', '-created_at']),
        ]


class ModelTrainingJob(models.Model):
    """Track model training jobs"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('training', 'Training'),
        ('evaluating', 'Evaluating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Job info
    model_type = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Data
    training_samples = models.IntegerField()
    validation_split = models.DecimalField(max_digits=3, decimal_places=2, default=0.2)
    
    # Progress
    progress = models.IntegerField(default=0)  # 0-100
    
    # Results
    accuracy = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'model_training_job'
        ordering = ['-created_at']


# ============================================================
# ML ENGINE
# ============================================================

class MLEngine:
    """Machine learning operations"""
    
    @staticmethod
    def train_demand_forecast_model():
        """Train demand forecasting model"""
        from apps.orders.models import Order, OrderItem
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        
        logger.info('Starting demand forecast model training...')
        
        # Collect training data
        orders = Order.objects.filter(created_at__gte=timezone.now() - timedelta(days=365))
        
        X = []
        y = []
        
        for order in orders:
            for item in order.orderitem_set.all():
                features = [
                    item.product.price,
                    item.product.stock,
                    item.product.rating or 0,
                    order.created_at.month,
                    order.created_at.day,
                ]
                
                X.append(features)
                y.append(item.quantity)
        
        if len(X) < 100:
            logger.error('Insufficient training data')
            return None
        
        X = np.array(X)
        y = np.array(y)
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_scaled, y)
        
        # Evaluate
        train_score = model.score(X_scaled, y)
        
        logger.info(f'Model trained with accuracy: {train_score:.4f}')
        
        # Save model
        return MLEngine.save_model(
            model_type='demand_forecast',
            model_obj=model,
            accuracy=train_score,
            training_samples=len(X)
        )
    
    @staticmethod
    def train_churn_prediction_model():
        """Train customer churn prediction model"""
        from apps.users.models import CustomUser
        from apps.orders.models import Order
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        
        logger.info('Starting churn prediction model training...')
        
        X = []
        y = []
        
        users = CustomUser.objects.filter(date_joined__gte=timezone.now() - timedelta(days=365))
        
        for user in users:
            # Features
            order_count = Order.objects.filter(customer=user).count()
            total_spend = user.order_set.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
            days_since_join = (timezone.now() - user.date_joined).days
            last_order = user.order_set.order_by('-created_at').first()
            days_since_last_order = (timezone.now() - last_order.created_at).days if last_order else days_since_join
            
            features = [
                order_count,
                float(total_spend),
                days_since_join,
                days_since_last_order,
            ]
            
            X.append(features)
            
            # Label: churned if no order in 90 days
            y.append(1 if days_since_last_order > 90 else 0)
        
        if len(X) < 100:
            return None
        
        X = np.array(X)
        y = np.array(y)
        
        # Train
        model = GradientBoostingClassifier(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        accuracy = model.score(X, y)
        
        return MLEngine.save_model(
            model_type='churn_prediction',
            model_obj=model,
            accuracy=accuracy,
            training_samples=len(X)
        )
    
    @staticmethod
    def predict_churn(user):
        """Predict if user will churn"""
        from apps.orders.models import Order
        from apps.ml.models import MLModel
        
        try:
            model_obj = MLModel.objects.filter(
                model_type='churn_prediction',
                is_active=True
            ).order_by('-created_at').first()
            
            if not model_obj:
                return None
            
            # Load model
            model = joblib.load(model_obj.model_file.path)
            
            # Prepare features
            order_count = Order.objects.filter(customer=user).count()
            total_spend = user.order_set.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
            days_since_join = (timezone.now() - user.date_joined).days
            last_order = user.order_set.order_by('-created_at').first()
            days_since_last_order = (timezone.now() - last_order.created_at).days if last_order else days_since_join
            
            features = [[
                order_count,
                float(total_spend),
                days_since_join,
                days_since_last_order,
            ]]
            
            # Predict
            prediction = model.predict(features)[0]
            probability = model.predict_proba(features)[0]
            
            return {
                'will_churn': bool(prediction),
                'confidence': float(probability[1]),
            }
        
        except Exception as e:
            logger.error(f'Churn prediction failed: {e}')
            return None
    
    @staticmethod
    def save_model(model_type, model_obj, accuracy, training_samples):
        """Save trained model"""
        from apps.ml.models import MLModel
        import tempfile
        from django.core.files.base import ContentFile
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as tmp:
            joblib.dump(model_obj, tmp.name)
            
            with open(tmp.name, 'rb') as f:
                model_data = f.read()
        
        # Create model record
        model = MLModel.objects.create(
            name=f'{model_type}_v1',
            model_type=model_type,
            version='1.0',
            accuracy=accuracy,
            training_samples=training_samples,
            training_features=len(model_obj.feature_names_in_) if hasattr(model_obj, 'feature_names_in_') else 0,
            training_completed=timezone.now(),
            status='validated',
        )
        
        model.model_file = ContentFile(model_data, name=f'{model_type}_v1.pkl')
        model.save()
        
        logger.info(f'Model saved: {model.name}')
        
        return model


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def train_all_models():
    '''Train all ML models'''
    MLEngine.train_demand_forecast_model()
    MLEngine.train_churn_prediction_model()

@shared_task
def evaluate_model_predictions():
    '''Evaluate model predictions against actuals'''
    from apps.ml.models import ModelPrediction
    
    predictions = ModelPrediction.objects.filter(
        actual_value__isnull=False,
        was_correct__isnull=True
    )
    
    for pred in predictions:
        # Compare prediction to actual
        pred.was_correct = str(pred.prediction) == str(pred.actual_value)
        pred.save()

# Add to CELERY_BEAT_SCHEDULE:
'train-models': {
    'task': 'apps.ml.tasks.train_all_models',
    'schedule': 604800.0,  # Weekly
},
'evaluate-predictions': {
    'task': 'apps.ml.tasks.evaluate_model_predictions',
    'schedule': 86400.0,  # Daily
},
"""