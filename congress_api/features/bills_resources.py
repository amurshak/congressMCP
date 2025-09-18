"""
Bills Resources - MCP resource functions for Congressional bills reference data.

This module provides static reference information about Congressional bills,
including bill types, Congress ranges, status definitions, and usage guides.
All operational bill functions have been moved to the bills/ module.
"""

from fastmcp import Context
from ..mcp_app import mcp

# --- MCP Resources ---

@mcp.resource("congress://bills/types")
async def get_bill_types_reference(ctx: Context) -> str:
    """
    Get reference information about Congressional bill types.
    
    Returns static reference data about the 8 types of Congressional bills
    and resolutions, including their codes, full names, and descriptions.
    """
    return """# Congressional Bill Types Reference

## Overview
The U.S. Congress considers 8 different types of bills and resolutions, each with specific purposes and legislative processes.

## Bill Types

### **Bills** (Require Presidential Signature)

#### **HR - House Bill**
- **Origin**: House of Representatives
- **Purpose**: General legislation affecting the public
- **Process**: Requires passage by both chambers and Presidential signature
- **Example**: HR 1 - "For the People Act"

#### **S - Senate Bill** 
- **Origin**: Senate
- **Purpose**: General legislation affecting the public
- **Process**: Requires passage by both chambers and Presidential signature
- **Example**: S 1 - "For the People Act"

### **Joint Resolutions** (Require Presidential Signature)

#### **HJRES - House Joint Resolution**
- **Origin**: House of Representatives  
- **Purpose**: Limited matters, constitutional amendments, continuing appropriations
- **Process**: Same as bills - requires both chambers and Presidential signature
- **Special**: Constitutional amendments need 2/3 majority in both chambers

#### **SJRES - Senate Joint Resolution**
- **Origin**: Senate
- **Purpose**: Limited matters, constitutional amendments, continuing appropriations  
- **Process**: Same as bills - requires both chambers and Presidential signature
- **Special**: Constitutional amendments need 2/3 majority in both chambers

### **Concurrent Resolutions** (No Presidential Signature Required)

#### **HCONRES - House Concurrent Resolution**
- **Origin**: House of Representatives
- **Purpose**: Rules for both chambers, Congressional sentiments, budget resolutions
- **Process**: Requires passage by both chambers only
- **Example**: Setting time for Congressional adjournment

#### **SCONRES - Senate Concurrent Resolution**
- **Origin**: Senate  
- **Purpose**: Rules for both chambers, Congressional sentiments, budget resolutions
- **Process**: Requires passage by both chambers only
- **Example**: Annual budget resolution

### **Simple Resolutions** (Single Chamber Only)

#### **HRES - House Simple Resolution**
- **Origin**: House of Representatives
- **Purpose**: House rules, House sentiments, House internal matters
- **Process**: House passage only
- **Example**: Expressing condolences, House procedural rules

#### **SRES - Senate Simple Resolution**
- **Origin**: Senate
- **Purpose**: Senate rules, Senate sentiments, Senate internal matters  
- **Process**: Senate passage only
- **Example**: Expressing congratulations, Senate procedural rules

## Search Tips
- Use lowercase when searching: "hr", "s", "hjres", etc.
- Bills and Joint Resolutions become law if signed by the President
- Resolutions express Congressional opinion or set internal rules
- Constitutional amendments use Joint Resolutions but don't require Presidential signature

## API Usage
When using the Bills API tools, specify bill types using these exact codes:
`hr`, `s`, `hjres`, `sjres`, `hconres`, `sconres`, `hres`, `sres`
"""

@mcp.resource("congress://bills/congress-ranges")
async def get_congress_ranges_reference(ctx: Context) -> str:
    """
    Get reference information about Congress number ranges and coverage.
    
    Returns information about available Congress numbers, date ranges,
    and data coverage limitations for different Congressional periods.
    """
    return """# Congressional Number Ranges & Data Coverage

## Current Congress Information
- **Current Congress**: 119th Congress (2025-2026)
- **Previous Congress**: 118th Congress (2023-2024)
- **API Coverage**: Comprehensive data from 103rd Congress (1993) forward

## Congress Numbering System
- **First Congress**: 1st Congress (1789-1791)
- **Current Range**: 1-119 (as of 2025)
- **Duration**: Each Congress lasts 2 years (2 sessions)
- **Numbering**: Sequential since 1789

## Data Coverage by Period

### **Modern Era (103rd Congress - Present)**
- **Years**: 1993-Present
- **Congress Range**: 103-119
- **Data Quality**: Complete
- **Available Data**: Full metadata, text, actions, sponsors, summaries, amendments

### **Digital Transition (93rd-102nd Congress)**  
- **Years**: 1973-1992
- **Congress Range**: 93-102
- **Data Quality**: Limited
- **Available Data**: Basic metadata, some text versions

### **Historical Period (6th-92nd Congress)**
- **Years**: 1799-1972  
- **Congress Range**: 6-92
- **Data Quality**: Very Limited
- **Available Data**: Basic records, limited searchability
- **Note**: Bills from 6th-14th Congress (1799-1817) were not numbered

## Search Recommendations

### **For Current Research**
- **Use**: Congress 119 (current) or 118 (recent)
- **Best Results**: Full data availability, active legislation

### **For Historical Research**
- **Use**: Congress 103+ (1993+) for comprehensive data
- **Limited**: Congress 93-102 for basic information only

### **Special Notes**
- **Reserved Bills**: Leadership reserves low numbers (HR 1, S 1, etc.)
- **Numbering Gaps**: Some numbers may be skipped or reserved
- **Update Frequency**: New bills added daily during Congressional sessions

## API Usage Tips
- Specify Congress number for targeted searches: `congress=119`
- Use recent Congress numbers (115+) for best search results
- Combine with bill types for efficient filtering
- Check data availability before deep historical searches

## Congress Calendar
- **Odd Years**: First session of each Congress
- **Even Years**: Second session of each Congress  
- **Elections**: Even years (House every 2 years, Senate staggered)
- **New Congress**: Begins January 3rd of odd years
"""

