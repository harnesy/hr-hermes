"""The one error of this plugin."""


class Refusal(Exception):
    """A check failed or a request cannot be done. Nothing was written; the message is the reason in plain words."""
