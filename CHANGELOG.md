# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-08-25

### Added
- **WebGL event display**: Add a dedicated WebGL 2 renderer for fast interaction with large renderer-neutral SPINE scenes containing points, marker symbols, line segments, arrow vectors, indexed or wireframe meshes, and filled or wireframe boxes.
- **Renderer parity**: Retain Plotly as a selectable compatibility renderer and provide common camera, theme, filtering, hover, reset-view, and PNG-export behavior across both rendering paths.
- **Object exploration**: Add searchable reconstruction and truth object filters, optional one-hop match linkage, click inspection with grouped attributes, direct match highlighting, and reversible matched-object isolation.
- **Source handling**: Add distinct Path, local Browse, temporary Upload, and public URL source modes with a native file picker, retryable chunked transfers, bounded session-private caching, and progress reporting.
- **Flexible inputs**: Detect HDF5 data, shared-view JSON, and UTF-8 file manifests by content, including extensionless sources, relative records, comments, globs, and equivalent S3DF host/container paths.
- **Event navigation**: Separate source opening from entry or run/subrun/event navigation and provide previous/next controls plus keyboard shortcuts.
- **Appearance controls**: Add point size and opacity controls, continuous color scales and transforms, automatic or manual color domains, scalar visibility ranges, a live draggable value histogram, axis visibility, and adaptive light/dark themes.
- **Portable views**: Add versioned share links and JSON exports that restore the source, event, display options, attributes, geometry, object filters, renderer, appearance, and camera.
- **Media exports**: Add optional SPINE/detector branding, WebGL rotating GIF export, Plotly standalone HTML export, and renderer-independent PNG output.
- **Detector-aware display**: Add automatic geometry selection and restoration, physical detector up-axis handling, selectable truth point sources, and geometry-aware camera fitting.
- **Application guidance**: Add a searchable keyboard-shortcut reference, contextual loading/error status, a focused authenticated landing page, and task-oriented Read the Docs documentation.
- **Quality gates**: Enforce complete Python statement coverage, strict documentation builds, pre-commit formatting and linting, and Codecov publication in CI.

### Changed
- **Production-ready milestone**: Establish the accelerated renderer, inspection, sharing, deployment, and documentation contracts as the public baseline for the 1.x release series.
- **SPINE integration**: Require SPINE v1.0.1 and consume its typed renderer-neutral scenes, field metadata, detector orientation, geometry, and Plotly compatibility backend.
- **Client-side presentation**: Transport compact binary scenes to the browser and apply camera motion, visibility, recoloring, appearance, hover, and theme updates without rebuilding the event on the server.
- **Caching model**: Reuse file-aware HDF5 readers, built events, downloaded sources, and serialized scenes across compatible presentation updates while enforcing configurable bounds.
- **Camera behavior**: Synchronize split reconstruction/truth views when requested, preserve cameras across presentation updates, reset them for new events or files, and fit projected detector bounds without changing the Plotly-matched viewing angle.
- **Auxiliary rendering**: Match endpoint, direction, and interaction-vertex colors to parent objects and render direction vectors as thick shafts with three-dimensional cone heads.
- **Object visibility**: Replace Plotly legend-driven and per-object trace splitting with explicit searchable object controls while retaining combined point-cloud traces and color scales.
- **Automatic refresh**: Refresh loaded scenes from display controls while applying multi-select changes when their menus close to avoid redundant server work.
- **Production CLI**: Run without the Dash development debugger unless `--debug` is explicitly supplied.
- **Script naming**: Rename the local Docker helper from `docker-run.sh` to `docker_run.sh` to match `check_coverage.sh` and SPINE's script naming convention.

### Fixed
- **S3DF path aliases**: Accept both `/data/...` and `/sdf/data/neutrino/...` paths for the same data source.
- **Complete scene rendering**: Preserve detector geometry, raw points, optical flashes, CRT hits, endpoints, directions, vertices, hover metadata, color domains, and object filters across WebGL and Plotly.
- **State restoration**: Apply shared or imported view state exactly once, load referenced Path or URL sources automatically, and reset entry-specific selections safely when the source changes.
- **Responsive loading**: Prevent duplicate WebGL renders and loading flashes while reporting renderer transitions and long-running source operations consistently.

## [0.4.4] - 2026-07-17
### Added
- Add PyPI release and supported Python version badges to the README

### Changed
- Require SPINE v0.15.1+ and Dash v4.4.0+
- Require Python 3.10+ to match the supported SPINE runtime
- Remove the unused Git installation from the runtime image

## [0.4.3] - 2026-05-13
### Fixed
- Use `attr_names()` to populate valid SPINE hover attributes, including derived quantities such as `RecoParticle.ke`, while excluding `points*` location fields from the attribute dropdown.

## [0.4.2] - 2026-05-11
### Fixed
- Require `spine` v0.12.0+ to avoid file loading issues in v0.11.1
- Update `HDF5Reader` import path for the current `spine.io` package structure

## [0.4.1] - 2026-05-09
### Fixed
- Align login form spacing with the main control panel
- Move authenticated session controls into the header utility cluster

## [0.4.0] - 2026-05-09
### Changed
- Updated `spine` dependency to v0.11.0+ for improved hovertext support
- Updated Dash dependency to v4.1.0+
- Modernized the application layout with a responsive control rail and event display shell
- Updated visual styling to follow the SPINE black, gray, and orange palette
- Added a dark mode toggle
- Propagated dark mode to SPINE drawing
- Configured Plotly PNG export for event displays
- Hide the event display plot until an entry is loaded
- Enable camera synchronization by default in split-scene view

### Fixed
- Keep dropdown menus and virtualized dropdown options in the active dark theme
- Apply dark theme styling to Dash 4 dropdown menus
- Keep entry/run input layout stable when switching input modes
- Replace native number widgets with numeric text inputs to avoid browser rendering artifacts in dark mode

## [0.3.5] - 2026-05-08
### Changed
- Updated `spine` dependency to v0.10.13 exactly

## [0.3.4] - 2026-03-04
### Changed
- Updated `spine` dependency to v0.10.5+ (includes fix for drawing display info for truth-only data)

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
