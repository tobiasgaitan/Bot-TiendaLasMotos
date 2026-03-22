import sys
import os
import re

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA

def test_markdown_cleanup():
    print("Testing Markdown Cleanup...")
    brain = CerebroIA()
    
    # Case 1: Triple backticks with language
    text_with_markdown = "Aquí tienes la info: ```python\nprint('hello')\n``` ¿Te gusta?"
    cleaned = brain.clean_markdown_blocks(text_with_markdown)
    print(f"Original: {text_with_markdown}")
    print(f"Cleaned: '{cleaned}'")
    assert "```python" not in cleaned
    assert "print('hello')" not in cleaned
    
    # Case 2: Just triple backticks
    text_with_fc = "Voy a buscar: ```\nsearch_catalog(query='moto')\n```"
    cleaned = brain.clean_markdown_blocks(text_with_fc)
    print(f"Original: {text_with_fc}")
    print(f"Cleaned: '{cleaned}'")
    assert "search_catalog" not in cleaned
    
    # Case 3: Residual backticks
    text_with_ticks = "Mira `esto` y ```aquí```"
    cleaned = brain.clean_markdown_blocks(text_with_ticks)
    print(f"Original: {text_with_ticks}")
    print(f"Cleaned: '{cleaned}'")
    assert "```" not in cleaned
    
    print("✅ Markdown cleanup tests passed!")

if __name__ == "__main__":
    try:
        test_markdown_cleanup()
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during tests: {e}")
        sys.exit(1)
