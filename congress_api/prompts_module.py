# prompts_module.py
from .mcp_app import mcp

@mcp.prompt()
def search_legislation_prompt() -> str:
    """Create a prompt for searching legislation."""
    return """
I need help finding legislation related to a specific topic. Please search for relevant bills, amendments, or committee activities.

The topic I'm interested in is: 
    """

@mcp.prompt()
def bill_analysis_prompt() -> str:
    """Create a prompt for analyzing a specific bill."""
    return """
I need help analyzing a specific bill. Please provide details about the following:

Bill Type (e.g., H.R., S.): 
Bill Number: 
Congress (e.g., 117 for 117th Congress): 

I'm particularly interested in understanding:
- The main provisions of the bill
- Key sponsors and cosponsors
- Committee activity
- Current status and recent actions
- Related amendments
    """

@mcp.prompt()
def member_legislation_prompt() -> str:
    """Create a prompt for analyzing a member's legislative activities."""
    return """
I'd like to learn about the legislative activities of a specific member of Congress.

Member Name: 
(Alternatively, if you know it) Bioguide ID: 

Please tell me about:
- Their sponsored and cosponsored legislation
- Committee assignments
- Voting patterns on major legislation
- Recent legislative activities
    """

@mcp.prompt()
def committee_activity_prompt() -> str:
    """Create a prompt for analyzing committee activities."""
    return """
I'm researching the activities of a specific congressional committee.

Chamber (House or Senate): 
Committee Name or Code: 

Please provide information about:
- Recent bills considered by this committee
- Hearings and markups
- Major actions taken
- Current leadership and membership
    """
