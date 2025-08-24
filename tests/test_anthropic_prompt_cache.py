"""
Test the simple cache callback functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def test_anthropic_cache_import():
    """Test that the Anthropic cache callback can be imported."""
    print("Testing Anthropic cache import...")
    
    try:
        from tinyagent.hooks import anthropic_prompt_cache, AnthropicPromptCacheCallback
        print("✓ Anthropic cache imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_anthropic_cache_creation():
    """Test creating an Anthropic cache callback."""
    print("Testing Anthropic cache creation...")
    
    try:
        from tinyagent.hooks import anthropic_prompt_cache, AnthropicPromptCacheCallback
        
        # Test factory function
        callback1 = anthropic_prompt_cache()
        assert isinstance(callback1, AnthropicPromptCacheCallback)
        print("✓ Factory function works")
        
        # Test direct instantiation
        callback2 = AnthropicPromptCacheCallback()
        assert callback2 is not None
        print("✓ Direct instantiation works")
        
        return True
    except Exception as e:
        print(f"✗ Creation failed: {e}")
        return False


def test_model_detection():
    """Test model detection logic."""
    print("Testing model detection...")
    
    try:
        from tinyagent.hooks import AnthropicPromptCacheCallback
        
        callback = AnthropicPromptCacheCallback()
        
        # Test Claude-3 models that support prompt caching
        claude_3_tests = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022", 
            "claude-3-7-sonnet-20250219",
            "CLAUDE-3-5-SONNET"  # Test case insensitive
        ]
        
        for model in claude_3_tests:
            assert callback._is_supported_model(model), f"Should support {model}"
        print("✓ All Claude-3 models detected correctly")
        
        # Test Claude-4 models that support prompt caching
        claude_4_tests = [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "CLAUDE-OPUS-4",  # Test case insensitive
            "CLAUDE-SONNET-4"  # Test case insensitive
        ]
        
        for model in claude_4_tests:
            assert callback._is_supported_model(model), f"Should support {model}"
        print("✓ All Claude-4 models detected correctly")
        
        # Test unsupported models
        unsupported_tests = [
            "gpt-4o",
            "gpt-5-mini", 
            "gpt-3.5-turbo",
            "gemini-pro",
            "llama-2-70b",
            "claude-2",  # Old Claude version
            "claude-1",
            "claude-3-haiku-20240307",  # Claude 3 models without prompt caching
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229"
        ]
        
        for model in unsupported_tests:
            assert not callback._is_supported_model(model), f"Should not support {model}"
        print("✓ Unsupported models correctly rejected")
        
        return True
    except Exception as e:
        print(f"✗ Model detection failed: {e}")
        return False


def test_cache_control_logic():
    """Test cache control addition logic."""
    print("Testing cache control logic...")
    
    try:
        from tinyagent.hooks import AnthropicPromptCacheCallback
        
        callback = AnthropicPromptCacheCallback()
        
        # Test short message (should not trigger caching)
        short_message = {"content": "Hello world"}
        assert not callback._should_add_cache_control(short_message)
        print("✓ Short messages correctly skipped")
        
        # Test long message (should trigger caching)
        long_content = "This is a long message. " * 200
        long_message = {"content": long_content}
        assert callback._should_add_cache_control(long_message)
        print("✓ Long messages correctly detected")
        
        # Test structured content - make sure it's long enough
        long_text_part = "Long part: " + "content " * 500  # Make it definitely long enough
        structured_message = {
            "content": [
                {"type": "text", "text": "Short part"},
                {"type": "text", "text": long_text_part}
            ]
        }
        print(f"Long text part length: {len(long_text_part)}")
        should_cache = callback._should_add_cache_control(structured_message)
        print(f"Structured message should cache: {should_cache}")
        assert should_cache, "Structured content should trigger caching"
        print("✓ Structured content correctly handled")
        
        return True
    except Exception as e:
        print(f"✗ Cache control logic failed: {e}")
        return False


def test_message_modification():
    """Test message modification with cache control."""
    print("Testing message modification...")
    
    try:
        from tinyagent.hooks import AnthropicPromptCacheCallback
        
        callback = AnthropicPromptCacheCallback()
        
        # Test string content conversion
        message1 = {"content": "Long content " * 200}
        callback._add_cache_to_message(message1)
        
        assert isinstance(message1["content"], list)
        assert len(message1["content"]) == 1
        assert message1["content"][0]["cache_control"] == {"type": "ephemeral"}
        print("✓ String content converted correctly")
        
        # Test structured content modification
        message2 = {
            "content": [
                {"type": "text", "text": "First part"},
                {"type": "text", "text": "Second part"}
            ]
        }
        callback._add_cache_to_message(message2)
        
        assert "cache_control" in message2["content"][-1]
        assert message2["content"][-1]["cache_control"] == {"type": "ephemeral"}
        print("✓ Structured content modified correctly")
        
        return True
    except Exception as e:
        print(f"✗ Message modification failed: {e}")
        return False


async def test_callback_integration():
    """Test callback integration with mock agent."""
    print("Testing callback integration...")
    
    try:
        from tinyagent.hooks import anthropic_prompt_cache
        
        # Create mock agent
        class MockAgent:
            def __init__(self, model):
                self.model = model
        
        callback = anthropic_prompt_cache()
        agent = MockAgent("claude-3-5-sonnet-20241022")
        
        # Test with long message (make sure it's over 4000 chars)
        long_content = "Test content " * 400  # ~4800 chars
        messages = [{"content": long_content}]
        
        print(f"Before callback - content type: {type(messages[0]['content'])}")
        print(f"Before callback - content length: {len(messages[0]['content'])}")
        print(f"Should add cache control: {callback._should_add_cache_control(messages[0])}")
        
        # Call the callback
        await callback("llm_start", agent, messages=messages)
        
        # Check if cache control was added
        content = messages[0]["content"]
        print(f"Message content after callback: {type(content)}")
        if isinstance(content, list):
            print(f"Content blocks: {len(content)}")
            if content and "cache_control" in content[0]:
                print("✓ Cache control found")
            else:
                print("✗ Cache control not found in first block")
                print(f"First block keys: {content[0].keys() if content else 'No blocks'}")
        
        assert isinstance(content, list), "Content should be converted to list"
        assert content, "Content list should not be empty"
        assert "cache_control" in content[0], "First block should have cache_control"
        print("✓ Callback integration works")
        
        return True
    except Exception as e:
        print(f"✗ Callback integration failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("=== Anthropic Prompt Cache Tests ===\n")
    
    tests = [
        ("Imports", test_anthropic_cache_import),
        ("Creation", test_anthropic_cache_creation),
        ("Model Detection", test_model_detection),
        ("Cache Control Logic", test_cache_control_logic),
        ("Message Modification", test_message_modification),
        ("Callback Integration", test_callback_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"--- {test_name} ---")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"✓ {test_name} PASSED\n")
            else:
                print(f"✗ {test_name} FAILED\n")
                
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}\n")
    
    print(f"=== Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)