@mcp.resource("congress://bills/status-definitions")
async def get_bill_status_definitions(ctx: Context) -> str:
    """
    Get reference definitions for bill statuses and legislative process stages.
    
    Returns explanations of common bill statuses, action types, and
    legislative process terminology used in bill tracking.
    """
    return """# Bill Status Definitions & Legislative Process

## Common Bill Statuses

### **Introduction & Referral**
- **Introduced**: Bill formally submitted to chamber
- **Referred to Committee**: Assigned to relevant committee for review
- **Subcommittee Referral**: Sent to specialized subcommittee

### **Committee Actions**
- **Committee Consideration**: Under active committee review
- **Markup**: Committee reviews and potentially amends bill text
- **Reported**: Committee approves bill and sends to full chamber
- **Committee Discharged**: Bill removed from committee without action

### **Floor Actions**
- **Placed on Calendar**: Scheduled for floor consideration
- **Floor Consideration**: Debated by full chamber
- **Passed Chamber**: Approved by originating chamber
- **Received in [Other Chamber]**: Sent to other chamber for consideration

### **Final Actions**
- **Passed Congress**: Approved by both House and Senate
- **Presented to President**: Sent to White House for signature
- **Became Public Law**: Signed by President, now law
- **Pocket Veto**: Unsigned by President when Congress adjourns
- **Veto Override**: Congress overrides Presidential veto

## Action Types Explained

### **Legislative Actions**
- **BecameLaw**: Bill signed into law by President
- **Introduced**: Initial submission to chamber
- **Passed**: Approved by a chamber
- **Failed**: Rejected by vote or procedural action

### **Committee Actions**
- **Referred**: Sent to committee
- **Reported**: Committee sends bill to floor
- **Discharged**: Removed from committee

### **Presidential Actions**
- **ToPresident**: Bill sent to White House
- **Signed**: President approves bill
- **Vetoed**: President rejects bill

## Bill Lifecycle Stages

### **Stage 1: Introduction**
1. Bill drafted by member or staff
2. Introduced in House or Senate
3. Assigned bill number
4. Referred to committee(s)

### **Stage 2: Committee Review**
1. Committee consideration
2. Hearings (optional)
3. Markup sessions
4. Committee vote
5. Report to full chamber

### **Stage 3: Floor Action**
1. Placed on calendar
2. Floor debate
3. Amendments considered
4. Final passage vote

### **Stage 4: Other Chamber**
1. Received from first chamber
2. Committee process (may be expedited)
3. Floor consideration
4. Passage or amendment

### **Stage 5: Resolution**
1. If amended, return to first chamber
2. Conference committee (if needed)
3. Final passage by both chambers
4. Sent to President

### **Stage 6: Presidential Action**
1. President signs (becomes law)
2. President vetoes (returns to Congress)
3. Pocket veto (if Congress adjourns)
4. Veto override (2/3 majority in both chambers)

## Status Interpretation Tips

### **Active Bills**
- Look for recent action dates
- "Passed" in one chamber means still active
- Committee activity indicates ongoing work

### **Stalled Bills**
- No recent actions (6+ months)
- Stuck in committee
- End of Congress approaching

### **Dead Bills**
- Failed vote
- End of Congress (bills die if not passed)
- Withdrawn by sponsor

## Search Strategy
- Use `get_bill_actions` for complete legislative history
- Check `latestAction` for current status
- Recent `updateDate` indicates active consideration
- Multiple chambers in actions = bill progressing
"""

