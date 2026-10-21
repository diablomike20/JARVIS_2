# Original Brahma visual core

Donor: https://github.com/diablomike20/Jarvis-Ai
Pinned commit: e0bd3c5a3a258cc1cf35014ae0a35c7b6b9db87f
Original path: assets/web_background/
License: DONOR-LICENSE.txt (upstream terms retained).

The eight JavaScript dependencies are byte-for-byte copies. index.html preserves the original scene, geometry, shaders, palettes and simulation; additions are the sandboxed message bridge, ready/error reporting, pause/reduced-motion handling and Hungarian document title. No remote CDN is needed. The iframe has only allow-scripts, no same-origin or desktop preload access. Both bridge ends validate the sender window. Outgoing messages contain state and amplitude only.

## SHA-256 of unchanged donor dependencies

- `CopyShader.js`: `6b5da4fe3b410286974590885f82fe4a446f25c728f7d6c888e2a2a331333949`
- `EffectComposer.js`: `4fc320fa3185847797332bc2b0125b1a39b9cf5fc4170a2f180cfa54fb057a2b`
- `LuminosityHighPassShader.js`: `00ed0682e61ca207d9c62298269472d6d4eedd9d33528400e7cbc633da8544da`
- `OrbitControls.js`: `02bb4ade710f3e607329e37a21f098bc3ac70eb6e33daf8a65e79f4db785e7b2`
- `RenderPass.js`: `57a549b2d6a947cddf0385a804dc70c3b2d155663d908e99e35d42274b3878be`
- `ShaderPass.js`: `2e64890b8e4c4dafcfd796d5c84877f2ad36a101c83263211c500ec40eaf1240`
- `UnrealBloomPass.js`: `1ed342b273e9b077a3e92e5caeecd45043f03071306c696564d5b53f0562dced`
- `three.min.js`: `9274bbcec8d96168626c732b5d31c775aa8cfb7eaa0599bec0c175908a2c1ce2`
