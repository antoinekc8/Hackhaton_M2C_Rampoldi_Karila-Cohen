# Hackhaton_M2C_Rampoldi_Karila-Cohen

Environment Setup
You must use Python 3.11. Using other versions will cause the pre-compiled checker to fail.

Installing Python 3.11
Windows: Download the "Windows installer (64-bit)" from Python.org. Important: Check the box "Add Python.exe to PATH" during installation.

Linux (Ubuntu/Debian):

Bash
sudo apt update
sudo apt install python3.11
macOS: Use brew install python@3.11 or download the installer from Python.org.

Installing Libraries
Open your terminal/command prompt in the project folder and run:

Bash
pip install pandas requests flask
Setting up the checker
The core logic of the hackathon is protected in a compiled file. You must "activate" the one that matches your Operating System.

Navigate to the checkers/ folder.

Windows Users: Find the file for Windows, rename it to checker.pyd, and move it to the main folder (where executable.py is).

Linux Users: Find the file for Linux, rename it to checker.so, and move it to the main folder.

macOS Users: The checker.so already provided in the main folder is the right one.

NOTE: If you cannot see any extensions, just name the file “checker”.

Running the code
The only file you should interact with for submission is executable.py.

Team Name: Open executable.py and change the TEAM_NAME variable to your chosen name.

Rule: Use the exact same name for every submission.

Rule: Ensure your name is unique (e.g., Team_Loosers_ENTPE).

Do Not Modify: Do not change any other logic in executable.py. It is responsible for reading your solutions and syncing your progress to the cloud leaderboard.

Understanding data formats
The system expects a specific structure to read your instances and validate your solutions.

Instance Files (instances/ folder)
There is an example that shows you how an instance should be written:

General information: number_of_request number_timesteps number_zones

Clients information: index_of_client zone_pickup zone_drop_off ...

Distance matrices: Each matrix is a matrix of nb_zones * nb_zones for a time-step.

Solution files (solutions/ folder)
An example is provided:

Index of vehicle

Sequence of visits (iP means pickup for client i, iD means dropoff for client i)

Departure times from each zone.

The Live Leaderboard
Every time you run executable.py, your best results are sent to: https://faycaltouzout.pythonanywhere.com/

Keep an eye on the board to see how you rank against other teams!

Some tips:
Check your paths: Ensure the instances/ and solutions/ folders are in the same directory as your script.

Valid Routes: If your solution is physically impossible (e.g., a vehicle exceeds its capacity), the checker will reject it, and it won't appear on the leaderboard.

Frequency: Don't spam the server; run the executable.py only when you have improved your solution!