# Faceclaw 38 main-reset model

These frozen components reproduce the previously observed Faceclaw 38 main-reset-to-frame path. The runner checks every component and the supplied main image by SHA-256. Execution starts at the main firmware vector, not the bootloader, and does not validate physical hardware. The firmware itself is not included.

The `strict.cs` model includes Renode-derived code with its original copyright and MIT license notices. See [third-party notices](../../NOTICE.md) and [the Renode license](../../licenses/renode.txt).
