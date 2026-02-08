# Pulumi KMS Secrets with S3 Backend: Investigation & Solution

**Date**: 2026-02-07  
**Status**: RESOLVED  
**Issue**: `error: passphrase must be set with PULUMI_CONFIG_PASSPHRASE` despite using KMS

---

## Executive Summary

When using Pulumi with an S3 backend and AWS KMS secrets provider, the `pulumi` CLI requires **both**:
1. The S3 state file to contain KMS secrets provider metadata (automatic)
2. The **local** `Pulumi.<stack>.yaml` file to contain `secretsprovider` and `encryptedkey` fields (can be lost)

In GitHub Actions workflows, the `devops/` directory is ephemeral, so local stack YAML files get regenerated without KMS metadata, causing Pulumi to fall back to passphrase encryption.

**Solution**: After selecting/creating a stack, programmatically ensure the local YAML file contains KMS metadata by extracting it from `pulumi stack export` and writing it to the local file.

---

## Investigation Process

### Strategy 1: Documentation Research

**Key Findings from Pulumi Docs**:

1. **S3 Backend Default**: When using S3 backend, Pulumi defaults to `passphrase` secrets provider unless explicitly specified during `stack init`
2. **Stack Settings File**: `Pulumi.<stack>.yaml` contains:
   - `secretsprovider` (optional): Which provider encrypts secrets (e.g., `awskms://...`)
   - `encryptedkey` (optional): KMS-encrypted data encryption key (auto-managed by Pulumi)
   - `encryptionsalt` (optional): Base64-encoded salt for passphrase-based encryption
   - `config`: Stack configuration values
3. **Two Storage Locations**:
   - **S3**: `.pulumi/stacks/<project>/<stack>.json` - The actual state file
   - **Local**: `Pulumi.<stack>.yaml` - Stack-specific configuration

### Strategy 2: Examining Existing Projects

Looked at how `althq-services` and `althq-frontend` were set up:

**`althq-services/devops/Pulumi.dev.althq-services.us-west-2.yaml`**:
```yaml
secretsprovider: awskms://alias/pulumi_backend_software?region=us-west-2
encryptedkey: AQICAHg3kCec... (base64-encoded KMS-encrypted key)
config:
  althq-services:alpha_vantage_api_key:
    secure: v1:jPBosxIsdhfWin30:1ZU0sA3c2wRiUGtHP2Bwhz2xY4e3OKVYUstZ/4jl4BM=
  althq-services:hostname: api
  # ... many more config values
```

**Why They Use `devops/` Folders in Each Service**:
- Each service controls its own infrastructure code
- Stack config files are version-controlled with the service
- Secrets are encrypted with KMS and safe to commit
- This gives developers autonomy but creates duplication

**Why We Want Platform-Engine Approach**:
- Centralized infrastructure code (DRY principle)
- Consistent patterns across services
- Platform team controls infrastructure evolution
- Services only need `platform.yaml` declaration

### Strategy 3: Local Testing

#### Test 1: Creating a Stack with KMS

```bash
cd /Users/tuanvu/Workspace/platform-engine-temp/devops
TEST_STACK="test-local.test-service.us-west-2"
KMS_PROVIDER="awskms://alias/pulumi_backend_software?region=us-west-2"

pulumi stack init "$TEST_STACK" --secrets-provider="$KMS_PROVIDER"
# Created stack 'test-local.test-service.us-west-2'
```

**Result**: ✅ Stack created successfully

#### Test 2: Examining Created Stack

**Local File** (`Pulumi.test-local.test-service.us-west-2.yaml`):
```yaml
secretsprovider: awskms://alias/pulumi_backend_software?region=us-west-2
encryptedkey: AQICAHjQyYllIFIL+lJwhAqA/TQKZ3jmdGF2HmcqJQ5vkG4uWAEcBPrCua2Z1i4oP8JTGgktAAAAfjB8BgkqhkiG9w0BBwagbzBtAgEAMGgGCSqGSIb3DQEHATAeBglghkgBZQMEAS4wEQQMnhBH6/o6orkQVF7rAgEQgDsnHSe9gjecN5kx+JCVXtqalGLVqVsHsOLDWepfoS+UpfrJc28qpYcRPyX7gOqaj5O/8ZHCayGtntj6VQ==
```

