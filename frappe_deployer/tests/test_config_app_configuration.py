
import toml
from pathlib import Path
from frappe_deployer.config.config import Config
from frappe_deployer.config.app import AppConfig
from unittest.mock import MagicMock, patch

def test_configure_apps_flag():
    # Create a dummy TOML configuration with configure_apps set to false
    config_content = """
    site_name = "test_site"
    mode = "fm"
    configure_apps = false

    [[apps]]
    repo = "https://github.com/frappe/frappe"
    branch = "develop"
    """
    
    # Write the content to a temporary file
    temp_config_file = Path("/tmp/test_config_no_apps.toml")
    temp_config_file.write_text(config_content)

    # Load the configuration
    config = Config.from_toml(config_file_path=temp_config_file)

    # Assert that configure_apps is False
    assert not config.configure_apps

    # Mock app.configure_app to ensure it's not called
    with patch.object(AppConfig, 'configure_app', new_callable=MagicMock) as mock_configure_app:
        # Re-load the configuration to trigger the model_validator
        config = Config.from_toml(config_file_path=temp_config_file)
        
        # Ensure configure_app was not called
        mock_configure_app.assert_not_called()

    # Clean up the temporary file
    temp_config_file.unlink()
