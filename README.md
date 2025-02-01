# Macropad

This is just an AutoHotKey script for my Megalodon Triple Knob Macropad. It allows me to open programs, run macros, or perform certain Windows functions at the click of a button. 

This is primarily for my own personal use, but I wanted to upload it in case anyone else could expand on it and improve its functionality, regardless of how niche it may be. 

## List of required programs

* [SoundVolumeView](https://www.nirsoft.net/utils/sound_volume_view.html) to control per application sound settings.
* [AutoControl](https://www.autocontrol.app/), which is a Chrome extension that allows for keyboard shortcuts and gestures to trigger actions in the browser.
  * I am unsure of an equivalent for Firefox.
  * The shortcuts that use this extension will also have information on how the action associated with it was configured for AutoControl.

## Note

Currently, the implementation of a layer system for the Megalodon macropad is somewhat flawed, at least for my use case. In the [VIA](https://usevia.app/) online editor, there is a layer switch "signal" (if that's the right term for it) that can be assigned to any button, but it seems to only work on the actual device, as there is no keycode that is associated with that action. 

As a workaround, to reuse the same keys on every layer without it triggering different functions, I have also added a layer switch in the AHK script itself. The button assigned to this function MUST be pressed in conjunction with the macropad layer switch button to allow the same key to perform different functions across layers. 

For example, I can assign F13 open Google Chrome on layer 1 and switch my audio devices on layer 2, as long as I also switch the layer in the AHK script.

Eventually, I plan to program my own software for the macropad using QMK and flash it onto the device, just so that I can have a single button send two distinct signals to switch layers, but until then, this patchwork of a solution should suffice. 


