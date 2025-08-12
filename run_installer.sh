#!/bin/bash

echo ""
echo "========================================"
echo "   Overcast Agent Installer"
echo "========================================"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for Python
PYTHON_CMD=""
if command_exists python3; then
    PYTHON_CMD="python3"
elif command_exists python; then
    # Check if it's Python 3
    if python -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python 3.9 or higher is not installed or not in PATH!"
    echo ""
    echo "Please install Python 3.9+ from:"
    echo "- Ubuntu/Debian: sudo apt install python3 python3-pip python3-tk"
    echo "- macOS: brew install python-tk (or download from python.org)"
    echo "- Fedora/RHEL: sudo dnf install python3 python3-pip python3-tkinter"
    echo ""
    read -p "Press Enter to exit..." 
    exit 1
fi

echo "Found Python: $($PYTHON_CMD --version)"
echo ""

# Check if we're in the correct directory
if [ ! -f "overcast_installer.py" ]; then
    echo "ERROR: overcast_installer.py not found!"
    echo ""
    echo "Please make sure you're running this script from the"
    echo "overcast-installer directory."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if template file exists
if [ ! -f "overcast_agent_template.py" ]; then
    echo "ERROR: overcast_agent_template.py not found!"
    echo ""
    echo "The installer template file is missing. Please re-download"
    echo "the complete installer package."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check for tkinter
if ! $PYTHON_CMD -c "import tkinter" 2>/dev/null; then
    echo "ERROR: tkinter is not available!"
    echo ""
    echo "Please install tkinter:"
    echo "- Ubuntu/Debian: sudo apt install python3-tk"
    echo "- macOS: Usually included with Python"
    echo "- Fedora/RHEL: sudo dnf install python3-tkinter"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Starting Overcast GUI Installer..."
echo ""
echo "TIP: The installer window should open shortly."
echo "     If it doesn't appear, check your desktop!"
echo ""

# Launch the Python installer
$PYTHON_CMD overcast_installer.py

# Check if the installer ran successfully
if [ $? -eq 0 ]; then
    echo ""
    echo "Installer completed successfully!"
    echo ""
else
    echo ""
    echo "ERROR: The installer encountered an error."
    echo ""
    echo "Common solutions:"
    echo "- Make sure you have Python 3.9 or higher"
    echo "- Install tkinter if missing"
    echo "- Check file permissions"
    echo ""
fi

echo ""
echo "Press Enter to close this window..."
read 