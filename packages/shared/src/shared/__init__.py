# START_MODULE_CONTRACT
#   PURPOSE: Top-level marker for the `shared` package; exposes only the package version.
#   SCOPE:   Package init for shared domain types — keeps the package import-safe and
#            advertises the semver string used by deployment tooling.
#   DEPENDS: stdlib only.
#   LINKS:   docs/development-plan.xml M-SHARED.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   __version__ - semver string for the shared package (currently "0.1.0")
# END_MODULE_MAP

__version__ = "0.1.0"
