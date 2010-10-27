#!/usr/bin/python

from urllib2 import urlopen
from urllib import urlencode
import cgi
from .backend import Backend
import cherrypy
from threading import Lock, Thread
import smpplib
import time
import traceback

class Smpp(Backend):

    def register(self, name, controller, config):
        self.name = name
        self.controller = controller
        self.smpp_name = config.get(name, 'smpp')
        self.number = config.get(name, 'number')
        self.smpp = Client.bind_client(self.smpp_name, config, self.number, self)
        controller.register_backend(name, self)

    def start(self):
        self.smpp.start()

    def receive(self, sender, message):
        """
        Called by the SMPP Client when a new message comes in
        """
        self.controller.add_incoming_message(self.name, sender, self.number, message)

    def send(self, message):
        """ 
        Adds the message as an outgoing message in our client
        """
        message.sender = self.number
        self.smpp.add_outgoing(message)


# global map of smpp clients, shared across various SMPP backends
_smpp_clients = {}
_smpp_lock = Lock()

class Client(object):
    """
    Wraps our smpplib client.  Throwing threading on top and adding a queue for outgoing 
    messages.
    """

    def __init__(self, host, port, username=None, password=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password

        self.lock = Lock()
        self.client = None

        self.backends = {}
        self.messages = []

        self.handled = set()

        self.controller = None

    def add_outgoing(self, message):
        if message.id in self.handled:
            return

        self.messages.append(message)
        self.handled.add(message.id)

    def receive_message(self, pdu):
        recipient = pdu.destination_addr
        sender = pdu.source_addr
        message = pdu.short_message

        # look up if we have a backend for this recipient
        if recipient in self.backends:
            self.backends[recipient].receive(sender, message)
        else:
            print "Unknown recipient for SMPP account: %s" % recipient

    def start(self):
        try:
            # already created?  exit
            if self.client: return

            # otherwise, lock, then create our client
            self.lock.acquire()
            if not self.client:
                self.client = smpplib.client.Client(self.host, self.port)

                # connect
                self.client.connect()

                # and bind as a transceiver
                if self.username:
                    print "binding with username: %s password: %s" % (self.username, self.password)
                    self.client.bind_transceiver(system_id=self.username, password=self.password)
                else:
                    self.client.bind_transceiver()

                # set our message handler
                self.client.set_message_received_handler(self.receive_message)

                # start a thread and start listening on it
                def manage_client():
                    while True:
                        try:
                            print "Listening ...."
                            self.client.listen(False)

                            # send any pending messages
                            while self.messages:
                                message = self.messages[0]

                                print "sending message: %s" % (str(message.id))
                                print "  from: %s" % message.sender
                                print "    to: %s" % message.recipient
                                print "   txt: %s" % message.message

                                self.client.send_message(source_addr_ton=0,
                                                         source_addr_npi=0,
                                                         source_addr=message.sender,
                                                         dest_addr_ton=smpplib.command.SMPP_TON_UNK,
                                                         dest_addr_npi = smpplib.command.SMPP_NPI_ISDN,
                                                         destination_addr=message.recipient,
                                                         short_message=message.message)

                                self.controller.mark_message_delivered(message)
                                self.messages.pop(0)

                        except Exception, e:
                            print "Error interacting with SMPP----"
                            print str(e)
                            traceback.print_exc(e)
                            time.sleep(5)
                            if self.client:
                                self.client.disconnect()
                                self.client = None
                                self.start()
                            break

                thread = Thread(target=manage_client)
                thread.daemon = True
                thread.start()

        finally:
            self.lock.release()

    def bind_backend(self, number, backend):
        self.backends[number] = backend

    @classmethod
    def bind_client(cls, name, config, number, backend):
        global _smpp_clients

        if not name in _smpp_clients:
            _smpp_lock.acquire()
            try:
                if not name in _smpp_clients:
                    host = config.get(name, 'host')
                    port = config.get(name, 'port')

                    username = None
                    password = None

                    # apply our username and password if appropriate
                    if config.has_option(name, 'username'):
                        username = config.get(name, 'username')
                        password = config.get(name, 'password')
                        
                    client = Client(host, port, username, password)
                    client.controller = backend.controller

                    _smpp_clients[name] = client

            finally:
                _smpp_lock.release()

        # grab the client
        client = _smpp_clients[name]

        # add a route to the backend
        client.bind_backend(number, backend)

        return _smpp_clients[name]
        
