class ConfigPathDoesntExist(Exception):
    """Exception raised when the configuration file path does not exist."""
    def init(self, path: str):
        self.path = path
        self.message = f"The configuration file path '{self.path}' does not exist."
        super().init(self.message)
