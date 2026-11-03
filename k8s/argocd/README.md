# Spinal Tap releases through Argo CD on S3DF

Status: **prepared for review; not applied**. Reuse the existing self-managed
Argo CD v3.5.6 instance in namespace `argocd` in the `neutrino-ml` vcluster.
Do not install a second instance. SPINE Learn remains a separate Application
with its own source, release channel and namespace permissions.

## Release flow

1. Prepare a patch release (`v1.2.3` is next): update
   `src/spinal_tap/version.py`, move Unreleased notes into a dated CHANGELOG
   section, and validate the exact commit on main.
2. Publish the stable GitHub Release for that commit. A tag push alone no longer
   publishes Docker images. Test PyPI's existing tag-push flow is separate.
3. Docker Image calls the existing tests/100% coverage and documentation workflow,
   verifies the stable tag matches the package version and dated changelog, then
   builds both lean and LArCV images. Each exact image is smoke-tested before push.
   The LArCV check imports ROOT and LArCV as well as SPINE.
4. Each variant publishes a `s3df-release-VARIANT` Actions artifact and an OCI
   bundle at `ghcr.io/deeplearnphysics/spinal-tap-deploy:vVERSION-VARIANT`.
   Bundles contain only Deployment, Service and NGINX Ingress; the image is pinned
   by SHA-256 digest. Flux CLI is the packager; no Flux controller is installed.
5. Only GitHub's latest stable release advances `release-larcv` and `release-lean`.
   Argo follows **release-larcv**, preserving the currently deployed runtime.
   Older releases cannot overwrite that channel after a newer release is latest.
6. Argo detects a new bundle and automatically syncs and self-heals it. No routine
   deployment approval is required after initial adoption. Pruning is disabled.

Main-branch changes, PRs, manual build checks, drafts and prereleases do not
advance S3DF. Manual and PR Docker checks build/test images without publishing.
The existing PyPI workflow remains separate; a PyPI failure does not invalidate
or automatically roll back an independently tested container deployment.

Both login and GUI pages already show the package version. Spinal Tap's version
is independent of its SPINE dependency version. Neither is restarted merely by
pushing documentation or an untagged main commit.

## Existing deployment and preservation

Read-only inspection confirmed:

- Namespace, Deployment, Service and Ingress: `spinal-tap`.
- Public address: `https://spinal-tap.slac.stanford.edu`.
- Runtime flavor: LArCV, currently configured with moving image tag `:larcv`.
- Running image digest at inspection:
  `sha256:ae4aa72b8eb77b837d0e7d3398ad9d5446eb9cece6385788a78e9e8e0e42b9bb`.
- Existing NGINX Ingress class `nginx`; no HTTPRoute migration is proposed.
- Existing bound `spinal-tap-data` PVC, mounted read-only at `/data`.
- Existing `spinal-tap-secrets` references; no Secret values were inspected.
- Existing 20Gi ephemeral cache and workload resource requests/limits.

Release rendering preserves these runtime settings, readiness/liveness probes,
selectors and the existing RollingUpdate strategy. It does not manage Secrets,
PVCs, Namespaces, storage classes or cluster-scoped infrastructure. Application
RBAC cannot delete resources. Do not use broad `apply -k k8s/base` for routine
updates once Argo manages the release; it includes storage and a moving image tag.

Changing the pod image causes a rolling replacement and resets the ephemeral
cache. Authentication/session behavior during a replacement must be verified;
there is no cross-pod session migration added by this setup. Never force-delete
the PVC, recreate credentials, or replace the Ingress to resolve adoption issues.

## Concrete configuration for review

- `project.yaml`: source restricted to this OCI package; destination restricted
  to namespace `spinal-tap`; only Deployment, Service and Ingress are managed.
- `rbac.yaml`: controller read/write permissions for those three resource types,
  and read-only Pod/ReplicaSet/Event health access in this namespace. No delete,
  Secret, PVC, exec, namespace or application-RBAC management grant.
- `shared-cluster.yaml`: non-sensitive cluster configuration, represented as an
  Argo cluster Secret, expanding discovery from `spine-learn` to
  `spine-learn,spinal-tap`. No token is included; in-cluster service-account
  authentication continues. Cluster-resource management stays disabled.
- `application.yaml`: separate `spinal-tap` Application targeting the
  `release-larcv` OCI channel, with automatic sync and self-heal enabled, pruning
  disabled, and FailOnSharedResource enabled. The existing manual restart
  timestamp is ignored and preserved during sync; no cascading deletion finalizer.

