"""
Test suite for Congressional Research & Professional Services Hub bucket tool.

Tests operation-level access control, parameter routing, and integration functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastmcp import Context
from fastmcp.exceptions import ToolError

from congress_api.features.buckets.research_professional_hub import (
    congressional_research_professional_hub,
    check_operation_access,
    route_research_professional_operation,
    FREE_OPERATIONS,
    PAID_OPERATIONS
)
from congress_api.core.auth.auth import SubscriptionTier


class TestResearchProfessionalHubAccessControl:
    """Test operation-level access control for Research & Professional Hub."""
    
    def test_free_operations_accessible_to_free_tier(self):
        """Test that free operations are accessible to free tier users."""
        # Mock context with free tier user
        ctx = MagicMock()
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            # Should not raise an error for free operations
            for operation in FREE_OPERATIONS:
                check_operation_access(ctx, operation)
    
    def test_paid_operations_blocked_for_free_tier(self):
        """Test that paid operations are blocked for free tier users."""
        ctx = MagicMock()
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
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
            with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
                mock_get_tier.return_value = tier
                
                # Should not raise an error for any operation
                for operation in FREE_OPERATIONS | PAID_OPERATIONS:
                    check_operation_access(ctx, operation)
    
    def test_invalid_operation_raises_error(self):
        """Test that invalid operation raises ToolError."""
        ctx = MagicMock()
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with pytest.raises(ToolError) as exc_info:
                check_operation_access(ctx, "invalid_operation")
            assert "Unknown operation" in str(exc_info.value)


class TestResearchProfessionalHubRouting:
    """Test operation routing functionality."""
    
    @pytest.mark.asyncio
    async def test_congress_info_operations_routing(self):
        """Test routing for congress information operations."""
        ctx = MagicMock()
        
        operations_map = {
            "get_congress_info": "congress_api.features.congress_info.get_congress_info",
            "search_congresses": "congress_api.features.congress_info.search_congresses"
        }
        
        for operation, mock_path in operations_map.items():
            with patch(mock_path, new_callable=AsyncMock) as mock_func:
                mock_func.return_value = f"Mock result for {operation}"
                
                result = await route_research_professional_operation(
                    ctx, operation, congress=117, limit=10
                )
                
                mock_func.assert_called_once_with(ctx, congress=117, limit=10)
                assert result == f"Mock result for {operation}"
    
    @pytest.mark.asyncio
    async def test_enhanced_congress_info_routing(self):
        """Test routing for enhanced congress info operation."""
        ctx = MagicMock()
        
        with patch('congress_api.features.congress_info.get_congress_info', new_callable=AsyncMock) as mock_func:
            mock_func.return_value = "Enhanced congress info"
            
            result = await route_research_professional_operation(
                ctx, "get_congress_info_enhanced", congress=117
            )
            
            # Should call with detailed=True for enhanced mode
            mock_func.assert_called_once_with(ctx, congress=117, detailed=True)
            assert result == "Enhanced congress info"
    
    @pytest.mark.asyncio
    async def test_crs_reports_routing(self):
        """Test routing for CRS reports operations."""
        ctx = MagicMock()
        
        with patch('congress_api.features.crs_reports.search_crs_reports', new_callable=AsyncMock) as mock_func:
            mock_func.return_value = "Mock CRS reports"
            
            result = await route_research_professional_operation(
                ctx, "search_crs_reports", keywords="climate", limit=5
            )
            
            mock_func.assert_called_once_with(ctx, keywords="climate", limit=5)
            assert result == "Mock CRS reports"
    
    @pytest.mark.asyncio
    async def test_future_features_routing(self):
        """Test routing for future professional features."""
        ctx = MagicMock()
        
        future_operations = ["get_congress_statistics", "get_legislative_analysis"]
        
        for operation in future_operations:
            with pytest.raises(ToolError) as exc_info:
                await route_research_professional_operation(ctx, operation)
            assert "coming soon" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_invalid_operation_routing_raises_error(self):
        """Test that invalid operation raises ToolError in routing."""
        ctx = MagicMock()
        
        with pytest.raises(ToolError) as exc_info:
            await route_research_professional_operation(ctx, "invalid_operation")
        assert "Unknown operation" in str(exc_info.value)


class TestResearchProfessionalHubIntegration:
    """Test full bucket tool integration."""
    
    @pytest.mark.asyncio
    async def test_bucket_tool_free_operation_success(self):
        """Test successful execution of free operation."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            with patch('congress_api.features.congress_info.get_congress_info', new_callable=AsyncMock) as mock_info:
                mock_info.return_value = "Mock congress info"
                
                result = await congressional_research_professional_hub(
                    ctx,
                    operation="get_congress_info",
                    congress=117,
                    detailed=False
                )
                
                mock_info.assert_called_once_with(ctx, congress=117, detailed=False)
                assert result == "Mock congress info"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_paid_operation_blocked_for_free_tier(self):
        """Test that paid operations are blocked for free tier."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.FREE
            
            with pytest.raises(ToolError) as exc_info:
                await congressional_research_professional_hub(
                    ctx,
                    operation="search_crs_reports",
                    keywords="climate change"
                )
            
            assert "requires a paid subscription" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_bucket_tool_paid_operation_success_for_paid_tier(self):
        """Test successful execution of paid operation for paid tier."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.crs_reports.search_crs_reports', new_callable=AsyncMock) as mock_search:
                mock_search.return_value = "Mock CRS report results"
                
                result = await congressional_research_professional_hub(
                    ctx,
                    operation="search_crs_reports",
                    keywords="healthcare",
                    limit=20
                )
                
                mock_search.assert_called_once_with(ctx, keywords="healthcare", limit=20)
                assert result == "Mock CRS report results"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_enhanced_operation_success(self):
        """Test successful execution of enhanced congress info operation."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.ENTERPRISE
            
            with patch('congress_api.features.congress_info.get_congress_info', new_callable=AsyncMock) as mock_info:
                mock_info.return_value = "Enhanced congress analytics"
                
                result = await congressional_research_professional_hub(
                    ctx,
                    operation="get_congress_info_enhanced",
                    congress=118
                )
                
                # Should add detailed=True for enhanced mode
                mock_info.assert_called_once_with(ctx, congress=118, detailed=True)
                assert result == "Enhanced congress analytics"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_parameter_filtering(self):
        """Test that only relevant parameters are passed to underlying functions."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.congress_info.search_congresses', new_callable=AsyncMock) as mock_search:
                mock_search.return_value = "Mock congress search results"
                
                result = await congressional_research_professional_hub(
                    ctx,
                    operation="search_congresses",
                    keywords="civil rights",
                    start_year=2000,
                    end_year=2020,
                    # These parameters should be filtered out as None
                    congress=None,
                    report_number=None
                )
                
                # Only non-None parameters should be passed
                mock_search.assert_called_once_with(
                    ctx, keywords="civil rights", start_year=2000, end_year=2020
                )
                assert result == "Mock congress search results"
    
    @pytest.mark.asyncio
    async def test_bucket_tool_error_handling(self):
        """Test proper error handling and logging."""
        ctx = MagicMock()
        
        with patch('congress_api.features.buckets.research_professional_hub.get_user_tier_from_context') as mock_get_tier:
            mock_get_tier.return_value = SubscriptionTier.PRO
            
            with patch('congress_api.features.congress_info.get_congress_info', new_callable=AsyncMock) as mock_info:
                mock_info.side_effect = Exception("API Error")
                
                with pytest.raises(ToolError) as exc_info:
                    await congressional_research_professional_hub(
                        ctx,
                        operation="get_congress_info",
                        congress=117
                    )
                
                assert "Error executing operation" in str(exc_info.value)
                assert "get_congress_info" in str(exc_info.value)
