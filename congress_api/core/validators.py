"""
Parameter validation utilities for Congressional MCP APIs.

This module provides standardized validation functions to prevent hanging issues,
ensure data consistency, and provide user-friendly error messages across all APIs.
"""

import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of a parameter validation check."""
    is_valid: bool
    error_message: Optional[str] = None
    suggestions: Optional[List[str]] = None
    sanitized_value: Optional[Any] = None

class ParameterValidator:
    """Centralized parameter validation for all Congressional APIs."""
    
    # Congressional data ranges based on API testing
    MIN_CONGRESS_NUMBER = 1
    MAX_CONGRESS_NUMBER = 119  # Current as of 2024
    
    # API-specific year ranges (can be overridden per API)
    DEFAULT_MIN_YEAR = 1789  # First Congress
    DEFAULT_MAX_YEAR = datetime.now().year
    
    # Bound Congressional Record specific range (based on testing)
    BOUND_RECORD_MIN_YEAR = 1873
    BOUND_RECORD_MAX_YEAR = 1997
    
    # Standard limit ranges
    DEFAULT_MAX_LIMIT = 250
    MIN_LIMIT = 1
    
    @staticmethod
    def validate_congress_number(congress: Optional[int]) -> ValidationResult:
        """
        Validate congress numbers.
        
        Args:
            congress: Congress number to validate
            
        Returns:
            ValidationResult with validation status and error details
        """
        if congress is None:
            return ValidationResult(is_valid=True)
        
        try:
            congress_int = int(congress)
            if congress_int < ParameterValidator.MIN_CONGRESS_NUMBER:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Congress number {congress} is too low. The first Congress was {ParameterValidator.MIN_CONGRESS_NUMBER}.",
                    suggestions=[f"Try a congress number between {ParameterValidator.MIN_CONGRESS_NUMBER} and {ParameterValidator.MAX_CONGRESS_NUMBER}"]
                )
            
            if congress_int > ParameterValidator.MAX_CONGRESS_NUMBER:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Congress number {congress} is too high. The current Congress is {ParameterValidator.MAX_CONGRESS_NUMBER}.",
                    suggestions=[f"Try a congress number between {ParameterValidator.MIN_CONGRESS_NUMBER} and {ParameterValidator.MAX_CONGRESS_NUMBER}"]
                )
            
            return ValidationResult(is_valid=True, sanitized_value=congress_int)
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid congress number format: {congress}. Please provide a valid integer.",
                suggestions=["Congress numbers are integers, e.g., 118 for the 118th Congress"]
            )
    
    @staticmethod
    def validate_year_range(year: Optional[str], min_year: int = None, max_year: int = None) -> ValidationResult:
        """
        Validate year parameters with configurable ranges.
        
        Args:
            year: Year string to validate
            min_year: Minimum allowed year (defaults to DEFAULT_MIN_YEAR)
            max_year: Maximum allowed year (defaults to DEFAULT_MAX_YEAR)
            
        Returns:
            ValidationResult with validation status and error details
        """
        if year is None:
            return ValidationResult(is_valid=True)
        
        if min_year is None:
            min_year = ParameterValidator.DEFAULT_MIN_YEAR
        if max_year is None:
            max_year = ParameterValidator.DEFAULT_MAX_YEAR
        
        try:
            year_int = int(year)
            if year_int < min_year or year_int > max_year:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Year {year} is outside the available range. Please try a year between {min_year} and {max_year}.",
                    suggestions=[f"Valid year range: {min_year}-{max_year}"]
                )
            
            return ValidationResult(is_valid=True, sanitized_value=year_int)
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid year format: {year}. Please provide a valid 4-digit year.",
                suggestions=["Years should be 4-digit integers, e.g., 2023"]
            )
    
    @staticmethod
    def validate_month(month: Optional[str]) -> ValidationResult:
        """
        Validate month parameter.
        
        Args:
            month: Month string to validate (1-12)
            
        Returns:
            ValidationResult with validation status and error details
        """
        if month is None:
            return ValidationResult(is_valid=True)
        
        try:
            month_int = int(month)
            if month_int < 1 or month_int > 12:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid month: {month}. Please provide a month between 1 and 12.",
                    suggestions=["Months are numbered 1-12 (1=January, 12=December)"]
                )
            
            return ValidationResult(is_valid=True, sanitized_value=month_int)
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid month format: {month}. Please provide a valid month number.",
                suggestions=["Months should be integers 1-12"]
            )
    
    @staticmethod
    def validate_day(day: Optional[str]) -> ValidationResult:
        """
        Validate day parameter.
        
        Args:
            day: Day string to validate (1-31)
            
        Returns:
            ValidationResult with validation status and error details
        """
        if day is None:
            return ValidationResult(is_valid=True)
        
        try:
            day_int = int(day)
            if day_int < 1 or day_int > 31:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid day: {day}. Please provide a day between 1 and 31.",
                    suggestions=["Days should be between 1 and 31"]
                )
            
            return ValidationResult(is_valid=True, sanitized_value=day_int)
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid day format: {day}. Please provide a valid day number.",
                suggestions=["Days should be integers 1-31"]
            )
    
    @staticmethod
    def validate_date_components(year: Optional[str], month: Optional[str], day: Optional[str]) -> ValidationResult:
        """
        Validate year/month/day combinations for logical consistency.
        
        Args:
            year: Year string
            month: Month string  
            day: Day string
            
        Returns:
            ValidationResult with validation status and error details
        """
        # Validate individual components first
        year_result = ParameterValidator.validate_year_range(year)
        if not year_result.is_valid:
            return year_result
        
        month_result = ParameterValidator.validate_month(month)
        if not month_result.is_valid:
            return month_result
        
        day_result = ParameterValidator.validate_day(day)
        if not day_result.is_valid:
            return day_result
        
        # If all components are provided, validate the date combination
        if year and month and day:
            try:
                # Check if the date is valid (handles leap years, month lengths)
                datetime(year_result.sanitized_value, month_result.sanitized_value, day_result.sanitized_value)
                return ValidationResult(is_valid=True)
            except ValueError as e:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid date combination: {year}-{month}-{day}. {str(e)}",
                    suggestions=["Check that the day exists in the specified month and year"]
                )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_limit_range(limit: int, max_limit: int = None) -> ValidationResult:
        """
        Validate limit parameters.
        
        Args:
            limit: Limit value to validate
            max_limit: Maximum allowed limit (defaults to DEFAULT_MAX_LIMIT)
            
        Returns:
            ValidationResult with validation status and sanitized limit
        """
        if max_limit is None:
            max_limit = ParameterValidator.DEFAULT_MAX_LIMIT
        
        try:
            limit_int = int(limit)
            
            if limit_int < ParameterValidator.MIN_LIMIT:
                # Auto-correct to minimum
                return ValidationResult(
                    is_valid=True,
                    sanitized_value=ParameterValidator.MIN_LIMIT,
                    error_message=f"Limit {limit} was too low, adjusted to {ParameterValidator.MIN_LIMIT}"
                )
            
            if limit_int > max_limit:
                # Auto-correct to maximum
                return ValidationResult(
                    is_valid=True,
                    sanitized_value=max_limit,
                    error_message=f"Limit {limit} was too high, adjusted to {max_limit}"
                )
            
            return ValidationResult(is_valid=True, sanitized_value=limit_int)
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid limit format: {limit}. Please provide a valid integer.",
                suggestions=[f"Limits should be integers between {ParameterValidator.MIN_LIMIT} and {max_limit}"]
            )
    
    @staticmethod
    def validate_bill_type(bill_type: Optional[str]) -> ValidationResult:
        """
        Validate bill type parameters.
        
        Args:
            bill_type: Bill type to validate (hr, s, hjres, sjres, hconres, sconres, hres, sres)
            
        Returns:
            ValidationResult with validation status and error details
        """
        if bill_type is None:
            return ValidationResult(is_valid=True)
        
        valid_bill_types = ['hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres']
        bill_type_lower = bill_type.lower().strip()
        
        if bill_type_lower not in valid_bill_types:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid bill type: {bill_type}. Valid types are: {', '.join(valid_bill_types)}",
                suggestions=[
                    "hr = House Bill",
                    "s = Senate Bill", 
                    "hjres = House Joint Resolution",
                    "sjres = Senate Joint Resolution"
                ]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=bill_type_lower)
    
    @staticmethod
    def validate_amendment_type(amendment_type: Optional[str]) -> ValidationResult:
        """
        Validate amendment type parameters.
        
        Args:
            amendment_type: Amendment type to validate (samdt, hamdt)
            
        Returns:
            ValidationResult with validation status and error details
        """
        if amendment_type is None:
            return ValidationResult(is_valid=True)
        
        valid_amendment_types = ['samdt', 'hamdt']
        amendment_type_lower = amendment_type.lower().strip()
        
        if amendment_type_lower not in valid_amendment_types:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid amendment type: {amendment_type}. Valid types are: {', '.join(valid_amendment_types)}",
                suggestions=[
                    "samdt = Senate Amendment",
                    "hamdt = House Amendment"
                ]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=amendment_type_lower)

    @staticmethod
    def validate_content_type(content_type: str) -> ValidationResult:
        """
        Validate content type parameters.
        
        Args:
            content_type: Content type to validate (e.g., "text", "summary")
            
        Returns:
            ValidationResult with validation status
        """
        if not content_type:
            return ValidationResult(
                is_valid=False,
                error_message="Content type cannot be empty",
                suggestions=["Use 'text' for bill text or 'summary' for bill summaries"]
            )
        
        valid_types = ["text", "summary"]
        content_type_lower = content_type.lower().strip()
        
        if content_type_lower not in valid_types:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid content type: {content_type}",
                suggestions=[f"Valid content types are: {', '.join(valid_types)}"]
            )
        
        return ValidationResult(
            is_valid=True,
            sanitized_value=content_type_lower
        )

    @staticmethod
    def validate_jacket_number(jacket_number: Optional[int]) -> ValidationResult:
        """
        Validate jacket number parameters for committee prints.
        
        Args:
            jacket_number: Jacket number to validate
            
        Returns:
            ValidationResult with validation status and error details
        """
        if jacket_number is None:
            return ValidationResult(
                is_valid=False,
                error_message="Jacket number is required",
                suggestions=["Provide a valid jacket number (positive integer)"]
            )
        
        if not isinstance(jacket_number, int) or jacket_number <= 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid jacket number: {jacket_number}. Must be a positive integer.",
                suggestions=["Use a positive integer for the jacket number (e.g., 48144)"]
            )
        
        # Jacket numbers are typically 5-6 digits based on API examples
        if jacket_number > 999999:
            return ValidationResult(
                is_valid=False,
                error_message=f"Jacket number {jacket_number} seems unusually large",
                suggestions=["Verify the jacket number is correct (typically 5-6 digits)"]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=jacket_number)
    
    @staticmethod
    def validate_chamber(chamber: str, allow_nochamber: bool = True) -> ValidationResult:
        """
        Validate chamber parameter for Congressional APIs.
        
        Args:
            chamber: Chamber name to validate
            allow_nochamber: Whether to allow 'nochamber' as valid option
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        if not isinstance(chamber, str):
            return ValidationResult(
                is_valid=False,
                error_message="Chamber must be a string",
                suggestions=["Provide chamber as 'house', 'senate'" + (", or 'nochamber'" if allow_nochamber else "")]
            )
        
        chamber_lower = chamber.lower().strip()
        valid_chambers = ["house", "senate"]
        if allow_nochamber:
            valid_chambers.append("nochamber")
        
        if chamber_lower not in valid_chambers:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid chamber: {chamber}",
                suggestions=[f"Must be one of: {', '.join(valid_chambers)}"]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=chamber_lower)
    
    @staticmethod
    def validate_report_type(report_type: str) -> ValidationResult:
        """
        Validate committee report types.
        
        Args:
            report_type: Report type to validate (e.g., 'hrpt', 'srpt', 'erpt')
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        if not isinstance(report_type, str):
            return ValidationResult(
                is_valid=False,
                error_message="Report type must be a string",
                suggestions=["Provide report type as 'hrpt', 'srpt', or 'erpt'"]
            )
        
        report_type_lower = report_type.lower().strip()
        valid_types = ["hrpt", "srpt", "erpt"]  # House, Senate, Executive reports
        
        if report_type_lower not in valid_types:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid report type: {report_type}",
                suggestions=[f"Must be one of: {', '.join(valid_types)}"]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=report_type_lower)
    
    @staticmethod
    def validate_report_number(report_number: int) -> ValidationResult:
        """
        Validate committee report numbers.
        
        Args:
            report_number: Report number to validate
            
        Returns:
            ValidationResult with validation status
        """
        if not isinstance(report_number, int):
            return ValidationResult(
                is_valid=False,
                error_message="Report number must be an integer",
                suggestions=["Provide a positive integer report number"]
            )
        
        if report_number <= 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"Report number must be positive: {report_number}",
                suggestions=["Provide a positive integer report number (e.g., 1, 100, 500)"]
            )
        
        # Committee reports typically don't exceed 9999 per congress
        if report_number > 9999:
            return ValidationResult(
                is_valid=False,
                error_message=f"Report number seems unusually high: {report_number}",
                suggestions=["Check the report number - typical range is 1-9999"]
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_conference_filter(conference: str) -> ValidationResult:
        """
        Validate conference report filter parameter.
        
        Args:
            conference: Conference filter value ('true' or 'false')
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        if not isinstance(conference, str):
            return ValidationResult(
                is_valid=False,
                error_message="Conference filter must be a string",
                suggestions=["Provide 'true' or 'false'"]
            )
        
        conference_lower = conference.lower().strip()
        valid_values = ["true", "false"]
        
        if conference_lower not in valid_values:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid conference filter: {conference}",
                suggestions=["Must be 'true' or 'false'"]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=conference_lower)
    
    @staticmethod
    def validate_offset(offset: int) -> ValidationResult:
        """
        Validate pagination offset parameter.
        
        Args:
            offset: Offset value for pagination
            
        Returns:
            ValidationResult with validation status
        """
        if not isinstance(offset, int):
            return ValidationResult(
                is_valid=False,
                error_message="Offset must be an integer",
                suggestions=["Provide a non-negative integer for pagination offset"]
            )
        
        if offset < 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"Offset must be non-negative: {offset}",
                suggestions=["Provide a non-negative integer (0 or greater)"]
            )
        
        # Reasonable upper limit for offset
        if offset > 10000:
            return ValidationResult(
                is_valid=False,
                error_message=f"Offset seems unusually high: {offset}",
                suggestions=["Consider using a smaller offset value for better performance"]
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_state_code(state_code: str) -> ValidationResult:
        """
        Validate US state codes for Congressional member queries.
        
        Args:
            state_code: Two-letter state code to validate
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        if not state_code:
            return ValidationResult(
                is_valid=False,
                error_message="State code cannot be empty",
                suggestions=["Provide a two-letter state code like 'CA', 'TX', 'NY'"]
            )
        
        # Sanitize input
        state_code_clean = str(state_code).strip().upper()
        
        # Valid US state and territory codes
        valid_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
            'DC', 'AS', 'GU', 'MP', 'PR', 'VI'  # Territories with Congressional representation
        }
        
        if len(state_code_clean) != 2:
            return ValidationResult(
                is_valid=False,
                error_message=f"State code must be exactly 2 characters: '{state_code}'",
                suggestions=["Use two-letter state codes like 'CA' for California, 'TX' for Texas"]
            )
        
        if state_code_clean not in valid_states:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid state code: '{state_code_clean}'",
                suggestions=[
                    "Use valid US state codes like 'CA', 'TX', 'NY', 'FL'",
                    "Territories: 'DC', 'PR', 'VI', 'GU', 'AS', 'MP'"
                ]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=state_code_clean)

    @staticmethod
    def validate_date_format(date_string: Optional[str]) -> ValidationResult:
        """
        Validate ISO date format (YYYY-MM-DDTHH:MM:SSZ) for API parameters.
        
        Args:
            date_string: Date string to validate in ISO format
            
        Returns:
            ValidationResult with validation status and error details
        """
        if date_string is None:
            return ValidationResult(is_valid=True)
        
        if not isinstance(date_string, str):
            return ValidationResult(
                is_valid=False,
                error_message="Date must be a string",
                suggestions=["Provide date in ISO format: YYYY-MM-DDTHH:MM:SSZ"]
            )
        
        # Check ISO format pattern: YYYY-MM-DDTHH:MM:SSZ
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'
        
        if not re.match(iso_pattern, date_string.strip()):
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid date format: {date_string}. Date must be in format YYYY-MM-DDTHH:MM:SSZ",
                suggestions=[
                    "Use ISO format: YYYY-MM-DDTHH:MM:SSZ",
                    "Example: 2023-01-01T00:00:00Z"
                ]
            )
        
        # Additional validation: try to parse the date to ensure it's valid
        try:
            datetime.strptime(date_string.strip(), '%Y-%m-%dT%H:%M:%SZ')
            return ValidationResult(is_valid=True, sanitized_value=date_string.strip())
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid date: {date_string}. {str(e)}",
                suggestions=[
                    "Check that the date values are valid (e.g., month 1-12, day 1-31)",
                    "Use format: YYYY-MM-DDTHH:MM:SSZ"
                ]
            )

    @staticmethod
    def validate_senate_communication_type(communication_type: Optional[str]) -> ValidationResult:
        """
        Validate senate communication type codes.
        
        Args:
            communication_type: Communication type code to validate
            
        Returns:
            ValidationResult with validation status and error details
        """
        if communication_type is None:
            return ValidationResult(is_valid=True)
        
        if not isinstance(communication_type, str):
            return ValidationResult(
                is_valid=False,
                error_message="Communication type must be a string",
                suggestions=["Use valid communication type codes like 'ec', 'pm', 'pom'"]
            )
        
        # Valid senate communication types based on Congress.gov API
        valid_types = {
            'ec': 'Executive Communication',
            'pm': 'Petition or Memorial',
            'pom': 'Petition or Memorial'
        }
        
        communication_type_clean = communication_type.strip().lower()
        
        if communication_type_clean not in valid_types:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid senate communication type: '{communication_type}'",
                suggestions=[
                    f"Valid types: {', '.join(valid_types.keys())}",
                    "ec = Executive Communication",
                    "pm = Petition or Memorial", 
                    "pom = Petition or Memorial"
                ]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=communication_type_clean)

    @staticmethod
    def validate_communication_number(communication_number: Optional[int]) -> ValidationResult:
        """
        Validate communication number.
        
        Args:
            communication_number: Communication number to validate
            
        Returns:
            ValidationResult with validation status and error details
        """
        if communication_number is None:
            return ValidationResult(is_valid=True)
        
        if not isinstance(communication_number, int):
            return ValidationResult(
                is_valid=False,
                error_message="Communication number must be an integer",
                suggestions=["Provide a positive integer communication number"]
            )
        
        if communication_number <= 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"Communication number must be positive, got: {communication_number}",
                suggestions=["Provide a positive integer communication number (e.g., 1, 100, 2561)"]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=communication_number)
    
    @staticmethod
    def validate_chamber(chamber: str, allow_nochamber: bool = True) -> ValidationResult:
        """
        Validate chamber parameter for Congressional APIs.
        
        Args:
            chamber: Chamber name to validate
            allow_nochamber: Whether to allow 'nochamber' as valid option
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        if not isinstance(chamber, str):
            return ValidationResult(
                is_valid=False,
                error_message="Chamber must be a string",
                suggestions=["Provide chamber as 'house', 'senate'" + (", or 'nochamber'" if allow_nochamber else "")]
            )
        
        chamber_lower = chamber.lower().strip()
        valid_chambers = ["house", "senate"]
        if allow_nochamber:
            valid_chambers.append("nochamber")
        
        if chamber_lower not in valid_chambers:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid chamber: {chamber}",
                suggestions=[f"Must be one of: {', '.join(valid_chambers)}"]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=chamber_lower)
    
    @staticmethod
    def validate_report_type(report_type: str) -> ValidationResult:
        """
        Validate committee report types.
        
        Args:
            report_type: Report type to validate (e.g., 'hrpt', 'srpt', 'erpt')
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        if not isinstance(report_type, str):
            return ValidationResult(
                is_valid=False,
                error_message="Report type must be a string",
                suggestions=["Provide report type as 'hrpt', 'srpt', or 'erpt'"]
            )
        
        report_type_lower = report_type.lower().strip()
        valid_types = ["hrpt", "srpt", "erpt"]  # House, Senate, Executive reports
        
        if report_type_lower not in valid_types:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid report type: {report_type}",
                suggestions=[f"Must be one of: {', '.join(valid_types)}"]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=report_type_lower)
    
    @staticmethod
    def validate_report_number(report_number: int) -> ValidationResult:
        """
        Validate committee report numbers.
        
        Args:
            report_number: Report number to validate
            
        Returns:
            ValidationResult with validation status
        """
        if not isinstance(report_number, int):
            return ValidationResult(
                is_valid=False,
                error_message="Report number must be an integer",
                suggestions=["Provide a positive integer report number"]
            )
        
        if report_number <= 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"Report number must be positive: {report_number}",
                suggestions=["Provide a positive integer report number (e.g., 1, 100, 500)"]
            )
        
        # Committee reports typically don't exceed 9999 per congress
        if report_number > 9999:
            return ValidationResult(
                is_valid=False,
                error_message=f"Report number seems unusually high: {report_number}",
                suggestions=["Check the report number - typical range is 1-9999"]
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_conference_filter(conference: str) -> ValidationResult:
        """
        Validate conference report filter parameter.
        
        Args:
            conference: Conference filter value ('true' or 'false')
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        if not isinstance(conference, str):
            return ValidationResult(
                is_valid=False,
                error_message="Conference filter must be a string",
                suggestions=["Provide 'true' or 'false'"]
            )
        
        conference_lower = conference.lower().strip()
        valid_values = ["true", "false"]
        
        if conference_lower not in valid_values:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid conference filter: {conference}",
                suggestions=["Must be 'true' or 'false'"]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=conference_lower)
    
    @staticmethod
    def validate_offset(offset: int) -> ValidationResult:
        """
        Validate pagination offset parameter.
        
        Args:
            offset: Offset value for pagination
            
        Returns:
            ValidationResult with validation status
        """
        if not isinstance(offset, int):
            return ValidationResult(
                is_valid=False,
                error_message="Offset must be an integer",
                suggestions=["Provide a non-negative integer for pagination offset"]
            )
        
        if offset < 0:
            return ValidationResult(
                is_valid=False,
                error_message=f"Offset must be non-negative: {offset}",
                suggestions=["Provide a non-negative integer (0 or greater)"]
            )
        
        # Reasonable upper limit for offset
        if offset > 10000:
            return ValidationResult(
                is_valid=False,
                error_message=f"Offset seems unusually high: {offset}",
                suggestions=["Consider using a smaller offset value for better performance"]
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def validate_state_code(state_code: str) -> ValidationResult:
        """
        Validate US state codes for Congressional member queries.
        
        Args:
            state_code: Two-letter state code to validate
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        if not state_code:
            return ValidationResult(
                is_valid=False,
                error_message="State code cannot be empty",
                suggestions=["Provide a two-letter state code like 'CA', 'TX', 'NY'"]
            )
        
        # Sanitize input
        state_code_clean = str(state_code).strip().upper()
        
        # Valid US state and territory codes
        valid_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
            'DC', 'AS', 'GU', 'MP', 'PR', 'VI'  # Territories with Congressional representation
        }
        
        if len(state_code_clean) != 2:
            return ValidationResult(
                is_valid=False,
                error_message=f"State code must be exactly 2 characters: '{state_code}'",
                suggestions=["Use two-letter state codes like 'CA' for California, 'TX' for Texas"]
            )
        
        if state_code_clean not in valid_states:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid state code: '{state_code_clean}'",
                suggestions=[
                    "Use valid US state codes like 'CA', 'TX', 'NY', 'FL'",
                    "Territories: 'DC', 'PR', 'VI', 'GU', 'AS', 'MP'"
                ]
            )
        
        return ValidationResult(is_valid=True, sanitized_value=state_code_clean)

# Convenience functions for specific APIs
class BoundCongressionalRecordValidator:
    """Specialized validator for Bound Congressional Record API."""
    
    @staticmethod
    def validate_parameters(year: Optional[str], month: Optional[str], day: Optional[str], limit: int) -> ValidationResult:
        """Validate all parameters for bound congressional record searches."""
        
        # Validate year with bound record specific range
        if year:
            year_result = ParameterValidator.validate_year_range(
                year, 
                ParameterValidator.BOUND_RECORD_MIN_YEAR, 
                ParameterValidator.BOUND_RECORD_MAX_YEAR
            )
            if not year_result.is_valid:
                return year_result
        
        # Validate date components
        date_result = ParameterValidator.validate_date_components(year, month, day)
        if not date_result.is_valid:
            return date_result
        
        # Validate limit
        limit_result = ParameterValidator.validate_limit_range(limit)
        if not limit_result.is_valid:
            return limit_result
        
        return ValidationResult(is_valid=True)
