"""Simulator-specific exception hierarchy.

Future modules should raise these instead of generic exceptions so callers
can fail safely without affecting production paths.
"""

from __future__ import annotations


class SimulationError(Exception):
    """Base class for all simulator errors."""


class EnvironmentError(SimulationError):
    """Raised when environment selection or validation fails."""


class ConfigurationError(SimulationError):
    """Raised when simulator configuration is invalid or incomplete."""


class SimulatorNotRunning(SimulationError):
    """Raised when an operation requires a running simulator."""


class SimulatorAlreadyRunning(SimulationError):
    """Raised when start is requested while the simulator is already running."""


class SimulatorNotEnabled(SimulationError):
    """Raised when an operation requires the simulator to be enabled."""


class InvalidStateTransition(SimulationError):
    """Raised when a lifecycle action is illegal in the current state."""


class InvalidEnvironmentTransition(EnvironmentError):
    """Raised when switching environments would break isolation rules."""


class IsolationViolation(SimulationError):
    """Raised when an operation would mix live and simulation data."""


class PersonaValidationError(SimulationError):
    """Raised when a persona fails validation."""


class GroupValidationError(SimulationError):
    """Raised when a group fails validation."""


class GenerationError(SimulationError):
    """Raised when world generation cannot complete."""


class SessionError(SimulationError):
    """Raised when session lifecycle operations fail."""


class ExecutionError(SimulationError):
    """Raised when the execution engine encounters a fatal error."""


class PipelineStageError(SimulationError):
    """Raised when a pipeline stage fails irrecoverably."""


class InvalidSessionTransition(SessionError):
    """Raised when a session state transition is illegal."""
