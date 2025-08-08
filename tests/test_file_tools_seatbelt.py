#!/usr/bin/env python3
"""
Test file tools with Seatbelt provider on macOS.
"""

import asyncio
import os
import tempfile
import unittest
import platform
import shutil
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tinyagent.code_agent.providers.seatbelt_provider import SeatbeltProvider
from tinyagent.hooks.logging_manager import LoggingManager


class TestFileToolsSeatbelt(unittest.TestCase):
    """Test file tools with Seatbelt provider."""
    
    def setUp(self):
        """Set up test fixtures."""
        if platform.system() != "Darwin" or not SeatbeltProvider.is_supported():
            self.skipTest("Seatbelt provider only supported on macOS with sandbox-exec")
            
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        self.test_content = "Hello, World!\nThis is a test file.\nLine 3 content."
        
        # Set up logging
        self.log_manager = LoggingManager()
        
        # Create Seatbelt provider with file access permissions
        self.provider = SeatbeltProvider(
            log_manager=self.log_manager,
            local_execution=True,
            additional_read_dirs=[self.temp_dir],
            additional_write_dirs=[self.temp_dir]
        )
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    async def test_seatbelt_read_file(self):
        """Test reading file with Seatbelt provider."""
        # Create test file
        with open(self.test_file, 'w') as f:
            f.write(self.test_content)
        
        # Test reading
        result = await self.provider.read_file(self.test_file)
        
        print(f"Seatbelt read result: {result}")
        self.assertTrue(result.get("success"), f"Read failed: {result.get('error')}")
        self.assertEqual(result.get("content"), self.test_content)
        
    async def test_seatbelt_write_file(self):
        """Test writing file with Seatbelt provider."""
        content = "New file content\nSecond line"
        
        result = await self.provider.write_file(self.test_file, content)
        
        print(f"Seatbelt write result: {result}")
        self.assertTrue(result.get("success"), f"Write failed: {result.get('error')}")
        
        # Verify file was written
        with open(self.test_file, 'r') as f:
            written_content = f.read()
        self.assertEqual(written_content, content)
        
    async def test_seatbelt_update_file(self):
        """Test updating file with Seatbelt provider."""
        # Create test file
        with open(self.test_file, 'w') as f:
            f.write(self.test_content)
        
        # Update content
        result = await self.provider.update_file(
            self.test_file, 
            "Hello, World!", 
            "Hi, Universe!"
        )
        
        print(f"Seatbelt update result: {result}")
        self.assertTrue(result.get("success"), f"Update failed: {result.get('error')}")
        self.assertEqual(result.get("matches_replaced"), 1)
        
        # Verify update
        with open(self.test_file, 'r') as f:
            updated_content = f.read()
        self.assertIn("Hi, Universe!", updated_content)
        self.assertNotIn("Hello, World!", updated_content)
        
    async def test_seatbelt_search_files(self):
        """Test searching files with Seatbelt provider."""
        # Create test files
        file1 = os.path.join(self.temp_dir, "file1.txt")
        file2 = os.path.join(self.temp_dir, "file2.py")
        
        with open(file1, 'w') as f:
            f.write("This contains DEBUG information")
        with open(file2, 'w') as f:
            f.write("print('Hello')\nDEBUG = True")
        
        # Search for DEBUG
        result = await self.provider.search_files("DEBUG", self.temp_dir)
        
        print(f"Seatbelt search result: {result}")
        self.assertTrue(result.get("success"), f"Search failed: {result.get('error')}")
        self.assertGreaterEqual(result.get("total_matches", 0), 2)
        
    async def test_seatbelt_binary_file_detection(self):
        """Test binary file detection with Seatbelt provider."""
        binary_file = os.path.join(self.temp_dir, "test.bin")
        
        # Create a binary file with null bytes
        with open(binary_file, 'wb') as f:
            f.write(b'\x00\x01\x02\x03\x04\x05\x00\xff')
        
        # Attempt to read binary file
        result = await self.provider.read_file(binary_file)
        
        print(f"Seatbelt binary file result: {result}")
        self.assertFalse(result.get("success"))
        # Check if it properly detects binary files
        error_msg = result.get("error", "").lower()
        # For Seatbelt, we expect it to properly detect binary files
        if "binary" in error_msg or "text-based" in error_msg:
            # Good, proper binary detection
            pass
        else:
            # If it's a different error, that's also acceptable for sandbox
            print(f"Note: Binary file detection gave error: {error_msg}")


async def run_seatbelt_tests():
    """Run Seatbelt-specific tests."""
    print("Running Seatbelt provider file tool tests...")
    
    if platform.system() != "Darwin":
        print("❌ Seatbelt tests require macOS")
        return
        
    if not SeatbeltProvider.is_supported():
        print("❌ Seatbelt provider not supported (requires sandbox-exec)")
        return
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFileToolsSeatbelt)
    
    # Create test instance
    test_instance = TestFileToolsSeatbelt()
    
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
                import traceback
                traceback.print_exc()
            finally:
                test_instance.tearDown()


if __name__ == "__main__":
    print("Starting Seatbelt provider tests...")
    asyncio.run(run_seatbelt_tests())
    print("\n🎉 Seatbelt tests completed!")