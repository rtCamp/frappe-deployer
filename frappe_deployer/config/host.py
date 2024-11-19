from pathlib import Path
from pydantic import BaseModel,  model_validator

class HostConfig(BaseModel):
    """
    HostConfig is a Pydantic model representing the configuration for a host.

    Attributes
    ----------
    bench_path : Path
        The path to the bench directory. This attribute is validated to ensure that it exists on the filesystem.
    """

    bench_path: Path

    @model_validator(mode='before')
    def check_bench_path_exists(cls, values):
        """
        Validates that the specified bench_path exists on the filesystem.

        Parameters
        ----------
        cls : type
            The class itself.
        values : dict
            A dictionary of values to be validated.

        Returns
        -------
        dict
            The validated and possibly modified values dictionary.

        Raises
        ------
        ValueError
            If the specified bench_path does not exist.
        """
        bench_path = values.get('bench_path')

        if (bench_path and not Path(bench_path).exists()) or not bench_path:
            raise ValueError(f"The bench_path '{bench_path}' does not exist.")

        values['bench_path'] = Path(bench_path)

        return values
