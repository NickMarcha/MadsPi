"""
Migration system for MadsPipeline project structure changes.

This module provides the infrastructure for migrating projects between
different structure versions. Migrations are only run when explicitly
requested by the user.

Current project version: 1.0
"""
from pathlib import Path
from typing import List

# Current project structure version
CURRENT_VERSION = "1.0"

# Migration registry - populated when migrations are implemented
# Format: {target_version: migration_function}
MIGRATIONS = {}


def get_migration_path(start_version: str, target_version: str) -> List[str]:
    """
    Get the sequence of versions to migrate through.
    
    Args:
        start_version: Starting version
        target_version: Target version
        
    Returns:
        List of version strings representing the migration path
    """
    # For now, simple version comparison
    # Future: implement semantic versioning-based migration path
    if start_version == target_version:
        return []
    
    # Placeholder for future migration path logic
    return []


def migrate_project(project_path: Path, target_version: str = CURRENT_VERSION) -> bool:
    """
    Migrate a project to a target version.
    
    Args:
        project_path: Path to project directory
        target_version: Target version to migrate to
        
    Returns:
        True if migration succeeded, False otherwise
        
    Note: This function is a placeholder. Actual migrations will be
    implemented when explicitly requested.
    """
    # Placeholder - migrations not implemented yet
    return False

