"""
Test suite for Congressional Committee Intelligence Hub bucket tool.

Tests operation-level access control, parameter routing, and integration functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastmcp import Context
from fastmcp.exceptions import ToolError

from congress_api.features.buckets.committee_intelligence_hub import (
    congressional_committee_intelligence_hub,
    check_operation_access,
    route_committee_intelligence_operation,
    FREE_OPERATIONS,
    PAID_OPERATIONS
)
from congress_api.core.auth.auth import SubscriptionTier


class TestCommitteeIntelligenceHubAccessControl:
    """Test operation-level access control for Committee Intelligence Hub."""
    
    def test_no_free_operations(self):
        """Test that there are no free operations (all are paid)."""
        assert len(FREE_OPERATIONS) == 0
        assert len(PAID_OPERATIONS) > 0
    
    def test_all_operations_blocked_for_free_tier(self):
        """Test that all operations are blocked for free tier users."""
        ctx = MagicMock()
        with patch('congress_api.features.buckets.committee_intelligence_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            # Should raise ToolError for all operations (all are paid)
            for operation in list(PAID_OPERATIONS)[:5]:  # Test first 5 operations
                with pytest.raises(ToolError) as exc_info:
                    check_operation_access(ctx, operation)
                assert "requires a paid subscription" in str(exc_info.value)
                assert "free" in str(exc_info.value).lower()
    
    def test_all_operations_accessible_to_paid_tiers(self):
        """Test that all operations are accessible to paid tier users."""
        ctx = MagicMock()
        
        for tier in [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]:
            with patch('congress_api.features.buckets.committee_intelligence_hub.get_user_tier_from_context') as mock_get_tier:
                mock_get_tier.return_value = tier
                
                # Should not raise an error for any operation
                for operation in PAID_OPERATIONS:
                    check_operation_access(ctx, operation)
    
    def test_invalid_operation_raises_error(self):
        """Test that invalid operation raises ToolError."""
        ctx = MagicMock()
        with patch('congress_api.features.buckets.committee_intelligence_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with pytest.raises(ToolError) as exc_info:
                check_operation_access(ctx, "invalid_operation")
            assert "Unknown operation" in str(exc_info.value)


class TestCommitteeIntelligenceHubRouting:
    """Test operation routing functionality."""
    
    @pytest.mark.asyncio
    async def test_committee_report_operations_routing(self):
        """Test routing for committee report operations."""
        ctx = MagicMock()
        
        operations_map = {
            "get_latest_committee_reports": "congress_api.features.committee_reports.get_latest_committee_reports",
            "get_committee_report_details": "congress_api.features.committee_reports.get_committee_report_details",
            "get_committee_report_content": "congress_api.features.committee_reports.get_committee_report_content"
        }
        
        for operation, mock_path in operations_map.items():
            with patch(mock_path, new_callable=AsyncMock) as mock_func:
                mock_func.return_value = f"Mock result for {operation}"
                
                result = await route_committee_intelligence_operation(
                    ctx, operation, congress=117, report_type="hrpt"
                )
                
                mock_func.assert_called_once_with(ctx, congress=117, report_type="hrpt")
                assert result == f"Mock result for {operation}"
    
    @pytest.mark.asyncio
    async def test_committee_print_operations_routing(self):
        """Test routing for committee print operations."""
        ctx = MagicMock()
        
        operations_map = {
            "get_latest_committee_prints": "congress_api.features.committee_prints.get_latest_committee_prints",
            "get_committee_print_details": "congress_api.features.committee_prints.get_committee_print_details"
        }
        
        for operation, mock_path in operations_map.items():
            with patch(mock_path, new_callable=AsyncMock) as mock_func:
                mock_func.return_value = f"Mock result for {operation}"
                
                result = await route_committee_intelligence_operation(
                    ctx, operation, congress=117, chamber="house"
                )
                
                mock_func.assert_called_once_with(ctx, congress=117, chamber="house")
                assert result == f"Mock result for {operation}"
    
    @pytest.mark.asyncio
    async def test_committee_meeting_operations_routing(self):
        """Test routing for committee meeting operations."""
        ctx = MagicMock()
        
        operations_map = {
            "get_latest_committee_meetings": "congress_api.features.committee_meetings.get_latest_committee_meetings",
            "get_committee_meeting_details": "congress_api.features.committee_meetings.get_committee_meeting_details",
            "search_committee_meetings": "congress_api.features.committee_meetings.search_committee_meetings"
        }
        
        for operation, mock_path in operations_map.items():
            with patch(mock_path, new_callable=AsyncMock) as mock_func:
                mock_func.return_value = f"Mock result for {operation}"
                
                result = await route_committee_intelligence_operation(
                    ctx, operation, congress=117, committee_code="hsag00"
                )
                
                mock_func.assert_called_once_with(ctx, congress=117, committee_code="hsag00")
                assert result == f"Mock result for {operation}"
    
    @pytest.mark.asyncio
    async def test_invalid_operation_routing_raises_error(self):
        """Test that invalid operation raises ToolError in routing."""
        ctx = MagicMock()
        
        with pytest.raises(ToolError) as exc_info:
            await route_committee_intelligence_operation(ctx, "invalid_operation")
        assert "Unknown operation" in str(exc_info.value)


class TestCommitteeIntelligenceHubIntegration:
    """Test full bucket tool integration."""
    
    @pytest.mark.asyncio
    async def test_bucket_tool_all_operations_blocked_for_free_tier(self):
        """Test that all operations are blocked for free tier."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.committee_intelligence_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            with pytest.raises(ToolError) as exc_info:
                await congressional_committee_intelligence_hub(
                    ctx,
                    operation="get_latest_committee_reports"
                )
            
            assert "requires a paid subscription" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_bucket_tool_paid_operation_success_for_paid_tier(self):
        """Test successful execution of paid operation for paid tier."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.committee_intelligence_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.committee_reports.get_committee_report_details', new_callable=AsyncMock) as mock_get_details:
                mock_get_details.return_value = "Mock committee report details"
                
                result = await congressional_committee_intelligence_hub(
                    ctx,
                    operation="get_committee_report_details",
                    congress=117,
                    report_type="hrpt",
                    report_number=123
                )
                
                mock_get_details.assert_called_once_with(
                    ctx, congress=117, report_type="hrpt", report_number=123
                )
                assert result == "Mock committee report details"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_parameter_filtering(self):
        """Test that only relevant parameters are passed to underlying functions."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.committee_intelligence_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.ENTERPRISE
            
            with patch('congress_api.features.committee_meetings.search_committee_meetings', new_callable=AsyncMock) as mock_search:
                mock_search.return_value = "Mock meeting results"
                
                result = await congressional_committee_intelligence_hub(
                    ctx,
                    operation="search_committee_meetings",
                    keywords="agriculture",
                    congress=117,
                    chamber="house",
                    # These parameters should be filtered out as None
                    report_number=None,
                    jacket_number=None
                )
                
                # Only non-None parameters should be passed
                mock_search.assert_called_once_with(
                    ctx, keywords="agriculture", congress=117, chamber="house"
                )
                assert result == "Mock meeting results"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_chunking_parameters(self):
        """Test handling of content chunking parameters."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.committee_intelligence_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.committee_reports.get_committee_report_content', new_callable=AsyncMock) as mock_content:
                mock_content.return_value = "Mock chunked content"
                
                result = await congressional_committee_intelligence_hub(
                    ctx,
                    operation="get_committee_report_content",
                    congress=117,
                    report_type="hrpt",
                    report_number=123,
                    chunk_number=2,
                    chunk_size=5000
                )
                
                mock_content.assert_called_once_with(
                    ctx, 
                    congress=117, 
                    report_type="hrpt", 
                    report_number=123,
                    chunk_number=2,
                    chunk_size=5000
                )
                assert result == "Mock chunked content"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_error_handling(self):
        """Test proper error handling and logging."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.committee_intelligence_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.committee_reports.get_latest_committee_reports', new_callable=AsyncMock) as mock_latest:
                mock_latest.side_effect = Exception("API Error")
                
                with pytest.raises(ToolError) as exc_info:
                    await congressional_committee_intelligence_hub(
                        ctx,
                        operation="get_latest_committee_reports"
                    )
                
                assert "Error executing operation" in str(exc_info.value)
                assert "get_latest_committee_reports" in str(exc_info.value)