**S3 State File** (`.pulumi/stacks/platform-engine/test-local.test-service.us-west-2.json`):
```json
{
    "version": 3,
    "checkpoint": {
        "Latest": {
            "secrets_providers": {
                "type": "cloud",
                "state": {
                    "url": "awskms://alias/pulumi_backend_software?region=us-west-2",
                    "encryptedkey": "AQICAHjQyYllIFIL+lJwhAqA/TQKZ3jmdGF2HmcqJQ5vkG4uWAEcBPrCua2Z1i4oP8JTGgktAAAAfjB8BgkqhkiG9w0BBwagbzBtAgEAMGgGCSqGSIb3DQEHATAeBglghkgBZQMEAS4wEQQMnhBH6/o6orkQVF7rAgEQgDsnHSe9gjecN5kx+JCVXtqalGLVqVsHsOLDWepfoS+UpfrJc28qpYcRPyX7gOqaj5O/8ZHCayGtntj6VQ=="
                }
            }
        }
    }
}
```

**Result**: ✅ Both locations have KMS configuration

#### Test 3: Using Stack Without Passphrase

```bash
unset PULUMI_CONFIG_PASSPHRASE
unset PULUMI_CONFIG_PASSPHRASE_FILE
pulumi stack select "$TEST_STACK"
pulumi config set aws:region us-west-2
```

**Result**: ✅ Works! No passphrase needed

#### Test 4: Simulating GitHub Actions Behavior (CRITICAL TEST)

```bash
# Rename local YAML to simulate missing file
mv "Pulumi.$TEST_STACK.yaml" "Pulumi.$TEST_STACK.yaml.backup"

# Select stack (will recreate local YAML from S3)
pulumi stack select "$TEST_STACK"

# Try to set config (triggers local YAML regeneration)
pulumi config set test:value "hello"

# Check what was created
cat "Pulumi.$TEST_STACK.yaml"
```

**Local YAML After Regeneration**:
```yaml
config:
  test:value: hello
```

**Result**: ❌ Local YAML regenerated **WITHOUT** `secretsprovider` and `encryptedkey` fields!

#### Test 5: Confirming the Passphrase Error

```bash
# Try to run pulumi preview with regenerated YAML (missing KMS metadata)
unset PULUMI_CONFIG_PASSPHRASE
unset PULUMI_CONFIG_PASSPHRASE_FILE
pulumi preview
```

**Result**: ❌ `error: passphrase must be set with PULUMI_CONFIG_PASSPHRASE`

#### Test 6: Fixing with Restored KMS Metadata

```bash
# Restore original YAML with KMS metadata
mv "Pulumi.$TEST_STACK.yaml.backup" "Pulumi.$TEST_STACK.yaml"

# Try preview again
pulumi preview
```

**Result**: ✅ Works! (Failed due to missing Python deps, but got past passphrase check)

---

## Root Cause Analysis

### The Problem

`pulumi stack init --secrets-provider="awskms://..."` creates KMS configuration in **two places**:

1. **S3 State File** (`.pulumi/stacks/platform-engine/<stack>.json`)
   - Contains `secrets_providers` with KMS URL and encrypted key
   - ✅ Persists across workflow runs
   
2. **Local Stack YAML** (`Pulumi.<stack>.yaml`)
   - Contains `secretsprovider` and `encryptedkey` fields
   - ❌ Ephemeral in GitHub Actions (not committed to repo)

### Why GitHub Actions Fails

```
Workflow Execution Timeline:
─────────────────────────────────────────────────────────────────

Step 1: Checkout platform-engine-temp
├─ engine/devops/ directory is created
└─ No local Pulumi.<stack>.yaml files exist yet

Step 2: Select or Create Stack
├─ pulumi stack init --secrets-provider="awskms://..."
├─ Creates stack in S3 with KMS metadata ✅
├─ Creates LOCAL Pulumi.<stack>.yaml with KMS metadata ✅
└─ File: engine/devops/Pulumi.dev.my-service.us-west-2.yaml

Step 3: Set Pulumi Config (NEW SHELL, NEW STEP)
├─ pulumi stack select "dev.my-service.us-west-2"
├─ Reads S3 state ✅
├─ Local YAML exists, Pulumi reads it ✅
└─ pulumi config set aws:region us-west-2

Step 4: Pulumi Up (NEW SHELL, NEW STEP)
├─ pulumi stack select "dev.my-service.us-west-2"
├─ Reads S3 state ✅
├─ Local YAML exists but may have been REGENERATED ⚠️
├─ Regenerated YAML only has config:, missing secretsprovider ❌
├─ Pulumi falls back to passphrase encryption
└─ ERROR: passphrase must be set ❌
```

