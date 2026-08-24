"""
Notification localization service for English templates.
Per PRS §54, Supported Locales is a Configuration Engine value.
"""
from typing import Optional
from dataclasses import dataclass

@dataclass
class NotificationTemplate:
    """Template for notification content."""
    title: str
    body: str

# Notification templates per PRS §49 Notification Matrix
NOTIFICATION_TEMPLATES = {
    "escalation": NotificationTemplate(
        title="Task Escalated",
        body="Task has been escalated to level {{level}}"
    ),
    "escalation_eta_limit": NotificationTemplate(
        title="Task Escalated — ETA Extension Limit Reached",
        body="Task has been escalated because the maximum ETA extension limit has been reached"
    ),
    "audit_failure": NotificationTemplate(
        title="Discrepancy Raised",
        body="A new discrepancy has been raised: {{description}}"
    ),
    "audit_failure_department": NotificationTemplate(
        title="Discrepancy Raised in Your Department",
        body="A new discrepancy has been raised in your department: {{description}}"
    ),
    "task_assignment": NotificationTemplate(
        title="New Task Assigned",
        body="You have been assigned to task: {{title}}"
    ),
    "task_eta_extended": NotificationTemplate(
        title="Task ETA Extended",
        body="Task ETA has been extended to {{new_eta}}"
    ),
    "due_today": NotificationTemplate(
        title="Due Today",
        body="{{item_type}} is due today"
    ),
    "late_observation": NotificationTemplate(
        title="Late Observation Submitted",
        body="Your observation for KPI {{kpi_title}} was submitted late"
    ),
    "kpi_reminder": NotificationTemplate(
        title="KPI Reminder",
        body="KPI {{kpi_title}} is due soon"
    ),
    "comment": NotificationTemplate(
        title="New Comment",
        body="{{author}} commented on {{item_type}}"
    ),
    "school_created": NotificationTemplate(
        title="School Created",
        body="New school '{{name}}' has been created successfully"
    ),
    "user_created": NotificationTemplate(
        title="User Account Created",
        body="Your account has been created successfully. Welcome, {{name}}!"
    ),
    "new_user_created": NotificationTemplate(
        title="New User Created",
        body="New user '{{name}}' has been created in your school"
    ),
    "kpi_created": NotificationTemplate(
        title="KPI Created",
        body="New KPI '{{title}}' has been created successfully"
    ),
    "kpi_created_global": NotificationTemplate(
        title="KPI Created",
        body="New KPI '{{title}}' has been created in the Global KPI Library"
    ),
    "scorecard_generated": NotificationTemplate(
        title="Scorecard Generated",
        body="Your performance scorecard for {{start_date}} to {{end_date}} has been generated"
    ),
    "scorecard_generated_user": NotificationTemplate(
        title="Scorecard Generated",
        body="Performance scorecard has been generated for user {{user_name}}"
    ),
    "school_scorecard_generated": NotificationTemplate(
        title="School Scorecard Generated",
        body="School performance scorecard for {{start_date}} to {{end_date}} has been generated"
    ),
    "department_scorecard_generated": NotificationTemplate(
        title="Department Scorecard Generated",
        body="Department scorecard for {{dept_name}} has been generated"
    ),
}

class NotificationLocalizationService:
    """Service for notification content."""
    
    def __init__(self, config_engine):
        self.config_engine = config_engine
    
    def get_template(self, template_key: str) -> NotificationTemplate:
        """Get notification template."""
        template = NOTIFICATION_TEMPLATES.get(template_key)
        if not template:
            # Fallback to a generic template
            return NotificationTemplate(
                title="Notification",
                body="You have a new notification"
            )
        return template
    
    def format_template(self, template: NotificationTemplate, **kwargs) -> tuple[str, str]:
        """Format template with variables and return title and body."""
        title = template.title
        body = template.body
        
        # Replace template variables
        for key, value in kwargs.items():
            placeholder = f"{{{{{key}}}}}"
            title = title.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        
        return title, body