@mcp.resource("congress://bills/usage-guide")
async def get_bills_api_usage_guide(ctx: Context) -> str:
    """
    Get usage guidelines and best practices for the Bills API.
    
    Returns information about search strategies, parameter combinations,
    rate limits, and tips for effective bill research.
    """
    return """# Bills API Usage Guide & Best Practices

## Search Strategies

### **1. Direct Bill Lookup**
**Best for**: Known bill numbers
```
search_bills("HR 1", congress=119)
search_bills("S 2025", congress=118)
```
- Use exact bill format: "HR 1", "S 1234"
- Include Congress number for precision
- Fastest method for specific bills

### **2. Keyword Search**
**Best for**: Topic-based research
```
search_bills("infrastructure", congress=119, limit=20)
search_bills("climate change", bill_type="hr")
```
- Use specific keywords for better results
- Searches bill titles and policy areas
- Combine with Congress/type filters

### **3. Targeted Filtering**
**Best for**: Focused research
```
search_bills("healthcare", congress=119, bill_type="hr", limit=10)
```
- Combine multiple filters for precision
- Use recent Congress numbers (118, 119)
- Limit results to manageable numbers

## Parameter Optimization

### **Congress Numbers**
- **Current Research**: Use 119 (current) or 118 (recent)
- **Recent Research**: Use 118 (2023-2024) 
- **Historical**: Use 103+ for comprehensive data
- **Avoid**: Very old Congress numbers (<100) unless necessary

### **Bill Types**
- **All Legislation**: Don't specify (searches all types)
- **Major Bills**: Use "hr" or "s" 
- **Resolutions**: Use "hres", "sres", "hconres", "sconres"
- **Constitutional**: Use "hjres", "sjres"

### **Limits & Sorting**
- **Default Limit**: 10 results (good starting point)
- **Research**: 20-50 results for comprehensive review
- **Default Sort**: updateDate+desc (most recent first)
- **Historical**: updateDate+asc for chronological order

## Effective Research Workflows

### **Topic Research Workflow**
1. **Broad Search**: `search_bills("topic", congress=119)`
2. **Review Results**: Identify relevant bills
3. **Deep Dive**: `get_bill_details()` for promising bills
4. **Track Progress**: `get_bill_actions()` for status
5. **Related Research**: `get_bill_related_bills()` for connections

### **Bill Tracking Workflow**
1. **Find Bill**: Direct lookup or keyword search
2. **Get Overview**: `get_bill_details()` for summary
3. **Check Status**: `get_bill_actions()` for latest activity
4. **Review Content**: `get_bill_summaries()` for analysis
5. **Monitor Changes**: `get_bill_text_versions()` for amendments

### **Legislative History Workflow**
1. **Identify Bill**: Search or direct lookup
2. **Full Actions**: `get_bill_actions()` for complete timeline
3. **Committee Work**: `get_bill_committees()` for review process
4. **Support Analysis**: `get_bill_cosponsors()` for backing
5. **Related Bills**: `get_bill_related_bills()` for context

## Common Use Cases

### **Journalists**
- Track breaking legislative news
- Research bill sponsors and supporters
- Monitor committee activities
- Find related legislation

### **Policy Researchers**
- Analyze legislative trends
- Compare similar bills across Congresses
- Study policy area development
- Track amendment patterns

### **Legal Professionals**
- Research legislative intent
- Track bill text changes
- Analyze procedural history
- Find related statutes

### **Government Affairs**
- Monitor client-relevant legislation
- Track bill progress and timing
- Identify key decision makers
- Prepare testimony and comments

## Performance Tips

### **Efficient Searches**
- Start with specific keywords
- Use Congress filters for recent data
- Limit initial results, expand if needed
- Cache frequently accessed bill details

### **Rate Limiting**
- Space out API calls for large research projects
- Use batch processing for multiple bills
- Implement retry logic for failed requests
- Monitor response times

### **Data Quality**
- Use Congress 103+ for reliable data
- Verify bill numbers with direct lookup
- Cross-reference with multiple data points
- Check update dates for freshness

## Troubleshooting

### **No Results Found**
- Check spelling of keywords
- Try broader search terms
- Verify Congress number is valid
- Remove filters and search again

### **Too Many Results**
- Add Congress number filter
- Specify bill type
- Use more specific keywords
- Reduce limit parameter

### **Outdated Information**
- Use recent Congress numbers
- Check bill update dates
- Verify bill is still active
- Look for newer related bills

## Advanced Techniques

### **Cross-Congress Comparison**
```
# Compare similar bills across Congresses
search_bills("infrastructure", congress=118)
search_bills("infrastructure", congress=119)
```

### **Comprehensive Bill Analysis**
```
# Get complete bill picture
get_bill_details(congress, bill_type, number)
get_bill_actions(congress, bill_type, number)
get_bill_summaries(congress, bill_type, number)
get_bill_related_bills(congress, bill_type, number)
```

### **Legislative Trend Analysis**
- Search same keywords across multiple Congresses
- Track policy area evolution
- Monitor sponsor patterns
- Analyze success rates by bill type
"""

# --- Date-Only Search Functions ---