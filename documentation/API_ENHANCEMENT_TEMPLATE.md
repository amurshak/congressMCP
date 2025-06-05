# Congressional API Enhancement Template
## Systematic Reliability Framework Integration Guide

This template provides a step-by-step process for enhancing any Congressional API with the reliability framework, based on the successful Committee Prints API enhancement.

## 📋 Pre-Enhancement Checklist

### 1. **API Assessment**
- [ ] Identify all MCP tools and resources in the API
- [ ] Document current error handling patterns
- [ ] List parameter validation methods used


### 2. **Framework Components Available**
- [ ] `ParameterValidator` (congress_api/core/validators.py)
- [ ] `DefensiveAPIWrapper` (congress_api/core/api_wrapper.py)
- [ ] `CommonErrors` (congress_api/core/exceptions.py)
- [ ] `ResponseProcessor` (congress_api/core/response_utils.py)

## 🔧 Enhancement Process

### Phase 1: Error Handling Consolidation

#### **Step 1.1: Replace Deprecated Error Methods**
```python
# OLD (deprecated)
return not_found()
return validation_error()
return api_failure()
return general_error(msg, suggestions, code)

# NEW (consolidated)
return CommonErrors.data_not_found(resource_type, identifier)
return CommonErrors.invalid_parameter(param_name, param_value, message)
return CommonErrors.api_server_error(message)
return CommonErrors.general_error(message, suggestions)
```

#### **Step 1.2: Update Error Method Signatures**
- Check all `general_error()` calls match new signature: `(message, suggestions=None)`
- Ensure all error responses use `format_error_response(error)`

### Phase 2: Parameter Validation Enhancement

#### **Step 2.1: Add Missing Validation Methods**
Check if these validators exist in `ParameterValidator`:
```python
# Common validators needed
validate_congress_number(congress)
validate_chamber(chamber)
validate_limit_range(limit, max_limit=250)
validate_offset(offset)
validate_date_time(date_string)

# API-specific validators (add as needed)
validate_jacket_number(jacket_number)  # Committee prints
validate_bill_number(bill_number)      # Bills
validate_member_id(member_id)          # Members
```

#### **Step 2.2: Replace Manual Validation**
```python
# OLD (manual checks)
if not congress or congress < 1:
    return error_response("Invalid congress")

# NEW (framework validation)
congress_result = ParameterValidator.validate_congress_number(congress)
if not congress_result.is_valid:
    error = CommonErrors.invalid_parameter("congress", congress, congress_result.error_message)
    return format_error_response(error)
```

### Phase 3: Defensive API Integration

#### **Step 3.1: Create API-Specific Wrapper**
```python
# In congress_api/core/api_wrapper.py
async def safe_{api_name}_request(endpoint: str, ctx: Context, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Defensive wrapper for {API_NAME} API requests with:
    - Parameter sanitization
    - Timeout handling
    - Retry logic
    - Standardized error responses
    """
    return await safe_api_request(endpoint, ctx, params or {})
```

#### **Step 3.2: Replace Direct API Calls**
```python
# OLD (direct API calls)
response = await make_api_request(endpoint, ctx)

# NEW (defensive wrapper)
response = await safe_{api_name}_request(endpoint, ctx, params)
```

### Phase 4: Response Structure Handling

#### **Step 4.1: Add Response Type Checking**
```python
# Handle API responses that may be lists or dictionaries
if isinstance(data, list):
    if len(data) > 0:
        item = data[0]  # Take first item
    else:
        return CommonErrors.data_not_found(resource_type, identifier)
else:
    # Handle dictionary response
    if "error" in data:
        return CommonErrors.api_server_error(data.get("error"))
    item = data.get("item") or data
```

#### **Step 4.2: Add Response Processing**
```python
# Create processor class in response_utils.py
class {APIName}Processor:
    @staticmethod
    def deduplicate_results(results: List[Dict]) -> List[Dict]:
        """Remove duplicates based on key fields"""
        
    @staticmethod
    def clean_response(data: Dict) -> Dict:
        """Clean and standardize response data"""
```

### Phase 5: Architecture Standardization

#### **Step 5.1: Tools vs Resources Evaluation**
```python
# CONVERT TO TOOLS (interactive/functional endpoints):
# - Search functions
# - Get details functions  
# - List/filter functions
# - Any function that takes user parameters

# KEEP AS RESOURCES (static/reference data):
# - Documentation
# - Static reference lists
# - Configuration data
```

#### **Step 5.2: MCP Tool Conversion**
```python
# OLD (MCP Resource)
@mcp.resource(uri="committee-prints://latest")
async def latest_committee_prints() -> str:

# NEW (MCP Tool)
@mcp.tool()
async def get_latest_committee_prints(ctx: Context) -> str:
```

