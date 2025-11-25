#!/bin/bash
# Script to generate password hashes and create Kubernetes secret

echo "Spinal Tap Password Hash Generator"
echo "===================================="
echo ""
echo "This script will help you create password hashes for each experiment."
echo "The hashes will be used in the Kubernetes secret."
echo ""

# Function to hash a password
hash_password() {
    echo -n "$1" | sha256sum | awk '{print $1}'
}

# Collect passwords
echo "Enter password for public dataset access:"
read -s PASSWORD_PUBLIC
HASH_PUBLIC=$(hash_password "$PASSWORD_PUBLIC")

echo "Enter password for DUNE experiment (provides access to 2x2 and NDLAR data):"
read -s PASSWORD_DUNE
HASH_DUNE=$(hash_password "$PASSWORD_DUNE")

echo "Enter password for ICARUS experiment:"
read -s PASSWORD_ICARUS
HASH_ICARUS=$(hash_password "$PASSWORD_ICARUS")

echo "Enter password for SBND experiment:"
read -s PASSWORD_SBND
HASH_SBND=$(hash_password "$PASSWORD_SBND")

# Generate random secret key
SECRET_KEY=$(openssl rand -hex 32)

echo ""
echo "Password hashes generated!"
echo ""
echo "Creating Kubernetes secret..."

# Create the secret
kubectl create secret generic spinal-tap-secrets \
  --from-literal=secret-key="$SECRET_KEY" \
  --from-literal=password-public="$HASH_PUBLIC" \
  --from-literal=password-dune="$HASH_DUNE" \
  --from-literal=password-icarus="$HASH_ICARUS" \
  --from-literal=password-sbnd="$HASH_SBND" \
  -n spinal-tap \
  --dry-run=client -o yaml > secret.yaml

echo ""
echo "Secret manifest created in secret.yaml"
echo ""
echo "To apply the secret, run:"
echo "  kubectl apply -f secret.yaml"
echo ""
echo "IMPORTANT: Keep your passwords safe and DO NOT commit secret.yaml to git!"
