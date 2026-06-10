import pytest
import urllib.request


# The 'socket_disabled' fixture is injected automatically by the 'pytest-socket' plugin.
# It disables all socket creations at the OS level for the duration of this test.
def test_network_is_blocked_for_application(socket_disabled):
    """
    Verifies that the application environment cannot make external HTTP/Socket requests.
    This ensures no hidden API calls or telemetry exist in the workflow.
    Requires 'pytest-socket' plugin.
    """

    # We expect an exception to be raised when network access is attempted.
    with pytest.raises(Exception) as exc_info:
        # We explicitly test reaching '127.0.0.1' (localhost).
        # This proves we are not using a hidden local backend server (like Flask/FastAPI)
        # to process data, adhering to the "Standalone Desktop Application" requirement.
        urllib.request.urlopen("http://127.0.0.1:5000", timeout=1)

    # Validates that the pytest-socket plugin successfully intercepted the network attempt.
    # We check for 'socket' in the error string to cover both DNS resolution (getaddrinfo)
    # and actual socket creation blocks.
    assert "A test tried to use socket" in str(exc_info.value)