#!/usr/bin/python

from urllib2 import urlopen
from urllib import urlencode
import cgi
from .backend import Backend
import cherrypy
import json
import pylru

class Kannel(Backend):

    URL = "http://%s/cgi-bin/sendsms?"
    STUFF_URL  = "http://127.0.0.1:13013/cgi-bin/sendsms?from=8500&username=USERNAME&password=DONTSTEALMYSHIT&text=%(text)s&to=%(recipient)s&smsc=%(backend)s&dlr_url=http%%3A%%2F%%2Ftestuganda.rapidsms.org%%2Frouter%%2Fdelivered%%2F%%3Fmessage_id%%3D%(id)s"

    def register(self, name, controller, config):
        self.host = config.get(name, 'host')
        self.url = Kannel.URL % self.host
        self.name = name

        self.username = config.get(name, 'username')
        self.password = config.get(name, 'password')

        self.controller = controller

        controller.register_backend(name, self)

        self.seen = pylru.lrucache(100)

    def start(self):
        pass

    def send(self, message):
        """ 
        Queues a message to be sent.
        """
        self.seen[message.id] = message
        self.controller.add_job(SendJob(self, message))

    @cherrypy.expose
    def delivered(self, id=None):
        """
        Called when a message is actually delivered.
        """
        if id:
            if id in self.seen:
                message = self.seen[id]
                del self.seen[id]
                self.controller.mark_message_delivered(message)
                return "{ status: 'ok' }"
            else:
                raise HTTPError(400, "Unable to find message with id: %s" % id)
        else:
            raise HTTPError(400, "Required format: delivered?id=<message id>")

class SendJob():
    def __init__(self, backend, message):
        self.backend = backend
        self.message = message

    def work(self, controller):
        params = {
            'username': self.backend.username,
            'password': self.backend.password,
            'text': self.message.message,
            'to': self.message.recipient
            }
        
        response = urlopen(self.backend.url + urlencode(params), timeout=15)
            
        # if we got a 200 back, read the response
        if response.getcode() / 100 == 2:
            controller.mark_message_delivered(self.message)
        # non 200 response, badness
        else:
            raise Exception("Unable deliver message, got status code: %d" % response.getcode())


