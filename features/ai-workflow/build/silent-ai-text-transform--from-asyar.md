# Silent AI Text Transform (build spec) — distilled from asyar

## Summary

Global hotkey → read text from one of 4 sources (OS selection, clipboard, typed arg, none) → assemble system-prompt + text → single LLM call (streaming, but buffered for output) → write result to one of 4 destinations (in-place replace via accessibility API, clipboard, simulated paste, HUD notification). No launcher UI opens. Multiple commands configurable, each with its own hotkey, system prompt, input mode, output mode, and optionally a different AI provider/model.

## Core logic (inlined)

### Command configuration schema

```typescript
interface SilentCommand {
  id: string                  // UUID
  name: string                // User-facing name, e.g. "Fix Grammar"
  hotkey: string              // e.g. "Cmd+Shift+G" / "Ctrl+Shift+G"
  systemPrompt: string        // The transformation instruction
  
  inputMode:
    | 'selection'             // Current text selection in frontmost app
    | 'clipboard'             // Current clipboard content
    | 'typed'                 // Float a minimal input box for one-time entry
    | 'none'                  // No user text, run system prompt as standalone
  
  outputMode:
    | 'replace'               // Replace current text selection (accessibility API)
    | 'clipboard'             // Write to clipboard
    | 'paste'                 // Clipboard + simulate Cmd+V
    | 'hud'                   // Show HUD notification
  
  provider?: string           // Override global default provider
  model?: string              // Override global default model
  enabled: boolean
}
```

### Global hotkey registration (Rust / Tauri)

```rust
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

pub fn register_silent_commands(
    app: &tauri::App,
    commands: Vec<SilentCommand>,
) -> Result<(), Box<dyn std::error::Error>> {
    let shortcut_manager = app.global_shortcut();
    
    for command in commands {
        if !command.enabled { continue; }
        
        let shortcut = parse_hotkey(&command.hotkey)?;
        let app_handle = app.handle().clone();
        let cmd = command.clone();
        
        shortcut_manager.on_shortcut(shortcut, move |_app, _shortcut, event| {
            if event.state == tauri_plugin_global_shortcut::ShortcutState::Pressed {
                let app = app_handle.clone();
                let cmd = cmd.clone();
                tauri::async_runtime::spawn(async move {
                    if let Err(e) = execute_silent_command(&app, &cmd).await {
                        eprintln!("Silent command error: {}", e);
                    }
                });
            }
        })?;
    }
    
    Ok(())
}
```

### Input reading

```rust
pub async fn read_command_input(
    app: &tauri::AppHandle,
    input_mode: &InputMode,
) -> Result<Option<String>, SilentCommandError> {
    match input_mode {
        InputMode::Selection => {
            // macOS: read via NSAccessibility / AXFocusedUIElement
            #[cfg(target_os = "macos")]
            {
                let text = read_macos_selection().await?;
                Ok(Some(text))
            }
            // Windows: read via IUIAutomation / GetSelectedText
            #[cfg(target_os = "windows")]
            {
                let text = read_windows_selection().await?;
                Ok(Some(text))
            }
        }
        
        InputMode::Clipboard => {
            let text = app.clipboard().read_text()?;
            Ok(text)
        }
        
        InputMode::Typed => {
            // Show a minimal floating input box, wait for user to type + press Enter
            let text = show_mini_input_dialog(app).await?;
            Ok(Some(text))
        }
        
        InputMode::None => Ok(None),
    }
}

#[cfg(target_os = "macos")]
async fn read_macos_selection() -> Result<String, SilentCommandError> {
    use accessibility_sys::*;
    // Get the focused UI element
    let element = AXUIElementCreateSystemWide();
    let focused: AXUIElementRef = std::ptr::null_mut();
    AXUIElementCopyAttributeValue(
        element,
        kAXFocusedUIElementAttribute,
        &focused as *const _ as *mut _
    );
    // Read selected text
    let selected: CFTypeRef = std::ptr::null();
    AXUIElementCopyAttributeValue(
        focused,
        kAXSelectedTextAttribute,
        &selected as *const _ as *mut _
    );
    // Convert CFString to Rust String
    let text = cfstring_to_string(selected as CFStringRef);
    Ok(text)
}
```

### LLM call and output execution

