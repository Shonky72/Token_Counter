"""Provider registry.

Importing the modules below runs their ``@register`` decorators. To add a
provider, create a module here and import it in this file.
"""

from .base import Provider, create_provider, register, registered_types

# Side-effect imports: register the built-in provider types.
from . import rate_limit  # noqa: F401
from . import local_ledger  # noqa: F401
from . import anthropic_admin  # noqa: F401
from . import gemini  # noqa: F401

__all__ = ["Provider", "create_provider", "register", "registered_types"]
