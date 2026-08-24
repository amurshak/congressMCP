"""
Pydantic models for Congressional MCP tool responses.
Provides structured, typed responses optimized for AI agent consumption.

Item models mirror what the Congress.gov list endpoints actually return
(issue #55): list responses often omit fields that only exist on detail
endpoints (nominee names, hearing titles, vote tallies, ...), so every
field that the live API can omit is Optional with a None default. The
response models' `results_count` MUST equal the number of items in the
populated list(s); converters derive it with len(), never by parsing text.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# Base Response Models
class ErrorInfo(BaseModel):
    """Section-9 error payload: stable code, human message, secret-safe
    detail, actionable remediation. Mirrors the bill-text tools' envelope
    (documentation/fulltext/04-tools-responses.md section 9)."""
    code: str = Field(description="Stable machine-readable error code (lowercase)")
    message: str = Field(description="What went wrong")
    detail: Optional[Dict[str, Any]] = Field(default=None, description="Structured context; never carries secrets")
    remediation: Optional[str] = Field(default=None, description="What the caller should do about it")


class BaseResponse(BaseModel):
    """Base response model with common fields."""
    success: bool = Field(description="Whether the operation was successful")
    operation: str = Field(description="The operation that was performed")
    error: Optional[ErrorInfo] = Field(
        default=None,
        description="Present when success is false: the section-9 error envelope")

class ErrorResponse(BaseResponse):
    """Error response model."""
    error: str = Field(description="Error message describing what went wrong")
    error_type: str = Field(description="Type of error (validation, timeout, not_found, etc.)")
    suggestions: List[str] = Field(default=[], description="Helpful suggestions for resolving the error")

# Legislative Content Models
class BillSummary(BaseModel):
    """Summary information about a bill."""
    congress: int = Field(description="Congress number (e.g., 118)")
    bill_type: str = Field(description="Type of bill (HR, S, HJRES, SJRES, etc.)")
    bill_number: int = Field(description="Bill number within the congress")
    title: str = Field(description="Official title of the bill")
    sponsor: Optional[str] = Field(default=None, description="Primary sponsor of the bill")
    introduced_date: Optional[str] = Field(default=None, description="Date bill was introduced (YYYY-MM-DD)")
    latest_action: Optional[str] = Field(default=None, description="Most recent action taken on the bill")
    url: Optional[str] = Field(default=None, description="Congress.gov URL for full bill details")

class AmendmentSummary(BaseModel):
    """Summary information about an amendment."""
    congress: int = Field(description="Congress number")
    amendment_type: str = Field(description="Type of amendment (HAMDT, SAMDT, etc.)")
    amendment_number: int = Field(description="Amendment number")
    purpose: Optional[str] = Field(default=None, description="Purpose/description of the amendment")
    sponsor: Optional[str] = Field(default=None, description="Amendment sponsor")
    submitted_date: Optional[str] = Field(default=None, description="Date amendment was submitted")
    bill_number: Optional[str] = Field(default=None, description="Bill this amendment applies to")
    url: Optional[str] = Field(default=None, description="Congress.gov URL for amendment details")

class MemberSummary(BaseModel):
    """Summary information about a member of Congress (list-level fields)."""
    bioguide_id: str = Field(description="Unique bioguide identifier for the member")
    name: str = Field(description="Full name of the member")
    party: Optional[str] = Field(default=None, description="Political party")
    state: Optional[str] = Field(default=None, description="State the member represents")
    district: Optional[str] = Field(default=None, description="District number (House members)")
    chamber: Optional[str] = Field(default=None, description="Chamber of the member's most recent term")
    current_member: Optional[bool] = Field(default=None, description="Whether currently serving (None if unknown)")
    url: Optional[str] = Field(default=None, description="Congress.gov API URL for member details")

class CommitteeSummary(BaseModel):
    """Summary information about a committee."""
    committee_code: str = Field(description="Official committee system code (e.g. hsju00)")
    name: str = Field(description="Full committee name")
    chamber: Optional[str] = Field(default=None, description="Chamber (House, Senate, Joint)")
    committee_type: Optional[str] = Field(default=None, description="Type of committee (Standing, Select, ...)")
    url: Optional[str] = Field(default=None, description="Congress.gov API URL for committee details")

# Legislation Hub Response (legacy)
class LegislationHubResponse(BaseResponse):
    """Response from the legislation hub tool."""
    results_count: int = Field(description="Number of results returned")
    total_available: Optional[int] = Field(default=None, description="Total results available (if known)")
    bills: List[BillSummary] = Field(default=[], description="Bill results")
    amendments: List[AmendmentSummary] = Field(default=[], description="Amendment results")
    summary: str = Field(description="Human-readable summary of the results")
    next_steps: List[str] = Field(default=[], description="Suggested next actions or related searches")

# Members & Committees Response
class MembersCommitteesResponse(BaseResponse):
    """Response from the members and committees tools.

    Some operations return items that are neither members nor committees
    (a member's sponsored bills, a committee's reports/communications/
    nominations); those arrive in `items` as the API's own dicts, labeled
    by `item_kind`.
    """
    results_count: int = Field(description="Number of items returned (equals the populated list's length)")
    members: List[MemberSummary] = Field(default=[], description="Member results")
    committees: List[CommitteeSummary] = Field(default=[], description="Committee results")
    items: List[Dict[str, Any]] = Field(
        default=[],
        description="Results of other kinds (bills, reports, communications, nominations), as returned by Congress.gov")
    item_kind: Optional[str] = Field(
        default=None,
        description="What `items` contains (bill, committee_report, communication, nomination, ...)")
    summary: str = Field(description="Human-readable summary of the results")
    context: str = Field(description="Context about the search or operation performed")

# Voting & Nominations Response
class VoteSummary(BaseModel):
    """Summary of a House roll-call vote (list-level fields)."""
    vote_number: int = Field(description="Roll call vote number")
    congress: Optional[int] = Field(default=None, description="Congress number")
    session: Optional[int] = Field(default=None, description="Session number")
    chamber: Optional[str] = Field(default=None, description="Chamber where the vote occurred")
    legislation: Optional[str] = Field(default=None, description="Legislation voted on (e.g. 'HR 5348')")
    vote_type: Optional[str] = Field(default=None, description="Vote type (Yea-And-Nay, 2/3 Yea-And-Nay, ...)")
    result: Optional[str] = Field(default=None, description="Vote result (Passed, Failed, ...)")
    date: Optional[str] = Field(default=None, description="Start date/time of the vote")
    vote_counts: Optional[Dict[str, int]] = Field(default=None, description="Tallies (detail operations only)")
    url: Optional[str] = Field(default=None, description="Congress.gov API URL for vote details")

class NominationSummary(BaseModel):
    """Summary of a nomination (list-level fields)."""
    nomination_number: str = Field(description="Nomination number")
    citation: Optional[str] = Field(default=None, description="Citation (e.g. PN123)")
    congress: Optional[int] = Field(default=None, description="Congress number")
    organization: Optional[str] = Field(default=None, description="Organization/agency")
    is_military: Optional[bool] = Field(default=None, description="Whether a military nomination")
    nominee: Optional[str] = Field(default=None, description="Nominee name (detail operations only)")
    position: Optional[str] = Field(default=None, description="Position (detail operations only)")
    received_date: Optional[str] = Field(default=None, description="Date the nomination was received")
    latest_action: Optional[str] = Field(default=None, description="Most recent action text")
    update_date: Optional[str] = Field(default=None, description="Last update timestamp")
    url: Optional[str] = Field(default=None, description="Congress.gov API URL for nomination details")

class VotingNominationsResponse(BaseResponse):
    """Response from the voting and nominations tool."""
    results_count: int = Field(description="Number of items returned (equals the populated list's length)")
    votes: List[VoteSummary] = Field(default=[], description="Vote results")
    nominations: List[NominationSummary] = Field(default=[], description="Nomination results")
    items: List[Dict[str, Any]] = Field(
        default=[],
        description="Results of other kinds (per-member votes), as parsed from the source data")
    item_kind: Optional[str] = Field(
        default=None, description="What `items` contains (member_vote, ...)")
    summary: str = Field(description="Human-readable summary of the results")

# Records & Hearings Response
class HearingSummary(BaseModel):
    """Summary of a committee hearing (list-level fields)."""
    jacket_number: str = Field(description="Hearing jacket number")
    congress: Optional[int] = Field(default=None, description="Congress number")
    chamber: Optional[str] = Field(default=None, description="Chamber (House/Senate/NoChamber)")
    title: Optional[str] = Field(default=None, description="Hearing title (detail operations only)")
    committee: Optional[str] = Field(default=None, description="Committee (detail operations only)")
    date: Optional[str] = Field(default=None, description="Hearing date")
    update_date: Optional[str] = Field(default=None, description="Last update timestamp")
    url: Optional[str] = Field(default=None, description="Congress.gov API URL for hearing details")

class RecordSummary(BaseModel):
    """Summary of a Congressional Record issue (list-level fields)."""
    volume: Optional[int] = Field(default=None, description="Congressional Record volume")
    issue: Optional[int] = Field(default=None, description="Issue number")
    session: Optional[int] = Field(default=None, description="Session number")
    congress: Optional[int] = Field(default=None, description="Congress number")
    date: Optional[str] = Field(default=None, description="Publication date")
    id: Optional[str] = Field(default=None, description="Record id")
    title: Optional[str] = Field(default=None, description="Title, where available")
    url: Optional[str] = Field(default=None, description="URL for the issue, where available")

class RecordsHearingsResponse(BaseResponse):
    """Response from the records and hearings tool.

    Communications and House requirements arrive in `items` as the API's
    own dicts, labeled by `item_kind`.
    """
    results_count: int = Field(description="Number of items returned (equals the populated list's length)")
    hearings: List[HearingSummary] = Field(default=[], description="Hearing results")
    records: List[RecordSummary] = Field(default=[], description="Congressional Record results")
    items: List[Dict[str, Any]] = Field(
        default=[],
        description="Results of other kinds (communications, requirements), as returned by Congress.gov")
    item_kind: Optional[str] = Field(
        default=None,
        description="What `items` contains (communication, requirement, daily_record, bound_record, ...)")
    summary: str = Field(description="Human-readable summary of the results")

# Committee Intelligence Response
class CommitteeActivitySummary(BaseModel):
    """Summary of a committee report, print, or meeting (list-level fields)."""
    activity_type: str = Field(description="Type of activity (report, print, meeting)")
    citation: Optional[str] = Field(default=None, description="Citation (e.g. 'H. Rept. 119-10')")
    identifier: Optional[str] = Field(default=None, description="Report number, jacket number, or event id")
    congress: Optional[int] = Field(default=None, description="Congress number")
    chamber: Optional[str] = Field(default=None, description="Chamber")
    committee_name: Optional[str] = Field(default=None, description="Committee name, where available")
    title: Optional[str] = Field(default=None, description="Title, where available")
    date: Optional[str] = Field(default=None, description="Activity or update date")
    url: Optional[str] = Field(default=None, description="Congress.gov API URL for details")

class CommitteeIntelligenceResponse(BaseResponse):
    """Response from the committee intelligence tool."""
    results_count: int = Field(description="Number of items returned (equals the populated list's length)")
    activities: List[CommitteeActivitySummary] = Field(default=[], description="Committee activity results")
    summary: str = Field(description="Human-readable summary of committee intelligence")
    insights: List[str] = Field(default=[], description="Key insights about committee activity")

# Research & Professional Response
class ResearchSummary(BaseModel):
    """Summary of research material (list-level fields)."""
    title: str = Field(description="Document or congress title")
    type: str = Field(description="Type of material (CRS Report, Congress, ...)")
    date: Optional[str] = Field(default=None, description="Publication or update date")
    status: Optional[str] = Field(default=None, description="Status, where available")
    summary: Optional[str] = Field(default=None, description="Brief summary of the document")
    topics: List[str] = Field(default=[], description="Key topics covered")
    url: Optional[str] = Field(default=None, description="URL to access the document")

class ResearchProfessionalResponse(BaseResponse):
    """Response from the research and professional tool."""
    results_count: int = Field(description="Number of items returned (equals the populated list's length)")
    research_materials: List[ResearchSummary] = Field(default=[], description="Research materials found")
    summary: str = Field(description="Human-readable summary of research results")
    recommended_reading: List[str] = Field(default=[], description="Recommended follow-up reading")

# Union type for all possible tool responses
ToolResponse = Union[
    LegislationHubResponse,
    MembersCommitteesResponse,
    VotingNominationsResponse,
    RecordsHearingsResponse,
    CommitteeIntelligenceResponse,
    ResearchProfessionalResponse,
    ErrorResponse
]