### Phase 6: Enhanced Logging and Debugging

#### **Step 6.1: Add Structured Logging**
```python
import logging
logger = logging.getLogger(__name__)

# Add throughout functions:
logger.debug(f"Fetching {resource_type} with parameters: {params}")
logger.info(f"Found {len(results)} {resource_type} results")
logger.error(f"API request failed: {error_message}")
```

#### **Step 6.2: Add Response Debugging**
```python
# For troubleshooting response structure issues
logger.debug(f"API response type: {type(data)}")
logger.debug(f"API response structure: {data}")
```

## 🧪 Testing Checklist

### **Functionality Testing**
- [ ] All functions execute without runtime errors
- [ ] Valid parameters return expected results
- [ ] Response formatting is consistent and professional

### **Validation Testing**
- [ ] Invalid congress numbers rejected with helpful errors
- [ ] Invalid chamber values rejected
- [ ] Negative/zero values rejected where appropriate
- [ ] Date format validation working

### **Error Handling Testing**
- [ ] API failures return user-friendly error messages
- [ ] Missing data returns appropriate "not found" responses
- [ ] Network timeouts handled gracefully

### **Edge Case Testing**
- [ ] Empty results handled properly
- [ ] Large result sets paginated correctly
- [ ] Malformed API responses don't cause crashes

## 📁 File Modification Checklist

### **Core Files to Update:**
- [ ] `congress_api/core/validators.py` - Add new validation methods
- [ ] `congress_api/core/api_wrapper.py` - Add API-specific wrapper
- [ ] `congress_api/core/response_utils.py` - Add response processor
- [ ] `congress_api/features/{api_name}.py` - Apply all enhancements

### **Documentation Updates:**
- [ ] Update function docstrings
- [ ] Document new parameters and return types
- [ ] Add usage examples

## 🎯 Success Criteria

### **Reliability Metrics:**
- ✅ Zero runtime errors during normal operation
- ✅ Graceful handling of all edge cases
- ✅ Consistent error messaging across all functions
- ✅ No hanging or timeout issues

### **User Experience Metrics:**
- ✅ Clear, actionable error messages
- ✅ Consistent response formatting
- ✅ Helpful parameter validation feedback
- ✅ Professional markdown output

### **Architecture Metrics:**
- ✅ Consistent MCP tool/resource patterns
- ✅ Reusable validation and error handling
- ✅ Defensive programming throughout
- ✅ Comprehensive logging for debugging

## 🔄 Reusable Patterns

### **Parameter Validation Pattern:**
```python
# 1. Validate all parameters
param_result = ParameterValidator.validate_param(value)
if not param_result.is_valid:
    error = CommonErrors.invalid_parameter("param", value, param_result.error_message)
    return format_error_response(error)

# 2. Make defensive API call
data = await safe_api_request(endpoint, ctx, params)

# 3. Handle response structure
if isinstance(data, list):
    items = data
else:
    items = data.get("items", [])

# 4. Process and return results
if not items:
    return CommonErrors.data_not_found(resource_type, identifier)
    
return format_results(items)
```

### **Error Handling Pattern:**
```python
try:
    # API operation
    result = await api_operation()
    return format_success_response(result)
except Exception as e:
    error = CommonErrors.api_server_error(f"Operation failed: {str(e)}")
    logger.error(f"API operation failed: {str(e)}")
    return format_error_response(error)
```

## 📈 Enhancement Priority

### **High Priority (Immediate Impact):**
1. Error handling consolidation
2. Parameter validation
3. Response structure fixes

### **Medium Priority (Quality of Life):**
4. Defensive API wrappers
5. Response processing/deduplication
6. Enhanced logging

### **Low Priority (Polish):**
7. Tools vs resources standardization
8. Documentation updates
9. Performance optimizations

## 🔍 Common Issues to Watch For

### **Runtime Errors:**
- `.get()` called on list objects
- Missing `ctx: Context` parameters
- Deprecated error method calls

### **API Issues:**
- Hanging on invalid parameters
- Inconsistent response structures
- Missing error handling

### **User Experience Issues:**
- Generic error messages
- Inconsistent formatting
- Confusing parameter validation

---

## 📝 Template Usage

1. **Copy this template** for each API enhancement project
2. **Customize the checklist** based on specific API needs
3. **Follow the phases sequentially** for systematic improvement
4. **Test thoroughly** at each phase before proceeding
5. **Document lessons learned** for future enhancements

This template ensures consistent, reliable enhancement of all Congressional APIs with minimal effort and maximum reliability.
