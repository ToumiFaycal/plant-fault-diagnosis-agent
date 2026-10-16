# References

The sources this project relies on, and what each one was used for.

## Setting up the project

- [venv: creation of virtual environments](https://docs.python.org/3/library/venv.html) (Python documentation). What a virtual environment is, and the note on Windows that explains why PowerShell may refuse to run `Activate.ps1` and which setting allows it.

## The plant data

- [Additional Tennessee Eastman Process Simulation Data for Anomaly Detection Evaluation](https://doi.org/10.7910/DVN/6C3JR1) (Rieth, Amsel, Tran and Cook, 2017, Harvard Dataverse). The recorded plant runs this project works on: normal runs and runs with each of 20 faults. Used to download the four data files and to check the facts we rely on (one sample every 3 minutes, run lengths, when each fault starts).
