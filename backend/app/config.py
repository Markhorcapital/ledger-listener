"""Configuration management"""
import yaml
from pathlib import Path
from typing import Dict, Any


class Config:
    """Load and manage configuration from YAML file"""
    
    def __init__(self, config_path: str = "config.yml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation (e.g., 'mongodb.host')"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    @property
    def mongodb(self) -> Dict[str, Any]:
        """Get MongoDB configuration"""
        return self._config.get('mongodb', {})
    
    @property
    def api(self) -> Dict[str, Any]:
        """Get API configuration"""
        return self._config.get('api', {})
    
    @property
    def service(self) -> Dict[str, Any]:
        """Get service configuration"""
        return self._config.get('service', {})
    
    @property
    def exchanges(self) -> Dict[str, Any]:
        """Get exchange configuration"""
        return self._config.get('exchanges', {})


# Global config instance
config = Config()

