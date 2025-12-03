# Amplifier Daemon

Two parts:

- [amplifierd/](amplifierd/README.md): FastAPI daemon serving the Amplifier API. Primarily intended to expose amplifier library functionality over HTTP for use by the [Amplifier app](../webapp/README.md) and other clients.
- [amplifier_library/](amplifier_library/README.md): Python library for interacting with the the Amplifier system. Uses [Amplifier Core](https://github.com/microsoft/amplifier-core) under the hood to provide higher-level abstractions for building applications on top of Amplifier Core.
