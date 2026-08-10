"""
Scaffold test file for Security (FR-191–210).
Covers core happy-path and failure cases for security functionality.
"""
import uuid
import pytest
from datetime import datetime, timedelta

from sqlalchemy import select

from shared.datetime_utils import utc_now
from shared.models import User, UserRole


@pytest.mark.asyncio
async def test_user_authentication_happy_path(db, school, department):
    """
    FR-191: User Authentication - Happy Path.
    Verify that users can authenticate with valid credentials.
    """
    # Create user with valid credentials
    user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Initialize authentication service
    from modules.school_dept_user_role.services.user_service import UserService
    from platform_services.audit_log_service.service import AuditLogService as _ALS
    user_service = UserService(db, _ALS(db))
    
    # Authenticate with valid credentials
    authenticated_user = await user_service.authenticate_user(
        email="user@test.com",
        password="valid_password"  # In real implementation, this would be hashed
    )
    
    # Assert successful authentication
    assert authenticated_user is not None
    assert authenticated_user.email == "user@test.com"
    assert authenticated_user.status == "active"


@pytest.mark.asyncio
async def test_user_authentication_invalid_credentials(db, school, department):
    """
    FR-191: User Authentication - Failure Case.
    Verify that authentication fails with invalid credentials.
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Initialize authentication service
    from modules.school_dept_user_role.services.user_service import UserService
    from platform_services.audit_log_service.service import AuditLogService as _ALS
    user_service = UserService(db, _ALS(db))
    
    # Attempt authentication with invalid credentials
    with pytest.raises(Exception) as exc_info:
        await user_service.authenticate_user(
            email="user@test.com",
            password="invalid_password"
        )
    
    # Verify authentication failed
    assert "credential" in str(exc_info.value).lower() or "auth" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_role_based_authorization_happy_path(db, school, department):
    """
    FR-192: Role-Based Authorization - Happy Path.
    Verify that users can access resources based on their assigned roles.
    """
    # Create user with admin role
    admin_user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="admin@test.com",
        full_name="Admin User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(admin_user)
    await db.commit()
    
    # Initialize authorization service
    from modules.school_dept_user_role.services.user_service import UserService
    from platform_services.audit_log_service.service import AuditLogService as _ALS
    user_service = UserService(db, _ALS(db))
    
    # Check if user has admin role
    has_admin_access = await user_service.user_has_role(
        user_id=admin_user.id,
        role="admin"
    )
    
    # Assert authorization
    assert has_admin_access is True


@pytest.mark.asyncio
async def test_role_based_authorization_unauthorized(db, school, department):
    """
    FR-192: Role-Based Authorization - Failure Case.
    Verify that users cannot access resources without required roles.
    """
    # Create user with checker role (not admin)
    checker_user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="checker@test.com",
        full_name="Checker User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(checker_user)
    await db.commit()
    
    # Initialize authorization service
    from modules.school_dept_user_role.services.user_service import UserService
    from platform_services.audit_log_service.service import AuditLogService as _ALS
    user_service = UserService(db, _ALS(db))
    
    # Check if user has admin role
    has_admin_access = await user_service.user_has_role(
        user_id=checker_user.id,
        role="admin"
    )
    
    # Assert authorization denied
    assert has_admin_access is False


@pytest.mark.asyncio
async def test_permission_matrix_enforcement_happy_path(db, school, department):
    """
    FR-193: Permission Matrix Enforcement - Happy Path.
    Verify that permission matrix correctly allows access to authorized actions.
    """
    # Create user with supervisor role
    supervisor_user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="supervisor@test.com",
        full_name="Supervisor User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["supervisor"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(supervisor_user)
    await db.commit()
    
    # Initialize permission service
    from modules.school_dept_user_role.services.user_service import UserService
    from platform_services.audit_log_service.service import AuditLogService as _ALS
    user_service = UserService(db, _ALS(db))
    
    # Check if supervisor can approve observations
    can_approve = await user_service.user_has_permission(
        user_id=supervisor_user.id,
        permission="approve_observation"
    )
    
    # Assert permission granted
    assert can_approve is True


@pytest.mark.asyncio
async def test_permission_matrix_enforcement_denied(db, school, department):
    """
    FR-193: Permission Matrix Enforcement - Failure Case.
    Verify that permission matrix correctly denies access to unauthorized actions.
    """
    # Create user with checker role
    checker_user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="checker@test.com",
        full_name="Checker User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(checker_user)
    await db.commit()
    
    # Initialize permission service
    from modules.school_dept_user_role.services.user_service import UserService
    from platform_services.audit_log_service.service import AuditLogService as _ALS
    user_service = UserService(db, _ALS(db))
    
    # Check if checker can approve observations (should be denied)
    can_approve = await user_service.user_has_permission(
        user_id=checker_user.id,
        permission="approve_observation"
    )
    
    # Assert permission denied
    assert can_approve is False


@pytest.mark.asyncio
async def test_session_management_happy_path(db, school, department):
    """
    FR-194: Session Management - Happy Path.
    Verify that user sessions are created and managed correctly.
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Initialize session service
    from platform_services.session_service.service import SessionService
    session_service = SessionService(db)
    
    # Create session
    session = await session_service.create_session(
        user_id=user.id,
        ip_address="192.168.1.1",
        user_agent="Test Browser"
    )
    
    # Assert session creation
    assert session.id is not None
    assert session.user_id == user.id
    assert session.is_active is True


