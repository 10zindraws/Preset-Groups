# Changelog
All notable changes to this project will be documented in this file.



## [1.1.2] - 2026-01-06

### Fixed
- The plugin updates your brush name if you renamed it in Brush Editor

### Changed
- Preset Groups docker can be resized to an even smaller width
- Brush Size textbox is smaller as it took extra unnecessary space



## [1.1.0] - 2025-12-30

### Changed
- Increased padding for group names

### Added
- Ability to change group font Size

### Fixed
- Stuttering/lag while drawing, zooming, panning with the plugin active
- Unnecessary CPU usage when the Preset Groups docker is hidden



## [1.0.8] - 2025-12-26

### Changed
- Simplified brush thumbnail refreshing by making a brush's thumbnail update when Brush Editor is closed
- When Exclusive Uncollapse is turned on, automatically collapse groups

### Removed
- Brush thumbnails hashing
- Continuous 2 second interval thumbnail comparison
- Brush thumbnails caching



## [1.0.7] - 2025-12-24

### Changed
- Reworked `thumbnail_manager.py` to use less CPU resources, previous version caused stuttering during painting
- 10 brushes are detected for thumbnail changes every 2 seconds instead of 50 brushes
- 16 x 16 sample points to detect thumbnail changes instead of 32 x 32



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
- When only group exists, automatically set/kept it as the active group so it can't be deselected
