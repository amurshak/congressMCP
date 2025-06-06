"""
Test suite for Congressional People & Relationships Hub bucket tool.

Tests operation-level access control and parameter routing across
member and committee operations.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastmcp import Context
from fastmcp.exceptions import ToolError

from congress_api.features.buckets.people_relationships_hub import (
    congressional_people_relationships_hub,
    check_operation_access,
    route_people_relationships_operation,
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
        with patch('congress_api.features.buckets.people_relationships_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.FREE):
            yield ctx
    
    @pytest.fixture
    def mock_context_pro(self):
        """Mock context for Pro tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.people_relationships_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.PRO):
            yield ctx
    
    def test_free_operations_accessible_to_all_tiers(self, mock_context_free, mock_context_pro):
        """Test that free operations are accessible to all user tiers."""
        for operation in FREE_OPERATIONS:
            # Should not raise any exception for any tier
            check_operation_access(mock_context_free, operation)
            check_operation_access(mock_context_pro, operation)
    
    def test_paid_operations_blocked_for_free_tier(self, mock_context_free):
        """Test that paid operations are blocked for free tier users."""
        for operation in PAID_OPERATIONS:
            with pytest.raises(ToolError, match="requires a paid subscription"):
                check_operation_access(mock_context_free, operation)
    
    def test_paid_operations_accessible_to_paid_tier(self, mock_context_pro):
        """Test that paid operations are accessible to Pro tier."""
        for operation in PAID_OPERATIONS:
            # Should not raise any exception for paid tier
            check_operation_access(mock_context_pro, operation)
    
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
    async def test_member_operations_routing(self, mock_context):
        """Test that member operations route to correct functions."""
        
        with patch('congress_api.features.members.search_members', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock member search results"
            
            result = await route_people_relationships_operation(
                mock_context, 
                "search_members", 
                name="Smith",
                state="CA",
                limit=5
            )
            
            mock_search.assert_called_once_with(
                mock_context,
                name="Smith",
                state="CA",
                limit=5
            )
            assert result == "mock member search results"
    
    @pytest.mark.asyncio
    async def test_committee_operations_routing(self, mock_context):
        """Test that committee operations route to correct functions."""
        
        with patch('congress_api.features.committees.search_committees', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock committee search results"
            
            result = await route_people_relationships_operation(
                mock_context,
                "search_committees",
                keywords="agriculture",
                chamber="house"
            )
            
            mock_search.assert_called_once_with(
                mock_context,
                keywords="agriculture", 
                chamber="house"
            )
            assert result == "mock committee search results"
    
    @pytest.mark.asyncio
    async def test_advanced_member_operations_routing(self, mock_context):
        """Test that advanced member operations route correctly."""
        
        with patch('congress_api.features.members.get_member_sponsored_legislation', new_callable=AsyncMock) as mock_legislation:
            mock_legislation.return_value = "mock sponsored legislation"
            
            result = await route_people_relationships_operation(
                mock_context,
                "get_member_sponsored_legislation",
                bioguide_id="A000055"
            )
            
            mock_legislation.assert_called_once_with(
                mock_context,
                bioguide_id="A000055"
            )
            assert result == "mock sponsored legislation"
    
    @pytest.mark.asyncio
    async def test_unknown_operation_routing_error(self, mock_context):
        """Test that unknown operations raise routing errors."""
        
        with pytest.raises(ToolError, match="Unknown operation: invalid_operation"):
            await route_people_relationships_operation(mock_context, "invalid_operation")


class TestBucketToolIntegration:
    """Test the main bucket tool function with full integration."""
    
    @pytest.fixture
    def mock_context_free(self):
        """Mock context for free tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.people_relationships_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.FREE):
            yield ctx
    
    @pytest.fixture
    def mock_context_pro(self):
        """Mock context for Pro tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.people_relationships_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.PRO):
            yield ctx
    
    @pytest.mark.asyncio
    async def test_free_user_can_access_free_operations(self, mock_context_free):
        """Test that free users can access free operations."""
        
        with patch('congress_api.features.members.search_members', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock member search results"
            
            result = await congressional_people_relationships_hub(
                mock_context_free,
                operation="search_members",
                name="Smith",
                state="CA"
            )
            
            assert result == "mock member search results"
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_free_user_blocked_from_paid_operations(self, mock_context_free):
        """Test that free users are blocked from paid operations."""
        
        with pytest.raises(ToolError, match="requires a paid subscription"):
            await congressional_people_relationships_hub(
                mock_context_free,
                operation="get_member_sponsored_legislation",  # This is a paid operation
                bioguide_id="A000055"
            )
    
    @pytest.mark.asyncio
    async def test_paid_user_can_access_all_operations(self, mock_context_pro):
        """Test that paid users can access both free and paid operations."""
        
        # Test free operation
        with patch('congress_api.features.members.search_members', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock member search results"
            
            result = await congressional_people_relationships_hub(
                mock_context_pro,
                operation="search_members",
                name="Smith"
            )
            
            assert result == "mock member search results"
        
        # Test paid operation
        with patch('congress_api.features.members.get_member_sponsored_legislation', new_callable=AsyncMock) as mock_legislation:
            mock_legislation.return_value = "mock sponsored legislation"
            
            result = await congressional_people_relationships_hub(
                mock_context_pro,
                operation="get_member_sponsored_legislation",
                bioguide_id="A000055"
            )
            
            assert result == "mock sponsored legislation"
    
    @pytest.mark.asyncio
    async def test_parameter_filtering_and_passing(self, mock_context_pro):
        """Test that parameters are correctly filtered and passed to operations."""
        
        with patch('congress_api.features.members.get_member_details', new_callable=AsyncMock) as mock_details:
            mock_details.return_value = "mock member details"
            
            # Call with both relevant and irrelevant parameters
            result = await congressional_people_relationships_hub(
                mock_context_pro,
                operation="get_member_details",
                bioguide_id="A000055",
                state="CA",
                party="D",
                # These should be filtered out (not relevant to member details)
                keywords=None,  # Should be filtered out (None value)
                committee_code="test"
            )
            
            # Verify parameters were passed correctly
            mock_details.assert_called_once_with(
                mock_context_pro,
                bioguide_id="A000055",
                state="CA",
                party="D",
                committee_code="test"  # Currently all params passed, might refine later
            )
            assert result == "mock member details"
    
    @pytest.mark.asyncio
    async def test_committee_operations_integration(self, mock_context_pro):
        """Test committee operations work through the bucket."""
        
        with patch('congress_api.features.committees.get_committee_bills', new_callable=AsyncMock) as mock_bills:
            mock_bills.return_value = "mock committee bills"
            
            result = await congressional_people_relationships_hub(
                mock_context_pro,
                operation="get_committee_bills",
                chamber="house",
                committee_code="hsag",
                limit=10
            )
            
            mock_bills.assert_called_once_with(
                mock_context_pro,
                chamber="house",
                committee_code="hsag",
                limit=10
            )
            assert result == "mock committee bills"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
