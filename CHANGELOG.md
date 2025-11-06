# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2025-11-06
### Changed
- Update banner styling: experiment name and logout button now use black color (#000000) for better consistency with "Spinal Tap" title
- Remove background color from logout button for cleaner appearance

### Fixed
- Fix Makefile context check to properly evaluate kubectl context instead of comparing against literal string
- Add venv/ to .gitignore to prevent tracking virtual environments

### Documentation
- Add password update instructions to k8s README with rollout restart steps

## [0.2.0] - 2025-11-05
### Added
- Add optional authentication system with experiment-based access control
- Add logout functionality with experiment name display in banner
- Add support for multiple folder paths per experiment (EXPERIMENT_PATHS)
- Add secure path validation to prevent directory traversal attacks
- Add generate-secrets.sh script for creating Kubernetes secrets with hashed passwords
- Add comprehensive authentication documentation (k8s/AUTHENTICATION.md)

### Changed
- Consolidate 2x2 and NDLAR experiments into single 'DUNE' experiment with access to both /data/2x2 and /data/ndlar
- Update login page styling to match main application colors and layout
- Enhance path validation with os.path.normpath() and os.sep for security

### Security
- Implement SHA256 password hashing for credential storage
- Add session-based authentication with Flask sessions
- Implement experiment-specific folder access restrictions

## [0.1.2] - 2025-10-15
- Add Docker containerization support
- Add Kubernetes deployment manifests (deployment, service, ingress)
- Add GitHub Actions workflow for automated Docker image publishing to GHCR
- Add automatic cleanup of old untagged Docker images
- Add comprehensive Kubernetes deployment documentation
- Add docker-run.sh script for local testing

## [0.1.1] - 2025-10-04
- Add CRT hit visualization options to UI
- Improve flash matching logic and option naming
- Enhance layout with new controls for CRT hit visualization
- Update dependencies and project metadata in pyproject.toml

## [0.1.0] - 2025-10-03
- Initial release
