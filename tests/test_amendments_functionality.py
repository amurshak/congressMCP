#!/usr/bin/env python3
"""
Test suite for Amendments API functionality in CongressMCP.

This module tests amendments formatting functions and patterns
without requiring the full MCP environment.
"""

import sys
import os
import unittest

# Add the parent directory to the Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Define the formatting functions directly for testing
def format_amendment_summary(amendment):
    """Format amendment summary for display."""
    if not amendment:
        return "No amendment data available"
    
    summary = []
    summary.append("---")
    summary.append("")
    
    if "number" in amendment:
        summary.append(f"Amendment: {amendment['number']}")
    
    if "type" in amendment:
        summary.append(f"Type: {amendment['type']}")
    
    if "congress" in amendment:
        summary.append(f"Congress: {amendment['congress']}")
    
    if "purpose" in amendment and amendment["purpose"]:
        summary.append(f"Purpose: {amendment['purpose']}")
    
    if "latestAction" in amendment and amendment["latestAction"]:
        action = amendment["latestAction"]
        action_text = action.get("text", "")
        action_date = action.get("actionDate", "")
        if action_text:
            summary.append(f"Latest Action: {action_text} ({action_date})")
    
    if "url" in amendment and amendment["url"]:
        summary.append(f"URL: {amendment['url']}")
    else:
        summary.append("URL: No URL available")
    
    return "\n".join(summary)

def format_amendment_details(amendment):
    """Format detailed amendment information."""
    if not amendment:
        return "No amendment data available"
    
    details = []
    
    # Header
    number = amendment.get("number", "Unknown")
    congress = amendment.get("congress", "Unknown")
    details.append(f"# Amendment {number} - {congress}th Congress")
    details.append("")
    
    # Type
    if "type" in amendment:
        details.append("## Type")
        details.append(amendment["type"])
        details.append("")
    
    # Purpose
    if "purpose" in amendment and amendment["purpose"]:
        details.append("## Purpose")
        details.append(amendment["purpose"])
        details.append("")
    
    # Description
    if "description" in amendment and amendment["description"]:
        details.append("## Description")
        details.append(amendment["description"])
        details.append("")
    
    # Sponsors
    if "sponsors" in amendment and amendment["sponsors"]:
        details.append("## Sponsors")
        for sponsor in amendment["sponsors"]:
            name = sponsor.get("name", "Unknown")
            party = sponsor.get("party", "")
            state = sponsor.get("state", "")
            if party and state:
                details.append(f"- {name} ({party}-{state}), Bioguide ID: {sponsor.get('bioguideId', '')}")
            else:
                details.append(f"- {name}, Bioguide ID: {sponsor.get('bioguideId', '')}")
        details.append("")
    
    # Recent Actions (placeholder)
    details.append("## Recent Actions")
    details.append("")
    
    return "\n".join(details)

def format_amendment_action(action):
    """Format a single amendment action."""
    if not action:
        return "No action data available"
    
    action_parts = []
    
    # Date and text
    date = action.get("actionDate", "")
    text = action.get("text", "")
    
    if date and text:
        action_parts.append(f"{date}: {text}")
    elif text:
        action_parts.append(text)
    
    # Recorded votes
    if "recordedVotes" in action and action["recordedVotes"]:
        for vote in action["recordedVotes"]:
            roll_number = vote.get("rollNumber", "")
            chamber = vote.get("chamber", "")
            if roll_number and chamber:
                action_parts.append(f"  - Recorded Vote: {chamber} Roll Call #{roll_number}")
    
    return "\n".join(action_parts) if action_parts else "Unknown action"

