#!/usr/bin/python
import getopt
import ConfigParser
import sys

from pysmsrouter.server import Server

def usage():
    print("smsrouter.py - router process for sms messages.")
    print("Required options:")
    print("\t--config=<path to config file>")

def main(args):
    try:
        opts, args = getopt.getopt(args, (), ('config='))
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)

    if len(opts) != 1:
        usage()
        sys.exit(2)

    # build our map of args
    conf = {}
    for k, v in opts:
        conf[k[2:]] = v

    server = Server()
    server.configure(**conf)
    server.start()

if __name__ == "__main__":
    main(sys.argv[1:])
