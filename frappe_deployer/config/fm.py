from typing import Optional
from pydantic import BaseModel, Field

class FMConfig(BaseModel):
    """
    FMConfig is a Pydantic model representing the configuration for FM.

    Attributes
    ----------
    db_bench_name : Optional[str]
        The name of the database bench. This attribute is optional and can be None.
    """

    restore_db_from_site: Optional[str] = Field(None, description="The name of the database bench. This attribute is optional and can be None.",alias='db_bench_name')
