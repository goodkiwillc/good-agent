import logging

from good_agent.agent.core import Agent
from good_agent.tools import tool

logger = logging.getLogger(__name__)


@tool
def search_web(query: str) -> str:
    """
    Searches the web for the given query.
    Note: This is a reference implementation using DuckDuckGo.
    You may need to install 'duckduckgo-search': pip install duckduckgo-search
    """
    # Temporarily disabled because duckduckgo_search is unavailable in this environment.
    # try:
    #     from duckduckgo_search import DDGS
    #
    #     with DDGS() as ddgs:
    #         results = list(ddgs.text(query, max_results=5))
    #         return str(results)
    # except ImportError:
    #     return "Error: duckduckgo-search is not installed. Please install it to use this tool: pip install duckduckgo-search"
    # except Exception as e:
    #     return f"Error performing search: {e}"
    return "DuckDuckGo search temporarily disabled. Install duckduckgo-search to re-enable."


@tool
def visit_page(url: str) -> str:
    """
    Visits a webpage and returns its text content.
    Note: This is a reference implementation using httpx and beautifulsoup4.
    You may need to install them: pip install httpx beautifulsoup4
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        response = httpx.get(url, follow_redirects=True, timeout=10.0)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()

        text = soup.get_text()

        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text[:5000]  # Return first 5000 chars

    except ImportError:
        return "Error: httpx or beautifulsoup4 is not installed. Please install them: pip install httpx beautifulsoup4"
    except Exception as e:
        return f"Error visiting page: {e}"


agent = Agent(
    """
You are a research agent. Your goal is to find information on the web.
You can use `search_web` to find relevant pages and `visit_page` to read their content.
Always cite your sources (URLs) when answering.
""",
    name="research-agent",
    model="gpt-4o",
    tools=[search_web, visit_page],
)
