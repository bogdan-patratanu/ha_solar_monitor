"""Template loader for inverter configurations."""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

logger = logging.getLogger(__name__)


class TemplateLoader:
    """Load and manage inverter templates."""
    
    def __init__(self, templates_dir: str = None):
        """Initialize template loader."""
        if templates_dir is None:
            # Default to templates directory relative to this file
            base_dir = Path(__file__).parent
            templates_dir = base_dir / "templates"
        
        self.templates_dir = Path(templates_dir)
        self._template_cache: Dict[str, Dict[str, Any]] = {}
        
        # Define profile to template path mapping
        self.profile_map = {
            "Deye_SG03LP1": "deye/SG03LP1.yaml",
            "Deye_SG04LP3": "deye/SG04LP3.yaml",
            # Add more mappings as needed
        }
        
        logger.info(f"Template loader initialized with directory: {self.templates_dir}")
    
    def list_manufacturers(self) -> list:
        """List available manufacturers."""
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return []
        
        manufacturers = []
        for item in self.templates_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                manufacturers.append(item.name)
        
        return sorted(manufacturers)
    
    def list_models(self, manufacturer: str) -> list:
        """List available models for a manufacturer."""
        manufacturer_dir = self.templates_dir / manufacturer.lower()
        
        if not manufacturer_dir.exists():
            logger.warning(f"Manufacturer directory not found: {manufacturer_dir}")
            return []
        
        models = []
        for item in manufacturer_dir.iterdir():
            if item.is_file() and item.suffix == '.yaml':
                model_name = item.stem
                models.append(model_name)
        
        return sorted(models)
    
    def load_template(self, profile: str) -> Optional[Dict[str, Any]]:
        """Load a template using a profile string."""
        if profile not in self.profile_map:
            logger.error(f"Profile '{profile}' not found in profile mapping")
            return None
            
        template_path = self.templates_dir / self.profile_map[profile]
        
        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            return None
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = yaml.safe_load(f)
            
            # Process includes (common sensor packages)
            if 'includes' in template:
                template = self._process_includes(template)
            
            # Validate template structure
            if not self._validate_template(template):
                logger.error(f"Invalid template structure: {template_path}")
                return None
            
            # Cache the template
            self._template_cache[profile] = template
            
            logger.info(f"Loaded template for profile '{profile}' from {template_path}")
            return template
        
        except Exception as e:
            logger.error(f"Error loading template {template_path}: {e}")
            return None
    
    def _process_includes(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Process template includes and merge common sensor packages."""
        includes = template.get('includes', [])
        merged_sensors = template.get('sensors', {})
        
        for include_path in includes:
            include_file = self.templates_dir / include_path
            
            if not include_file.exists():
                logger.warning(f"Include file not found: {include_file}")
                continue
            
            try:
                with open(include_file, 'r', encoding='utf-8') as f:
                    include_data = yaml.safe_load(f)
                
                # Skip if include_data is None or doesn't contain sensors
                if not include_data or not isinstance(include_data, dict) or 'sensors' not in include_data:
                    logger.warning(f"Include file {include_path} is empty or invalid - skipping")
                    continue
                
                # Handle case where sensors might be None
                sensors = include_data.get('sensors', {})
                if sensors is None:
                    logger.warning(f"Include file {include_path} has null sensors - skipping")
                    continue
                
                # Recursively merge sensors from include
                for sensor_id, sensor_def in sensors.items():
                    if sensor_id in merged_sensors:
                        # Merge existing sensor definition with new one
                        merged_sensors[sensor_id] = {**merged_sensors[sensor_id], **sensor_def}
                    else:
                        # Add new sensor definition
                        merged_sensors[sensor_id] = sensor_def
                logger.debug(f"Merged {len(sensors)} sensors from {include_path}")
            except Exception as e:
                logger.error(f"Error loading include {include_file}: {e}")
                continue
        
        # Update template with merged sensors
        template['sensors'] = merged_sensors
        return template
    
    def _validate_template(self, template: Dict[str, Any]) -> bool:
        """Validate template structure."""
        required_keys = ['metadata', 'sensors']
        
        for key in required_keys:
            if key not in template:
                logger.error(f"Missing required key in template: {key}")
                return False
        
        # Validate metadata
        metadata = template['metadata']
        if 'manufacturer' not in metadata or 'model' not in metadata:
            logger.error("Template metadata missing manufacturer or model")
            return False
        
        # Validate sensors - can be empty if using includes
        sensors = template['sensors']
        if not isinstance(sensors, dict):
            logger.error("Template sensors must be a dictionary")
            return False
        
        return True
    
    def get_sensor_definition(self, template: Dict[str, Any], sensor_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific sensor definition from a template."""
        if not template or 'sensors' not in template:
            return None
        
        return template['sensors'].get(sensor_id)
    
    def get_all_sensors(self, template: Dict[str, Any]) -> list:
        """Get list of all sensor IDs from a template."""
        if not template or 'sensors' not in template:
            return []
        
        return list(template['sensors'].keys())
    
    def get_communication_defaults(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Get default communication settings from template."""
        if not template or 'communication' not in template:
            return {}
        
        return template['communication']
    
    def get_metadata(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Get template metadata."""
        if not template or 'metadata' not in template:
            return {}
        
        return template['metadata']


# Global template loader instance
_template_loader: Optional[TemplateLoader] = None


def get_template_loader() -> TemplateLoader:
    """Get the global template loader instance."""
    global _template_loader
    
    if _template_loader is None:
        _template_loader = TemplateLoader()
    
    return _template_loader


def load_inverter_template(profile: str) -> Optional[Dict[str, Any]]:
    """Convenience function to load an inverter template."""
    loader = get_template_loader()
    return loader.load_template(profile)
