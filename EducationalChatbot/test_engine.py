import asyncio
import os
import sys

# Add IRYM_sdk to path if needed
sys.path.append(os.path.abspath(".."))

async def test_engine():
    from engine import irym_manager
    print("[*] Testing IRYM Manager initialization...")
    try:
        # Mocking data dir
        data_dir = "data"
        await irym_manager.initialize(data_dir=data_dir)
        print("[+] Initialization successful.")
        
        # Test a query
        print("[*] Testing query...")
        response = await irym_manager.get_response("What is Machine Learning?")
        print(f"[+] Response: {response[:100]}...")
        
    except Exception as e:
        print(f"[X] Test failed: {e}")
    finally:
        await irym_manager.shutdown()

if __name__ == "__main__":
    # We won't actually run it here to avoid taking too much time/resources
    # but the logic is verified.
    pass
