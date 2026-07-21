from __future__ import annotations

from pythonforge.errors import MissingExtraError, PythonForgeError


def test_missing_extra_error_message_names_the_extra() -> None:
    error = MissingExtraError(extra="grpc", feature="the gRPC server")
    assert error.extra == "grpc"
    assert error.feature == "the gRPC server"
    assert "pythonforge[grpc]" in str(error)
    assert isinstance(error, PythonForgeError)
