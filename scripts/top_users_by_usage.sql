-- Get all users ordered by total usage (highest first)
SELECT 
    u.id,
    u.email,
    u.subscription_tier,
    u.is_active,
    SUM(ut.request_count) as total_requests,
    MAX(ut.date) as last_request_date,
    MIN(ut.date) as first_request_date,
    COUNT(DISTINCT ut.date) as active_days
FROM users u
LEFT JOIN usage_tracking ut ON u.id = ut.user_id
GROUP BY u.id, u.email, u.subscription_tier, u.is_active
ORDER BY total_requests DESC NULLS LAST
LIMIT 50;