import logging
import os
import warnings
from pathlib import Path

import pytest
import pytest_asyncio
import vcr  # type: ignore[import-untyped]
from pydantic import PydanticDeprecatedSince20, PydanticDeprecatedSince211

from good_agent.core.event_router import current_test_nodeid

# ---------------------------------------------------------------------------
# Coverage policy helpers
# ---------------------------------------------------------------------------

_COVERAGE_POLICY_URL = "coverage/phase5/baseline/"
_SKIP_COVERAGE_ERROR = (
    "@pytest.mark.skip_coverage requires a non-empty 'reason' kwarg referencing "
    f"the coverage policy documented under {_COVERAGE_POLICY_URL}."
)


@pytest.fixture(autouse=True)
def _enforce_skip_coverage_reason(request):
    """Ensure tests opting out of coverage document their rationale."""
    marker = request.node.get_closest_marker("skip_coverage")
    if not marker:
        return

    reason = marker.kwargs.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise AssertionError(_SKIP_COVERAGE_ERROR)


# ---------------------------------------------------------------------------
# Warning controls
# ---------------------------------------------------------------------------

# LiteLLM relies on Pydantic's `model_dump(mode="json")` for cassette recording,
# which emits noisy `PydanticSerializationUnexpectedValue` warnings that we can't
# fix locally. Silence them so real regressions stay visible.
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings:",
    category=UserWarning,
    module="pydantic.main",
)

# LiteLLM's custom httpx cleanup uses the pre-3.11 event loop getter, which raises
# a DeprecationWarning during teardown. Ignore it to keep the suite quiet.
warnings.filterwarnings(
    "ignore",
    message="There is no current event loop",
    category=DeprecationWarning,
    module="litellm.llms.custom_httpx.async_client_cleanup",
)


# Monkey-patch VCR's httpx stub to fix _decoder assertion issue and compression
# This is a workaround for https://github.com/kevin1024/vcrpy/issues/895
# and httpx/vcr/litellm compression inconsistencies
async def _patched_to_serialized_response(resp, aread):
    import gzip
    import logging
    import zlib

    logger = logging.getLogger("tests.conftest")
    logger.debug(
        f"VCR PATCH CALLED - Status: {resp.status_code}, Content-Type: {resp.headers.get('content-type', 'unknown')}"
    )

    # Store decoder state if it exists and handle the assertion
    had_decoder = hasattr(resp, "_decoder")
    getattr(resp, "_decoder", None)

    # Remove _decoder temporarily to satisfy VCR's assertion
    if had_decoder:
        delattr(resp, "_decoder")
        logger.debug("Removed _decoder attribute")

    # Get content encoding before we modify headers
    content_encoding = resp.headers.get("content-encoding", "").lower()
    logger.debug(f"Original content-encoding: {content_encoding}")

    # Read the content with proper decompression handling
    try:
        if aread:
            await resp.aread()
        else:
            resp.read()

        content = resp.content
        logger.debug(f"Raw content length: {len(content)} bytes")

        # If content is compressed but not automatically decompressed, handle it
        if content and content_encoding in ["gzip", "deflate"]:
            logger.debug(f"Attempting to decompress {content_encoding} content")
            try:
                if content_encoding == "gzip":
                    # Try to decompress if it's still compressed
                    if content.startswith(b"\x1f\x8b"):  # gzip magic number
                        content = gzip.decompress(content)
                        logger.debug("Manually decompressed gzip content for VCR")
                    else:
                        logger.debug("Content not gzip compressed (no magic header)")
                elif content_encoding == "deflate":
                    # Try to decompress if it's still compressed
                    try:
                        content = zlib.decompress(content)
                        logger.debug("Manually decompressed deflate content for VCR")
                    except zlib.error:
                        # Try without header
                        content = zlib.decompress(content, -zlib.MAX_WBITS)
                        logger.debug(
                            "Manually decompressed raw deflate content for VCR"
                        )
            except Exception as e:
                logger.debug(f"Could not decompress content: {e}, using as-is")

        # Transform headers and remove compression headers
        headers = _transform_headers(resp)
        original_header_count = len(headers)

        # Remove compression-related headers since we're storing decompressed content
        headers_to_remove = ["content-encoding", "Content-Encoding"]
        for header in headers_to_remove:
            if header in headers:
                del headers[header]
                logger.debug(f"Removed compression header: {header}")

        result = {
            "status": {"code": resp.status_code, "message": resp.reason_phrase},
            "headers": headers,
            "body": {"string": content},
        }

        logger.debug(
            f"VCR serialized response - Body length: {len(content)}, Headers: {len(headers)}/{original_header_count}"
        )

    except Exception as e:
        logger.error(f"Error in VCR response serialization: {e}")
        # Fallback to original approach
        result = {
            "status": {"code": resp.status_code, "message": resp.reason_phrase},
            "headers": _transform_headers(resp),
            "body": {"string": resp.content},
        }

    # Clean up decoder if it still exists
    if hasattr(resp, "_decoder"):
        del resp._decoder

    return result


