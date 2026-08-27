"""Errors that the ingestion layer raises."""


class IngestionError(Exception):
    """The base class for every ingestion error."""


class UnsupportedFormatError(IngestionError):
    """No registered loader can read this source's format.

    Attributes:
        extension: The file extension that no loader claims.
    """

    def __init__(self, extension: str) -> None:
        """Bind the offending extension to the error."""
        super().__init__(f"No loader registered for {extension!r}")
        self.extension = extension


class MissingExtraError(UnsupportedFormatError):
    """A loader exists for this format, but its package extra is not installed.

    This class extends ``UnsupportedFormatError`` on purpose. An error policy can then
    treat
    a missing extra the same way it treats an unsupported format, instead of always
    stopping
    the whole batch.

    Attributes:
        extension: The file extension that needs the extra.
        extra: The name of the package extra to install.
    """

    def __init__(self, extension: str, extra: str) -> None:
        """Bind the offending extension and the missing extra to the error."""
        IngestionError.__init__(
            self,
            f"{extension!r} needs the {extra!r} extra: "
            f"pip install 'agentic-graphrag[{extra}]'",
        )
        self.extension = extension
        self.extra = extra


class DecodeError(IngestionError):
    """The source bytes do not decode to text."""


class MalformedRecordError(IngestionError):
    """One record in a record-family source does not parse."""


class DocumentTooLargeError(IngestionError):
    """A prose source is larger than the configured byte limit."""
