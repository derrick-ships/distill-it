# Screen Element Localization (build spec) — distilled from clicky

## Summary
Detect the on-screen pixel of a UI element a user is asking about by sending a screenshot + question to Claude's Computer Use beta and reading back a click coordinate. Input: screenshot `Data`, the user's question string, and the display's size in points. Output: a `CGPoint?` in **display-local AppKit coordinates (bottom-left origin)**, or `nil` if no element / failure. The whole thing is one class, `ElementLocationDetector`, with one public async method.

## Core logic (inlined)

Public entry point — orchestrates resolution choice, resize, API call, then clamp/scale/flip:

```swift
func detectElementLocation(
    screenshotData: Data,
    userQuestion: String,
    displayWidthInPoints: Int,
    displayHeightInPoints: Int
) async -> CGPoint? {
    let res = bestComputerUseResolution(forDisplayWidth: displayWidthInPoints,
                                        displayHeight: displayHeightInPoints)
    guard let resized = resizeScreenshotForComputerUse(
        originalImageData: screenshotData,
        targetWidth: res.width, targetHeight: res.height) else { return nil }

    guard let coord = await callComputerUseAPI(
        resizedScreenshotData: resized, userQuestion: userQuestion,
        declaredDisplayWidth: res.width, declaredDisplayHeight: res.height) else { return nil }

    // Clamp — Claude sometimes returns slightly out-of-range values.
    let clampedX = max(0, min(coord.x, CGFloat(res.width)))
    let clampedY = max(0, min(coord.y, CGFloat(res.height)))
    // Scale Computer-Use-space -> display points.
    let scaledX = (clampedX / CGFloat(res.width))  * CGFloat(displayWidthInPoints)
    let scaledYTopLeft = (clampedY / CGFloat(res.height)) * CGFloat(displayHeightInPoints)
    // Flip Y: Computer Use is top-left origin, AppKit is bottom-left.
    let scaledYBottomLeft = CGFloat(displayHeightInPoints) - scaledYTopLeft
    return CGPoint(x: scaledX, y: scaledYBottomLeft)
}
```

Resolution table + nearest-aspect-ratio picker:

```swift
private static let supportedComputerUseResolutions: [(width: Int, height: Int, aspectRatio: Double)] = [
    (1024, 768,  1024.0 / 768.0),  // 4:3   = 1.333
    (1280, 800,  1280.0 / 800.0),  // 16:10 = 1.600  (default / most Macs)
    (1366, 768,  1366.0 / 768.0)   // ~16:9 = 1.779
]

private func bestComputerUseResolution(forDisplayWidth w: Int, displayHeight h: Int) -> (width: Int, height: Int) {
    let displayAspect = Double(w) / Double(max(1, h))
    var bestW = 1280, bestH = 800
    var smallestDiff = Double.greatestFiniteMagnitude
    for r in Self.supportedComputerUseResolutions {
        let diff = abs(displayAspect - r.aspectRatio)
        if diff < smallestDiff { smallestDiff = diff; bestW = r.width; bestH = r.height }
    }
    return (bestW, bestH)
}
```

Retina-safe resize (THE critical gotcha — do not use `NSImage.lockFocus()`):

```swift
private func resizeScreenshotForComputerUse(originalImageData: Data, targetWidth: Int, targetHeight: Int) -> Data? {
    guard let originalImage = NSImage(data: originalImageData) else { return nil }
    // Exact-pixel bitmap; bypasses NSImage's Retina-aware 2x doubling.
    guard let bitmapRep = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: targetWidth, pixelsHigh: targetHeight,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { return nil }
    bitmapRep.size = NSSize(width: targetWidth, height: targetHeight) // 1:1, no Retina scaling
    NSGraphicsContext.saveGraphicsState()
    let ctx = NSGraphicsContext(bitmapImageRep: bitmapRep)
    NSGraphicsContext.current = ctx
    ctx?.imageInterpolation = .high
    originalImage.draw(in: NSRect(x: 0, y: 0, width: targetWidth, height: targetHeight),
                       from: NSRect(origin: .zero, size: originalImage.size),
                       operation: .copy, fraction: 1.0)
    NSGraphicsContext.restoreGraphicsState()
    return bitmapRep.representation(using: .jpeg, properties: [.compressionFactor: 0.85])
}
```

The API call (note the `computer_20251124` tool type, beta header, and the prompt):

