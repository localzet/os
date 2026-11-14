# Profile implementation: selection and source boundaries

The approved product matrix is now machine-readable in config/profiles.json.
The read-only planner selects required and optional applications and a single
Chrome/Edge choice, retains mandatory Telegram and ONLYOFFICE for Standard and
Complete, and keeps Ubuntu package candidates separate from external and
Localzet-specific components. No installation, network calls or privileges
are used by the planner. The existing ISO remains unchanged.

CI checks package candidates and dependency resolution against Ubuntu 26.04's
signed archive, without installation. A passing simulation is not a license,
runtime or redistribution review. Every entry remains pending until actual
installation, launch, licensing, updates and profile tests pass.

External links are official-source references, not executable download URLs.
ONLYOFFICE and proprietary apps must be separately reviewed and verified.
Gaming, Containers, Windows Runtime and UserNet still require their integration
gates. Discord stays optional and proxy-only readiness is not claimed.
Next: verified source-specific provisioning, installer selection UI, package
size/license display, explicit consent and actual installed-profile QA.
