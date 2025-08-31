from agent_defender import AgentDefender
import traceback
import subprocess, sys

from base import AgentDefenderError


def curl_zhihu():
    try:
        result = subprocess.check_output('curl http://zhihu.com', shell = True, executable = "/bin/bash", stderr = subprocess.STDOUT)
    except subprocess.CalledProcessError as cpe:
        result = cpe.output
    finally:
        for line in result.splitlines():
            print(line.decode())

def bash_ls_tmp():
    try:
        result = subprocess.check_output('ls /tmp', shell = True, executable = "/bin/bash", stderr = subprocess.STDOUT)
    except subprocess.CalledProcessError as cpe:
        result = cpe.output
    finally:
        for line in result.splitlines():
            print(line.decode())

def normal():
    curl_zhihu()

def with_monitor():
    try:
        defender = AgentDefender()
    except AgentDefenderError as e:
        print(e)
        print(traceback.format_exc())
        exit(1)

    defender.start_tracing()
    curl_zhihu()
    defender.stop_tracing()
    record = defender.get_last_tracing_record()
    print(record)

    defender.start_tracing()
    bash_ls_tmp()
    defender.stop_tracing()
    record = defender.get_last_trace_record()
    print(record)

    defender.close()


def main():
    with_monitor()

if __name__ == '__main__':
    main()