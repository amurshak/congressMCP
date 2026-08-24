"""
Standardized error handling and response formatting for Congressional MCP APIs.

This module provides consistent error response formats, user-friendly error messages,
and debugging utilities across all APIs.
"""

import logging
from typing import List, Optional, Dict, Any
import json
import re as _re_mod
from urllib.parse import urlsplit, urlunsplit
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """Standard error types for Congressional MCP APIs."""
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    GENERAL = "general"

@dataclass
class APIErrorResponse:
    """Standardized error response format."""
    error_type: str
    message: str
    suggestions: List[str]
    error_code: str
    details: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Ensure error_type is valid."""
        if isinstance(self.error_type, ErrorType):
            self.error_type = self.error_type.value

class ErrorText(str):
    """The formatted error string, still carrying its typed APIErrorResponse.

    Converters for structured (Pydantic) tools read `.error_response` to
    populate the typed `error` field; str-returning tools emit the string
    as-is. A plain-str consumer sees only the JSON envelope text.
    """

    error_response: "APIErrorResponse"

    def __new__(cls, text: str, error_response: "APIErrorResponse"):
        obj = super().__new__(cls, text)
        obj.error_response = error_response
        return obj


_URL_RE = _re_mod.compile(r"https?://\S+")


def _strip_url_secrets(value):
    """Spec section 9 (F22 rule): any URL reaching an error `detail` is
    stripped to scheme+host+path -- query strings can carry the api_key or
    signed redirect tokens."""
    if isinstance(value, str) and "://" in value:
        try:
            parts = urlsplit(value)
            if parts.scheme and parts.netloc:
                return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            # URL embedded mid-sentence: strip the query of every match.
            return _URL_RE.sub(lambda m: m.group(0).split("?", 1)[0].split("#", 1)[0], value)
        except ValueError:
            return value
    return value


def error_envelope(error: APIErrorResponse) -> dict:
    """Section-9 error envelope dict for a typed error.

    {"error": {"code", "message", "detail", "remediation"}} with a stable
    lowercase code, secret-stripped detail, and the suggestions folded into
    one actionable remediation string.
    """
    detail = None
    if error.details:
        detail = {k: _strip_url_secrets(v) for k, v in error.details.items()
                  if v is not None}
        detail = detail or None
    remediation = "; ".join(error.suggestions) if error.suggestions else None
    return {
        "error": {
            "code": (error.error_code or "general_error").lower(),
            "message": error.message,
            "detail": detail,
            "remediation": remediation,
        }
    }


def format_error_response(error: APIErrorResponse) -> str:
    """Render a typed error as the section-9 JSON envelope (one envelope
    format for the whole server -- models parse structure, not prose).

    Returns an ErrorText: a str whose `.error_response` lets the structured
    converters rebuild the typed `error` field without re-parsing JSON.
    """
    return ErrorText(json.dumps(error_envelope(error), indent=2), error)


class CongressionalAPIError(Exception):
    """Base exception for Congressional MCP API errors."""
    
    def __init__(self, error_response: APIErrorResponse):
        self.error_response = error_response
        super().__init__(format_error_response(error_response))

# Pre-defined error responses for common scenarios
class CommonErrors:
    """Common error responses for reuse across APIs."""
    
    @staticmethod
    def invalid_congress_number(congress: Any) -> APIErrorResponse:
        """Error for invalid congress numbers."""
        return APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=f"Invalid congress number: {congress}",
            suggestions=[
                "Congress numbers should be integers between 1 and 119",
                "The current Congress is 119 (2025-2026)",
                "The first Congress was 1 (1789-1791)"
            ],
            error_code="INVALID_CONGRESS_NUMBER",
            details={"provided_value": str(congress)}
        )
    
    @staticmethod
    def invalid_year_range(year: Any, min_year: int, max_year: int) -> APIErrorResponse:
        """Error for years outside valid range."""
        return APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=f"Year {year} is outside the available range ({min_year}-{max_year})",
            suggestions=[
                f"Try a year between {min_year} and {max_year}",
                "Different Congressional data types have different year ranges",
                "Bound Congressional Records: 1873-1997",
                "Bills and Amendments: 1973-present"
            ],
            error_code="YEAR_OUT_OF_RANGE",
            details={
                "provided_year": str(year),
                "min_year": min_year,
                "max_year": max_year
            }
        )
    
    @staticmethod
    def invalid_date_format(date_component: str, value: Any) -> APIErrorResponse:
        """Error for invalid date components."""
        return APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=f"Invalid {date_component}: {value}",
            suggestions=[
                f"{date_component.title()} should be a valid integer",
                "Years: 4-digit format (e.g., 2023)",
                "Months: 1-12 (1=January, 12=December)",
                "Days: 1-31 (depending on month)"
            ],
            error_code=f"INVALID_{date_component.upper()}",
            details={"provided_value": str(value)}
        )
    
    @staticmethod
    def invalid_bill_type(bill_type: Any) -> APIErrorResponse:
        """Error for invalid bill types."""
        valid_types = ['hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres']
        return APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=f"Invalid bill type: {bill_type}",
            suggestions=[
                f"Valid bill types: {', '.join(valid_types)}",
                "hr = House Bill, s = Senate Bill",
                "hjres = House Joint Resolution, sjres = Senate Joint Resolution",
                "hconres = House Concurrent Resolution, sconres = Senate Concurrent Resolution"
            ],
            error_code="INVALID_BILL_TYPE",
            details={"provided_value": str(bill_type), "valid_types": valid_types}
        )
    
    @staticmethod
    def invalid_amendment_type(amendment_type: Any) -> APIErrorResponse:
        """Error for invalid amendment types."""
        valid_types = ['samdt', 'hamdt']
        return APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=f"Invalid amendment type: {amendment_type}",
            suggestions=[
                f"Valid amendment types: {', '.join(valid_types)}",
                "samdt = Senate Amendment",
                "hamdt = House Amendment"
            ],
            error_code="INVALID_AMENDMENT_TYPE",
            details={"provided_value": str(amendment_type), "valid_types": valid_types}
        )
    
    @staticmethod
    def invalid_communication_type(communication_type: Any) -> APIErrorResponse:
        """Error for invalid house communication types."""
        valid_types = ['ec', 'ml', 'pm', 'pt']
        return APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=f"Invalid communication type: {communication_type}",
            suggestions=[
                f"Valid communication types: {', '.join(valid_types)}",
                "ec = Executive Communication",
                "ml = Memorial Letter",
                "pm = Petition or Memorial",
                "pt = Petition"
            ],
            error_code="INVALID_COMMUNICATION_TYPE",
            details={"provided_value": str(communication_type), "valid_types": valid_types}
        )
    
    @staticmethod
    def api_timeout(endpoint: str, timeout_seconds: float) -> APIErrorResponse:
        """Error for API timeouts."""
        return APIErrorResponse(
            error_type=ErrorType.TIMEOUT,
            message=f"Request to {endpoint} timed out after {timeout_seconds} seconds",
            suggestions=[
                "The Congressional API may be experiencing delays",
                "Try again in a few moments",
                "Consider using a smaller date range or limit",
                "Check if your parameters are valid"
            ],
            error_code="API_TIMEOUT",
            details={"endpoint": endpoint, "timeout_seconds": timeout_seconds}
        )
    
    @staticmethod
    def invalid_parameter(parameter_name: str, value: Any, message: str = None) -> APIErrorResponse:
        """Error for invalid parameter values."""
        error_message = f"Invalid {parameter_name}: {value}"
        if message:
            error_message += f". {message}"
        
        return APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=error_message,
            suggestions=[
                f"Check the {parameter_name} value and try again",
                "Refer to the API documentation for valid parameter values"
            ],
            error_code="INVALID_PARAMETER",
            details={"parameter": parameter_name, "provided_value": str(value)}
        )

    @staticmethod
    def api_server_error(endpoint: str, status_code: int = None, message: str = None) -> APIErrorResponse:
        """Error for API server issues and failures."""
        default_message = "The Congressional API is experiencing issues"
        if message:
            default_message = message
        elif status_code:
            default_message = f"API request to {endpoint} failed with status {status_code}"
        
        return APIErrorResponse(
            error_type=ErrorType.SERVER_ERROR,
            message=default_message,
            suggestions=[
                "Try again in a few minutes",
                "The issue is on the API server side, not your request",
                "Consider trying a different endpoint or simpler query",
                "Check the Congress.gov status page for known issues"
            ],
            error_code="SERVER_ERROR",
            details={"endpoint": endpoint, "status_code": status_code}
        )

    @staticmethod
    def rate_limit_exceeded(endpoint: str, retry_after: Optional[int] = None) -> APIErrorResponse:
        """Error for rate limiting."""
        suggestions = [
            "Wait before making another request",
            "Consider reducing the frequency of your requests",
            "Use pagination to get data in smaller chunks"
        ]
        
        if retry_after:
            suggestions.insert(0, f"Try again after {retry_after} seconds")
        
        return APIErrorResponse(
            error_type=ErrorType.RATE_LIMIT,
            message="Too many requests to the Congressional API",
            suggestions=suggestions,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"endpoint": endpoint, "retry_after": retry_after}
        )

    @staticmethod
    def data_not_found(resource_type: str, search_criteria: Dict[str, Any] = None, identifier: str = None) -> APIErrorResponse:
        """Error for when requested data is not found."""
        if identifier:
            message = f"{resource_type} not found: {identifier}"
            suggestions = [
                f"Verify the {resource_type.lower()} identifier is correct",
                "Check if the resource exists in the specified congress",
                "Try searching for similar resources"
            ]
            details = {"resource_type": resource_type, "identifier": identifier}
        else:
            message = f"No {resource_type} found matching your search criteria"
            suggestions = [
                "Check that your parameters are correct",
                "Try broadening your search criteria",
                "Verify the data exists for the time period you're searching",
                "Some historical data may not be available"
            ]
            details = {"resource_type": resource_type}
            if search_criteria:
                details["search_criteria"] = search_criteria
        
        return APIErrorResponse(
            error_type=ErrorType.NOT_FOUND,
            message=message,
            suggestions=suggestions,
            error_code="DATA_NOT_FOUND",
            details=details
        )

    @staticmethod
    def general_error(message: str, suggestions: List[str] = None, error_code: str = "GENERAL_ERROR") -> APIErrorResponse:
        """Generic error for unexpected situations."""
        return APIErrorResponse(
            error_type=ErrorType.GENERAL,
            message=message,
            suggestions=suggestions or [
                "Try again in a few moments",
                "Contact support if the issue persists"
            ],
            error_code=error_code,
            details={}
        )

# Utility functions for error handling
def handle_validation_error(validation_result) -> None:
    """
    Handle validation errors by raising CongressionalAPIError.
    
    Args:
        validation_result: ValidationResult from parameter validation
        
    Raises:
        CongressionalAPIError: If validation failed
    """
    if not validation_result.is_valid:
        error_response = APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=validation_result.error_message,
            suggestions=validation_result.suggestions or [],
            error_code="VALIDATION_FAILED"
        )
        raise CongressionalAPIError(error_response)

def log_error(error: APIErrorResponse, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log error details for debugging.
    
    Args:
        error: The error response to log
        context: Additional context for logging
    """
    log_data = {
        "error_type": error.error_type,
        "error_code": error.error_code,
        "message": error.message
    }
    
    if error.details:
        log_data.update(error.details)
    
    if context:
        log_data["context"] = context
    
    logger.error(f"Congressional API Error: {log_data}")

def create_user_friendly_error(
    error_type: ErrorType,
    message: str,
    suggestions: List[str],
    error_code: str,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a user-friendly error message.
    
    Args:
        error_type: Type of error
        message: Error message
        suggestions: List of suggestions
        error_code: Internal error code
        details: Additional error details
        
    Returns:
        Formatted error string
    """
    error_response = APIErrorResponse(
        error_type=error_type,
        message=message,
        suggestions=suggestions,
        error_code=error_code,
        details=details
    )
    
    return format_error_response(error_response)
