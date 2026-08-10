"""
Notification localization service for English + Hindi templates.
Per PRS §54, Supported Locales is a Configuration Engine value.
"""
from typing import Optional
from dataclasses import dataclass

@dataclass
class NotificationTemplate:
    """Template for notification content with i18n support."""
    title_en: str
    title_hi: str
    body_en: str
    body_hi: str
    
    def get_title(self, locale: str = "en") -> str:
        """Get localized title based on locale."""
        return self.title_hi if locale == "hi" else self.title_en
    
    def get_body(self, locale: str = "en") -> str:
        """Get localized body based on locale."""
        return self.body_hi if locale == "hi" else self.body_en

# Notification templates per PRS §49 Notification Matrix
NOTIFICATION_TEMPLATES = {
    "escalation": NotificationTemplate(
        title_en="Task Escalated",
        title_hi="कार्य एस्केलेट किया गया",
        body_en="Task has been escalated to level {{level}}",
        body_hi="कार्य को स्तर {{level}} पर एस्केलेट किया गया है"
    ),
    "escalation_eta_limit": NotificationTemplate(
        title_en="Task Escalated — ETA Extension Limit Reached",
        title_hi="कार्य एस्केलेट किया गया — ईटीए एक्सटेंशन सीमा पूरी हो गई",
        body_en="Task has been escalated because the maximum ETA extension limit has been reached",
        body_hi="कार्य को एस्केलेट किया गया है क्योंकि अधिकतम ईटीए एक्सटेंशन सीमा पूरी हो गई है"
    ),
    "audit_failure": NotificationTemplate(
        title_en="Discrepancy Raised",
        title_hi="विसंगति उठाई गई",
        body_en="A new discrepancy has been raised: {{description}}",
        body_hi="एक नई विसंगति उठाई गई है: {{description}}"
    ),
    "audit_failure_department": NotificationTemplate(
        title_en="Discrepancy Raised in Your Department",
        title_hi="आपके विभाग में विसंगति उठाई गई",
        body_en="A new discrepancy has been raised in your department: {{description}}",
        body_hi="आपके विभाग में एक नई विसंगति उठाई गई है: {{description}}"
    ),
    "task_assignment": NotificationTemplate(
        title_en="New Task Assigned",
        title_hi="नया कार्य सौंपा गया",
        body_en="You have been assigned to task: {{title}}",
        body_hi="आपको कार्य सौंपा गया है: {{title}}"
    ),
    "task_eta_extended": NotificationTemplate(
        title_en="Task ETA Extended",
        title_hi="कार्य ईटीए विस्तारित",
        body_en="Task ETA has been extended to {{new_eta}}",
        body_hi="कार्य ईटीए को {{new_eta}} तक विस्तारित किया गया है"
    ),
    "due_today": NotificationTemplate(
        title_en="Due Today",
        title_hi="आज देय",
        body_en="{{item_type}} is due today",
        body_hi="{{item_type}} आज देय है"
    ),
    "late_observation": NotificationTemplate(
        title_en="Late Observation Submitted",
        title_hi="देर से अवलोकन जमा किया गया",
        body_en="Your observation for KPI {{kpi_title}} was submitted late",
        body_hi="आपका अवलोकन केपीआई {{kpi_title}} के लिए देर से जमा किया गया था"
    ),
    "kpi_reminder": NotificationTemplate(
        title_en="KPI Reminder",
        title_hi="केपीआई रिमाइंडर",
        body_en="KPI {{kpi_title}} is due soon",
        body_hi="केपीआई {{kpi_title}} जल्द ही देय है"
    ),
    "comment": NotificationTemplate(
        title_en="New Comment",
        title_hi="नई टिप्पणी",
        body_en="{{author}} commented on {{item_type}}",
        body_hi="{{author}} ने {{item_type}} पर टिप्पणी की"
    ),
    "school_created": NotificationTemplate(
        title_en="School Created",
        title_hi="स्कूल बनाया गया",
        body_en="New school '{{name}}' has been created successfully",
        body_hi="नया स्कूल '{{name}}' सफलतापूर्वक बनाया गया है"
    ),
    "user_created": NotificationTemplate(
        title_en="User Account Created",
        title_hi="उपयोगकर्ता खाता बनाया गया",
        body_en="Your account has been created successfully. Welcome, {{name}}!",
        body_hi="आपका खाता सफलतापूर्वक बनाया गया है। स्वागत है, {{name}}!"
    ),
    "new_user_created": NotificationTemplate(
        title_en="New User Created",
        title_hi="नया उपयोगकर्ता बनाया गया",
        body_en="New user '{{name}}' has been created in your school",
        body_hi="आपके स्कूल में नया उपयोगकर्ता '{{name}}' बनाया गया है"
    ),
    "kpi_created": NotificationTemplate(
        title_en="KPI Created",
        title_hi="केपीआई बनाया गया",
        body_en="New KPI '{{title}}' has been created successfully",
        body_hi="नया केपीआई '{{title}}' सफलतापूर्वक बनाया गया है"
    ),
    "kpi_created_global": NotificationTemplate(
        title_en="KPI Created",
        title_hi="केपीआई बनाया गया",
        body_en="New KPI '{{title}}' has been created in the Global KPI Library",
        body_hi="नया केपीआई '{{title}}' ग्लोबल केपीआई लाइब्रेरी में बनाया गया है"
    ),
    "scorecard_generated": NotificationTemplate(
        title_en="Scorecard Generated",
        title_hi="स्कोरकार्ड जनरेट किया गया",
        body_en="Your performance scorecard for {{start_date}} to {{end_date}} has been generated",
        body_hi="{{start_date}} से {{end_date}} तक आपका प्रदर्शन स्कोरकार्ड जनरेट किया गया है"
    ),
    "scorecard_generated_user": NotificationTemplate(
        title_en="Scorecard Generated",
        title_hi="स्कोरकार्ड जनरेट किया गया",
        body_en="Performance scorecard has been generated for user {{user_name}}",
        body_hi="उपयोगकर्ता {{user_name}} के लिए प्रदर्शन स्कोरकार्ड जनरेट किया गया है"
    ),
    "school_scorecard_generated": NotificationTemplate(
        title_en="School Scorecard Generated",
        title_hi="स्कूल स्कोरकार्ड जनरेट किया गया",
        body_en="School performance scorecard for {{start_date}} to {{end_date}} has been generated",
        body_hi="{{start_date}} से {{end_date}} तक स्कूल प्रदर्शन स्कोरकार्ड जनरेट किया गया है"
    ),
    "department_scorecard_generated": NotificationTemplate(
        title_en="Department Scorecard Generated",
        title_hi="विभाग स्कोरकार्ड जनरेट किया गया",
        body_en="Department scorecard for {{dept_name}} has been generated",
        body_hi="विभाग {{dept_name}} के लिए विभाग स्कोरकार्ड जनरेट किया गया है"
    ),
}

