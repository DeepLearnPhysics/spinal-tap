# SLAC S3DF Configuration Guide for Spinal Tap

## Overview

This guide provides detailed SLAC S3DF-specific configuration information for customizing and understanding the Spinal Tap Kubernetes deployment.

**For deployment instructions**, see [README.md](README.md).

## Table of Contents

- [Storage Configuration](#storage-configuration)
- [Authentication and Access Control](#authentication-and-access-control)
- [Ingress Configuration](#ingress-configuration)
- [Namespace Configuration](#namespace-configuration)
- [Resource Limits](#resource-limits)
- [SLAC Best Practices](#slac-best-practices)
- [Support Contacts](#support-contacts)

## Storage Configuration

### Available Storage Classes

S3DF uses facility-specific storage classes to control access to filesystem paths. Common storageClasses:

- `sdf-data-neutrino` - For neutrino physics data
- `sdf-data-lcls` - For LCLS data
- `sdf-data-atlas` - For ATLAS data
- `sdf-data-rubin` - For Rubin Observatory data

### Requesting a New Storage Class

If you need access to a filesystem path not covered by existing storageClasses:

**Email**: `s3df-help@slac.stanford.edu`

**Include**:
- Filesystem path (e.g., `/sdf/data/neutrino/myproject`)
- Access justification
- Estimated data size
- vCluster name (e.g., `neutrino-ml`)

### Adapting for Other Facilities

To use a different facility, update `pvc.yaml`:

```yaml
spec:
  storageClassName: sdf-data-YOUR_FACILITY  # e.g., sdf-data-lcls, sdf-data-atlas
```

And update the `subPath` in `deployment.yaml` volumeMounts section to match your facility's directory structure.

### Mounting Storage

The `pvc.yaml` defines the storage request. For the neutrino facility, it's pre-configured for read-only access:

```yaml
spec:
  accessModes:
  - ReadOnlyMany  # Read-only access
  storageClassName: sdf-data-neutrino
  resources:
    requests:
      storage: 1Gi  # Minimal size for mounting existing data
```

The storage will be mounted at `/data` inside the container, accessing only the `/sdf/data/neutrino/spinal-tap/` subdirectory from the SDF filesystem (via `subPath` in the deployment).

**How it works:**
- The `sdf-data-neutrino` storage class is pre-configured by S3DF to map to `/sdf/data/neutrino` on the filesystem
- The `subPath: spinal-tap` limits the mount to the `spinal-tap` subdirectory
- The `mountPath: /data` makes it available at `/data` inside the container

**Exposing Data via Symlinks:**

On the SDF filesystem, create a directory structure like:

```bash
/sdf/data/neutrino/spinal-tap/
├── run123 -> /sdf/data/neutrino/reconstruction/run123
├── run124 -> /sdf/data/neutrino/reconstruction/run124
└── analysis-2024 -> /sdf/data/neutrino/analysis/2024
```

Inside the container, users will see:
```
/data/run123/
/data/run124/
/data/analysis-2024/
```

This allows you to selectively expose only the data you want accessible through Spinal Tap.

## Authentication and Access Control

### Overview

Spinal Tap includes optional authentication to control access to experiment-specific data. When deployed to Kubernetes, authentication is enabled by default.

**For complete authentication setup**, see [AUTHENTICATION.md](AUTHENTICATION.md).

### Experiment-Specific Access

Users are restricted to their experiment's data directory:
- **2x2**: `/data/2x2/`
- **NDLAR**: `/data/ndlar/`
- **ICARUS**: `/data/icarus/`
- **SBND**: `/data/sbnd/`

### Shared Folders

You can designate folders that all authenticated users can access, regardless of experiment. This is useful for:
- Calibration data
- Common analysis tools
- Documentation
- Tutorial/example files

**Configure shared folders** in `deployment.yaml`:

```yaml
env:
- name: SPINAL_TAP_SHARED_FOLDERS
  value: "/data/generic,/data/common,/data/calibration"
```

Default: `/data/generic`

### Filesystem Organization Example

For multi-experiment access with shared resources:

```bash
/sdf/data/neutrino/
├── 2x2/
│   └── spine/prod/      # 2x2-only files
├── ndlar/
│   └── spine/prod/      # NDLAR-only files
├── icarus/
│   └── spine/prod/      # ICARUS-only files
├── sbnd/
│   └── spine/prod/      # SBND-only files
└── generic/
    ├── calibration/     # Shared calibration data
    ├── geometry/        # Shared geometry files
    └── examples/        # Tutorial files
```

## Ingress Configuration

### Domain

The application is accessible at:
```
https://spinal-tap.slac.stanford.edu
```

### Custom Subdomain

To use a different subdomain, update `k8s/ingress.yaml`:

```yaml
spec:
  rules:
  - host: my-app.slac.stanford.edu  # ← Change this
```

Then coordinate with S3DF admins for DNS setup.

### TLS/HTTPS

HTTPS is automatically configured by S3DF ingress controller. No additional cert-manager configuration needed.

## Namespace

By default, resources are deployed in the `spinal-tap` namespace (defined in `kustomization.yaml`).

### Using a Different Namespace

1. Edit `k8s/kustomization.yaml`:
```yaml
namespace: my-namespace  # ← Change this
```

2. Create the namespace:
```bash
kubectl create namespace my-namespace
```

3. Ensure your vCluster has access to that namespace (contact S3DF support if needed).

## Resource Limits

### Default Configuration

Current defaults in `deployment.yaml`:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

### When to Adjust

**Increase memory** if:
- Pods are OOMKilled (`kubectl describe pod` shows exit code 137)
- Loading large datasets
- High concurrent user load

**Increase CPU** if:
- Slow response times
- High CPU usage (`kubectl top pod` shows CPU near limit)

### Monitoring

Check current resource usage:
```bash
kubectl top pod -n spinal-tap
```

Check for resource-related issues:
```bash
kubectl describe pod -n spinal-tap -l app=spinal-tap | grep -E "State|Reason|Exit Code|Memory|CPU"
```

Adjust based on your vCluster quotas and actual usage patterns.

## SLAC Best Practices

This deployment follows patterns from [slaclab/slac-k8s-examples](https://github.com/slaclab/slac-k8s-examples):

1. **Use Kustomize**: Manage all resources via `kustomization.yaml` for consistent deployments
2. **Use Makefile**: Standard interface (`make apply`, `make dump`, `make delete`) 
3. **Separate YAML files**: One Kubernetes resource per file for clarity
4. **StorageClasses**: Use facility-specific storage classes (e.g., `sdf-data-neutrino`)
5. **Labels**: Consistent labeling with `app: spinal-tap` for easy resource selection
6. **ReadOnly mounts**: Use `ReadOnlyMany` for shared data access across replicas
7. **Symlinks**: Expose only needed data via symlinks rather than mounting entire filesystems

## Support Contacts

- **S3DF Infrastructure & Kubernetes**: `s3df-help@slac.stanford.edu`
- **vCluster Access & Permissions**: `s3df-help@slac.stanford.edu`
- **Storage Class Approvals**: `s3df-help@slac.stanford.edu`
- **Application Issues**: [GitHub Issues](https://github.com/DeepLearnPhysics/spinal-tap/issues)