# Helper function needed by our patch
def _transform_headers(resp):
    """Transform headers to VCR format."""
    out: dict[str, list[str]] = {}
    for key, var in resp.headers.raw:
        decoded_key = key.decode("utf-8")
        if decoded_key not in out:
            out[decoded_key] = []
        out[decoded_key].append(var.decode("utf-8"))
    return out


# Apply the monkey-patch to handle _decoder assertion issue
try:
    from vcr.stubs import httpx_stubs  # type: ignore[import-untyped]

    httpx_stubs._to_serialized_response = _patched_to_serialized_response
    httpx_stubs._transform_headers = _transform_headers
    # Note: logger is defined later in the file
    print("VCR MONKEY-PATCH APPLIED SUCCESSFULLY")
except ImportError as e:
    print(f"VCR httpx stubs not available: {e}")
except Exception as e:
    print(f"Failed to apply VCR monkey-patch: {e}")


# Configure logging based on environment variable or pytest verbosity
def get_log_level():
    """Determine log level from environment or default to WARNING for less noise."""
    # Check for LOGURU_LEVEL or LOG_LEVEL environment variables
    env_level = os.getenv("LOGURU_LEVEL") or os.getenv("LOG_LEVEL")
    if env_level:
        return getattr(logging, env_level.upper(), logging.WARNING)

    # Check for DEBUG environment variable
    if os.getenv("DEBUG") and os.getenv("DEBUG", "").lower() != "false":
        return logging.DEBUG

    # Default to WARNING for cleaner test output
    return logging.WARNING