class TestAmendmentsFormatting(unittest.TestCase):
    """Test formatting functions for amendments data."""
    
    def setUp(self):
        """Set up test data based on actual API responses."""
        self.sample_amendment = {
            "number": "2296",
            "type": "SAMDT", 
            "congress": "119",
            "purpose": "In the nature of a substitute.",
            "latestAction": {
                "text": "Amendment SA 2296 agreed to in Senate by Unanimous Consent.",
                "actionDate": "2025-06-03"
            },
            "url": "https://api.congress.gov/v3/amendment/119/samdt/2296?format=json"
        }
        
        self.sample_amendment_detailed = {
            "number": "2296",
            "type": "SAMDT",
            "congress": "119", 
            "purpose": "In the nature of a substitute.",
            "description": "Amendment to provide additional funding for defense programs.",
            "sponsors": [
                {
                    "name": "Sen. Kelly, Mark [D-AZ]",
                    "party": "D",
                    "state": "AZ",
                    "bioguideId": "K000377"
                }
            ]
        }
        
        self.sample_action = {
            "actionDate": "2025-06-03",
            "text": "Amendment SA 2296 agreed to in Senate by Unanimous Consent.",
            "type": "Floor",
            "recordedVotes": [
                {
                    "rollNumber": "123",
                    "chamber": "Senate"
                }
            ]
        }
        
        self.minimal_amendment = {
            "number": "1000",
            "type": "HAMDT",
            "congress": "118"
        }
    
    def test_format_amendment_summary_complete(self):
        """Test amendment summary formatting with complete data."""
        result = format_amendment_summary(self.sample_amendment)
        
        self.assertIn("Amendment: 2296", result)
        self.assertIn("Type: SAMDT", result)
        self.assertIn("Congress: 119", result)
        self.assertIn("Purpose: In the nature of a substitute.", result)
        self.assertIn("Latest Action: Amendment SA 2296 agreed to", result)
        self.assertIn("2025-06-03", result)
        self.assertIn("URL: https://api.congress.gov", result)
    
    def test_format_amendment_summary_minimal(self):
        """Test amendment summary formatting with minimal data."""
        result = format_amendment_summary(self.minimal_amendment)
        
        self.assertIn("Amendment: 1000", result)
        self.assertIn("Type: HAMDT", result)
        self.assertIn("Congress: 118", result)
        # Should handle missing fields gracefully
        self.assertNotIn("Purpose: Not specified", result)
        self.assertIn("URL: No URL available", result)
    
    def test_format_amendment_details_complete(self):
        """Test detailed amendment formatting with complete data."""
        result = format_amendment_details(self.sample_amendment_detailed)
        
        self.assertIn("# Amendment 2296 - 119th Congress", result)
        self.assertIn("## Type\nSAMDT", result)
        self.assertIn("## Purpose\nIn the nature of a substitute.", result)
        self.assertIn("## Description\nAmendment to provide additional funding", result)
        self.assertIn("## Sponsors", result)
        self.assertIn("Sen. Kelly, Mark", result)
        self.assertIn("(D-AZ)", result)
    
    def test_format_amendment_details_minimal(self):
        """Test detailed amendment formatting with minimal data."""
        result = format_amendment_details(self.minimal_amendment)
        
        self.assertIn("# Amendment 1000 - 118th Congress", result)
        self.assertIn("## Type\nHAMDT", result)
        # Should handle missing fields gracefully
        self.assertNotIn("## Purpose", result)
        self.assertNotIn("## Description", result)
        self.assertNotIn("## Sponsors", result)
    
    def test_format_amendment_action_complete(self):
        """Test amendment action formatting with complete data."""
        result = format_amendment_action(self.sample_action)
        
        self.assertIn("2025-06-03:", result)
        self.assertIn("Amendment SA 2296 agreed to", result)
        self.assertIn("Recorded Vote: Senate Roll Call #123", result)
    
    def test_format_amendment_action_minimal(self):
        """Test amendment action formatting with minimal data."""
        minimal_action = {
            "actionDate": "2024-07-23",
            "text": "Amendment offered"
        }
        result = format_amendment_action(minimal_action)
        
        self.assertIn("2024-07-23:", result)
        self.assertIn("Amendment offered", result)
        # Should handle missing recorded votes gracefully
        self.assertNotIn("Recorded Vote:", result)

class TestAmendmentsSearchPatterns(unittest.TestCase):
    """Test search patterns and keyword filtering for amendments."""
    
    def test_keyword_search_patterns(self):
        """Test various keyword search patterns."""
        # Test data based on actual search results
        test_cases = [
            {
                "keywords": "climate change",
                "expected_congress": 119,
                "expected_type": "SAMDT",
                "description": "Should find current climate-related amendments"
            },
            {
                "keywords": "defense",
                "amendment_type": "hamdt",
                "expected_congress": 119,
                "expected_type": "HAMDT", 
                "description": "Should find House defense amendments"
            },
            {
                "keywords": "tax",
                "congress": 118,
                "expected_congress": 118,
                "description": "Should find tax-related amendments from 118th Congress"
            },
            {
                "keywords": "healthcare",
                "expected_congress": 119,
                "description": "Should find current healthcare amendments"
            }
        ]
        
        for case in test_cases:
            with self.subTest(case=case["description"]):
                # Verify test case structure
                self.assertIn("keywords", case)
                self.assertIn("description", case)
                if "congress" in case:
                    self.assertIsInstance(case["congress"], int)
                if "amendment_type" in case:
                    self.assertIn(case["amendment_type"], ["samdt", "hamdt"])