### Why Pulumi Regenerates YAML Without KMS Metadata

When Pulumi reads/writes config values and the local YAML file gets modified or recreated, it only includes:
- The `config:` section with configuration values
- **NOT** the `secretsprovider` or `encryptedkey` fields

This appears to be a Pulumi behavior where the CLI assumes:
1. If using S3 backend, stack metadata is in S3
2. Local YAML is just for config values
3. But then **contradicts itself** by requiring local YAML to have secrets provider info for operations!

---

## The Solution

### Implementation

After selecting or creating a stack, programmatically ensure the local `Pulumi.<stack>.yaml` file contains KMS metadata:

```bash
# 1. Export stack to get secrets provider info from S3 state
STACK_EXPORT=$(uv run pulumi stack export -C devops 2>&1)

# 2. Extract KMS provider URL and encrypted key from JSON
KMS_URL=$(echo "$STACK_EXPORT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
sp = data.get('deployment', {}).get('secrets_providers', {})
if sp.get('type') == 'cloud':
    print(sp['state']['url'])
")

KMS_KEY=$(echo "$STACK_EXPORT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
sp = data.get('deployment', {}).get('secrets_providers', {})
if sp.get('type') == 'cloud':
    print(sp['state']['encryptedkey'])
")

# 3. Read existing config from local YAML (if any)
if [ -f "$STACK_YAML" ]; then
  EXISTING_CONFIG=$(python3 -c "
  import yaml
  with open('$STACK_YAML', 'r') as f:
      data = yaml.safe_load(f) or {}
      config = data.get('config', {})
      print(yaml.dump({'config': config}) if config else '')
  ")
fi

# 4. Write new YAML with KMS metadata + existing config
python3 -c "
import yaml
data = {
    'secretsprovider': '$KMS_URL',
    'encryptedkey': '$KMS_KEY'
}
if '''$EXISTING_CONFIG''':
    existing = yaml.safe_load('''$EXISTING_CONFIG''')
    if existing and 'config' in existing:
        data['config'] = existing['config']
with open('$STACK_YAML', 'w') as f:
    yaml.dump(data, f, default_flow_style=False)
"
```

### Why This Works

1. **S3 as source of truth**: We read KMS metadata from S3 state (via `pulumi stack export`)
2. **Local YAML is complete**: We write a complete local YAML with both KMS metadata AND config
3. **All subsequent commands work**: `pulumi up`, `pulumi config`, etc. all see KMS provider
4. **No passphrase needed**: Pulumi uses KMS encryption from local YAML

### Workflow Changes

See commit `7c06ff4` for the full implementation in `.github/workflows/provision_from_platform_yaml.yaml`.

---

## Key Learnings

### 1. Pulumi S3 Backend Requires Local + Remote State

Unlike the Pulumi Cloud backend, S3 backends have a split-brain issue:
- **Remote (S3)**: Has the full state including secrets provider metadata
- **Local (YAML)**: Gets regenerated and loses secrets provider metadata
- **CLI Requirement**: Requires BOTH to have consistent secrets provider info

### 2. GitHub Actions Ephemeral Environments Are Tricky

Each step runs in a fresh shell, but shares the filesystem. However:
- Files can be modified by tools (like Pulumi) between steps
- Tools may have different behavior when files exist vs. don't exist
- State that's "obvious" to a human (like "we created this with KMS") isn't preserved

### 3. The Value of Local Testing

By testing locally and simulating the GitHub Actions behavior (removing the local file, letting Pulumi regenerate it), we discovered the exact failure mode and could verify the fix.

### 4. Why Existing Projects Have `devops/` Folders

The old approach (each service has `devops/` folder) works because:
- Local `Pulumi.<stack>.yaml` files are committed to the service repo
- They persist across deployments
- Secrets are safely encrypted with KMS
- No risk of losing KMS metadata

Our platform-engine approach is better because:
- Infrastructure code is centralized (DRY)
- Consistent patterns across all services
- But requires this workaround to ensure KMS metadata persists

---

## References

- [Pulumi Stack Settings File Reference](https://www.pulumi.com/docs/iac/concepts/projects/stack-settings-file/)
- [Pulumi State & Backend Options](https://www.pulumi.com/docs/concepts/state/)
- [Pulumi CLI: stack init](https://www.pulumi.com/docs/cli/commands/pulumi_stack_init/)
- [Pulumi Secrets Management](https://www.pulumi.com/blog/pulumi-secrets-management/)
