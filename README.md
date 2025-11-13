# `adb-tui`: A Simple Python-Based ADB Terminal Interface

`adb-tui` is a lightweight **Terminal User Interface (TUI)** built with Python and the `curses` library. It provides a cleaner way to interact with files on an Android device without typing long ADB commands.

## Getting Started

1. Connect your phone with USB debugging enabled.  
2. Run the script from the directory where you want the pulled files to be saved.

## Current Feature: File Pull (`adb pull`)

The tool currently has only one function: copying files **from your device to your computer**.

- Navigate through your device’s directories and select the files you want.  
- Press `o`, then `c` to start copying.  
- A progress terminal will appear, showing the transfer status.  
- All selected files are saved directly to the directory where you launched the script.

---

## Planned Features

These improvements are planned for future versions:

- [ ] Support for pushing files from the computer to the device.  
- [ ] Ability to copy entire directories.  
- [ ] Option to choose custom destinations on your computer.  
- [ ] A connection screen to manage devices before entering the file manager.

