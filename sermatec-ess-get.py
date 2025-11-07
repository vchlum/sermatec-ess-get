#!/usr/bin/env python3

import sys
import os
import json
import re
import time
from datetime import datetime

sys.dont_write_bytecode = True
import run

def read_config(filename = 'config.json'):
    try:
        with open(filename, 'r') as file:
            config = json.load(file)
    except Exception as err:
        print(f"Error parsing json file {filename}: {err}")
        return {}
    return config

def append_line(filename, line):
    try:
        with open(filename, 'a') as file:
            file.write(line + '\n')
    except Exception as err:
        print(f"Error writing to file {filename}: {err}")

def get_header(config):
    header = ["timestamp", "day", "time"]

    if "cmds" in config.keys():
        for cmd in config["cmds"].keys():
            for regex in config["cmds"][cmd]:
                header.append(regex.split(":")[0])

    if "postprocessing" in config.keys():
        for pp in config["postprocessing"].keys():
            header.append(pp)

    return header

def get_sermatec_ess(tool, ip, cmd):
    cmd = [tool, '-i', ip, 'get', '--el', cmd]

    env = os.environ.copy()
    env['RUST_BACKTRACE'] = '1' 

    try:
        #res = run.run_with_subprocess(cmd, encoding="utf-8", env=env)
        #res = run.run_with_tty(cmd, encoding="utf-8", env=env)
        res = run.run_in_pty(cmd, encoding="utf-8", env=env)
        if res.returncode != 0:
            print(f"sermatec-ess failed to run command \"{' '.join(cmd)}\" return code {res.returncode}")
            print(f"stdout: {res.stdout}")
            print(f"stderr: {res.stderr}")
        return res.stdout
    except Exception as err:
        print(f"sermatec-ess failed to run command \"{' '.join(cmd)}\" error: {err=}, {type(err)=}")
        return ""

if __name__ == '__main__':
    if ("--config" in sys.argv):
        index = sys.argv.index("--config")
        if index + 1 < len(sys.argv):
            config_file = sys.argv[index + 1]
        else:
            print("Error: --config option requires an argument")
            exit(1)
    else:
        config_file = "config.json"

    config = read_config(config_file)
    
    delimiter = ";"
    filename = ""
    data = {}

    if "output" in config.keys():
        filename = config["output"]["filename"]
        delimiter = config["output"]["delimiter"]
    
    if "--header" in sys.argv:
        header = get_header(config)
        print(delimiter.join(header))
        exit(0)

    ip = ""
    if "device" in config.keys():
        if "ip" in config["device"]:
            ip = config["device"]["ip"]
    if ip == "":
        print("Error: config sermatec IP address first")
        exit(1)

    tool = ""
    if "tool" in config.keys():
        if "path" in config["tool"]:
            tool = config["tool"]["path"]
    if tool == "":
        print("Error: config sermatec IP address first")
        exit(1)

    epoch_time = time.time()
    human_date = datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d')
    human_time = datetime.fromtimestamp(epoch_time).strftime('%H:%M:%S')

    line = [str(int(epoch_time)), human_date, human_time]
    if "cmds" in config.keys():
        for cmd in config["cmds"].keys():
            result = get_sermatec_ess(tool, ip, cmd)
            for regex in config["cmds"][cmd]:
                match = re.search(regex, result)
                if match:
                    value = match.group(1)
                    line.append(value.replace(".", ","))
                    data[regex] = float(value)
                else:
                    line.append("")
                    data[regex] = 0
                    print(F"{regex}: No match found")
    else:
        print("Error: no commands configured")
        exit(1)
        
    if "postprocessing" in config.keys():
        for pp in config["postprocessing"].keys():
            if config["postprocessing"][pp]["op"] == "+":
                value = 0
                for item in config["postprocessing"][pp]["items"]:
                    value += data[item]
                line.append(str(value).replace(".", ","))
                data[pp] = value
            elif config["postprocessing"][pp]["op"] == "-":
                value = data[config["postprocessing"][pp]["items"][0]]
                for item in config["postprocessing"][pp]["items"][1:]:
                    value -= data[item]
                line.append(str(value).replace(".", ","))
                data[pp] = value
            elif config["postprocessing"][pp]["op"] == "*":
                value = data[config["postprocessing"][pp]["items"][0]]
                for item in config["postprocessing"][pp]["items"][1:]:
                    value *= data[item]
                line.append(str(value).replace(".", ","))
                data[pp] = value
            elif config["postprocessing"][pp]["op"] == "/":
                value = data[config["postprocessing"][pp]["items"][0]]
                for item in config["postprocessing"][pp]["items"][1:]:
                    value /= data[item]
                line.append(str(value).replace(".", ","))
                data[pp] = value
            else:
                line.append("")


    if filename != "":
        if not os.path.exists(filename):
            header = get_header(config)
            append_line(filename, delimiter.join(header))
        append_line(filename, delimiter.join(line))
    else:
        print("No file name configured")
