"""
Pydantic models for Congressional MCP tool responses.
Provides structured, typed responses optimized for AI agent consumption.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

# Base Response Models
class BaseResponse(BaseModel):
    """Base response model with common fields."""
    success: bool = Field(description="Whether the operation was successful")
    operation: str = Field(description="The operation that was performed")
    
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
    sponsor: Optional[str] = Field(description="Primary sponsor of the bill")
    introduced_date: Optional[str] = Field(description="Date bill was introduced (YYYY-MM-DD)")
    latest_action: Optional[str] = Field(description="Most recent action taken on the bill")
    url: Optional[str] = Field(description="Congress.gov URL for full bill details")

class AmendmentSummary(BaseModel):
    """Summary information about an amendment."""
    congress: int = Field(description="Congress number")
    amendment_type: str = Field(description="Type of amendment (HAMDT, SAMDT, etc.)")
    amendment_number: int = Field(description="Amendment number")
    purpose: Optional[str] = Field(description="Purpose/description of the amendment")
    sponsor: Optional[str] = Field(description="Amendment sponsor")
    submitted_date: Optional[str] = Field(description="Date amendment was submitted")
    bill_number: Optional[str] = Field(description="Bill this amendment applies to")
    url: Optional[str] = Field(description="Congress.gov URL for amendment details")

class MemberSummary(BaseModel):
    """Summary information about a member of Congress."""
    bioguide_id: str = Field(description="Unique bioguide identifier for the member")
    name: str = Field(description="Full name of the member")
    party: Optional[str] = Field(description="Political party (D, R, I)")
    state: Optional[str] = Field(description="State the member represents")
    district: Optional[str] = Field(description="District number (for House members)")
    chamber: str = Field(description="Chamber (House or Senate)")
    current_member: bool = Field(description="Whether this person is currently serving")
    url: Optional[str] = Field(description="Congress.gov URL for member details")

class CommitteeSummary(BaseModel):
    """Summary information about a committee."""
    committee_code: str = Field(description="Official committee code")
    name: str = Field(description="Full committee name")
    chamber: str = Field(description="Chamber (House, Senate, Joint)")
    committee_type: str = Field(description="Type of committee (Standing, Select, etc.)")
    url: Optional[str] = Field(description="Congress.gov URL for committee details")

# Legislation Hub Response
class LegislationHubResponse(BaseResponse):
    """Response from the legislation hub tool."""
    results_count: int = Field(description="Number of results returned")
    total_available: Optional[int] = Field(description="Total results available (if known)")
    bills: List[BillSummary] = Field(default=[], description="Bill results")
    amendments: List[AmendmentSummary] = Field(default=[], description="Amendment results")
    summary: str = Field(description="Human-readable summary of the results")
    next_steps: List[str] = Field(default=[], description="Suggested next actions or related searches")

# Members & Committees Response  
class MembersCommitteesResponse(BaseResponse):
    """Response from the members and committees tool."""
    results_count: int = Field(description="Number of results returned")
    members: List[MemberSummary] = Field(default=[], description="Member results")
    committees: List[CommitteeSummary] = Field(default=[], description="Committee results")
    summary: str = Field(description="Human-readable summary of the results")
    context: str = Field(description="Context about the search or operation performed")

# Voting & Nominations Response
class VoteSummary(BaseModel):
    """Summary of a vote."""
    vote_number: int = Field(description="Vote number")
    chamber: str = Field(description="Chamber where vote occurred (House/Senate)")
    date: str = Field(description="Date of the vote")
    description: str = Field(description="Description of what was voted on")
    result: str = Field(description="Vote result (Passed, Failed, etc.)")
    vote_counts: Dict[str, int] = Field(description="Vote breakdown (Yea, Nay, Present, Not Voting)")
    url: Optional[str] = Field(description="Congress.gov URL for vote details")

class NominationSummary(BaseModel):
    """Summary of a nomination."""
    nomination_number: str = Field(description="Nomination number")
    nominee: str = Field(description="Name of the nominee")
    position: str = Field(description="Position being nominated for")
    organization: str = Field(description="Organization/agency")
    received_date: Optional[str] = Field(description="Date nomination was received")
    status: Optional[str] = Field(description="Current status of nomination")
    url: Optional[str] = Field(description="Congress.gov URL for nomination details")

class VotingNominationsResponse(BaseResponse):
    """Response from the voting and nominations tool."""
    results_count: int = Field(description="Number of results returned")
    votes: List[VoteSummary] = Field(default=[], description="Vote results")
    nominations: List[NominationSummary] = Field(default=[], description="Nomination results")
    summary: str = Field(description="Human-readable summary of the results")

# Records & Hearings Response
class HearingSummary(BaseModel):
    """Summary of a committee hearing."""
    congress: int = Field(description="Congress number")
    chamber: str = Field(description="Chamber (House/Senate)")
    jacket_number: str = Field(description="Hearing jacket number")
    title: str = Field(description="Hearing title")
    committee: str = Field(description="Committee that held the hearing")
    date: Optional[str] = Field(description="Hearing date")
    url: Optional[str] = Field(description="Congress.gov URL for hearing details")

class RecordSummary(BaseModel):
    """Summary of a Congressional Record entry."""
    volume: int = Field(description="Congressional Record volume")
    issue: int = Field(description="Issue number")
    date: str = Field(description="Publication date")
    section: str = Field(description="Section of the record (House, Senate, Extensions)")
    title: str = Field(description="Title or topic")
    url: Optional[str] = Field(description="Congress.gov URL for full text")

class RecordsHearingsResponse(BaseResponse):
    """Response from the records and hearings tool."""
    results_count: int = Field(description="Number of results returned")
    hearings: List[HearingSummary] = Field(default=[], description="Hearing results")
    records: List[RecordSummary] = Field(default=[], description="Congressional Record results")
    summary: str = Field(description="Human-readable summary of the results")

# Committee Intelligence Response
class CommitteeActivitySummary(BaseModel):
    """Summary of committee activity."""
    committee_name: str = Field(description="Committee name")
    activity_type: str = Field(description="Type of activity (meeting, markup, hearing)")
    title: str = Field(description="Activity title")
    date: Optional[str] = Field(description="Activity date")
    status: str = Field(description="Current status")
    url: Optional[str] = Field(description="Congress.gov URL for details")

class CommitteeIntelligenceResponse(BaseResponse):
    """Response from the committee intelligence tool."""
    results_count: int = Field(description="Number of results returned")
    activities: List[CommitteeActivitySummary] = Field(default=[], description="Committee activity results")
    summary: str = Field(description="Human-readable summary of committee intelligence")
    insights: List[str] = Field(default=[], description="Key insights about committee activity")

# Research & Professional Response  
class ResearchSummary(BaseModel):
    """Summary of research material."""
    title: str = Field(description="Research document title")
    type: str = Field(description="Type of document (CRS Report, Committee Report, etc.)")
    date: Optional[str] = Field(description="Publication or update date")
    summary: Optional[str] = Field(description="Brief summary of the document")
    topics: List[str] = Field(default=[], description="Key topics covered")
    url: Optional[str] = Field(description="URL to access the document")

class ResearchProfessionalResponse(BaseResponse):
    """Response from the research and professional tool."""
    results_count: int = Field(description="Number of results returned")
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