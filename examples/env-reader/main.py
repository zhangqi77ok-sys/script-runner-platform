import os

value = os.environ.get("SCRIPT_PLATFORM_TEST_VALUE")
if not value:
    raise RuntimeError("SCRIPT_PLATFORM_TEST_VALUE is required")
print(f"value={value}")
