from pathlib import Path
from pydantic import BaseModel,  model_validator

class HostConfig(BaseModel):
    bench_path: Path

    @model_validator(mode='before')
    def check_bench_path_exists(cls, values):
        bench_path = values.get('bench_path')

        if bench_path and not Path(bench_path).exists():
            raise ValueError(f"The bench_path '{bench_path}' does not exist.")

        values['bench_path'] = Path(bench_path)

        return values
