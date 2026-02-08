#!/usr/bin/env python3
"""
Ensure Pulumi stack YAML file has KMS secrets provider metadata.

This script extracts KMS secrets provider configuration from Pulumi's S3 state
and writes it to the local Pulumi.<stack>.yaml file. This is necessary because
Pulumi CLI requires the local YAML to contain 'secretsprovider' and 'encryptedkey'
fields when using KMS encryption with S3 backends.

Without this, Pulumi falls back to expecting PULUMI_CONFIG_PASSPHRASE.

Usage:
    python3 scripts/ensure_kms_metadata.py <stack-export-json> <stack-yaml-path>

Args:
    stack-export-json: Path to file containing `pulumi stack export` JSON output
    stack-yaml-path: Path to the local Pulumi.<stack>.yaml file to update

Example:
    pulumi stack export > /tmp/stack.json
    python3 scripts/ensure_kms_metadata.py /tmp/stack.json devops/Pulumi.dev.myservice.us-west-2.yaml
"""

import json
import sys
import yaml
from pathlib import Path


def extract_kms_metadata(stack_export_data: dict) -> tuple[str | None, str | None]:
    """
    Extract KMS provider URL and encrypted key from Pulumi stack export.
    
    Args:
        stack_export_data: Parsed JSON from `pulumi stack export`
        
    Returns:
        Tuple of (kms_url, encrypted_key) or (None, None) if not found
    """
    try:
        secrets_providers = stack_export_data.get('deployment', {}).get('secrets_providers', {})
        
        if secrets_providers.get('type') == 'cloud':
            state = secrets_providers.get('state', {})
            kms_url = state.get('url')
            encrypted_key = state.get('encryptedkey')
            return kms_url, encrypted_key
            
    except (KeyError, AttributeError) as e:
        print(f"Error extracting KMS metadata: {e}", file=sys.stderr)
        
    return None, None


def read_existing_config(yaml_path: Path) -> dict:
    """
    Read existing config section from Pulumi stack YAML file.
    
    Args:
        yaml_path: Path to Pulumi.<stack>.yaml file
        
    Returns:
        Dictionary with 'config' key containing existing config, or empty dict
    """
    if not yaml_path.exists():
        return {}
        
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f) or {}
            config = data.get('config', {})
            return {'config': config} if config else {}
    except Exception as e:
        print(f"Warning: Could not read existing config from {yaml_path}: {e}", file=sys.stderr)
        return {}


def write_stack_yaml(yaml_path: Path, kms_url: str, encrypted_key: str, existing_config: dict):
    """
    Write Pulumi stack YAML with KMS metadata and existing config.
    
    Args:
        yaml_path: Path to Pulumi.<stack>.yaml file
        kms_url: KMS provider URL (e.g., awskms://alias/...)
        encrypted_key: Base64-encoded KMS-encrypted data encryption key
        existing_config: Dictionary with 'config' key containing existing config values
    """
    data = {
        'secretsprovider': kms_url,
        'encryptedkey': encrypted_key,
    }
    
    # Preserve existing config if present
    if existing_config and 'config' in existing_config:
        data['config'] = existing_config['config']
    
    # Ensure parent directory exists
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write YAML
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    print(f"✓ Updated {yaml_path} with KMS metadata")
    print(f"  Provider: {kms_url}")
    print(f"  Encrypted key: {encrypted_key[:50]}...")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    
    stack_export_path = Path(sys.argv[1])
    stack_yaml_path = Path(sys.argv[2])
    
    # Read stack export JSON
    if not stack_export_path.exists():
        print(f"Error: Stack export file not found: {stack_export_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(stack_export_path, 'r') as f:
            stack_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in stack export file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract KMS metadata
    kms_url, encrypted_key = extract_kms_metadata(stack_data)
    
    if not kms_url or not encrypted_key:
        print("Error: Could not extract KMS configuration from stack export", file=sys.stderr)
        print("Stack may not be using KMS secrets provider", file=sys.stderr)
        sys.exit(1)
    
    # Read existing config
    existing_config = read_existing_config(stack_yaml_path)
    
    # Write updated YAML
    write_stack_yaml(stack_yaml_path, kms_url, encrypted_key, existing_config)
    
    print("✓ Successfully ensured KMS metadata in stack YAML")


if __name__ == '__main__':
    main()
