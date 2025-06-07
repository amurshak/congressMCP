"""
Test suite for Congressional Voting & Political Processes Hub bucket tool.

Tests operation-level access control and parameter routing across
voting and nomination operations.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastmcp import Context
from fastmcp.exceptions import ToolError

from congress_api.features.buckets.voting_political_hub import (
    congressional_voting_political_hub,
    check_operation_access,
    route_voting_political_operation,
    FREE_OPERATIONS,
    PAID_OPERATIONS
)
from congress_api.core.auth.auth import SubscriptionTier


class TestOperationAccessControl:
    """Test operation-level access control for different user tiers."""
    
    @pytest.fixture
    def mock_context_free(self):
        """Mock context for free tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.voting_political_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.FREE):
            yield ctx
    
    @pytest.fixture
    def mock_context_pro(self):
        """Mock context for Pro tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.voting_political_hub.get_user_tier_from_context', 
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


class TestParameterRouting:
    """Test parameter routing to underlying tool functions."""
    
    @pytest.fixture
    def mock_context(self):
        """Mock context for routing tests."""
        return Mock(spec=Context)
    
    @pytest.mark.asyncio
    async def test_voting_operations_routing(self, mock_context):
        """Test that voting operations route to correct functions."""
        
        with patch('congress_api.features.house_votes.get_house_votes_by_congress', new_callable=AsyncMock) as mock_votes:
            mock_votes.return_value = "mock house votes results"
            
            result = await route_voting_political_operation(
                mock_context, 
                "get_house_votes_by_congress", 
                congress=118,
                limit=20
            )
            
            mock_votes.assert_called_once_with(
                mock_context,
                congress=118,
                limit=20
            )
            assert result == "mock house votes results"
    
    @pytest.mark.asyncio
    async def test_nomination_operations_routing(self, mock_context):
        """Test that nomination operations route to correct functions."""
        
        with patch('congress_api.features.nominations.search_nominations', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock nomination search results"
            
            result = await route_voting_political_operation(
                mock_context,
                "search_nominations",
                keywords="supreme court",
                congress=118
            )
            
            mock_search.assert_called_once_with(
                mock_context,
                keywords="supreme court", 
                congress=118
            )
            assert result == "mock nomination search results"


class TestBucketToolIntegration:
    """Test the main bucket tool function with full integration."""
    
    @pytest.fixture
    def mock_context_free(self):
        """Mock context for free tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.voting_political_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.FREE):
            yield ctx
    
    @pytest.fixture
    def mock_context_pro(self):
        """Mock context for Pro tier user."""
        ctx = Mock(spec=Context)
        with patch('congress_api.features.buckets.voting_political_hub.get_user_tier_from_context', 
                   return_value=SubscriptionTier.PRO):
            yield ctx
    
    @pytest.mark.asyncio
    async def test_free_user_can_access_free_operations(self, mock_context_free):
        """Test that free users can access free operations."""
        
        with patch('congress_api.features.house_votes.get_house_votes_by_congress', new_callable=AsyncMock) as mock_votes:
            mock_votes.return_value = "mock house votes"
            
            result = await congressional_voting_political_hub(
                mock_context_free,
                operation="get_house_votes_by_congress",
                congress=118
            )
            
            assert result == "mock house votes"
            mock_votes.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_free_user_blocked_from_paid_operations(self, mock_context_free):
        """Test that free users are blocked from paid operations."""
        
        with pytest.raises(ToolError, match="requires a paid subscription"):
            await congressional_voting_political_hub(
                mock_context_free,
                operation="get_house_vote_details",  # This is a paid operation
                congress=118,
                session=1,
                vote_number=1
            )
    
    @pytest.mark.asyncio
    async def test_paid_user_can_access_all_operations(self, mock_context_pro):
        """Test that paid users can access both free and paid operations."""
        
        # Test free operation
        with patch('congress_api.features.nominations.search_nominations', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "mock nomination search"
            
            result = await congressional_voting_political_hub(
                mock_context_pro,
                operation="search_nominations",
                keywords="judge"
            )
            
            assert result == "mock nomination search"
        
        # Test paid operation
        with patch('congress_api.features.nominations.get_nomination_details', new_callable=AsyncMock) as mock_details:
            mock_details.return_value = "mock nomination details"
            
            result = await congressional_voting_political_hub(
                mock_context_pro,
                operation="get_nomination_details",
                congress=118,
                nomination_number=123
            )
            
            assert result == "mock nomination details"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
