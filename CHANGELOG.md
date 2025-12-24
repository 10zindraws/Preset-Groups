# Changelog
All notable changes to this project will be documented in this file.

## [1.0.6] - 2025-12-24

### Changed
- Made spinbox for Max Brush Size thinner

### Added
- Option to change font size for displayed brush names

## [1.0.5] - 2025-12-23

### Changed
- Reuse widgets for grid buttons instead of delete/recreate
- Longer polling intervals to reduce CPU usage

### Added
- Thumbnail caching system with chunked processing
- MD5-based thumbnail hash detection
- Recognizes separate brush presets being used for eraser and brush

## [1.0.4] - 2025-12-23

### Changed
- Lowered `setMinimumWidth` in `preset_groups.py` to let users make the docker even smaller for compact setups

## [1.0.3] - 2025-12-22

### Changed
- "Add Brush" icon uniformity. The icon was previously an outlined square and a + symbol which could be offset on different Krita setups
- Clarification on what "Add Brush" does in the settings dialog

## [1.0.2] - 2025-12-22

### Added
- Option for exclusive uncollapse mode: only one group can be uncollapsed, uncollapsing a group selects it

## [1.0.1] - 2025-12-22

### Added
- This CHANGELOG file

### Changed
- When only group exists, automatically set/kept it as the active group so it can't be deselected.