logging.basicConfig(
    level=get_log_level(), format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Plugin code directly in conftest for now


# VCR Configuration
def scrub_sensitive_data(request):
    """Remove sensitive data from recorded requests."""
    # Remove API keys from headers
    if "Authorization" in request.headers:
        request.headers["Authorization"] = "Bearer REDACTED"
    if "x-api-key" in request.headers:
        request.headers["x-api-key"] = "REDACTED"
    if "api-key" in request.headers:
        request.headers["api-key"] = "REDACTED"

    # Remove API keys from URLs
    if "api_key=" in request.uri:
        import re

        request.uri = re.sub(r"api_key=[^&]+", "api_key=REDACTED", request.uri)

    return request


def scrub_response_headers(response):
    """Remove sensitive data from recorded responses and handle compressed content."""
    # Remove any API usage headers that might contain sensitive info
    headers_to_scrub = [
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "openai-organization",
        "openai-processing-ms",
        "x-request-id",
    ]

    # Remove compression headers since decode_compressed_response=True
    # decompresses the content but headers indicate compression
    compression_headers_to_remove = [
        "content-encoding",
        "Content-Encoding",
        "transfer-encoding",
        "Transfer-Encoding",
    ]

    headers = response.get("headers", {})

    # Scrub sensitive headers
    for header in headers_to_scrub:
        if header in headers:
            headers[header] = ["REDACTED"]

    # Remove compression headers to prevent mismatch with decompressed content
    for header in compression_headers_to_remove:
        if header in headers:
            del headers[header]

    logger.debug(f"Response headers after scrubbing: {headers}")

    return response


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Store current test info in context var for logging and apply VCR if needed."""
    current_test_nodeid.set(item.nodeid)
    logger.debug(f"Starting test: {item.nodeid}")

    # Auto-apply VCR for tests marked with @pytest.mark.vcr
    if item.get_closest_marker("vcr"):
        if "llm_vcr" not in item.fixturenames:
            item.fixturenames.append("llm_vcr")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item):
    """Clear test info after test"""
    test_nodeid = current_test_nodeid.get()
    if test_nodeid:
        logger.debug(f"Finishing test: {test_nodeid}")
        current_test_nodeid.set(None)


# @pytest.hookimpl(hookwrapper=True)
# def pytest_runtest_call(item):
#     """Wrap test execution to catch issues"""
#     # Only log test execution at DEBUG level
#     logger.debug(f"=== EXECUTING TEST: {item.nodeid} ===")

#     outcome = yield

#     # Log test end
#     if outcome.excinfo is None:
#         logger.debug(f"=== TEST PASSED: {item.nodeid} ===")
#         # Test passed, check for any pending tasks
#         import gc
#         gc.collect()  # Force collection to trigger any pending task warnings
#     else:
#         # Keep errors at ERROR level so they're always visible
#         logger.error(f"=== TEST FAILED: {item.nodeid} ===")


@pytest_asyncio.fixture(autouse=True)
async def clear_tool_registry():
    """Clear the global tool registry before each test to ensure clean state."""
    from good_agent.tools import clear_tool_registry

    # Clear before test
    await clear_tool_registry()

    # Run test
    yield

    # Clear after test
    await clear_tool_registry()


# VCR Fixtures
@pytest.fixture
def vcr_config():
    """Get VCR configuration for tests."""
    return {
        "record_mode": os.environ.get("VCR_RECORD_MODE", "once"),
        "match_on": ["method", "scheme", "host", "port", "path"],
        "filter_headers": ["authorization", "x-api-key", "api-key"],
        "before_record_request": scrub_sensitive_data,
        "before_record_response": scrub_response_headers,
        "decode_compressed_response": True,
        "ignore_hosts": ["localhost", "127.0.0.1", "0.0.0.0"],
    }


@pytest.fixture
def vcr_cassette_dir(request):
    """Return the directory to store cassettes for the current test."""
    # Use centralized cassettes directory
    tests_root = Path(__file__).parent
    cassette_dir = tests_root / "fixtures" / "cassettes"
    cassette_dir.mkdir(exist_ok=True, parents=True)
    return str(cassette_dir)


@pytest.fixture
def vcr_cassette_name(request):
    """Generate cassette name based on test name."""
    # Get test class and method names
    test_class = request.cls.__name__ if request.cls else ""
    test_name = request.node.name

    # Clean up parametrized test names
    test_name = test_name.replace("[", "_").replace("]", "").replace("-", "_")

    if test_class:
        return f"{test_class}_{test_name}.yaml"
    return f"{test_name}.yaml"


@pytest.fixture
def vcr_cassette(vcr_config, vcr_cassette_dir, vcr_cassette_name):
    """Create a VCR instance for recording/replaying HTTP interactions."""
    cassette_path = Path(vcr_cassette_dir) / vcr_cassette_name

    # Allow overriding record mode via environment variable
    record_mode = os.environ.get("VCR_RECORD_MODE", vcr_config["record_mode"])

    # Create VCR instance with config
    vcr_instance = vcr.VCR(**vcr_config)
    vcr_instance.record_mode = record_mode

    with vcr_instance.use_cassette(str(cassette_path)) as cassette:
        yield cassette


@pytest.fixture
def llm_vcr(vcr_cassette_dir, vcr_cassette_name):
    """Fixture specifically for LLM API calls with appropriate matching."""
    cassette_path = Path(vcr_cassette_dir) / f"llm_{vcr_cassette_name}"

    # Configure LiteLLM to use standard httpx transport for VCR compatibility
    import litellm

    original_disable_aiohttp = getattr(litellm, "disable_aiohttp_transport", False)
    litellm.disable_aiohttp_transport = True
    logger.debug("Disabled LiteLLM aiohttp transport for VCR compatibility")

    # Delete existing cassette if in record mode to force re-recording
    if os.environ.get("VCR_RECORD_MODE") == "new_episodes" and cassette_path.exists():
        os.remove(cassette_path)

    # Special configuration for LLM calls
    llm_vcr = vcr.VCR(
        cassette_library_dir=vcr_cassette_dir,
        record_mode=os.environ.get("VCR_RECORD_MODE", "once"),
        match_on=[
            "method",
            "scheme",
            "host",
            "port",
            "path",
        ],  # Don't match on body - too strict
        filter_headers=["authorization", "x-api-key", "api-key", "openai-beta"],
        before_record_request=scrub_sensitive_data,
        before_record_response=scrub_response_headers,
        decode_compressed_response=True,  # Decompress during recording to avoid replay issues
        ignore_hosts=["localhost", "127.0.0.1", "0.0.0.0"],
        # Custom serializer to handle JSON bodies
        serializer="yaml",
        # Custom cassette persister settings
        path_transformer=vcr.VCR.ensure_suffix(".yaml"),
        # Ensure binary responses are handled properly
        inject_cassette=True,
        record_on_exception=False,
    )

    try:
        with llm_vcr.use_cassette(str(cassette_path)) as cassette:
            yield cassette
    finally:
        # Restore original LiteLLM aiohttp transport setting
        litellm.disable_aiohttp_transport = original_disable_aiohttp
        logger.debug("Restored LiteLLM aiohttp transport setting")


# Register custom markers
def pytest_configure(config):
    """Register custom markers and silence known third-party warnings."""
    warnings.filterwarnings(
        "ignore",
        message="Pydantic serializer warnings:",
        category=UserWarning,
        module="pydantic.main",
    )
    warnings.filterwarnings(
        "ignore",
        message="There is no current event loop",
        category=DeprecationWarning,
        module="litellm.llms.custom_httpx.async_client_cleanup",
    )
    warnings.filterwarnings(
        "ignore",
        message="enable_cleanup_closed ignored",
        category=DeprecationWarning,
        module="aiohttp.connector",
    )
    warnings.filterwarnings(
        "ignore",
        message="Accessing the 'model_fields' attribute",
        category=PydanticDeprecatedSince211,
        module="litellm",
    )
    warnings.filterwarnings(
        "ignore",
        message="Accessing the 'model_computed_fields' attribute",
        category=PydanticDeprecatedSince211,
        module="litellm",
    )
    warnings.filterwarnings(
        "ignore",
        message="The `dict` method is deprecated",
        category=PydanticDeprecatedSince20,
        module="litellm",
    )
    config.addinivalue_line(
        "markers",
        "vcr: mark test to use VCR.py for recording/replaying HTTP interactions (including LLM API calls)",
    )
    config.addinivalue_line(
        "markers",
        "requires_signals: mark test as requiring real OS signal handling (enable with --requires-signals)",
    )


def pytest_addoption(parser):
    """Add CLI option to enable signal-dependent tests."""
    parser.addoption(
        "--requires-signals",
        action="store_true",
        default=False,
        help="run tests that send real OS signals",
    )


def pytest_collection_modifyitems(config, items):
    """Skip signal-dependent tests unless explicitly enabled."""
    if config.getoption("--requires-signals"):
        return

    skip_marker = pytest.mark.skip(reason="need --requires-signals option to run")
    for item in items:
        if "requires_signals" in item.keywords:
            item.add_marker(skip_marker)