```swift
private func callComputerUseAPI(resizedScreenshotData: Data, userQuestion: String,
                                declaredDisplayWidth: Int, declaredDisplayHeight: Int) async -> CGPoint? {
    var request = URLRequest(url: apiURL)               // https://api.anthropic.com/v1/messages
    request.httpMethod = "POST"
    request.timeoutInterval = 15
    request.setValue(apiKey,                forHTTPHeaderField: "x-api-key")
    request.setValue("2023-06-01",          forHTTPHeaderField: "anthropic-version")
    request.setValue("application/json",    forHTTPHeaderField: "Content-Type")
    request.setValue("computer-use-2025-11-24", forHTTPHeaderField: "anthropic-beta") // activates pixel-counting

    let mediaType = detectImageMediaType(for: resizedScreenshotData)   // sniff PNG magic, else image/jpeg
    let base64 = resizedScreenshotData.base64EncodedString()
    let userPrompt = """
    The user asked this question while looking at their screen: "\(userQuestion)"

    Look at the screenshot. If there is a specific UI element (button, link, menu item, text field, icon, etc.) \
    that the user should interact with or is asking about, click on that element.

    If the question is purely conceptual (e.g., "what does HTML mean?") and there's no specific element to point to, \
    just respond with text saying "no specific element".
    """
    let body: [String: Any] = [
        "model": model,                 // default "claude-sonnet-4-6"
        "max_tokens": 256,
        "tools": [[
            "type": "computer_20251124", "name": "computer",
            "display_width_px": declaredDisplayWidth, "display_height_px": declaredDisplayHeight
        ]],
        "messages": [[ "role": "user", "content": [
            ["type": "image", "source": ["type": "base64", "media_type": mediaType, "data": base64]],
            ["type": "text", "text": userPrompt]
        ]]]
    ]
    // ... JSONSerialization -> session.data(for:) -> guard 200...299 -> parseCoordinateFromResponse(data:)
}
```

Parse the `tool_use` block (text-only reply ⇒ nil = "no element"):

```swift
private func parseCoordinateFromResponse(data: Data) -> CGPoint? {
    guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let contentBlocks = json["content"] as? [[String: Any]] else { return nil }
    for block in contentBlocks {
        guard let t = block["type"] as? String, t == "tool_use",
              let input = block["input"] as? [String: Any],
              let coordinate = input["coordinate"] as? [NSNumber], coordinate.count == 2 else { continue }
        return CGPoint(x: CGFloat(coordinate[0].doubleValue), y: CGFloat(coordinate[1].doubleValue))
    }
    return nil  // Claude returned text -> conceptual question, nothing to point at
}

private func detectImageMediaType(for d: Data) -> String {
    if d.count >= 4, [UInt8](d.prefix(4)) == [0x89,0x50,0x4E,0x47] { return "image/png" }
    return "image/jpeg"
}
```

## Data contracts
- **Input:** `screenshotData: Data` (JPEG/PNG), `userQuestion: String`, `displayWidthInPoints: Int`, `displayHeightInPoints: Int`.
- **Init:** `init(apiKey: String, model: String = "claude-sonnet-4-6")`. URLSession config: `timeoutIntervalForRequest = 15`, `timeoutIntervalForResource = 20`, `waitsForConnectivity = false`, `urlCache = nil`, `httpCookieStorage = nil`.
- **Anthropic request:** POST `https://api.anthropic.com/v1/messages`; headers `x-api-key`, `anthropic-version: 2023-06-01`, `anthropic-beta: computer-use-2025-11-24`; tool `{type:"computer_20251124", name:"computer", display_width_px, display_height_px}`; `max_tokens: 256`.
- **Anthropic response shape consumed:** `content[]` array; find `{"type":"tool_use", "input":{"coordinate":[x,y]}}`. (The `action` field is `"left_click"` but is not read — only `coordinate` matters.)
- **Output:** `CGPoint?` in **display-local points, bottom-left origin**. NOTE: this is display-LOCAL (origin at that display's bottom-left), not global multi-monitor coordinates — converting to global is the caller's job (see CompanionManager in the pointer feature).

## Dependencies & assumptions
- macOS, `AppKit` + `Foundation`. No third-party deps.
- An Anthropic API key with access to the `computer-use-2025-11-24` beta.
- Caller supplies the screenshot and the display's point dimensions (clicky gets these from ScreenCaptureKit).
- Assumes the screenshot covers exactly one display whose dimensions are passed in.

## To port this, you need:
- [ ] An image resize that hits EXACT pixel dimensions on Retina (use `NSBitmapImageRep`, never `lockFocus()`); on other platforms ensure no implicit DPR scaling.
- [ ] The three-row resolution table and the nearest-aspect-ratio picker.
- [ ] The Messages API call with the `computer` tool declared at the chosen resolution + the beta header.
- [ ] A `tool_use`-block parser that treats a text-only reply as "no element" (nil).
- [ ] The post-processing pipeline: clamp → scale to display points → flip Y (top-left → bottom-left).
- [ ] An API key and the beta entitlement.

## Gotchas
- **Retina doubling** is the #1 failure mode: `lockFocus()` on a 2x display yields a 2x bitmap, so the declared `display_*_px` no longer matches the image, and every coordinate is off by ~2x. Exact-pixel `NSBitmapImageRep` fixes it.
- **Aspect-ratio mismatch** stretches the image and degrades X accuracy — match it, don't default to 4:3.
- **Bigger ≠ better:** higher resolutions get API-downsampled and lose precision. Keep declared sizes small.
- **Clamp before scaling** — out-of-range coords map off-screen otherwise.
- **Two transforms, easy to swap:** the scale (pixels→points) and the Y-flip (top-left→bottom-left) are distinct steps.
- Output is **display-local**, not global. Don't feed it straight into a multi-monitor pointer without adding the display's frame origin.
- `media_type` must be sniffed; sending PNG bytes labeled `image/jpeg` (or vice-versa) can fail.

## Origin (reference only)
clicky — `leanring-buddy/ElementLocationDetector.swift` (class `ElementLocationDetector`). Repo: https://github.com/farzaa/clicky (note the misspelled `leanring-buddy` directory). Default model `claude-sonnet-4-6`.
