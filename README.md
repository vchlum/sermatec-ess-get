# sermatec-ess-get tool
This is a tool to get values from a Sermatec ESS inverter and store them in a csv file. It uses the sermatec inverter tool `sermatec-ess` to get the data from the inverter.

## Usage

 * Gets data from sermatec inverter and stores configured values into file: `python sermatec-ess-get.py --config config.json` or `python sermatec-ess-get.py`
 * Shows only the columns names: `python sermatec-ess-get.py --config config.json --header`

### Configuration
Read the documentation to `sermatec-ess` first.

Example cron records are like:
```
*/15 * * * * username /path/to/sermatec-ess-get.py --config /path/to/config.json
50 23 * * * username /path/to/sermatec-ess-get.py --config /path/to/config-daily.json
```

The configuration file is a json file with the following structure:
```
{
    "tool": {"path": "/path/to/sermatec-ess"},
    "device": {"ip": "192.168.1.123"},
    "cmds": {
        "9c": [
            "line regex1 here: ([0-9\\.]+)",
            "line regex2 here: ([0-9\\.]+)"
        ]
    },
    "postprocessing": {
        "Value regex1 + regex2": {"op": "+", "items": ["line regex1 here: ([0-9\\.]+)", "line regex2 here: ([0-9\\.]+)"]}
        # "Value regex1 + regex2" can be used also in postprocessing in subsequent lines.
    },
    "output": {
        "filename": "sermatec.csv",
        "delimiter": ";"
    }
}
```



