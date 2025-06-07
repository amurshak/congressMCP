"""
Test suite for Congressional Records & Communications Hub bucket tool.

Tests operation-level access control, parameter routing, and integration functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastmcp import Context
from fastmcp.exceptions import ToolError

from congress_api.features.buckets.records_communications_hub import (
    congressional_records_communications_hub,
    check_operation_access,
    route_records_communications_operation,
    FREE_OPERATIONS,
    PAID_OPERATIONS
)
from congress_api.core.auth.auth import SubscriptionTier


class TestRecordsCommunicationsHubAccessControl:
    """Test operation-level access control for Records & Communications Hub."""
    
    def test_free_operations_accessible_to_free_tier(self):
        """Test that free operations are accessible to free tier users."""
        # Mock context with free tier user
        ctx = MagicMock()
        with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            # Should not raise an error for free operations
            for operation in FREE_OPERATIONS:
                check_operation_access(ctx, operation)
    
    def test_paid_operations_blocked_for_free_tier(self):
        """Test that paid operations are blocked for free tier users."""
        ctx = MagicMock()
        with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            # Should raise ToolError for paid operations
            for operation in list(PAID_OPERATIONS)[:3]:  # Test first 3 paid operations
                with pytest.raises(ToolError) as exc_info:
                    check_operation_access(ctx, operation)
                assert "requires a paid subscription" in str(exc_info.value)
                assert "free" in str(exc_info.value).lower()
    
    def test_all_operations_accessible_to_paid_tiers(self):
        """Test that all operations are accessible to paid tier users."""
        ctx = MagicMock()
        
        for tier in [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]:
            with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
                mock_get_tier.return_value = tier
                
                # Should not raise an error for any operation
                for operation in FREE_OPERATIONS | PAID_OPERATIONS:
                    check_operation_access(ctx, operation)
    
    def test_invalid_operation_raises_error(self):
        """Test that invalid operation raises ToolError."""
        ctx = MagicMock()
        with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with pytest.raises(ToolError) as exc_info:
                check_operation_access(ctx, "invalid_operation")
            assert "Unknown operation" in str(exc_info.value)


class TestRecordsCommunicationsHubRouting:
    """Test operation routing functionality."""
    
    @pytest.mark.asyncio
    async def test_congressional_record_operations_routing(self):
        """Test routing for congressional record operations."""
        ctx = MagicMock()
        
        operations_map = {
            "search_congressional_record": "congress_api.features.congressional_record.search_congressional_record",
            "search_daily_congressional_record": "congress_api.features.daily_congressional_record.search_daily_congressional_record",
            "search_bound_congressional_record": "congress_api.features.bound_congressional_record.search_bound_congressional_record"
        }
        
        for operation, mock_path in operations_map.items():
            with patch(mock_path, new_callable=AsyncMock) as mock_func:
                mock_func.return_value = f"Mock result for {operation}"
                
                result = await route_records_communications_operation(
                    ctx, operation, year=2022, congress=117
                )
                
                mock_func.assert_called_once_with(ctx, year=2022, congress=117)
                assert result == f"Mock result for {operation}"
    
    @pytest.mark.asyncio
    async def test_house_communication_operations_routing(self):
        """Test routing for House communication operations."""
        ctx = MagicMock()
        
        operations_map = {
            "search_house_communications": "congress_api.features.house_communications.search_house_communications",
            "get_house_communication_details": "congress_api.features.house_communications.get_house_communication_details"
        }
        
        for operation, mock_path in operations_map.items():
            with patch(mock_path, new_callable=AsyncMock) as mock_func:
                mock_func.return_value = f"Mock result for {operation}"
                
                result = await route_records_communications_operation(
                    ctx, operation, congress=117, communication_type="ec"
                )
                
                mock_func.assert_called_once_with(ctx, congress=117, communication_type="ec")
                assert result == f"Mock result for {operation}"
    
    @pytest.mark.asyncio
    async def test_hearing_operations_routing(self):
        """Test routing for hearing operations."""
        ctx = MagicMock()
        
        operations_map = {
            "search_hearings": "congress_api.features.hearings.search_hearings",
            "get_hearing_details": "congress_api.features.hearings.get_hearing_details"
        }
        
        for operation, mock_path in operations_map.items():
            with patch(mock_path, new_callable=AsyncMock) as mock_func:
                mock_func.return_value = f"Mock result for {operation}"
                
                result = await route_records_communications_operation(
                    ctx, operation, congress=117, chamber="house"
                )
                
                mock_func.assert_called_once_with(ctx, congress=117, chamber="house")
                assert result == f"Mock result for {operation}"
    
    @pytest.mark.asyncio
    async def test_invalid_operation_routing_raises_error(self):
        """Test that invalid operation raises ToolError in routing."""
        ctx = MagicMock()
        
        with pytest.raises(ToolError) as exc_info:
            await route_records_communications_operation(ctx, "invalid_operation")
        assert "Unknown operation" in str(exc_info.value)


class TestRecordsCommunicationsHubIntegration:
    """Test full bucket tool integration."""
    
    @pytest.mark.asyncio
    async def test_bucket_tool_free_operation_success(self):
        """Test successful execution of free operation."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            with patch('congress_api.features.congressional_record.search_congressional_record', new_callable=AsyncMock) as mock_search:
                mock_search.return_value = "Mock congressional record results"
                
                result = await congressional_records_communications_hub(
                    ctx,
                    operation="search_congressional_record",
                    year=2022,
                    congress=117,
                    limit=10
                )
                
                mock_search.assert_called_once_with(ctx, year=2022, congress=117, limit=10)
                assert result == "Mock congressional record results"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_paid_operation_blocked_for_free_tier(self):
        """Test that paid operations are blocked for free tier."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            with pytest.raises(ToolError) as exc_info:
                await congressional_records_communications_hub(
                    ctx,
                    operation="get_house_communication_details",
                    congress=117,
                    communication_type="ec",
                    communication_number=123
                )
            
            assert "requires a paid subscription" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_bucket_tool_paid_operation_success_for_paid_tier(self):
        """Test successful execution of paid operation for paid tier."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.house_communications.get_house_communication_details', new_callable=AsyncMock) as mock_get_details:
                mock_get_details.return_value = "Mock communication details"
                
                result = await congressional_records_communications_hub(
                    ctx,
                    operation="get_house_communication_details",
                    congress=117,
                    communication_type="ec",
                    communication_number=123
                )
                
                mock_get_details.assert_called_once_with(
                    ctx, congress=117, communication_type="ec", communication_number=123
                )
                assert result == "Mock communication details"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_parameter_filtering(self):
        """Test that only relevant parameters are passed to underlying functions."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.hearings.search_hearings', new_callable=AsyncMock) as mock_search:
                mock_search.return_value = "Mock hearing results"
                
                result = await congressional_records_communications_hub(
                    ctx,
                    operation="search_hearings",
                    keywords="agriculture",
                    congress=117,
                    chamber="house",
                    # These parameters should be filtered out as None
                    year=None,
                    communication_type=None
                )
                
                # Only non-None parameters should be passed
                mock_search.assert_called_once_with(
                    ctx, keywords="agriculture", congress=117, chamber="house"
                )
                assert result == "Mock hearing results"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_error_handling(self):
        """Test proper error handling and logging."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.records_communications_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.congressional_record.search_congressional_record', new_callable=AsyncMock) as mock_search:
                mock_search.side_effect = Exception("API Error")
                
                with pytest.raises(ToolError) as exc_info:
                    await congressional_records_communications_hub(
                        ctx,
                        operation="search_congressional_record",
                        year=2022
                    )
                
                assert "Error executing operation" in str(exc_info.value)
                assert "search_congressional_record" in str(exc_info.value)
