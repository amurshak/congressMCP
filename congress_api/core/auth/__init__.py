# Re-export commonly used auth functions and classes for backward compatibility
from .auth import (
    get_user_tier_from_context,
    SubscriptionTier,
    validate_api_key,
    check_feature_access,
    check_rate_limit,
    require_paid_access,
    generate_api_key,
    generate_jwt_token
)

__all__ = [
    'get_user_tier_from_context',
    'SubscriptionTier', 
    'validate_api_key',
    'check_feature_access',
    'check_rate_limit',
    'require_paid_access',
    'generate_api_key',
    'generate_jwt_token'
]