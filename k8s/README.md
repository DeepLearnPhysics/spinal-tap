# Spinal Tap Kubernetes Deployment for SLAC S3DF

This directory contains Kubernetes manifests for deploying Spinal Tap on SLAC's S3DF Kubernetes infrastructure.

## Prerequisites

- Access to SLAC S3DF Kubernetes vCluster
- `kubectl` configured for your S3DF vCluster context
- Appropriate storageClass access for your facility's data

## SLAC S3DF Configuration

### Ingress

The application is configured to be accessible at:
- **URL**: `https://spinal-tap.slac.stanford.edu`

The ingress is automatically handled by the S3DF ingress controller.

### Storage

The deployment includes a PersistentVolumeClaim (`pvc.yaml`) that provides read-only access to S3DF filesystem storage:

- **Mount path**: `/data` (inside container)
- **Source path**: `/sdf/data/neutrino/spinal-tap/` (on SDF filesystem, via `sdf-data-neutrino` storage class)
- **Storage class**: `sdf-data-neutrino`
- **Access mode**: ReadOnlyMany (read-only access)
- **Size**: 1Gi (minimal, only for mounting existing data)

**Note**: The deployment mounts only the `/sdf/data/neutrino/spinal-tap/` subdirectory (via `subPath`). Create symlinks inside this directory to expose specific data folders to users.

**Important**: The storageClass is configured for the neutrino facility. If deploying for a different facility, update the `storageClassName` in `pvc.yaml`. Common patterns:
- `sdf-data-<facility>` (e.g., `sdf-data-neutrino`, `sdf-data-lcls`, `sdf-data-atlas`)

If your required path is not available, contact S3DF support at `s3df-help@slac.stanford.edu` with:
- Desired filesystem path (e.g., `/sdf/data/neutrino/myproject`)
- Access justification
- Expected data size

## Quick Start

### Using Kustomize (Recommended)

Following SLAC best practices, use Kustomize to deploy all resources:

```bash
# Preview what will be deployed
make dump

# Deploy to your vCluster
make apply
```

Or directly with kubectl:

```bash
kubectl apply -k .
```

### Manual Deployment

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f pvc.yaml
kubectl apply -f ingress.yaml
```

## Configuration

### Storage Class (Optional)

The deployment is pre-configured for the neutrino facility with `sdf-data-neutrino`. 

To use a different facility, edit `pvc.yaml`:

```yaml
spec:
  storageClassName: sdf-data-YOUR_FACILITY  # Update this!
```

And update the mount path in `deployment.yaml`:

### Verify Deployment

```bash
# Check pods
kubectl get pods -l app=spinal-tap

# Check persistent volume claim
kubectl get pvc spinal-tap-data

# Check ingress
kubectl get ingress spinal-tap
```

### Access the Application

Once deployed, access Spinal Tap at:
**https://spinal-tap.slac.stanford.edu**

## SLAC Best Practices

This deployment follows SLAC S3DF Kubernetes patterns:

1. **Kustomize**: All manifests are managed via `kustomization.yaml`
2. **Makefile**: Standard targets (`apply`, `dump`, `delete`) for consistency
3. **Storage**: Uses SDF-specific storageClasses for filesystem access
4. **Ingress**: Simple ingress configuration (no annotations needed)
5. **Namespace**: Resources deployed in `spinal-tap` namespace

## Troubleshooting

### PVC Not Binding

```bash
kubectl describe pvc spinal-tap-data
```

**Common issues**:
- Wrong storageClassName
- Insufficient permissions for that storageClass
- Contact S3DF support for storageClass approval

### Pods Not Starting

```bash
kubectl describe pod -l app=spinal-tap
kubectl logs -l app=spinal-tap
```

### Ingress Not Working

```bash
kubectl describe ingress spinal-tap
```

Verify the ingress shows a valid address/hostname.

## Cleanup

```bash
make delete
```

Or:

```bash
kubectl delete -k .
```

## Support

For S3DF-specific issues:
- Email: `s3df-help@slac.stanford.edu`
- Docs: Check SLAC confluence for S3DF Kubernetes documentation
- Examples: https://github.com/slaclab/slac-k8s-examples
