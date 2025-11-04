# SLAC S3DF Configuration Guide for Spinal Tap

## Overview

This guide provides SLAC S3DF-specific configuration details for deploying Spinal Tap on S3DF Kubernetes.

## Storage Configuration

### Available Storage Classes

S3DF uses facility-specific storage classes to control access to filesystem paths. Common storageClasses:

- `sdf-data-neutrino` - For neutrino physics data
- `sdf-data-lcls` - For LCLS data
- `sdf-data-atlas` - For ATLAS data
- `sdf-data-rubin` - For Rubin Observatory data

### Requesting a New Storage Class

If you need access to a filesystem path not covered by existing storageClasses:

1. Email: `s3df-help@slac.stanford.edu`
2. Include:
   - Filesystem path (e.g., `/sdf/data/neutrino/myproject`)
   - Access justification
   - Estimated data size
   - vCluster name

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

For other facilities, update both `pvc.yaml` and the `volumeMounts` in `deployment.yaml`.

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

To use a different namespace:

1. Edit `k8s/kustomization.yaml`:
```yaml
namespace: my-namespace  # ← Change this
```

2. Ensure your vCluster has access to that namespace.

## Resource Limits

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

Adjust based on your needs and vCluster quotas.

## Example Deployment Workflow

1. **Clone and navigate**:
   ```bash
   cd spinal-tap/k8s
   ```

2. **Verify storage class** in `pvc.yaml` (pre-configured for neutrino):
   ```yaml
   storageClassName: sdf-data-neutrino
   ```

3. **Preview changes**:
   ```bash
   make dump
   ```

4. **Deploy**:
   ```bash
   make apply
   ```

5. **Verify**:
   ```bash
   kubectl get pods,pvc,ingress -l app=spinal-tap
   ```

6. **Access**:
   Open `https://spinal-tap.slac.stanford.edu` in your browser

## Common Issues

### PVC Stuck in Pending

**Symptom**: `kubectl get pvc` shows `Pending` status

**Cause**: StorageClass not approved for your vCluster

**Solution**: Contact S3DF support to request access

### Pod CrashLoopBackOff

**Check logs**:
```bash
kubectl logs -l app=spinal-tap --tail=50
```

**Common causes**:
- Storage mount issues
- Missing dependencies in container
- Application configuration errors

### Ingress Not Accessible

**Check ingress**:
```bash
kubectl describe ingress spinal-tap
```

**Verify**:
- Ingress has an address assigned
- DNS is correctly configured
- No firewall rules blocking access

## SLAC Best Practices

Following patterns from https://github.com/slaclab/slac-k8s-examples:

1. **Use Kustomize**: Manage all resources via `kustomization.yaml`
2. **Use Makefile**: Standard interface (`make apply`, `make dump`)
3. **Separate YAML files**: One resource per file for clarity
4. **StorageClasses**: Use facility-specific storage classes
5. **Labels**: Consistent labeling with `app: spinal-tap`

## Support Contacts

- **S3DF Infrastructure**: s3df-help@slac.stanford.edu
- **Neutrino Physics** (example): Contact your facility coordinator
- **GitHub Issues**: https://github.com/DeepLearnPhysics/spinal-tap/issues