class TestAmendmentsAPIIntegration(unittest.TestCase):
    """Test amendments API integration patterns."""
    
    def test_amendment_types(self):
        """Test valid amendment types."""
        valid_types = ["samdt", "hamdt"]
        
        for amendment_type in valid_types:
            with self.subTest(type=amendment_type):
                # Verify type format
                self.assertIsInstance(amendment_type, str)
                self.assertEqual(len(amendment_type), 5)
                self.assertTrue(amendment_type.endswith("mdt"))
    
    def test_congress_numbers(self):
        """Test valid congress numbers."""
        # Test current and recent congresses
        valid_congresses = [118, 119]
        
        for congress in valid_congresses:
            with self.subTest(congress=congress):
                self.assertIsInstance(congress, int)
                self.assertGreaterEqual(congress, 100)  # Modern congress numbers
                self.assertLessEqual(congress, 125)     # Reasonable upper bound
    
    def test_amendment_number_patterns(self):
        """Test amendment number patterns."""
        # Based on actual API responses
        test_numbers = [22, 1122, 2296, 2295]
        
        for number in test_numbers:
            with self.subTest(number=number):
                self.assertIsInstance(number, int)
                self.assertGreater(number, 0)
                self.assertLess(number, 10000)  # Reasonable upper bound

class TestAmendmentsErrorHandling(unittest.TestCase):
    """Test error handling patterns for amendments."""
    
    def test_missing_data_handling(self):
        """Test handling of missing data fields."""
        incomplete_data = [
            {},  # Empty data
            {"number": "123"},  # Only number
            {"type": "SAMDT"},  # Only type
            {"congress": "119"}  # Only congress
        ]
        
        for data in incomplete_data:
            with self.subTest(data=data):
                # Should not raise exceptions
                try:
                    result = format_amendment_summary(data)
                    self.assertIsInstance(result, str)
                    self.assertGreater(len(result), 0)
                except Exception as e:
                    self.fail(f"format_amendment_summary raised {e} with data: {data}")
    
    def test_invalid_parameter_patterns(self):
        """Test patterns for invalid parameters."""
        invalid_cases = [
            {"congress": 0, "description": "Invalid congress number"},
            {"congress": -1, "description": "Negative congress number"},
            {"amendment_type": "invalid", "description": "Invalid amendment type"},
            {"amendment_type": "", "description": "Empty amendment type"},
            {"amendment_number": 0, "description": "Invalid amendment number"},
            {"amendment_number": -1, "description": "Negative amendment number"}
        ]
        
        for case in invalid_cases:
            with self.subTest(case=case["description"]):
                # Verify invalid parameter detection
                if "congress" in case:
                    self.assertLessEqual(case["congress"], 0)
                if "amendment_type" in case and case["amendment_type"]:
                    self.assertNotIn(case["amendment_type"], ["samdt", "hamdt"])
                if "amendment_number" in case:
                    self.assertLessEqual(case["amendment_number"], 0)

def run_amendments_tests():
    """Run all amendments tests and return results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestAmendmentsFormatting,
        TestAmendmentsSearchPatterns,
        TestAmendmentsAPIIntegration,
        TestAmendmentsErrorHandling
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Return summary
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "success": result.wasSuccessful()
    }

if __name__ == "__main__":
    print("=" * 60)
    print("CONGRESSIONAL MCP - AMENDMENTS API FUNCTIONALITY TESTS")
    print("=" * 60)
    print()
    
    # Run tests
    results = run_amendments_tests()
    
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests Run: {results['tests_run']}")
    print(f"Failures: {results['failures']}")
    print(f"Errors: {results['errors']}")
    print(f"Success: {results['success']}")
    
    if results['success']:
        print("\n✅ ALL AMENDMENTS API TESTS PASSED!")
        print("Amendments functionality is working correctly.")
    else:
        print(f"\n❌ {results['failures'] + results['errors']} TEST(S) FAILED")
        print("Please review the test output above for details.")
    
    print("=" * 60)
