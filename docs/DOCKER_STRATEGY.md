# Docker Image Build Strategy

## Build Triggers

The Docker image is built and published **only when**:

1. **A version tag is pushed** (e.g., `v0.1.1`, `v1.0.0`)
   - Builds both the lean and LArCV image flavors
   - Creates lean tags: `0.1.1`, `0.1`, and `latest`
   - Creates LArCV tags: `0.1.1-larcv`, `0.1-larcv`, and `larcv`
   
2. **Pull requests** (for testing only)
   - Builds the image but doesn't push to registry
   - Tagged as `pr-<number>` locally

3. **Manual trigger** via GitHub Actions UI
   - Can be triggered manually when needed

## Why Not Build on Every Commit?

❌ **Avoided:** Building on every push to `main`

**Reasons:**
- **Storage efficiency** - Each build creates layers, even if deduplicated
- **Resource usage** - CI/CD minutes are consumed unnecessarily  
- **Clutter** - Many intermediate images that aren't releases
- **Best practice** - Production images should align with releases

## Image Tagging Strategy

When you create a tag like `v0.1.1`:

```
ghcr.io/deeplearnphysics/spinal-tap:0.1.1    (full version)
ghcr.io/deeplearnphysics/spinal-tap:0.1      (minor version)
ghcr.io/deeplearnphysics/spinal-tap:latest   (latest release)
ghcr.io/deeplearnphysics/spinal-tap:0.1.1-larcv (LArCV full version)
ghcr.io/deeplearnphysics/spinal-tap:0.1-larcv   (LArCV minor version)
ghcr.io/deeplearnphysics/spinal-tap:larcv       (latest LArCV release)
```

Benefits:
- Users can pin to exact version: `image: spinal-tap:0.1.1`
- Users can auto-update minor versions: `image: spinal-tap:0.1`
- Users can always get latest: `image: spinal-tap:latest`
- ROOT/LArCV dependencies remain isolated in the `-larcv`/`larcv` flavor

## Automatic Cleanup

The workflow includes automatic cleanup:
- Keeps the 5 most recent versions
- Deletes untagged image versions (intermediate build artifacts)
- Runs after each successful build

## Storage Considerations

### GHCR Free Tier Limits:
- ✅ **Unlimited public images**
- ✅ **No bandwidth limits** for public images
- ⚠️ **500MB free storage** for private packages
- ✅ For public packages: **No practical limit**

### Image Size Optimization:
The default Dockerfile uses a Python slim base and remains free of ROOT and
LArCV. The optional multi-stage LArCV Dockerfile starts from the dedicated
LArCV runtime image and copies only the `spine-prod` configuration tree.

## Workflow Summary

```
Developer creates tag v0.1.1
    ↓
GitHub Action triggered
    ↓
Build lean and LArCV Docker images
    ↓
Push lean tags: 0.1.1, 0.1, latest
Push LArCV tags: 0.1.1-larcv, 0.1-larcv, larcv
    ↓
Cleanup old untagged images
    ↓
Image available at ghcr.io/deeplearnphysics/spinal-tap
```

## Comparison: Build Strategies

| Strategy | Pros | Cons |
|----------|------|------|
| **Every commit** | Always up-to-date | Wasteful, cluttered, many intermediate images |
| **Main branch only** | Tracks development | Still creates many images, not tied to releases |
| **Tags only** ✅ | Clean, matches releases, efficient | Need to create tags (good practice anyway!) |

## Alternative: Build on Main + Tags

If you want images for both development and releases:

```yaml
on:
  push:
    branches:
      - main    # Creates 'edge' or 'dev' tag
    tags:
      - 'v*.*.*'  # Creates version tags + latest
```

Then tag strategy:
```yaml
tags: |
  type=ref,event=branch,suffix=-dev     # main -> latest-dev
  type=semver,pattern={{version}}        # v0.1.1 -> 0.1.1
  type=semver,pattern={{major}}.{{minor}} # v0.1.1 -> 0.1
  type=raw,value=latest,enable=${{ startsWith(github.ref, 'refs/tags/v') }}
```

This gives you:
- `latest` - Latest stable release
- `latest-dev` - Latest development version
- `0.1.1` - Specific versions

Let me know if you want this hybrid approach!
