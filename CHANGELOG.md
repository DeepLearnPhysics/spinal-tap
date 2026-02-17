# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.3] - 2026-02-16
### Changed
- Updated to Dash 4.0.0 with style adjustments
- Updated `spine` dependency to v0.10.3+ (includes fix to underlying Drawer tool)

### Fixed
- Fixed attribute list allowed to be displayed/used as color

### Added
- Re-added auto-complete functionality to file path (it was gone when using Dash 4.0.0)

## [0.3.2] - 2026-02-12
### Fixed
- Updated `spine` dependency to v0.10.2+ (includes update allowing to display attributes on truth but not reco)
- Ensure the overall proposed attribute set includes both reco and truth attributes
- Strip file names from white space on the edges to prevent loading issues

## [0.3.1] - 2026-02-12
### Changed
- Updated dependency from `spine-ml` to `spine` (now at v0.10.1+)
- Enhanced geometry handling to automatically load geometry configuration from data files

### Fixed
- Prevent displaying stale geometry from previous entries when no geometry is specified

### Added
- Type hints for `initialize_reader` and `load_data` functions in utils module

## [0.3.0] - 2026-01-20
### Changed
- **Breaking**: Update to support SPINE v0.8.0+ geometry system
- Fetch available geometries dynamically from SPINE's `geo_dict()` instead of hard-coded list
- Add geometry tag/version dropdown with automatic selection of latest version
- Split geometry selection into detector name and tag

### Added
- Dynamic geometry list populated from SPINE's geometry configuration
- Support for all SPINE geometries: 2x2, ICARUS, SBND, ND-LAr, ProtoDUNE-VD/SP/HD, DUNE10kt-1x2x6, FSD
- Automatic tag selection for geometry versions
- Updated DUNE log-in access list to include /data/dune and /data/pdune

## [0.2.4] - 2025-11-24
### Added
- Add "Public" login option to access public datasets only

## [Unreleased]

## [0.2.1] - 2025-11-06
### Added
- Add logout button to allow one to change experiment directory

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
