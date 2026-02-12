# Docker Image Build Strategy

## Build Triggers

The Docker image is built and published **only when**:

1. **A version tag is pushed** (e.g., `v0.1.1`, `v1.0.0`)
   - Creates versioned tags: `0.1.1`, `0.1`, and `latest`
   
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
```

Benefits:
- Users can pin to exact version: `image: spinal-tap:0.1.1`
- Users can auto-update minor versions: `image: spinal-tap:0.1`
- Users can always get latest: `image: spinal-tap:latest`

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
Our Dockerfile uses:
- **Python slim base** (~150MB vs 1GB for full Python)
- **Multi-stage builds** would further reduce size (can add if needed)
- **Layer caching** - Only changed layers are rebuilt

Current estimated image size: **~500MB - 1GB** (depending on spine dependencies)

## Workflow Summary

```
Developer creates tag v0.1.1
    ↓
GitHub Action triggered
    ↓
Build Docker image
    ↓
Push with tags: 0.1.1, 0.1, latest
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
