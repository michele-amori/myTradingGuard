import AppKit
import Foundation

// Draw a dark background + yellow bolt icon at 1024x1024
let size = CGSize(width: 1024, height: 1024)

let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: Int(size.width),
    pixelsHigh: Int(size.height),
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .calibratedRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
)!

NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

// Dark navy background
NSColor(calibratedRed: 0.06, green: 0.07, blue: 0.16, alpha: 1).setFill()
NSRect(origin: .zero, size: size).fill()

// Rounded rect clip
let path = NSBezierPath(roundedRect: NSRect(origin: .zero, size: size),
                        xRadius: 200, yRadius: 200)
path.setClip()
NSColor(calibratedRed: 0.06, green: 0.07, blue: 0.16, alpha: 1).setFill()
NSRect(origin: .zero, size: size).fill()

// Yellow bolt glyph via SF Symbols
let cfg = NSImage.SymbolConfiguration(pointSize: 620, weight: .bold)
if let bolt = NSImage(systemSymbolName: "bolt.fill", accessibilityDescription: nil)?
    .withSymbolConfiguration(cfg) {
    let bs = bolt.size
    let bx = (size.width  - bs.width)  / 2
    let by = (size.height - bs.height) / 2
    NSColor(calibratedRed: 1.0, green: 0.84, blue: 0.0, alpha: 1).set()
    bolt.draw(in: NSRect(x: bx, y: by, width: bs.width, height: bs.height),
              from: .zero, operation: .sourceOver, fraction: 1.0)
}

NSGraphicsContext.current = nil

let img = NSImage(size: size)
img.addRepresentation(rep)
if let tiff = img.tiffRepresentation,
   let bmp  = NSBitmapImageRep(data: tiff),
   let png  = bmp.representation(using: .png, properties: [:]) {
    let url = URL(fileURLWithPath: "/tmp/mtg_icon_1024.png")
    try! png.write(to: url)
    print("ok")
} else {
    print("fail")
}
