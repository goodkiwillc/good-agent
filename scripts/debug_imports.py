import os
import sys

# Add src to python path
sys.path.insert(0, os.path.abspath("src"))

try:
    from good_agent import CitationIndex
    print("Successfully imported CitationIndex from good_agent")
    print(f"Type: {type(CitationIndex)}")
except ImportError as e:
    print(f"Failed to import CitationIndex from good_agent: {e}")
except AttributeError as e:
    print(f"AttributeError importing CitationIndex from good_agent: {e}")

try:
    from good_agent.extensions import CitationIndex
    print("Successfully imported CitationIndex from good_agent.extensions")
except ImportError as e:
    print(f"Failed to import CitationIndex from good_agent.extensions: {e}")
except AttributeError as e:
    print(f"AttributeError importing CitationIndex from good_agent.extensions: {e}")
