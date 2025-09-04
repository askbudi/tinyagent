from .base import CodeExecutionProvider
from .modal_provider import ModalProvider

# Import platform-specific providers conditionally
import platform

# Import SeatbeltProvider conditionally to avoid errors on non-macOS systems
if platform.system() == "Darwin":
    try:
        from .seatbelt_provider import SeatbeltProvider
    except ImportError:
        # If there's an issue importing, just don't make it available
        pass

# Import BubblewrapProvider conditionally to avoid errors on non-Linux systems
if platform.system() == "Linux":
    try:
        from .bubblewrap_provider import BubblewrapProvider
    except ImportError:
        # If there's an issue importing, just don't make it available
        pass

# Import DockerProvider - works on all platforms where Docker is available
try:
    from .docker_provider import DockerProvider
except ImportError:
    # If there's an issue importing, just don't make it available
    pass

__all__ = ["CodeExecutionProvider", "ModalProvider"]

# Add platform-specific providers to __all__ if they were successfully imported
if platform.system() == "Darwin" and "SeatbeltProvider" in globals():
    __all__.append("SeatbeltProvider")

if platform.system() == "Linux" and "BubblewrapProvider" in globals():
    __all__.append("BubblewrapProvider")

if "DockerProvider" in globals():
    __all__.append("DockerProvider") 