import sys


def test_installation() -> None:
    try:
        import pythonforge  # noqa: F401  -- the import itself is what's under test

        print("SUCCESS: pythonforge imported successfully.")
    except ImportError as e:
        print(f"FAILURE: Could not import pythonforge. Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_installation()
