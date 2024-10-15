from typing import Optional
from pydantic import BaseModel, Field

class FMConfig(BaseModel):
    db_bench_name: Optional[str] = Field(None)
