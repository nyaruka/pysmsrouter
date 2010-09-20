#!/usr/bin/python

import os
import time
import re
from urllib2 import urlopen
from urllib import urlencode
import cgi
import json
from tempfile import NamedTemporaryFile
import logging
import getopt
import sys

class Relayer(object):

    def __init__(self, incoming=None, outgoing=None, server=None, backend=None, log=None):
        self.do_run = True

        self.incoming = incoming
        self.outgoing = outgoing
        self.incoming_url = 'http://%s/' % server + 'sms/%s/receive/'
        self.outgoing_url = 'http://%s/' % server + 'sms/%s/outbox/'
        self.log = log
        self.backends = (backend,)

    def start_logger(self):
        logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                            level=logging.DEBUG,
                            filename=self.log)
        self.logger = logging.getLogger('smsrelay')

    @classmethod
    def get_files(cls, path):
        date_file_pairs = [(os.path.getmtime(os.path.join(path, f)), os.path.join(path, f)) for f in os.listdir(path)]
        date_file_pairs.sort()
        files = [p[1] for p in date_file_pairs]
        return files

    def run(self):
        self.start_logger()
        files = ()

        while self.do_run:
            # get our files, sorted by date (oldest first)
            if not files:
                files = self.get_files(self.incoming)

            # handle our oldest file
            while files:
                message = files.pop()
                file = os.path.basename(message)

                try:
                    self.handle_incoming(message)
                    os.unlink(message)

                    # we break out when we succesfully handle a message
                    break
                except Exception as e:
                    error = getattr(e, 'reason', str(e))
                    logging.error("INCOMING - %s : %s" % (file, error))

            # now do outgoing
            try:
                self.handle_outgoing()
            except Exception as e:
                error = getattr(e, 'reason', str(e))
                logging.error("OUTGOING - %s" % error)

            # no files remaining? sleep a bit
            if not files:
                time.sleep(5)

    def handle_incoming(self, incoming_file):
        file = os.path.basename(incoming_file)

        # open the file
        f = open(incoming_file)
        message = f.read()
        f.close()

        # read our backend
        match = re.search(r'^Modem: (.*?)$', message, re.MULTILINE | re.DOTALL)
        if match:
            backend = match.group(1)
        else:
            raise Exception("Unable to read 'Modem:' from: %s" % message)

        # read who it was from
        match = re.search(r'^From: (.*?)$', message, re.MULTILINE | re.DOTALL)
        if match:
            sender = match.group(1)
        else:
            raise Exception("Unable to read 'From:' from: %s" % message)

        # read the body
        match = re.search(r'^Length: (\d+)\n\n(.*)', message, re.MULTILINE | re.DOTALL)
        if match:
            body = match.group(2)
        else:
            raise Exception("Unable to read SMS body from: %s" % body)

        # make our request to the server
        params = {
            'sender': sender,
            'message': body
        }

        logging.info("INCOMING - %s : %s : %s : %s" % (file, backend, sender, body))

        url = "%s?%s" % (self.incoming_url % backend, urlencode(params))
        response = urlopen(url)
        response_body = response.read()
        if response.getcode() != 200:
            raise Exception("Error delivering message to router: %s" % response_body)

        # all good, this message was delivered

    def handle_outgoing(self):
        for backend in self.backends:
            url = self.outgoing_url % backend

            try:
                response_body = None
                response = urlopen(url)
                if response.getcode() != '200':
                    response_body = response.read()

                    # parse it
                    messages = json.loads(response_body)

                    # add each message to our outgoing queue
                    for message in messages:
                        f = NamedTemporaryFile(delete=False, prefix="%s." % backend, dir=self.outgoing)
                        f.write("To: %s\n" % message['recipient'])
                        f.write("Modem: %s\n" % backend)
                        f.write("\n%s" % message['message'])
                        f.close()

                else:
                    raise Exception("Got error (%d) from router: %s" % (response.getcode(), response_body))
            except Exception as e:
                logging.error("OUTGOING - Unable to reach outbox for %s (%s): %s" % (backend, url, e))

def usage():
    print("sms-relay - relays messages from sms server tools to an sms router via http.")
    print("Required options:")
    print("\t--incoming=<path to smstools incoming>")
    print("\t--outgoing=<path to smstools outgoing>")
    print("\t--server=<server hostname>")
    print("\t--backend=<the backend to relay>")
    print("\t--log=<full path to the log file>")

def main(args):
    try:
        opts, args = getopt.getopt(args, (), ('incoming=', 'outgoing=', 'server=', 'backend=', 'log='))
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)

    if len(opts) != 5:
        usage()
        sys.exit(2)

    # build our map of args
    conf = {}
    for k, v in opts:
        conf[k[2:]] = v

    relayer = Relayer(**conf)
    relayer.run()

if __name__ == "__main__":
    main(sys.argv[1:])

