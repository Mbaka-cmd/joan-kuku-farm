# Business Process Automation (BPA) Engine

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('automation')

# ============================================================
# AUTOMATION MODELS
# ============================================================

class AutomationWorkflow(models.Model):
    """Automation workflows"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('archived', 'Archived'),
    ]
    
    # Workflow
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Trigger
    trigger_event = models.CharField(max_length=100)  # order_created, payment_received, etc
    
    # Actions
    actions = models.JSONField(default=list)  # Sequence of actions
    
    # Conditions
    conditions = models.JSONField(default=list)  # Pre-requisites
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Stats
    total_executions = models.IntegerField(default=0)
    successful_executions = models.IntegerField(default=0)
    failed_executions = models.IntegerField(default=0)
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    schedule_cron = models.CharField(max_length=100, blank=True)
    
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'automation_workflow'
        ordering = ['-created_at']


class WorkflowExecution(models.Model):
    """Track workflow executions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    workflow = models.ForeignKey(AutomationWorkflow, on_delete=models.CASCADE)
    
    # Trigger
    trigger_object_type = models.CharField(max_length=100)
    trigger_object_id = models.IntegerField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Actions
    actions_executed = models.IntegerField(default=0)
    
    # Results
    results = models.JSONField(default=list)  # Results of each action
    
    # Error
    error_message = models.TextField(blank=True)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'workflow_execution'
        ordering = ['-created_at']


class AutomationAction(models.Model):
    """Available automation actions"""
    ACTION_TYPE = [
        ('send_email', 'Send Email'),
        ('send_sms', 'Send SMS'),
        ('create_task', 'Create Task'),
        ('update_field', 'Update Field'),
        ('create_order', 'Create Order'),
        ('trigger_webhook', 'Trigger Webhook'),
        ('add_tag', 'Add Tag'),
        ('send_notification', 'Send Notification'),
        ('pause_workflow', 'Pause Workflow'),
    ]
    
    name = models.CharField(max_length=255)
    action_type = models.CharField(max_length=50, choices=ACTION_TYPE)
    
    # Configuration
    config = models.JSONField(default=dict)
    
    # Description
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'automation_action'


class ConditionalRule(models.Model):
    """Conditional rules for workflows"""
    OPERATOR_CHOICES = [
        ('equals', 'Equals'),
        ('not_equals', 'Not Equals'),
        ('greater_than', 'Greater Than'),
        ('less_than', 'Less Than'),
        ('contains', 'Contains'),
        ('not_contains', 'Not Contains'),
    ]
    
    workflow = models.ForeignKey(AutomationWorkflow, on_delete=models.CASCADE)
    
    # Condition
    field = models.CharField(max_length=255)  # order.status, customer.email, etc
    operator = models.CharField(max_length=50, choices=OPERATOR_CHOICES)
    value = models.CharField(max_length=500)
    
    # Logical
    logical_operator = models.CharField(max_length=10, choices=[('and', 'AND'), ('or', 'OR')])
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'conditional_rule'


# ============================================================
# AUTOMATION ENGINE
# ============================================================

