#!/usr/bin/env python3
"""
Functional tests for file manipulation tools.
Tests actual file operations using Modal local mode and Seatbelt provider.
"""

import asyncio
import os
import tempfile
import unittest
import platform
import shutil
from pathlib import Path
import sys
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tinyagent.code_agent.providers.modal_provider import ModalProvider
from tinyagent.code_agent.providers.seatbelt_provider import SeatbeltProvider
from tinyagent.hooks.logging_manager import LoggingManager


class TestFileToolsFunctional(unittest.TestCase):
    """Functional tests for file tools."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        self.test_content = "Hello, World!\nThis is a test file.\nLine 3 content."
        
        # Set up logging
        self.log_manager = LoggingManager()
        
        # Create providers
        self.modal_provider = ModalProvider(
            log_manager=self.log_manager,
            local_execution=True,
            authorized_imports=["os", "pathlib", "mimetypes", "re", "fnmatch"]
        )
        
        # Only create seatbelt provider on macOS
        if platform.system() == "Darwin" and SeatbeltProvider.is_supported():
            self.seatbelt_provider = SeatbeltProvider(
                log_manager=self.log_manager,
                local_execution=True
            )
        else:
            self.seatbelt_provider = None
            
        # Test with both providers
        self.providers = [("Modal", self.modal_provider)]
        if self.seatbelt_provider:
            self.providers.append(("Seatbelt", self.seatbelt_provider))
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    async def test_read_file_basic(self):
        """Test basic file reading functionality."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                # Create test file
                with open(self.test_file, 'w') as f:
                    f.write(self.test_content)
                
                # Test reading
                result = await provider.read_file(self.test_file)
                
                self.assertTrue(result.get("success"), f"Read failed: {result.get('error')}")
                self.assertEqual(result.get("content"), self.test_content)
                self.assertTrue("file_size" in result)
                self.assertGreater(result["file_size"], 0)
                
    async def test_read_file_with_line_range(self):
        """Test reading file with line range."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                # Create test file
                with open(self.test_file, 'w') as f:
                    f.write(self.test_content)
                
                # Test reading specific lines
                result = await provider.read_file(self.test_file, start_line=2, max_lines=1)
                
                self.assertTrue(result.get("success"), f"Read failed: {result.get('error')}")
                # Should contain only line 2
                self.assertIn("This is a test file.", result.get("content", ""))
                self.assertNotIn("Hello, World!", result.get("content", ""))
                
    async def test_write_file_basic(self):
        """Test basic file writing functionality."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                content = "New file content\nSecond line\nThird line"
                
                result = await provider.write_file(self.test_file, content)
                
                self.assertTrue(result.get("success"), f"Write failed: {result.get('error')}")
                
                # Verify file was written correctly
                with open(self.test_file, 'r') as f:
                    written_content = f.read()
                self.assertEqual(written_content, content)
                
    async def test_write_file_with_directory_creation(self):
        """Test writing file with automatic directory creation."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                nested_file = os.path.join(self.temp_dir, "subdir", "nested", "file.txt")
                content = "Content in nested directory"
                
                result = await provider.write_file(nested_file, content, create_dirs=True)
                
                self.assertTrue(result.get("success"), f"Write failed: {result.get('error')}")
                
                # Verify file and directories were created
                self.assertTrue(os.path.exists(nested_file))
                with open(nested_file, 'r') as f:
                    written_content = f.read()
                self.assertEqual(written_content, content)
                
    async def test_update_file_basic(self):
        """Test basic file update functionality."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                # Create test file
                with open(self.test_file, 'w') as f:
                    f.write(self.test_content)
                
                # Update content
                result = await provider.update_file(
                    self.test_file, 
                    "Hello, World!", 
                    "Hi, Universe!"
                )
                
                self.assertTrue(result.get("success"), f"Update failed: {result.get('error')}")
                self.assertEqual(result.get("matches_replaced"), 1)
                
                # Verify update
                with open(self.test_file, 'r') as f:
                    updated_content = f.read()
                self.assertIn("Hi, Universe!", updated_content)
                self.assertNotIn("Hello, World!", updated_content)
                
    async def test_update_file_multiple_matches(self):
        """Test updating file with multiple matches."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                content_with_duplicates = "test test test"
                with open(self.test_file, 'w') as f:
                    f.write(content_with_duplicates)
                
                # Update all occurrences
                result = await provider.update_file(
                    self.test_file, 
                    "test", 
                    "demo",
                    expected_matches=3
                )
                
                self.assertTrue(result.get("success"), f"Update failed: {result.get('error')}")
                self.assertEqual(result.get("matches_replaced"), 3)
                
                # Verify all updates
                with open(self.test_file, 'r') as f:
                    updated_content = f.read()
                self.assertEqual(updated_content, "demo demo demo")
                
    async def test_search_files_content(self):
        """Test searching files by content."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                # Create multiple test files
                file1 = os.path.join(self.temp_dir, "file1.txt")
                file2 = os.path.join(self.temp_dir, "file2.py")
                file3 = os.path.join(self.temp_dir, "file3.txt")
                
                with open(file1, 'w') as f:
                    f.write("This contains DEBUG information")
                with open(file2, 'w') as f:
                    f.write("print('Hello')\nDEBUG = True")
                with open(file3, 'w') as f:
                    f.write("No debug info here")
                
                # Search for DEBUG
                result = await provider.search_files("DEBUG", self.temp_dir)
                
                self.assertTrue(result.get("success"), f"Search failed: {result.get('error')}")
                self.assertGreaterEqual(result.get("total_matches", 0), 2)
                
                # Check that files with DEBUG are found
                found_files = [match["file_path"] for match in result.get("matches", [])]
                self.assertTrue(any("file1.txt" in f for f in found_files))
                self.assertTrue(any("file2.py" in f for f in found_files))
                
    async def test_search_files_with_filters(self):
        """Test searching files with file type filters."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                # Create files with different extensions
                py_file = os.path.join(self.temp_dir, "script.py")
                txt_file = os.path.join(self.temp_dir, "document.txt")
                js_file = os.path.join(self.temp_dir, "script.js")
                
                content = "function test() { return true; }"
                for file_path in [py_file, txt_file, js_file]:
                    with open(file_path, 'w') as f:
                        f.write(content)
                
                # Search only in .py files
                result = await provider.search_files(
                    "function", 
                    self.temp_dir,
                    file_types=["py"]
                )
                
                self.assertTrue(result.get("success"), f"Search failed: {result.get('error')}")
                found_files = [match["file_path"] for match in result.get("matches", [])]
                
                # Should only find the .py file
                self.assertTrue(any("script.py" in f for f in found_files))
                self.assertFalse(any("document.txt" in f for f in found_files))
                self.assertFalse(any("script.js" in f for f in found_files))
                
    async def test_error_handling_nonexistent_file(self):
        """Test error handling for non-existent files."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                fake_file = os.path.join(self.temp_dir, "nonexistent.txt")
                
                # Test read
                result = await provider.read_file(fake_file)
                self.assertFalse(result.get("success"))
                self.assertIn("not found", result.get("error", "").lower())
                
                # Test update
                result = await provider.update_file(fake_file, "old", "new")
                self.assertFalse(result.get("success"))
                self.assertIn("not found", result.get("error", "").lower())
                
    async def test_error_handling_directory_as_file(self):
        """Test error handling when trying to read directory as file."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                # Try to read directory as file
                result = await provider.read_file(self.temp_dir)
                self.assertFalse(result.get("success"))
                self.assertIn("directory", result.get("error", "").lower())
                
    async def test_binary_file_detection(self):
        """Test binary file detection and rejection."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                binary_file = os.path.join(self.temp_dir, "test.bin")
                
                # Create a binary file with null bytes
                with open(binary_file, 'wb') as f:
                    f.write(b'\x00\x01\x02\x03\x04\x05\x00\xff')
                
                # Attempt to read binary file
                result = await provider.read_file(binary_file)
                self.assertFalse(result.get("success"))
                # Should contain helpful message about binary files
                error_msg = result.get("error", "").lower()
                print(f"Binary file error message: {error_msg}")  # Debug output
                self.assertTrue(
                    any(keyword in error_msg for keyword in ["binary", "text-based", "text file"]),
                    f"Expected binary file error message, got: {error_msg}"
                )
                
    async def test_large_file_handling(self):
        """Test handling of large files."""
        for provider_name, provider in self.providers:
            with self.subTest(provider=provider_name):
                large_file = os.path.join(self.temp_dir, "large.txt")
                
                # Create a file with many lines
                large_content = "\n".join([f"Line {i}" for i in range(1000)])
                with open(large_file, 'w') as f:
                    f.write(large_content)
                
                # Test reading with line limit
                result = await provider.read_file(large_file, max_lines=10)
                
                self.assertTrue(result.get("success"), f"Read failed: {result.get('error')}")
                lines = result.get("content", "").split('\n')
                self.assertLessEqual(len(lines), 10)
                self.assertIn("Line 0", result.get("content", ""))
                self.assertIn("Line 9", result.get("content", ""))


async def run_functional_tests():
    """Run all functional tests."""
    print("Running file tools functional tests...")
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFileToolsFunctional)
    
    # Create test instance
    test_instance = TestFileToolsFunctional()
    
    for test in suite:
        if hasattr(test, '_testMethodName'):
            test_method_name = test._testMethodName
            test_method = getattr(test_instance, test_method_name)
            
            print(f"\nRunning {test_method_name}...")
            test_instance.setUp()
            
            try:
                if asyncio.iscoroutinefunction(test_method):
                    await test_method()
                else:
                    test_method()
                print(f"✅ {test_method_name} passed")
            except Exception as e:
                print(f"❌ {test_method_name} failed: {e}")
                raise
            finally:
                test_instance.tearDown()


if __name__ == "__main__":
    print("Starting functional tests for file tools...")
    asyncio.run(run_functional_tests())
    print("\n🎉 All functional tests completed successfully!")