#SingleInstance Force

global Layer := 1     
global Window := 0    
global FadeTimer := 0  
global ActiveFade := false

; Layer increment
^+F24:: 
{
    global Layer 
    Layer := Mod(Layer, 4) + 1
    CreateWindow(Layer)
}

CreateWindow(val) 
{
    global Window, FadeTimer, ActiveFade
    if !IsObject(Window)  {
        Window := Gui()
        Window.Name := "Layer"
        Window.Opt("+AlwaysOnTop -Caption +ToolWindow +E0x20")  ; Opaque, no title bar
        Window.MarginX := 10
        Window.MarginY := 10
        Window.BackColor := "Black"  
        Window.SetFont("s25 cWhite")  
        Window.Add("Text", "xm-10 ym+15 w100 h50 Center vDisplayText")  
    }

    Window.Show("x10 y10 w100 h100")  
    Window["DisplayText"].Value := val  
    WinSetTransparent(255, Window)
    ActiveFade := false

    if (FadeTimer) {
        SetTimer(FadeTimer, 0)
        FadeTimer := 0
    } 
    else 
        FadeTimer := SetTimer(() => StartFade(), -1000)
}

StartFade()
{
    global Window, ActiveFade
    ActiveFade := true
    Window.opacity := 255
    SetTimer(() => FadeStep(), 50)
}

FadeStep() 
{
    global Window, ActiveFade
    if (!ActiveFade) {
        SetTimer(, 0)
        return
    }
    
    Window.opacity := Max(0, Window.opacity - 15)
    try WinSetTransparent(Window.opacity, Window)
    
    if (Window.opacity <= 0) {
        ActiveFade := false
        Window.Hide()
        SetTimer(, 0)     ; Delete timer at this point
    }
}

F13:: 
{
    global Layer
    switch Layer
    {
        ; Audio switch (The assigned shortcut in Soundswitch is Alt + Ctrl + F11)
        case 1:
            Send("{Alt Down}{Ctrl Down}{F11}{Ctrl Up}{Alt Up}")
        case 2:
            MsgBox "Test"
    }
}    

; Normal terminal
F14:: Run("wt.exe")

; Server access
F15:: Run('wt.exe --profile "Server SSH"')

; Cut 
F17:: Send("{Ctrl Down}{x}{Ctrl Up}")

; Copy 
F18:: Send("{Ctrl Down}{c}{Ctrl Up}")

; Paste 
F19:: Send("{Ctrl Down}{v}{Ctrl Up}")

; Adjust focused application sound. Requires SoundVolumeView 
!^=:: AdjustVolume(5)
!^-:: AdjustVolume(-5)

AdjustVolume(step) 
{
    ; Change path to wherever you placed the SoundVolumeView program 
    programPath := "D:\Programs\SoundVolumeView\SoundVolumeView.exe"

    focusedWindowPID := WinGetPID("A")
    focusedProcessName := ProcessGetName(focusedWindowPID)
    focusedAppVol := programPath " /ChangeVolume " focusedProcessName " " step
    Run(focusedAppVol)
}