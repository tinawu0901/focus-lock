# Focus Lock website allowlists (Chrome / Edge)

The extension talks to a native host on your own computer. It does not edit hosts, proxies, firewall rules, company policy or security software.

## Install

1. Build both EXEs with `build.ps1`, or unzip the complete Windows release folder. Keep the folder in a stable location.
2. From the source checkout run `powershell -File .\install_browser_bridge.ps1 -ReleaseDir dist -Browser Chrome`. From an unzipped release folder run `powershell -File .\install_browser_bridge.ps1 -ReleaseDir . -Browser Chrome`. Use `-Browser Edge` for Edge. This adds only Focus Lock's Native Messaging Host key under the current user's registry; admin rights are not needed.
3. Open `chrome://extensions` or `edge://extensions`, enable developer mode and load the `browser-extension` folder as an unpacked extension. Follow your organization's policy; do not bypass restrictions on extensions.
4. The extension ID should be `koigccfincjhmhemiaeebkapebogngla`. Its popup should report that the local bridge is connected. Extension messages use the browser's UI language (English or Traditional Chinese).
5. Edit a profile and choose Chrome or Edge under Allowed URLs. Choose from currently open tabs, or enter URLs manually. Page/path scope is recommended; whole-site scope is an explicit option. Adding URLs enables restrictions automatically.
6. Start the profile, optionally open tools and URLs from preflight, and wait for work windows plus a connected bridge before starting focus.

Close older Focus Lock instances before opening a new version. Existing compatible host installations can remain in use. Reload the unpacked extension after updating its files; this version's extension update only adds localization, without changing URL rule semantics.

## Scope

- `https://example.com/` allows that exact HTTPS origin and all its paths, not subdomains or HTTP.
- `https://example.com/learn/` allows `/learn` and descendants, not `/learning`.
- If a URL includes a query string, its path and query must match exactly. Add sign-in redirects separately.
- Normal supporting resources may load inside an allowed page. This is top-level navigation control, not full network isolation.
- Existing disallowed pages receive an interaction cover; new navigation is restricted. Forms are not deliberately discarded. Pausing, ending, breaks and emergency unlock release restrictions. If redirected, navigate back yourself.
- Installations, permissions and native connections are specific to browser profiles. Incognito, other profiles, browser-internal pages and embedded browsers are not comprehensively protected. The desktop app cannot prove every browser profile has a working extension.
- The policy uses an approximately eight-second lease and background checks. Browser throttling, sleep and disconnection can delay updates. There is no zero-delay guarantee.
- Open-tab titles and URLs are shared locally with the app only while the user opens the tab picker, up to 100 normal HTTP(S) tabs. No browsing-history API is used and this list is not sent to a cloud service.

## Check and remove

Use a dedicated test profile and disposable tabs. Allow `https://example.com/`, verify another site is covered/restricted, then verify pause, resume, break, end and emergency unlock. Do not test with unsaved work.

To remove: stop focus, remove the extension, then run `powershell -File .\uninstall_browser_bridge.ps1`. The script removes only Focus Lock's own native-host keys; it does not delete other settings.
