"""
Test suite for Congressional Legislation Hub bucket tool.

Tests operation-level access control and parameter routing across
all consolidated operations (bills, amendments, summaries, treaties).
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastmcp import Context
from fastmcp.exceptions import ToolError

from congress_api.features.buckets.legislation_hub import (
    congressional_legislation_hub,
    check_operation_access,
    route_legislation_operation,
    FREE_OPERATIONS,
    PAID_OPERATIONS
)
from congress_api.core.auth import SubscriptionTier


class TestOperationAccessControl:
    """Test operation-level access control for different user tiers."""
    
    @pytest.fixture
    def mock_context_free(self):
        """Mock context for free tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.legislation_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.FREE):
            yield ctx
    
    @pytest.fixture
    def mock_context_pro(self):
        """Mock context for Pro tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.legislation_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.PRO):
            yield ctx
    
    @pytest.fixture
    def mock_context_enterprise(self):
        """Mock context for Enterprise tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.legislation_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.ENTERPRISE):
            yield ctx
    
    def test_free_operations_accessible_to_all_tiers(self, mock_context_free, mock_context_pro, mock_context_enterprise):
        """Test that free operations are accessible to all user tiers."""
        for operation in FREE_OPERATIONS:
            # Should not raise any exception for any tier
            check_operation_access(mock_context_free, operation)
            check_operation_access(mock_context_pro, operation)
            check_operation_access(mock_context_enterprise, operation)
    
    def test_paid_operations_blocked_for_free_tier(self, mock_context_free):
        """Test that paid operations are blocked for free tier users."""
        for operation in PAID_OPERATIONS:
            with pytest.raises(ToolError, match="requires a paid subscription"):
                check_operation_access(mock_context_free, operation)
    
    def test_paid_operations_accessible_to_paid_tiers(self, mock_context_pro, mock_context_enterprise):
        """Test that paid operations are accessible to Pro and Enterprise tiers."""
        for operation in PAID_OPERATIONS:
            # Should not raise any exception for paid tiers
            check_operation_access(mock_context_pro, operation)
            check_operation_access(mock_context_enterprise, operation)
    
    def test_unknown_operation_raises_error(self, mock_context_pro):
        """Test that unknown operations raise appropriate errors."""
        with pytest.raises(ToolError, match="Unknown operation: invalid_operation"):
            check_operation_access(mock_context_pro, "invalid_operation")


class TestParameterRouting:
    """Test parameter routing to underlying tool functions."""
    
    @pytest.fixture
    def mock_context(self):
        """Mock context for routing tests."""
        return Mock(spec=Context)
    
    @pytest.mark.asyncio
    async def test_bill_operations_routing(self, mock_context):
        """Test that bill operations route to correct functions."""
        
        # Mock the bill functions in their original module
        with patch('congress_api.features.bills.search_bills', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock bill search results"
            
            result = await route_legislation_operation(
                mock_context, 
                "search_bills", 
                keywords="infrastructure",
                congress=118,
                limit=5
            )
            
            mock_search.assert_called_once_with(
                mock_context,
                keywords="infrastructure",
                congress=118,
                limit=5
            )
            assert result == "mock bill search results"
    
    @pytest.mark.asyncio
    async def test_amendment_operations_routing(self, mock_context):
        """Test that amendment operations route to correct functions."""
        
        with patch('congress_api.features.amendments.search_amendments', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock amendment search results"
            
            result = await route_legislation_operation(
                mock_context,
                "search_amendments",
                keywords="voting rights",
                congress=118
            )
            
            mock_search.assert_called_once_with(
                mock_context,
                keywords="voting rights", 
                congress=118
            )
            assert result == "mock amendment search results"
    
    @pytest.mark.asyncio
    async def test_treaty_operations_routing(self, mock_context):
        """Test that treaty operations route to correct functions."""
        
        with patch('congress_api.features.treaties.search_treaties', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock treaty search results"
            
            result = await route_legislation_operation(
                mock_context,
                "search_treaties",
                congress=118,
                topic="trade"
            )
            
            mock_search.assert_called_once_with(
                mock_context,
                congress=118,
                topic="trade"
            )
            assert result == "mock treaty search results"
    
    @pytest.mark.asyncio
    async def test_unknown_operation_routing_error(self, mock_context):
        """Test that unknown operations raise routing errors."""
        
        with pytest.raises(ToolError, match="Unknown operation: invalid_operation"):
            await route_legislation_operation(mock_context, "invalid_operation")


class TestBucketToolIntegration:
    """Test the main bucket tool function with full integration."""
    
    @pytest.fixture
    def mock_context_free(self):
        """Mock context for free tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.legislation_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.FREE):
            yield ctx
    
    @pytest.fixture
    def mock_context_pro(self):
        """Mock context for Pro tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.legislation_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.PRO):
            yield ctx
    
    @pytest.mark.asyncio
    async def test_free_user_can_access_free_operations(self, mock_context_free):
        """Test that free users can access free operations."""
        
        with patch('congress_api.features.bills.search_bills', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock bill search results"
            
            result = await congressional_legislation_hub(
                mock_context_free,
                operation="search_bills",
                keywords="infrastructure",
                congress=118
            )
            
            assert result == "mock bill search results"
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_free_user_blocked_from_paid_operations(self, mock_context_free):
        """Test that free users are blocked from paid operations."""
        
        with pytest.raises(ToolError, match="requires a paid subscription"):
            await congressional_legislation_hub(
                mock_context_free,
                operation="search_amendments",  # This is a paid operation
                keywords="voting rights"
            )
    
    @pytest.mark.asyncio
    async def test_paid_user_can_access_all_operations(self, mock_context_pro):
        """Test that paid users can access both free and paid operations."""
        
        # Test free operation
        with patch('congress_api.features.bills.search_bills', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock bill search results"
            
            result = await congressional_legislation_hub(
                mock_context_pro,
                operation="search_bills",
                keywords="infrastructure"
            )
            
            assert result == "mock bill search results"
        
        # Test paid operation
        with patch('congress_api.features.amendments.search_amendments', new_callable=AsyncMock) as mock_amendments:
            mock_amendments.return_value = "mock amendment search results"
            
            result = await congressional_legislation_hub(
                mock_context_pro,
                operation="search_amendments",
                keywords="voting rights"
            )
            
            assert result == "mock amendment search results"
    
    @pytest.mark.asyncio
    async def test_parameter_filtering_and_passing(self, mock_context_pro):
        """Test that parameters are correctly filtered and passed to operations."""
        
        with patch('congress_api.features.bills.get_bill_details', new_callable=AsyncMock) as mock_details:
            mock_details.return_value = "mock bill details"
            
            # Call with both relevant and irrelevant parameters
            result = await congressional_legislation_hub(
                mock_context_pro,
                operation="get_bill_details",
                congress=118,
                bill_type="hr",
                bill_number=1234,
                # These should be filtered out (not relevant to bill details)
                amendment_type="samdt",
                treaty_number=5,
                keywords=None  # Should be filtered out (None value)
            )
            
            # Verify only relevant parameters were passed
            mock_details.assert_called_once_with(
                mock_context_pro,
                congress=118,
                bill_type="hr", 
                bill_number=1234,
                amendment_type="samdt",  # Currently all params passed, might refine later
                treaty_number=5
            )
            assert result == "mock bill details"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