The shared Argo installation's original manifests are in
[spine-learn](https://github.com/DeepLearnPhysics/spine-learn/tree/main/k8s/argocd).
Its `install/local-cluster.yaml` and `projects.yaml` need matching updates, so
reapplying that installation cannot silently remove spinal-tap's discovery or
project permissions. Those matching local changes are part of the review.
Do not reapply stale copies of the previously denied spinal-tap project.

Protect Argo administrators and release publishing rights: permission to update
the workload allows indirect use of its existing application credentials even
though Argo has no direct Secret permissions in this application namespace.
Local `k8s/secret.yaml` and `k8s/secret.backup.yaml` are excluded from Git; never
include either in a release bundle, commit or review output.

## Initial rollout and patch-release test

Review all four Argo files, shared-installation changes, release workflow, and a
rendered bundle **before applying configuration or publishing the test release**.
No deployment change or release has been made by preparing these files.

First publish the approved patch release and wait for the LArCV job to pass.
Confirm the new deployment package is anonymously readable, or provision separate
approved read-only registry access in Argo. Public source does not imply public
GHCR packages. The existing repo-server already accepts the Flux layer media type.

Download `s3df-release-larcv` from that exact Docker Image release run into a fresh
directory. Inspect the OCI `vVERSION-larcv` and `release-larcv` tags: their manifest
digests must match, with one expected Flux layer. Compare the extracted files
byte for byte with the Actions artifact. Render with `kubectl kustomize`, verify
the image digest and the three expected namespaced kinds, and compare to live
resources before syncing. Preserve platform-added Ingress fields.

After review, apply `rbac.yaml`, `shared-cluster.yaml`, and `project.yaml` with
`--context neutrino-ml`, then `application.yaml`. Do not create the Application
against a missing OCI channel. The Application will then appear as **spinal-tap**
in the same Argo UI as SPINE Learn. Automatic sync performs the first rollout.

Verify Synced/Healthy and an automated successful operation, then check the ready
pod image against the published bundle. Open the login page and verify `Tap 1.2.3`;
a maintainer should sign in privately and verify file access, a representative
event, and LArCV input if available. Never put shared passwords in chat or CI.
Record the previous image and release bundle digest before any later deployment.
Only after verification should this README say the Application is installed.

## Private access and operational checks

Use the same private Argo UI and permanent admin login as SPINE Learn. On S3DF:

```bash
module load kubectl
kubectl --context neutrino-ml -n argocd port-forward --address 127.0.0.1 svc/argocd-server 8080:443
```

Keep that running. On the laptop, tunnel to the exact S3DF machine running it
(`hostname -f`), using the normal external login host as a jump host if needed:

```bash
ssh -J USER@S3DF_LOGIN_HOST -N -o ExitOnForwardFailure=yes \
  -L 8080:127.0.0.1:8080 USER@EXACT_INTERNAL_HOST
```

Open `https://localhost:8080`, then Applications → spinal-tap. Closing the tunnels
has no effect on automated deployment. No new public Argo route is introduced.

```bash
kubectl --context neutrino-ml -n argocd get application spinal-tap
kubectl --context neutrino-ml -n spinal-tap get pods,service,ingress
kubectl --context neutrino-ml -n spinal-tap rollout status deployment/spinal-tap --timeout=600s
curl --fail https://spinal-tap.slac.stanford.edu/
```

A passing login endpoint or Argo health status does not verify authenticated data
access or a representative event. Check those privately after a release. No
external monitor or automatic rollback is added by this configuration.

## Pause and rollback

Pause first so self-heal cannot undo the rollback:

```bash
kubectl --context neutrino-ml -n argocd patch application spinal-tap --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"enabled":false}}}}'
```

In the private Argo UI, select an earlier validated **OCI bundle manifest digest**
(`sha256:...`, not its container image digest), and Sync without pruning. Verify
the expected image, ready pod, login, authentication and data access. Keep that
revision pinned while investigating. Do not use only `kubectl rollout undo`;
it does not change Argo's desired revision.

After a corrective release is promoted, resume with the reviewed active config:

```bash
kubectl --context neutrino-ml apply -f k8s/argocd/application.yaml
```

This restores `release-larcv` tracking, automatic sync and self-heal. It can
redeploy the problematic release if the channel has not yet been corrected.
A flavor change, pruning, storage changes or Argo installation upgrade requires
separate review. Do not recursively apply the whole `k8s` directory.
