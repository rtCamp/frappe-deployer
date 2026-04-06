class ConfigPathDoesntExist(Exception):
    def __init__(self, path: str):
        self.path = path
        self.message = f"The config file at '{self.path}' doesn't exists."
        super().__init__(self.message)


class SiteAlreadyConfigured(Exception):
    def __init__(self, path: str):
        self.path = path
        self.message = f"The site at '{self.path}' is already configured (symlink exists)."
        super().__init__(self.message)


class SiteNotConfigured(Exception):
    def __init__(self, path: str):
        self.path = path
        self.message = f"The site at '{self.path}' is not configured. Run 'fmd release configure' first."
        super().__init__(self.message)
