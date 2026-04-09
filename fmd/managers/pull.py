from fmd.config.config import Config
from fmd.managers.release import ReleaseManager


class PullManager:
    def __init__(self, config: Config, release_runner, exec_runner, host_runner, printer):
        self.config = config
        self.release_manager = ReleaseManager(config, release_runner, exec_runner, host_runner, printer)
        self.printer = printer

    def deploy(self) -> None:
        bench_path = self.config.bench_path

        if not bench_path.is_symlink():
            self.printer.change_head("Site not configured — running configure first")
            self.release_manager.configure()

        release_name = self.release_manager.create()
        self.printer.print(f"Release [blue]{release_name}[/blue] created")

        self.release_manager.switch(release_name)
        self.printer.print(f"Switched to [blue]{release_name}[/blue]")
