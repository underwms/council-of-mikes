# Council structure

Active shared definitions live in skills/, instructions/, rules/, profiles/, adapters/, exclusions/, and scripts/. The active Python engine is council/. setup-council.ps1 deploys profile assets and optionally provisions runtime/; NativeOnly deploys clients without the engine. council.ps1 launches the installed engine. memory/, backups/, work/, runtime/, and legacy/ are private or historical and excluded from the developer artifact. Regression tests live in scripts/tests and are included in the artifact. Its docs/structure.md records the exact distributable inventory.