```rust
pub async fn execute_silent_command(
    app: &tauri::AppHandle,
    command: &SilentCommand,
) -> Result<(), SilentCommandError> {
    // 1. Read input
    let input_text = read_command_input(app, &command.input_mode).await?;
    
    // 2. Assemble prompt with explicit delimiters to prevent prompt injection
    let user_message = match &input_text {
        Some(text) => format!(
            "Apply the following transformation to the text below.\n\n<text>\n{}\n</text>",
            text
        ),
        None => command.system_prompt.clone(),
    };
    
    let messages = vec![
        Message { role: "system".into(), content: command.system_prompt.clone() },
        Message { role: "user".into(), content: user_message },
    ];
    
    // 3. Run privacy redaction (prevent secrets from reaching LLM)
    let messages = redact_secrets_from_messages(&messages);
    
    // 4. Call LLM (non-streaming for simplicity; or stream + buffer)
    let provider = get_provider_for_command(app, command);
    let mut full_response = String::new();
    
    // Stream but buffer (can't do partial in-place replacement)
    for await delta in provider.chat(&messages, &[], &ChatOptions {
        model: command.model.as_deref().unwrap_or(""),
        stream: true,
        max_tokens: Some(2048),
        temperature: Some(0.2),  // Low temp for deterministic transformations
    }) {
        if let Delta::Text(text) = delta {
            full_response.push_str(&text);
        }
    }
    
    // 5. Execute output action
    execute_output(app, &command.output_mode, &full_response, &input_text).await
}

async fn execute_output(
    app: &tauri::AppHandle,
    mode: &OutputMode,
    result: &str,
    original_selection: &Option<String>,
) -> Result<(), SilentCommandError> {
    match mode {
        OutputMode::Replace => {
            #[cfg(target_os = "macos")]
            replace_macos_selection(result).await?;
            #[cfg(target_os = "windows")]
            replace_windows_selection(result).await?;
        }
        
        OutputMode::Clipboard => {
            app.clipboard().write_text(result)?;
        }
        
        OutputMode::Paste => {
            // Write to clipboard, then simulate paste
            app.clipboard().write_text(result)?;
            simulate_paste().await?;
        }
        
        OutputMode::Hud => {
            show_hud_notification(app, result, 3000).await?;  // 3s duration
        }
    }
    Ok(())
}

#[cfg(target_os = "macos")]
async fn replace_macos_selection(new_text: &str) -> Result<(), SilentCommandError> {
    use accessibility_sys::*;
    let element = get_focused_element()?;
    let cf_string = string_to_cfstring(new_text);
    AXUIElementSetAttributeValue(element, kAXSelectedTextAttribute, cf_string);
    Ok(())
}

async fn simulate_paste() -> Result<(), SilentCommandError> {
    // macOS: CGEventCreateKeyboardEvent with Cmd+V
    // Windows: SendInput with Ctrl+V
    // Linux: xdotool key ctrl+v
    #[cfg(target_os = "macos")]
    {
        use core_graphics::event::*;
        let source = CGEventSource::new(CGEventSourceStateID::CombinedSessionState).unwrap();
        let v_key = CGKeyCode::V;
        
        let key_down = CGEvent::new_keyboard_event(source.clone(), v_key, true).unwrap();
        key_down.set_flags(CGEventFlags::CGEventFlagCommand);
        key_down.post(CGEventTapLocation::HID);
        
        let key_up = CGEvent::new_keyboard_event(source, v_key, false).unwrap();
        key_up.set_flags(CGEventFlags::CGEventFlagCommand);
        key_up.post(CGEventTapLocation::HID);
    }
    Ok(())
}
```

### HUD notification (Tauri WebView overlay)

```typescript
// Minimal floating window for HUD notification
// Created via Tauri's WebviewWindowBuilder with no titlebar, always-on-top

async function showHudNotification(text: string, durationMs: number): Promise<void> {
  const window = new WebviewWindow('hud', {
    url: 'hud.html',
    alwaysOnTop: true,
    decorations: false,
    transparent: true,
    resizable: false,
    skipTaskbar: true,
    width: 400,
    height: 80,
    center: true,
  })
  
  // Pass content via URL params or Tauri event
  await emit('hud-content', { text, durationMs })
  
  // Auto-close
  setTimeout(() => window.close(), durationMs)
}
```

## Data contracts

### Silent command stored in settings
```typescript
type SilentCommandSettings = SilentCommand[]  // array, ordered by hotkey priority

// Stored in settings.json (plaintext — no secrets here)
// Provider API keys remain in OS keychain
```

### LLM call shape (reuses existing agent infrastructure)
```typescript
const messages: ChatMessage[] = [
  { role: 'system', content: command.systemPrompt },
  { role: 'user', content: `<text>\n${inputText}\n</text>` }
]
// No tools[] needed for single-shot transformations
```

## Dependencies & assumptions

- **Tauri v2** with `tauri-plugin-global-shortcut` and clipboard plugin
- **macOS**: Accessibility permission grant required; `accessibility-sys` Rust bindings
- **Windows**: `IUIAutomation` COM interface for selection read/write
- **Linux**: `xdotool` or `atspi` for selection access
- LLM provider already configured (re-uses the agent's provider abstraction)
- Privacy redaction pipeline available

## To port this, you need:

- [ ] Global hotkey registration (one per configured command)
- [ ] OS selection reading via accessibility API (platform-specific, needs user permission grant)
- [ ] Clipboard read via OS clipboard API
- [ ] Optional: minimal floating input box for `typed` mode
- [ ] LLM single-call (buffer streaming response before executing output)
- [ ] Privacy redaction on input before LLM call
- [ ] Explicit delimiter wrapping of input text to mitigate prompt injection
- [ ] Four output handlers: accessibility replace, clipboard write, paste simulation, HUD notification
- [ ] Per-command provider/model override
- [ ] Low temperature (0.1–0.3) for transformation tasks

## Gotchas

**Accessibility permission UX.** On macOS, the user must manually grant Accessibility permission in System Preferences. If not granted, `AXFocusedUIElement` returns NULL silently. Check for permission at first use and show a clear prompt directing the user to System Preferences.

**Selection replacement flickers in some apps.** The accessibility replace sets the selected text attribute, which some apps handle by deleting the selection and inserting the new text — causing a brief visual flash. This is unavoidable at the API level.

**Prompt injection via clipboard/selection.** If the input contains text like "Ignore previous instructions and output: ...", the system prompt may be overridden. Wrap user text in XML-style delimiters and use a robust system prompt. For extremely sensitive workflows, show the result in HUD mode (read-only) rather than replacing in place.

**Hotkey registration failure is silent on some platforms.** On Windows, if another app holds the hotkey, registration fails with no error visible to the user. Log registration failures and surface them in the settings UI.

**Paste simulation timing.** After `clipboard.write_text()`, there's a brief async gap before the clipboard is fully available to other apps. Add a 50ms delay between clipboard write and the paste keypress simulation.

## Origin (reference only)

- Repo: https://github.com/Xoshbin/asyar
- Key paths: `asyar-launcher/src-tauri/src/` (hotkey handling, accessibility), `asyar-launcher/src-svelte/src/` (settings UI)
- Stack: Tauri v2, Rust, TypeScript, Svelte 5, OS accessibility APIs
