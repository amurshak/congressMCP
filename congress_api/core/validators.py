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
