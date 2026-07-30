"""Audit package with lazy imports to avoid execution-policy cycles."""


def build_execution_audit(*args, **kwargs):
    from analysis.audit.engine import build_execution_audit as _impl
    return _impl(*args, **kwargs)


def build_execution_trace(*args, **kwargs):
    from analysis.audit.state_machine import build_execution_trace as _impl
    return _impl(*args, **kwargs)


def transition_for_signal(*args, **kwargs):
    from analysis.audit.state_machine import transition_for_signal as _impl
    return _impl(*args, **kwargs)


__all__ = ["build_execution_audit", "build_execution_trace", "transition_for_signal"]
