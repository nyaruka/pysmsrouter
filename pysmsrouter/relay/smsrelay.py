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
import signal
import threading
import traceback

def dumpstacks(signal, frame):
    logging.error("Dumping stack")
    id2name = dict([(th.ident, th.name) for th in threading.enumerate()])
    code = []
    for threadId, stack in sys._current_frames().items():
        logging.error("\n# Thread: %s(%d)" % (id2name[threadId], threadId))
        for filename, lineno, name, line in traceback.extract_stack(stack):
            logging.error('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                logging.error("  %s" % (line.strip()))

class Relayer(object):

    def __init__(self, incoming=None, outgoing=None, server=None, backend=None, log=None):
        self.do_run = True

        self.incoming = incoming
        self.outgoing = outgoing
        self.incoming_url = 'http://%s/' % server + 'backends/%s/receive/?'
        if outgoing:
            self.outgoing_url = 'http://%s/' % server + 'backends/%s/outbox/'
            self.delivery_url = 'http://%s/' % server + 'backends/%s/delivered/?'
        else:
            self.outgoing_url = None
            self.delivery_url = None
        self.log = log
        self.backends = (backend,)
        self.ignore_list = set()
        self.sent_list = set()
        signal.signal(signal.SIGQUIT, dumpstacks)

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

                if file in self.ignore_list:
                    continue

                try:
                    self.handle_incoming(message)

                    try:
                        os.unlink(message)
                    except Exception as e:
                        # we couldn't remove the message, tell as much, and add this message to our ignore list
                        logging.error("INCOMING - %s : Unable to unlink file." % file)
                        self.ignore_list.add(file)
                        continue

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

        url = "%s%s" % (self.incoming_url % backend, urlencode(params))
        response = urlopen(url, None, 5)
        response_body = response.read()
        if response.getcode() != 200:
            raise Exception("Error delivering message to router: %s" % response_body)

        # all good, this message was delivered

    def handle_outgoing(self):
        for backend in self.backends:
            # skip over outgoing if we don't have one
            if not self.outgoing_url:
                return

            url = self.outgoing_url % backend

            try:
                response_body = None
                response = urlopen(url, None, 5)
                if response.getcode() == 200:
                    response_body = response.read()

                    # parse it
                    messages = json.loads(response_body)

                    # add each message to our outgoing queue
                    for message in messages:
                        if message['id'] in self.sent_list:
                            continue

                        logging.info("OUTGOING - %s : %s : %s" % (backend, message['recipient'], message['message']))

                        f = NamedTemporaryFile(delete=False, prefix="%s." % backend, dir=self.outgoing)
                        f.write("To: %s\n" % message['recipient'])
                        f.write("Modem: %s\n" % backend)
                        f.write("\n%s" % message['message'])
                        f.close()

                        # mark it as delivered
                        try:
                            params = { 'id': message['id'] }
                            url = self.delivery_url % backend + urlencode(params)
                            r = urlopen(url, None, 5)
                            if r.getcode() != 200:
                                logging.error("OUTGOING - %s : Unable to mark message as delivered, got status: %s" % (message['id'], r.getcode()))
                                self.sent_list.add(message['id'])
                        except Exception as e:
                            self.sent_list.add(message['id'])
                            logging.error("OUTGOING - %s : Unable to mark message as delivered: %s" % (message['id'], str(e)))

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

    if len(opts) < 4:
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

