from dnserver import DNSServer
from time import sleep

server = DNSServer.from_toml('zones.toml', port=53)
server.start()
assert server.is_running

while True:
    sleep(5)