class NotificationLocalizationService:
    """Service for localizing notification content."""
    
    def __init__(self, config_engine):
        self.config_engine = config_engine
    
    async def get_user_locale(self, user_id) -> str:
        """Get user's preferred locale from Configuration Engine."""
        try:
            locale = await self.config_engine.get("supported_locales")
            # For now, return the first supported locale or default to English
            # In a full implementation, this would check user-specific preferences
            if isinstance(locale, list) and len(locale) > 0:
                return locale[0] if locale[0] in ["en", "hi"] else "en"
            return "en"
        except Exception:
            return "en"
    
    def get_localized_template(self, template_key: str, locale: str = "en") -> NotificationTemplate:
        """Get localized notification template."""
        template = NOTIFICATION_TEMPLATES.get(template_key)
        if not template:
            # Fallback to a generic template
            return NotificationTemplate(
                title_en="Notification",
                title_hi="अधिसूचना",
                body_en="You have a new notification",
                body_hi="आपके पास एक नई अधिसूचना है"
            )
        return template
    
    def format_template(self, template: NotificationTemplate, locale: str, **kwargs) -> tuple[str, str]:
        """Format template with variables and return localized title and body."""
        title = template.get_title(locale)
        body = template.get_body(locale)
        
        # Replace template variables
        for key, value in kwargs.items():
            placeholder = f"{{{{{key}}}}}"
            title = title.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        
        return title, body
