import SwiftUI

@main
struct MyTradingGuardApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) {}   // hide "New Window"
        }
        .defaultSize(width: 780, height: 560)
    }
}
