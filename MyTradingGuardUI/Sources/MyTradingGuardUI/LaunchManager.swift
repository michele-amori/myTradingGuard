import Foundation
import AppKit

/// Handles proxy + TradingView lifecycle on behalf of the app.
@MainActor
final class LaunchManager: ObservableObject {

    enum AppLaunchState {
        case checkingSetup       // reading project_path file
        case notConfigured       // setup_macos.sh was never run
        case startingProxy       // start.sh launched, waiting for ui_state.json
        case running             // proxy active, ui_state.json present
        case error(String)
    }

    @Published var launchState: AppLaunchState = .checkingSetup

    private let projectPathFile = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".mytradingguard/project_path")

    private let uiStateFile = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".mytradingguard/ui_state.json")

    private var pollTimer: Timer?

    // ── Public entry point ───────────────────────────────────────── //

    func start() {
        Task { await checkAndLaunch() }
    }

    // ── Core logic ───────────────────────────────────────────────── //

    private func checkAndLaunch() async {
        launchState = .checkingSetup

        // 1. Read project path written by setup_macos.sh
        guard let projectPath = readProjectPath() else {
            launchState = .notConfigured
            return
        }

        // 2. If ui_state.json is fresh (< 5s old) the proxy is already running
        if isProxyRunning() {
            launchState = .running
            return
        }

        // 3. Proxy not running — launch start.sh in a Terminal window
        launchState = .startingProxy
        launchStartScript(projectPath: projectPath)

        // 4. Poll until ui_state.json appears (proxy is ready)
        startPolling()
    }

    // ── Helpers ──────────────────────────────────────────────────── //

    private func readProjectPath() -> String? {
        guard let data = try? Data(contentsOf: projectPathFile),
              let path = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines),
              !path.isEmpty
        else { return nil }
        return path
    }

    private func isProxyRunning() -> Bool {
        guard FileManager.default.fileExists(atPath: uiStateFile.path) else {
            return false
        }
        // Consider the proxy running if ui_state.json was written in the last 5 seconds
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: uiStateFile.path),
              let modified = attrs[.modificationDate] as? Date
        else { return false }
        return Date().timeIntervalSince(modified) < 5
    }

    private func launchStartScript(projectPath: String) {
        // Open a new Terminal window and run start.sh inside it
        let script = """
        tell application "Terminal"
            activate
            do script "cd \(projectPath) && bash start.sh"
        end tell
        """
        var error: NSDictionary?
        NSAppleScript(source: script)?.executeAndReturnError(&error)
        if let err = error {
            launchState = .error("Could not open Terminal: \(err)")
        }
    }

    private func startPolling() {
        pollTimer?.invalidate()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if self.isProxyRunning() {
                    self.pollTimer?.invalidate()
                    self.launchState = .running
                }
            }
        }
    }
}
