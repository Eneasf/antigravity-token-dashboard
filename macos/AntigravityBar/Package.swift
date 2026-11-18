// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AntigravityBar",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "AntigravityBar", targets: ["AntigravityBar"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "AntigravityBar",
            dependencies: [],
            path: "Sources/AntigravityBar"
        ),
        .testTarget(
            name: "AntigravityBarTests",
            dependencies: ["AntigravityBar"],
            path: "Tests/AntigravityBarTests"
        )
    ]
)
