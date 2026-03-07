// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MyTradingGuardUI",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "MyTradingGuardUI",
            path: "Sources/MyTradingGuardUI"
        )
    ]
)
