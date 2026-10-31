from typing import Annotated

from pydantic import Field

# Intentionally not EmailStr: management consoles use internal names such as admin@serverpilot.local,
# which email-validator rejects as a special-use domain.
EmailAddress = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$", max_length=255),
]
