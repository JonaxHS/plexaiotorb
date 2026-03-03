import sys
try:
    import pyfuse3_asyncio
    print("pyfuse3_asyncio OK")
except Exception as e:
    print(f"pyfuse3_asyncio Error: {e}")

try:
    import trio
    print("trio OK")
except Exception as e:
    print(f"trio Error: {e}")
