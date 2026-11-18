#Requires AutoHotkey v2.0
#SingleInstance Force

; ============================================================
;  DOIO KB16 macro pad - pairs with the custom firmware
;
;  The pad tells us its layer by tapping Ctrl+Alt+Shift+F13 (layer 1)
;  through Ctrl+Alt+Shift+F20 (layer 8) whenever the layer changes.
;  Tap the left knob = next layer, hold it = back to layer 1 (re-sync).
; ============================================================

global Layer := 1
LayerCount := 8

LayerToast := Toast(10, 10, 100, 100, 25, 1000)
InfoToast  := Toast((A_ScreenWidth - 520) // 2, (A_ScreenHeight - 260) // 2, 520, 260, 16, 2500, "Consolas")

; What each pad button sends (same on every layer). Button 1 = top left,
; numbered left to right, top to bottom.
PadKeys := [
    "+F13", "+F14", "+F15", "+F16",
    "F13",  "F14",  "F15",  "F16",
    "F17",  "F18",  "F19",  "F20",
    "F21",  "F22",  "F23",  "F24"
]

; Actions[layer][button] := [label, function]
; A function of 0 means "label only": the firmware handles that key
; (media, Calc, Delete, nav) and the label just shows in the info window.
; Actions[0] is the fallback for every layer.
Actions := Map()

Actions[0] := Map(
    1, ["Info", ShowButtonInfo]
)

Actions[1] := Map(
    2,  ["Prev", 0],  3, ["Play", 0],  4, ["Next", 0],
    5,  ["Audio",    () => Send("^!{F11}")],     ; SoundSwitch shortcut
    6,  ["Terminal", () => Run("wt.exe")],
    7,  ["Server",   () => Run('wt.exe --profile "Server SSH"')],
    8,  ["Calc", 0],
    9,  ["Cut",      () => Send("^x")],
    10, ["Copy",     () => Send("^c")],
    11, ["Paste",    () => Send("^v")],
    12, ["Del", 0],
    13, ["Home", 0], 14, ["PgUp", 0], 15, ["PgDn", 0], 16, ["End", 0]
)

Actions[2] := Map(
    5, ["Test", () => MsgBox("Test")]
)

; Add layers 3-8 the same way, e.g.
; Actions[3] := Map(5, ["Spotify", () => Run("spotify.exe")])

; ---------- Wiring (no need to edit below for new actions) ----------

for i, key in PadKeys
    Hotkey(key, PadPress.Bind(i))

Loop LayerCount
    Hotkey("^!+F" (12 + A_Index), SetLayer.Bind(A_Index))

PadPress(button, *) {
    act := GetAction(Layer, button)
    if act && act[2]
        act[2]()
}

GetAction(layerNum, button) {
    for l in [layerNum, 0]
        if Actions.Has(l) && Actions[l].Has(button)
            return Actions[l][button]
    return 0
}

SetLayer(n, *) {
    global Layer := n
    LayerToast.Show(n)
}

ShowButtonInfo(*) {
    text := "Layer " Layer "`n`n"
    Loop 16 {
        act := GetAction(Layer, A_Index)
        label := act ? act[1] : "-"
        text .= Format("{:-12}", SubStr(label, 1, 11))
        if Mod(A_Index, 4) = 0
            text .= "`n"
    }
    InfoToast.Show(RTrim(text, "`n"))
}

; ---------- One reusable fading window ----------
; Built once, then re-shown. Pressing again while it's fading resets it
; instead of stacking a new window on top.

class Toast {
    __New(x, y, w, h, fontSize, holdMs, font := "") {
        this.gui := Gui("+AlwaysOnTop -Caption +ToolWindow +E0x20")
        this.gui.BackColor := "Black"
        this.gui.SetFont("s" fontSize " cWhite", font)
        this.gui.MarginX := 10, this.gui.MarginY := 10
        this.text := this.gui.Add("Text", "x10 y10 w" (w - 20) " h" (h - 20) " Center")
        this.pos := "x" x " y" y " w" w " h" h
        this.holdMs := holdMs
        this.opacity := 0
        this.fadeFn := ObjBindMethod(this, "FadeStep")
        this.startFn := ObjBindMethod(this, "StartFade")
    }

    Show(msg) {
        SetTimer(this.fadeFn, 0)                  ; cancel a fade in progress
        this.text.Value := msg
        this.opacity := 255
        this.gui.Show("NoActivate " this.pos)     ; NoActivate: don't steal focus
        WinSetTransparent(255, "ahk_id " this.gui.Hwnd)
        SetTimer(this.startFn, -this.holdMs)      ; re-calling resets the hold timer
    }

    StartFade() => SetTimer(this.fadeFn, 50)

    FadeStep() {
        this.opacity := Max(0, this.opacity - 15)
        WinSetTransparent(this.opacity, "ahk_id " this.gui.Hwnd)
        if this.opacity = 0 {
            SetTimer(this.fadeFn, 0)
            this.gui.Hide()
        }
    }
}

; ---------- Per-app volume (regular keyboard shortcuts) ----------
; Requires SoundVolumeView.

!^=:: AdjustVolume(5)
!^-:: AdjustVolume(-5)

AdjustVolume(step) {
    programPath := "D:\Programs\SoundVolumeView\SoundVolumeView.exe"
    try {
        name := ProcessGetName(WinGetPID("A"))
        Run(programPath " /ChangeVolume " name " " step)
    }
}