@pytest.mark.asyncio
async def test_session_expiration(db, school, department):
    """
    FR-194: Session Management - Failure Case.
    Verify that expired sessions are invalidated.
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Initialize session service
    from platform_services.session_service.service import SessionService
    session_service = SessionService(db)
    
    # Create session with past expiration
    session = await session_service.create_session(
        user_id=user.id,
        ip_address="192.168.1.1",
        user_agent="Test Browser",
        expires_at=utc_now() - timedelta(hours=1)  # Already expired
    )
    
    # Attempt to validate expired session
    is_valid = await session_service.validate_session(session.id)
    
    # Assert session is invalid
    assert is_valid is False


@pytest.mark.asyncio
async def test_data_encryption_happy_path(db, school, department):
    """
    FR-195: Data Encryption - Happy Path.
    Verify that sensitive data is encrypted at rest.
    """
    # Create user with sensitive data
    user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Initialize encryption service
    from platform_services.encryption_service.service import EncryptionService
    encryption_service = EncryptionService(db)
    
    # Encrypt sensitive data
    encrypted_data = await encryption_service.encrypt(
        data="sensitive_information",
        context="user_personal_data"
    )
    
    # Assert data is encrypted
    assert encrypted_data != "sensitive_information"
    assert encrypted_data is not None
    
    # Decrypt and verify
    decrypted_data = await encryption_service.decrypt(
        encrypted_data=encrypted_data,
        context="user_personal_data"
    )
    
    assert decrypted_data == "sensitive_information"


@pytest.mark.asyncio
async def test_password_policy_enforcement_happy_path(db, school, department):
    """
    FR-196: Password Policy Enforcement - Happy Path.
    Verify that passwords comply with security policies.
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Initialize password service
    from platform_services.password_service.service import PasswordService
    password_service = PasswordService(db)
    
    # Set compliant password
    is_compliant = await password_service.validate_password_policy(
        password="SecureP@ssw0rd123!",
        user_id=user.id
    )
    
    # Assert password is compliant
    assert is_compliant is True


@pytest.mark.asyncio
async def test_password_policy_enforcement_weak_password(db, school, department):
    """
    FR-196: Password Policy Enforcement - Failure Case.
    Verify that weak passwords are rejected.
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Initialize password service
    from platform_services.password_service.service import PasswordService
    password_service = PasswordService(db)
    
    # Attempt to set weak password
    is_compliant = await password_service.validate_password_policy(
        password="weak",  # Too short and simple
        user_id=user.id
    )
    
    # Assert password is not compliant
    assert is_compliant is False


@pytest.mark.asyncio
async def test_audit_logging_security_events(db, school, department):
    """
    FR-197: Audit Logging Security Events - Happy Path.
    Verify that security events are logged in the audit trail.
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Initialize audit service
    from platform_services.audit_log_service.service import AuditLogService
    audit_log_service = AuditLogService(db)
    
    # Log security event
    await audit_log_service.log_security_event(
        event_type="login_success",
        user_id=user.id,
        ip_address="192.168.1.1",
        details="Successful login"
    )
    
    # Verify audit entry exists
    audit_entries = await audit_log_service.get_user_security_events(user_id=user.id)
    
    # Assert security event was logged
    assert len(audit_entries) > 0
    assert audit_entries[0].event_type == "login_success"