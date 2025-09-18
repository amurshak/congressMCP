"""
Bills Response Formatters - Presentation logic for bill data.

Contains all formatting and presentation logic for converting
bill data into markdown responses. No business logic or API calls.
"""

from typing import Dict, List, Any, Optional
import logging

# Set up logger
logger = logging.getLogger(__name__)


class BillsFormatter:
    """Handles all bill response formatting logic."""

    @staticmethod
    def format_bills_list(bills_response: Dict[str, Any], title: str = "Bills") -> str:
        """
        Format a list of bills into a markdown response.

        Args:
            bills_response: API response containing bills data
            title: Title for the response

        Returns:
            Formatted markdown string
        """
        try:
            if "error" in bills_response:
                return f"Error: {bills_response['error']}"

            bills = bills_response.get('bills', [])
            if not bills:
                return f"No {title.lower()} found."

            result = [f"## {title}", ""]

            for bill in bills:
                if isinstance(bill, dict):
                    bill_summary = BillsFormatter.format_bill_summary(bill)
                    result.append(bill_summary)
                    result.append("---")
                    result.append("")

            # Remove trailing separator
            if result and result[-3] == "---":
                result = result[:-3]

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting bills list: {str(e)}")
            return f"Error formatting bills: {str(e)}"

    @staticmethod
    def format_bill_summary(bill: Dict[str, Any]) -> str:
        """
        Format a bill into a brief readable summary.

        Args:
            bill: Bill dictionary from API

        Returns:
            Formatted bill summary
        """
        try:
            result = []

            # Basic info
            bill_id = f"{bill.get('type', 'Unknown')} {bill.get('number', 'Unknown')}"
            result.append(f"**{bill_id}** (Congress {bill.get('congress', 'Unknown')})")

            if "title" in bill:
                result.append(f"**Title:** {bill['title']}")

            # Latest action
            if "latestAction" in bill:
                action = bill["latestAction"]
                result.append(f"**Latest Action:** {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")

            # URL
            if "url" in bill:
                result.append(f"**URL:** {bill['url']}")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting bill summary: {str(e)}")
            return f"Error formatting bill: {str(e)}"

    @staticmethod
    def format_bill_detail(bill: Dict[str, Any]) -> str:
        """
        Format a bill into comprehensive detailed information.

        Args:
            bill: Bill dictionary from API

        Returns:
            Formatted detailed bill information
        """
        try:
            result = []

            # Header
            bill_id = f"{bill.get('type', 'Unknown')} {bill.get('number', 'Unknown')}"
            result.append(f"# {bill_id} - Congress {bill.get('congress', 'Unknown')}")
            result.append("")

            # Title
            if "title" in bill:
                result.append(f"**Title:** {bill['title']}")

            # Sponsors
            if "sponsors" in bill and bill["sponsors"]:
                sponsors = bill["sponsors"]
                sponsor_names = [s.get("fullName", "Unknown") for s in sponsors]
                result.append(f"**Sponsor{'s' if len(sponsor_names) > 1 else ''}:** {', '.join(sponsor_names)}")

            # Cosponsors
            if "cosponsors" in bill and "count" in bill["cosponsors"]:
                result.append(f"**Cosponsors:** {bill['cosponsors']['count']}")

            # Latest Action
            if "latestAction" in bill:
                action = bill["latestAction"]
                result.append(f"**Latest Action:** {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")

            # Committees
            if "committees" in bill and "count" in bill["committees"]:
                result.append(f"**Committees:** {bill['committees']['count']}")

            # Policy Area
            if "policyArea" in bill and "name" in bill["policyArea"]:
                result.append(f"**Policy Area:** {bill['policyArea']['name']}")

            # Subjects
            if "subjects" in bill and "count" in bill["subjects"]:
                result.append(f"**Subjects:** {bill['subjects']['count']}")

            # Text Versions
            if "textVersions" in bill and "count" in bill["textVersions"] and bill["textVersions"]["count"] > 0:
                result.append("**Text Versions Available:** Use get_bill_text_versions tool for text versions.")

            # URL
            if "url" in bill:
                result.append(f"\n**URL:** {bill['url']}")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting bill detail: {str(e)}")
            return f"Error formatting bill details: {str(e)}"

    @staticmethod
    def format_bill_actions(
        actions: List[Dict[str, Any]],
        congress: int,
        bill_type: str,
        bill_number: int
    ) -> str:
        """
        Format bill actions into a readable timeline.

        Args:
            actions: List of action dictionaries
            congress: Congress number
            bill_type: Bill type
            bill_number: Bill number

        Returns:
            Formatted actions timeline
        """
        try:
            if not actions:
                return f"No actions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."

            result = [f"## Legislative Actions Timeline for {bill_type.upper()} {bill_number} - {congress}th Congress", ""]

            for action in actions:
                action_date = action.get('actionDate', 'Unknown date')
                action_text = action.get('text', 'No description')
                action_type = action.get('type', '')

                result.append(f"**{action_date}** - {action_text}")
                if action_type:
                    result.append(f"  *Type: {action_type}*")
                result.append("")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting bill actions: {str(e)}")
            return f"Error formatting actions: {str(e)}"

    @staticmethod
    def format_bill_text_versions(versions: List[Dict[str, Any]]) -> str:
        """
        Format bill text versions into a readable list.

        Args:
            versions: List of text version dictionaries

        Returns:
            Formatted text versions list
        """
        try:
            if not versions:
                return "No text versions found."

            result = ["## Available Text Versions", ""]

            for version in versions:
                version_type = version.get('type', 'Unknown')
                date = version.get('date', 'Unknown date')

                result.append(f"**{version_type}** ({date})")

                if 'formats' in version:
                    for format_info in version['formats']:
                        format_type = format_info.get('type', 'Unknown format')
                        url = format_info.get('url', 'No URL')
                        result.append(f"  - {format_type}: {url}")

                result.append("")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting text versions: {str(e)}")
            return f"Error formatting text versions: {str(e)}"

    @staticmethod
    def format_bill_titles(titles: List[Dict[str, Any]]) -> str:
        """
        Format bill titles into a readable list.

        Args:
            titles: List of title dictionaries

        Returns:
            Formatted titles list
        """
        try:
            if not titles:
                return "No titles found."

            result = ["## Bill Titles", ""]

            for title in titles:
                title_text = title.get('title', 'Unknown title')
                title_type = title.get('titleType', 'Unknown type')

                result.append(f"**{title_type}:** {title_text}")
                result.append("")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting bill titles: {str(e)}")
            return f"Error formatting titles: {str(e)}"

    @staticmethod
    def format_bill_cosponsors(cosponsors: List[Dict[str, Any]]) -> str:
        """
        Format bill cosponsors into a readable list.

        Args:
            cosponsors: List of cosponsor dictionaries

        Returns:
            Formatted cosponsors list
        """
        try:
            if not cosponsors:
                return "No cosponsors found."

            result = ["## Bill Cosponsors", ""]

            for cosponsor in cosponsors:
                name = cosponsor.get('fullName', 'Unknown')
                party = cosponsor.get('party', 'Unknown')
                state = cosponsor.get('state', 'Unknown')
                date_cosponsored = cosponsor.get('dateCosponsored', 'Unknown date')

                result.append(f"**{name}** ({party}-{state}) - Cosponsored: {date_cosponsored}")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting cosponsors: {str(e)}")
            return f"Error formatting cosponsors: {str(e)}"

    @staticmethod
    def format_bill_subjects(subjects: List[Dict[str, Any]]) -> str:
        """
        Format bill subjects into a readable list.

        Args:
            subjects: List of subject dictionaries

        Returns:
            Formatted subjects list
        """
        try:
            if not subjects:
                return "No subjects found."

            result = ["## Bill Subjects", ""]

            for subject in subjects:
                name = subject.get('name', 'Unknown subject')
                result.append(f"- {name}")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting subjects: {str(e)}")
            return f"Error formatting subjects: {str(e)}"

    @staticmethod
    def format_bill_committees(committees: List[Dict[str, Any]]) -> str:
        """
        Format bill committees into a readable list.

        Args:
            committees: List of committee dictionaries

        Returns:
            Formatted committees list
        """
        try:
            if not committees:
                return "No committees found."

            result = ["## Bill Committees", ""]

            for committee in committees:
                name = committee.get('name', 'Unknown committee')
                chamber = committee.get('chamber', 'Unknown chamber')
                system_code = committee.get('systemCode', 'Unknown code')

                result.append(f"**{name}** ({chamber}) - Code: {system_code}")
                result.append("")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting committees: {str(e)}")
            return f"Error formatting committees: {str(e)}"

    @staticmethod
    def format_bill_related_bills(related_bills: List[Dict[str, Any]]) -> str:
        """
        Format related bills into a readable list.

        Args:
            related_bills: List of related bill dictionaries

        Returns:
            Formatted related bills list
        """
        try:
            if not related_bills:
                return "No related bills found."

            result = ["## Related Bills", ""]

            for related in related_bills:
                title = related.get('title', 'Unknown title')
                bill_type = related.get('type', 'Unknown')
                number = related.get('number', 'Unknown')
                congress = related.get('congress', 'Unknown')
                relationship = related.get('relationshipDetails', [])

                result.append(f"**{bill_type.upper()} {number}** (Congress {congress})")
                result.append(f"Title: {title}")

                if relationship:
                    for rel in relationship:
                        rel_type = rel.get('type', 'Unknown relationship')
                        result.append(f"Relationship: {rel_type}")

                result.append("")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting related bills: {str(e)}")
            return f"Error formatting related bills: {str(e)}"

    @staticmethod
    def format_bill_amendments(amendments: List[Dict[str, Any]]) -> str:
        """
        Format bill amendments into a readable list.

        Args:
            amendments: List of amendment dictionaries

        Returns:
            Formatted amendments list
        """
        try:
            if not amendments:
                return "No amendments found."

            result = ["## Bill Amendments", ""]

            for amendment in amendments:
                amendment_type = amendment.get('type', 'Unknown')
                number = amendment.get('number', 'Unknown')
                purpose = amendment.get('purpose', 'No purpose specified')
                sponsor = amendment.get('sponsors', [])

                result.append(f"**{amendment_type} {number}**")
                result.append(f"Purpose: {purpose}")

                if sponsor:
                    sponsor_name = sponsor[0].get('fullName', 'Unknown') if sponsor else 'Unknown'
                    result.append(f"Sponsor: {sponsor_name}")

                result.append("")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting amendments: {str(e)}")
            return f"Error formatting amendments: {str(e)}"

    @staticmethod
    def format_bill_summaries(summaries: List[Dict[str, Any]]) -> str:
        """
        Format bill summaries into a readable list.

        Args:
            summaries: List of summary dictionaries

        Returns:
            Formatted summaries list
        """
        try:
            if not summaries:
                return "No summaries found."

            result = ["## Bill Summaries", ""]

            for summary in summaries:
                action_desc = summary.get('actionDesc', 'Unknown action')
                date = summary.get('actionDate', 'Unknown date')
                text = summary.get('text', 'No summary text available')

                result.append(f"**{action_desc}** ({date})")
                result.append(text)
                result.append("")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error formatting summaries: {str(e)}")
            return f"Error formatting summaries: {str(e)}"