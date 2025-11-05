# Spinal Tap Authentication Setup

## Overview

Spinal Tap supports optional authentication to restrict access to experiment-specific data. When enabled, users must log in with an experiment-specific password to access data.

## Modes

### Local Mode (No Authentication)
When running locally on your laptop, authentication is **disabled by default**:
```bash
spinal-tap --port 8888
```
You can access any files on your local filesystem without restrictions.

### Kubernetes Mode (Authentication Required)
When deployed to Kubernetes, authentication is **enabled** via the `SPINAL_TAP_AUTH` environment variable.

## Setup for Kubernetes Deployment

### 1. Generate Passwords

Choose a password for each experiment:
- DUNE (provides access to both 2x2 and NDLAR data)
- ICARUS  
- SBND

### 2. Create Kubernetes Secret

Use the provided script to generate password hashes and create the secret:

```bash
cd k8s
./generate-secrets.sh
```

This will:
1. Prompt you for passwords for each experiment
2. Generate SHA256 hashes
3. Create a `secret.yaml` file
4. Generate a random secret key for Flask sessions

### 3. Apply the Secret

```bash
kubectl apply -f secret.yaml
```

**IMPORTANT**: Do NOT commit `secret.yaml` to git! It's already in `.gitignore`.

### 4. Deploy the Application

```bash
make apply
```

The deployment will automatically use the secrets.

## How It Works

### User Flow

1. User visits `https://spinal-tap.slac.stanford.edu`
2. Login page appears with experiment dropdown and password field
3. User selects their experiment and enters password
4. On successful login, user can access files in `/data/{experiment}/`
5. Attempts to access other experiments' data are blocked

### Access Control

- **DUNE users**: Can access files in both `/data/2x2/` and `/data/ndlar/`
- **ICARUS users**: Can only access files starting with `/data/icarus/`
- **SBND users**: Can only access files starting with `/data/sbnd/`
- **All users**: Can access shared folders (default: `/data/generic/`, `/data/public_html/`)

### Shared Folders

Shared folders are accessible to all authenticated users, regardless of experiment. By default, `/data/generic/` and `/data/public_html/` are shared.

To add more shared folders, update the `SPINAL_TAP_SHARED_FOLDERS` environment variable in `deployment.yaml`:

```yaml
- name: SPINAL_TAP_SHARED_FOLDERS
  value: "/data/generic,/data/common,/data/calibration"
```

Multiple folders can be specified as a comma-separated list.

## Password Distribution

Share passwords securely through each experiment's existing document management system:

- **2x2**: Share via 2x2 DocDB or collaboration wiki
- **NDLAR**: Share via NDLAR collaboration channels
- **ICARUS**: Share via ICARUS DocDB
- **SBND**: Share via SBND collaboration channels

## Changing Passwords

To change a password:

1. Generate new hash:
   ```bash
   echo -n "new_password" | sha256sum
   ```

2. Update the secret:
   ```bash
   kubectl patch secret spinal-tap-secrets -n spinal-tap \
     -p '{"stringData":{"password-2x2":"NEW_HASH_HERE"}}'
   ```

3. Restart deployment to pick up new secret:
   ```bash
   kubectl rollout restart deployment spinal-tap -n spinal-tap
   ```

## Security Notes

- Passwords are hashed with SHA256 (not stored in plain text)
- Sessions are encrypted with Flask's secure session cookie
- File access is validated on every request
- All data access is read-only
- Login attempts are not rate-limited (consider adding this for production)

## Troubleshooting

### Login not working

Check that:
1. Secret exists: `kubectl get secret spinal-tap-secrets -n spinal-tap`
2. Environment variables are set: `kubectl describe pod -n spinal-tap -l app=spinal-tap | grep -A 10 Environment`
3. Pods restarted after secret creation: `kubectl rollout restart deployment spinal-tap -n spinal-tap`

### Access denied errors

- Verify you're logged in as the correct experiment
- Check file path starts with `/data/{experiment}/`
- Clear browser cookies and log in again

### Testing locally without auth

Set environment variable to disable auth:
```bash
export SPINAL_TAP_AUTH=false
spinal-tap
```
