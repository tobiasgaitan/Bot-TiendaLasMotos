try:
    from langfuse.decorators import langfuse_context, observe
    print("SUCCESS: langfuse.decorators import successful")
    print(f"langfuse_context: {langfuse_context}")
except ImportError as e:
    print(f"FAILED: langfuse.decorators import failed: {e}")
except Exception as e:
    print(f"ERROR: {e}")
