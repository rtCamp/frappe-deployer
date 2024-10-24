class ConfigPathDoesntExist(Exception):
    """Exception raised when the configuration file path does not exist."""
    def __init__(self, path: str):
        self.path = path
        self.message = f"The config file at '{self.path}' doesn't exists."
        super().__init__(self.message)

class SiteAlreadyConfigured(Exception):
    """Exception raised when the site is already configured."""
    def __init__(self, path: str):
        self.path = path
        self.message = f"The site at '{self.path}' is already configured (symlink exists)."
        super().__init__(self.message)
