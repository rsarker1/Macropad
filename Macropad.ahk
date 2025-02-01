#SingleInstance Force

global Layer := 1     
global Window := 0    
global FadeTimer  

; Layer increment
^+F24:: 
{
    global Layer 
    if (Layer == 4) 
        Layer := 1
    else
        Layer++
    CreateWindow(Layer)
}

CreateWindow(val) {
    global Window
    if !IsObject(Window)  
    {
        Window := Gui()
        Window.Name := "Layer"
        Window.Opt("+AlwaysOnTop -Caption +ToolWindow +E0x20")  ; Opaque, no title bar
        Window.MarginX := 10
        Window.MarginY := 10
        Window.BackColor := "Black"  
        Window.SetFont("s25 cWhite")  
        Window.Add("Text", "xm-10 ym+15 w100 h50 Center vDisplayText")  
    }

    Window["DisplayText"].Value := val  
    Window.Show("x10 y10 w100 h100")  

    Window.Opt("+LastFound")  
    WinSetTransparent(255)

    global FadeTimer
    FadeTimer := SetTimer(FadeWindow, -1000)  ; Start the fade
}

FadeWindow()
{
    Opacity := 255
    while Opacity >= 0  
    {
        global Window
        WinSetTransparent(Opacity, Window)  
        Sleep(50)  
        Opacity -= 15  
    }
    global Window
    Window.Hide()  
}


Numpad1:: Send("{Alt Down}{Ctrl Down}{F11}{Ctrl Up}{Alt Up}")
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
Numpad4:: Run("wt.exe")
F14:: Run("wt.exe")

; Server access
Numpad5:: Run('wt.exe --profile "Server SSH"')
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

AdjustVolume(step) {
    focusedWindowPID := WinGetPID("A")
    focusedProcessName := ProcessGetName(focusedWindowPID)

    focusedAppVolumeCommand := "D:\Programs\SoundVolumeView\SoundVolumeView.exe /ChangeVolume " focusedProcessName " " step
    Run(focusedAppVolumeCommand)
}