# Spinal Tap Kubernetes Deployment for SLAC S3DF

This directory contains Kubernetes manifests for deploying Spinal Tap on SLAC's S3DF Kubernetes infrastructure.

## Prerequisites

### 1. Access SLAC S3DF

Log into SLAC S3DF:
```bash
ssh USERNAME@s3dflogin.slac.stanford.edu
```

### 2. Configure kubectl for vCluster

Follow the setup instructions at: **https://k8s.slac.stanford.edu/neutrino-ml**

This will configure your `kubectl` to use the `neutrino-ml` vCluster context.

Verify your context:
```bash
kubectl config current-context
# Should show: neutrino-ml
```

### 3. Create Namespace (First-time only)

The `spinal-tap` namespace must be created before first deployment:
```bash
kubectl create namespace spinal-tap
```

### 4. Request Storage Class Access (First-time only)

Contact S3DF support to request approval for the `sdf-data-neutrino` storage class:

**Email**: `s3df-help@slac.stanford.edu`

**Template**:
```
Subject: Request storage class approval for neutrino-ml vCluster

Hello,

I need access to the sdf-data-neutrino storage class for the neutrino-ml vCluster.

Details:
- User: <your-email>@slac.stanford.edu
- vCluster: neutrino-ml
- Namespace: spinal-tap
- Required storage class: sdf-data-neutrino
- Purpose: Read-only access to /sdf/data/neutrino/spinal-tap/ for Spinal Tap data visualization

Please approve this storage class for the neutrino-ml vCluster.

Thanks!
```

Wait for approval before proceeding (usually quick).

### 5. Set Up Authentication (First-time only)

Spinal Tap requires authentication when deployed to Kubernetes to control access to experiment-specific data.

**Quick setup:**
```bash
cd k8s
./generate-secrets.sh
kubectl apply -f secret.yaml
```

**For detailed authentication setup**, see **[AUTHENTICATION.md](AUTHENTICATION.md)**.

## SLAC S3DF Configuration

This deployment is pre-configured for SLAC S3DF with:
- **Ingress**: `https://spinal-tap.slac.stanford.edu`
- **Storage**: Read-only access to `/sdf/data/neutrino/spinal-tap/` via `sdf-data-neutrino` storage class
- **Namespace**: `spinal-tap`

**For detailed configuration information** including:
- How storage classes and filesystem paths work
- Setting up data symlinks
- Customizing ingress/namespace/resources
- Adapting for other facilities

See **[SLAC_CONFIG.md](SLAC_CONFIG.md)** for the complete configuration guide

## Quick Start

### First-Time Deployment

1. **Log into S3DF**:
   ```bash
   ssh USERNAME@s3dflogin.slac.stanford.edu
   ```

2. **Navigate to the k8s directory**:
   ```bash
   cd /path/to/spinal-tap/k8s
   ```

3. **Preview what will be deployed**:
   ```bash
   make dump
   ```

4. **Deploy**:
   ```bash
   make apply
   ```

5. **Verify deployment**:
   ```bash
   kubectl get pods,pvc,ingress -n spinal-tap
   ```

### Updating the Deployment

To update manifests after making changes:

1. **Pull latest changes**:
   ```bash
   cd /path/to/spinal-tap
   git pull
   ```

2. **Apply updates**:
   ```bash
   cd k8s
   make apply
   ```

Kubernetes will automatically perform a rolling update with zero downtime (if using multiple replicas).

### Using Kustomize Directly

Alternatively, use kubectl directly:

```bash
# Apply all resources
kubectl apply -k .

# Preview changes
kubectl kustomize .
```

## Configuration

### Replicas

The deployment defaults to `replicas: 1` in `deployment.yaml`. 

**When to scale:**
- **1 replica**: Development, low traffic (< 10 concurrent users)
- **2-3 replicas**: Production, high availability, 10-50 concurrent users
- **5+ replicas**: High traffic, mission-critical (50+ concurrent users)

**Scale the deployment:**
```bash
# Edit deployment.yaml and change replicas, then:
make apply

# Or scale directly:
kubectl scale deployment spinal-tap -n spinal-tap --replicas=3
```

**Note**: The `ReadOnlyMany` PVC access mode supports multiple replicas reading simultaneously.

### Resource Limits

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

Adjust based on your needs. Monitor usage with:
```bash
kubectl top pod -n spinal-tap
```

If pods are OOMKilled, increase memory limits in `deployment.yaml` and reapply.

**For detailed resource tuning guidance**, see [SLAC_CONFIG.md](SLAC_CONFIG.md#resource-limits).

### Storage Class

The deployment uses `sdf-data-neutrino` for the neutrino facility. 

**To use a different facility or customize storage**, see [SLAC_CONFIG.md](SLAC_CONFIG.md#storage-configuration) for details on:
- Available storage classes
- How to adapt for other facilities  
- Setting up data symlinks
- Requesting new storage classes

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

This deployment follows SLAC S3DF Kubernetes best practices:

1. **Kustomize**: All manifests managed via `kustomization.yaml`
2. **Makefile**: Standard targets (`apply`, `dump`, `delete`)
3. **Storage**: Facility-specific storage classes for filesystem access
4. **Ingress**: Simple configuration, automatically handled by S3DF
5. **Labels**: Consistent labeling with `app: spinal-tap`

For more details, see [SLAC_CONFIG.md](SLAC_CONFIG.md#slac-best-practices).

## Troubleshooting

### Namespace Not Found Error

**Error**: `namespaces "spinal-tap" not found`

**Solution**: Create the namespace first:
```bash
kubectl create namespace spinal-tap
```

### PVC Stuck in Pending - Storage Class Blocked

**Error**: `validation error: Allowed storageClasses at vcluster--neutrino-ml`

**Cause**: The Kyverno policy is blocking the storage class for your vCluster.

**Solution**: Contact S3DF support to approve `sdf-data-neutrino` for the `neutrino-ml` vCluster:
```bash
# Check PVC status
kubectl describe pvc spinal-tap-data -n spinal-tap

# Email s3df-help@slac.stanford.edu for storage class approval
```

### PVC Not Binding - General

```bash
kubectl describe pvc spinal-tap-data -n spinal-tap
```

**Common issues**:
- Wrong storageClassName
- Insufficient permissions for that storageClass
- Storage path doesn't exist on filesystem

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n spinal-tap

# Get detailed information
kubectl describe pod -n spinal-tap -l app=spinal-tap

# View logs
kubectl logs -n spinal-tap -l app=spinal-tap --tail=50
```

### Permission Denied Errors

**Error**: `User "username@slac.stanford.edu" cannot get resource...`

**Solution**: You need appropriate RBAC permissions. Contact S3DF support to request access to the vCluster and namespace.

### Ingress Not Working

```bash
kubectl describe ingress spinal-tap -n spinal-tap
```

Verify the ingress shows a valid address/hostname.

### Monitor Resource Usage

Check if pods are running out of memory or CPU:
```bash
# View current resource usage
kubectl top pod -n spinal-tap

# Watch resource usage continuously
kubectl top pod -n spinal-tap --watch

# Check for OOMKilled pods
kubectl get pods -n spinal-tap
kubectl describe pod -n spinal-tap -l app=spinal-tap | grep -E "State|Reason|Exit Code"
```

### Force Pod Restart

If you need to restart pods (e.g., to pick up a new `:latest` image):
```bash
kubectl rollout restart deployment spinal-tap -n spinal-tap

# Monitor the rollout
kubectl rollout status deployment spinal-tap -n spinal-tap
```

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
