import SwiftUI

@main
struct MyTradingGuardApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
        .defaultSize(width: 780, height: 560)
    }
}
