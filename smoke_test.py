import sys
import importlib.util

def test_installation():
    try:
        # Attempt to import pythonforge
        # Since we haven't installed it yet, we might need to check if it's in path
        # or just check if the module exists in the current structure
        import pythonforge
        print("SUCCESS: pythonforge imported successfully.")
    except ImportError as e:
        print(f"FAILURE: Could not import pythonforge. Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_installation()