class AutomationEngine:
    """Execute business process automation"""
    
    @staticmethod
    def trigger_workflow(trigger_event, trigger_object_type, trigger_object_id):
        """Trigger workflow based on event"""
        from apps.automation.models import AutomationWorkflow, WorkflowExecution
        
        workflows = AutomationWorkflow.objects.filter(
            trigger_event=trigger_event,
            status='active'
        )
        
        executions = []
        
        for workflow in workflows:
            # Check conditions
            if not AutomationEngine.evaluate_conditions(workflow, trigger_object_type, trigger_object_id):
                continue
            
            # Create execution
            execution = WorkflowExecution.objects.create(
                workflow=workflow,
                trigger_object_type=trigger_object_type,
                trigger_object_id=trigger_object_id,
            )
            
            # Execute workflow
            AutomationEngine.execute_workflow(execution)
            
            executions.append(execution)
        
        logger.info(f'Triggered {len(executions)} workflows for {trigger_event}')
        
        return executions
    
    @staticmethod
    def evaluate_conditions(workflow, object_type, object_id):
        """Evaluate workflow conditions"""
        from apps.automation.models import ConditionalRule
        
        rules = ConditionalRule.objects.filter(workflow=workflow)
        
        if not rules.exists():
            return True
        
        # Get the object
        obj = AutomationEngine.get_trigger_object(object_type, object_id)
        
        if not obj:
            return False
        
        # Evaluate rules
        all_passed = True
        
        for rule in rules:
            field_value = AutomationEngine.get_field_value(obj, rule.field)
            
            passed = AutomationEngine.evaluate_rule(
                field_value,
                rule.operator,
                rule.value
            )
            
            if not passed:
                all_passed = False
                break
        
        return all_passed
    
    @staticmethod
    def execute_workflow(execution):
        """Execute workflow actions"""
        from apps.automation.models import AutomationAction
        
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.save()
        
        workflow = execution.workflow
        results = []
        
        try:
            for action_config in workflow.actions:
                action_type = action_config.get('type')
                
                result = AutomationEngine.execute_action(
                    action_type,
                    action_config,
                    execution.trigger_object_type,
                    execution.trigger_object_id
                )
                
                results.append({
                    'action': action_type,
                    'success': result['success'],
                    'message': result.get('message', ''),
                })
                
                execution.actions_executed += 1
                
                if not result['success'] and action_config.get('stop_on_error'):
                    break
            
            execution.status = 'completed'
            execution.results = results
            
            workflow.total_executions += 1
            workflow.successful_executions += 1
            workflow.save()
            
            logger.info(f'Workflow executed: {workflow.name} ({execution.id})')
        
        except Exception as e:
            execution.status = 'failed'
            execution.error_message = str(e)
            
            workflow.total_executions += 1
            workflow.failed_executions += 1
            workflow.save()
            
            logger.error(f'Workflow execution failed: {e}')
        
        execution.completed_at = timezone.now()
        execution.save()
    
    @staticmethod
    def execute_action(action_type, config, object_type, object_id):
        """Execute single action"""
        try:
            if action_type == 'send_email':
                return AutomationEngine.send_email_action(config, object_type, object_id)
            
            elif action_type == 'send_sms':
                return AutomationEngine.send_sms_action(config, object_type, object_id)
            
            elif action_type == 'create_task':
                return AutomationEngine.create_task_action(config, object_type, object_id)
            
            elif action_type == 'update_field':
                return AutomationEngine.update_field_action(config, object_type, object_id)
            
            elif action_type == 'send_notification':
                return AutomationEngine.send_notification_action(config, object_type, object_id)
            
            elif action_type == 'trigger_webhook':
                return AutomationEngine.trigger_webhook_action(config, object_type, object_id)
            
            else:
                return {'success': False, 'message': f'Unknown action: {action_type}'}
        
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def send_email_action(config, object_type, object_id):
        """Send email action"""
        from apps.notifications.models import Notification
        
        obj = AutomationEngine.get_trigger_object(object_type, object_id)
        
        if hasattr(obj, 'customer'):
            recipient = obj.customer
        elif hasattr(obj, 'user'):
            recipient = obj.user
        else:
            return {'success': False, 'message': 'No recipient found'}
        
        Notification.objects.create(
            recipient=recipient,
            channel='email',
            subject=config.get('subject', ''),
            body=config.get('body', ''),
        )
        
        return {'success': True, 'message': 'Email queued'}
    
    @staticmethod
    def create_task_action(config, object_type, object_id):
        """Create task action"""
        # Create task in system
        logger.info(f'Task created: {config.get("title")}')
        
        return {'success': True, 'message': 'Task created'}
    
    @staticmethod
    def update_field_action(config, object_type, object_id):
        """Update field action"""
        obj = AutomationEngine.get_trigger_object(object_type, object_id)
        
        if obj:
            field = config.get('field')
            value = config.get('value')
            
            setattr(obj, field, value)
            obj.save()
            
            return {'success': True, 'message': f'Field updated: {field}'}
        
        return {'success': False, 'message': 'Object not found'}
    
    @staticmethod
    def send_notification_action(config, object_type, object_id):
        """Send notification action"""
        from apps.notifications.engine import NotificationEngine
        
        obj = AutomationEngine.get_trigger_object(object_type, object_id)
        
        if hasattr(obj, 'customer'):
            recipient = obj.customer
        else:
            return {'success': False, 'message': 'No recipient'}
        
        NotificationEngine.trigger_notification(
            config.get('event_type'),
            recipient,
            config.get('context', {})
        )
        
        return {'success': True, 'message': 'Notification sent'}
    
    @staticmethod
    def trigger_webhook_action(config, object_type, object_id):
        """Trigger webhook action"""
        import requests
        
        url = config.get('url')
        data = config.get('data', {})
        
        try:
            response = requests.post(url, json=data, timeout=10)
            
            return {'success': response.status_code < 400, 'message': f'Status: {response.status_code}'}
        
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def get_trigger_object(object_type, object_id):
        """Get trigger object"""
        if object_type == 'order':
            from apps.orders.models import Order
            return Order.objects.filter(id=object_id).first()
        
        elif object_type == 'customer':
            from apps.users.models import CustomUser
            return CustomUser.objects.filter(id=object_id).first()
        
        elif object_type == 'payment':
            from apps.payments.models import Payment
            return Payment.objects.filter(id=object_id).first()
        
        return None
    
    @staticmethod
    def get_field_value(obj, field_path):
        """Get nested field value"""
        parts = field_path.split('.')
        value = obj
        
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
        
        return value
    
    @staticmethod
    def evaluate_rule(field_value, operator, expected_value):
        """Evaluate conditional rule"""
        if operator == 'equals':
            return str(field_value) == str(expected_value)
        elif operator == 'not_equals':
            return str(field_value) != str(expected_value)
        elif operator == 'greater_than':
            return float(field_value) > float(expected_value)
        elif operator == 'less_than':
            return float(field_value) < float(expected_value)
        elif operator == 'contains':
            return str(expected_value) in str(field_value)
        elif operator == 'not_contains':
            return str(expected_value) not in str(field_value)
        
        return False


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def trigger_workflow_event(event_type, object_type, object_id):
    '''Trigger workflow for event'''
    AutomationEngine.trigger_workflow(event_type, object_type, object_id)

@shared_task
def execute_scheduled_workflows():
    '''Execute scheduled workflows'''
    from apps.automation.models import AutomationWorkflow
    
    scheduled = AutomationWorkflow.objects.filter(
        is_scheduled=True,
        status='active'
    )
    
    for workflow in scheduled:
        # Execute if schedule matches
        pass

# Add to CELERY_BEAT_SCHEDULE:
'execute-scheduled-workflows': {
    'task': 'apps.automation.tasks.execute_scheduled_workflows',
    'schedule': 600.0,  # Every 10 minutes
},
"""