"""
Amendments Response Formatters - Presentation logic for amendment data.

This module contains presentation logic only:
- Markdown formatting for amendment responses
- Response structuring and organization
- No business logic or API calls
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class AmendmentsFormatter:
    """
    Handles formatting of amendment data for user presentation.

    This class contains pure presentation logic without business logic or API calls.
    """

    @staticmethod
    def format_amendment_summary(amendment: Dict[str, Any]) -> str:
        """Format an amendment into a readable summary."""
        result = []
        result.append(f"Amendment: {amendment.get('number', 'Unknown')}")
        result.append(f"Type: {amendment.get('type', 'Unknown')}")
        result.append(f"Congress: {amendment.get('congress', 'Unknown')}")

        if "purpose" in amendment:
            result.append(f"Purpose: {amendment.get('purpose', 'Not specified')}")

        if "latestAction" in amendment:
            action = amendment["latestAction"]
            result.append(f"Latest Action: {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")

        result.append(f"URL: {amendment.get('url', 'No URL available')}")
        return "\n".join(result)

    @staticmethod
    def format_amendment_details(amendment: Dict[str, Any]) -> str:
        """Format detailed amendment information."""
        result = []

        # Basic information
        result.append(f"# Amendment {amendment.get('number', 'Unknown')} - {amendment.get('congress', 'Unknown')}th Congress\n")

        if "type" in amendment:
            result.append(f"## Type\n{amendment['type']}\n")

        if "purpose" in amendment:
            result.append(f"## Purpose\n{amendment['purpose']}\n")

        if "description" in amendment:
            result.append(f"## Description\n{amendment['description']}\n")

        if "sponsors" in amendment and amendment["sponsors"]:
            sponsors = amendment["sponsors"]
            result.append("## Sponsors")
            for sponsor in sponsors:
                name = sponsor.get("name", "Unknown")
                party = sponsor.get("party", "")
                state = sponsor.get("state", "")
                bioguide_id = sponsor.get("bioguideId", "")
                result.append(f"- {name} ({party}-{state}), Bioguide ID: {bioguide_id}")
            result.append("")

        if "actions" in amendment and amendment["actions"]:
            actions = amendment["actions"]
            result.append("## Recent Actions")

            # Handle different data structures for actions
            if isinstance(actions, list):
                # If actions is a list, take up to 5 items
                action_items = actions[:5] if len(actions) > 5 else actions
            elif isinstance(actions, dict) and "item" in actions:
                # If actions is a dict with an 'item' key (common in Congress.gov API)
                items = actions["item"]
                if isinstance(items, list):
                    action_items = items[:5] if len(items) > 5 else items
                else:
                    # If there's only one item, wrap it in a list
                    action_items = [items]
            else:
                # If we can't determine the structure, just use an empty list
                logger.warning(f"Unexpected actions structure: {type(actions)}")
                action_items = []

            for action in action_items:
                date = action.get("actionDate", "Unknown date")
                text = action.get("text", "Unknown action")
                result.append(f"- {date}: {text}")
            result.append("")

        return "\n".join(result)

    @staticmethod
    def format_amendment_action(action: Dict[str, Any]) -> str:
        """Format an amendment action into a readable string."""
        result = []
        date = action.get("actionDate", "Unknown date")
        text = action.get("text", "Unknown action")
        result.append(f"- {date}: {text}")

        if "recordedVotes" in action and action["recordedVotes"]:
            votes = action["recordedVotes"]
            for vote in votes:
                chamber = vote.get("chamber", "Unknown")
                roll_number = vote.get("rollNumber", "Unknown")
                result.append(f"  - Recorded Vote: {chamber} Roll Call #{roll_number}")

        return "\n".join(result)

    @staticmethod
    def format_amendments_list(amendments: List[Dict[str, Any]], title: str = "Amendments", duplicates_removed: int = 0) -> str:
        """Format a list of amendments with title and metadata."""
        result = [f"# {title}\n"]

        if duplicates_removed > 0:
            result.append(f"*Found {len(amendments) + duplicates_removed} results ({duplicates_removed} duplicates removed)*\n")

        for amendment in amendments:
            result.append("---\n")
            result.append(AmendmentsFormatter.format_amendment_summary(amendment))

        return "\n\n".join(result)

    @staticmethod
    def format_amendment_actions_list(actions: List[Dict[str, Any]], amendment_type: str, amendment_number: int, congress: int, duplicates_removed: int = 0) -> str:
        """Format a list of amendment actions."""
        result = [f"# Actions for {amendment_type.upper()} {amendment_number} - {congress}th Congress"]

        if duplicates_removed > 0:
            result.append(f"*({duplicates_removed} duplicate actions removed)*")

        for action in actions:
            result.append(AmendmentsFormatter.format_amendment_action(action))

        return "\n".join(result)

    @staticmethod
    def format_amendment_sponsors_list(cosponsors: List[Dict[str, Any]], amendment_type: str, amendment_number: int, congress: int, duplicates_removed: int = 0) -> str:
        """Format a list of amendment sponsors/cosponsors."""
        result = [f"# Cosponsors for {amendment_type.upper()} {amendment_number} - {congress}th Congress"]

        if duplicates_removed > 0:
            result.append(f"*({duplicates_removed} duplicate cosponsors removed)*")

        result.append(f"Total: {len(cosponsors)} cosponsors\n")

        for cosponsor in cosponsors:
            name = cosponsor.get("name", "Unknown")
            party = cosponsor.get("party", "")
            state = cosponsor.get("state", "")
            district = cosponsor.get("district", "")

            sponsor_info = f"- **{name}**"
            if party:
                sponsor_info += f" ({party}"
                if state:
                    sponsor_info += f"-{state}"
                    if district:
                        sponsor_info += f"-{district}"
                sponsor_info += ")"
            elif state:
                sponsor_info += f" ({state})"

            if "sponsorshipDate" in cosponsor:
                sponsor_info += f" - Sponsored: {cosponsor['sponsorshipDate']}"

            result.append(sponsor_info)

        return "\n".join(result)