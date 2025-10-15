# Spinal Tap Kubernetes Deployment

This directory contains Kubernetes manifests for deploying Spinal Tap.

## Prerequisites

- Kubernetes cluster (1.19+)
- kubectl configured to communicate with your cluster
- (Optional) Ingress controller (e.g., NGINX Ingress Controller)
- (Optional) cert-manager for TLS certificates

## Docker Image

The Docker image is automatically built and published to GitHub Container Registry (ghcr.io) via GitHub Actions when:
- A new version tag is created (e.g., `v0.1.1`)
- Manual workflow dispatch is triggered

This ensures only release versions are published, keeping the registry clean and efficient.

### Building Locally

To build the Docker image locally:

```bash
docker build -t spinal-tap:local .
```

To run locally:

```bash
docker run -p 8888:8888 spinal-tap:local
```

Access the application at http://localhost:8888

## Kubernetes Deployment

### Quick Start

1. Apply all manifests:

```bash
kubectl apply -f k8s/
```

2. Check the deployment status:

```bash
kubectl get pods -l app=spinal-tap
kubectl get svc spinal-tap
```

3. Access the application:

**Port-forward (for testing):**
```bash
kubectl port-forward svc/spinal-tap 8888:8888
```
Then visit http://localhost:8888

**Via Ingress (for production):**
Edit `k8s/ingress.yaml` to set your domain and apply it.

### Individual Resources

You can also apply resources individually:

```bash
# Deploy the application
kubectl apply -f k8s/deployment.yaml

# Create the service
kubectl apply -f k8s/service.yaml

# (Optional) Create the ingress
kubectl apply -f k8s/ingress.yaml
```

## Configuration

### Environment Variables

You can add environment variables to the deployment by editing `k8s/deployment.yaml`:

```yaml
env:
- name: CUSTOM_VAR
  value: "custom_value"
```

### Resource Limits

Adjust resource requests and limits in `k8s/deployment.yaml`:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

### Replicas

To scale the deployment:

```bash
kubectl scale deployment spinal-tap --replicas=3
```

Or edit the `replicas` field in `k8s/deployment.yaml`.

## Ingress Configuration

### NGINX Ingress Controller

If using NGINX Ingress Controller, edit `k8s/ingress.yaml`:

1. Set your domain:
```yaml
- host: spinal-tap.yourdomain.com
```

2. Uncomment TLS section for HTTPS:
```yaml
tls:
- hosts:
  - spinal-tap.yourdomain.com
  secretName: spinal-tap-tls
```

3. If using cert-manager, uncomment the annotation:
```yaml
annotations:
  cert-manager.io/cluster-issuer: letsencrypt-prod
```

## Monitoring

### Check logs

```bash
kubectl logs -l app=spinal-tap -f
```

### Check pod status

```bash
kubectl describe pod -l app=spinal-tap
```

### Check service endpoints

```bash
kubectl get endpoints spinal-tap
```

## Updating

### Update to a new version

1. Edit `k8s/deployment.yaml` and update the image tag:
```yaml
image: ghcr.io/deeplearnphysics/spinal-tap:v0.1.2
```

2. Apply the changes:
```bash
kubectl apply -f k8s/deployment.yaml
```

Or use kubectl set image:
```bash
kubectl set image deployment/spinal-tap spinal-tap=ghcr.io/deeplearnphysics/spinal-tap:v0.1.2
```

### Rollback

```bash
kubectl rollout undo deployment/spinal-tap
```

## Cleanup

To remove all resources:

```bash
kubectl delete -f k8s/
```

## Troubleshooting

### Pods not starting

Check pod events:
```bash
kubectl describe pod -l app=spinal-tap
```

### Image pull errors

Ensure the image is public or configure imagePullSecrets:
```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_TOKEN
```

Then reference it in the deployment:
```yaml
imagePullSecrets:
- name: ghcr-secret
```

### Can't access the service

1. Check if pods are running:
```bash
kubectl get pods -l app=spinal-tap
```

2. Check if service is created:
```bash
kubectl get svc spinal-tap
```

3. Test connectivity from within the cluster:
```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- curl http://spinal-tap:8888
```
