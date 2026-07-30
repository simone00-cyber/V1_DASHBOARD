# v12.2 — Performance & Loading Experience

- Fixed full-screen loading overlay for page and workspace transitions.
- Asset Workspace renders only the active module; inactive modules are not executed.
- Technical Analysis internal sections are lazy-rendered instead of all running inside eager tabs.
- Yahoo header downloads cached for 60 seconds.
- Complete Security Report calculations cached for one hour.
- Lazy page imports reduce initial startup work.
- Workspace ticker submission uses a form to avoid unnecessary reruns while typing.
