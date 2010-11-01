#!/usr/bin/python

from urllib2 import urlopen
from urllib import urlencode
import cgi
from .backend import Backend
import json
import cherrypy
import json
import pylru

class Mailbox(Backend):
    """
    The relay backend just acts as a relay for some other backend.  It's purpose is to queue
    outgoing messages
    """

    def register(self, name, controller, config):
        self.name = name
        self.controller = controller
        self.queue = []

        controller.register_backend(name, self)

    def start(self):
        pass

    def send(self, message):
        """ 
        Called when someone wants to send a message off.  We add the message as an outgoing
        message.
        """
        # check to see if this message already exists
        for existing in self.queue:
            if existing.id == message.id:
                return

        # not already there?  append it
        self.queue.append(message)
        return message

    @cherrypy.expose
    def delivered(self, id=None):
        """
        Called when a message is actually delivered.
        """
        if id:
            for i in range(len(self.queue)):
                message = self.queue[i]
                if str(message.id) == str(id):
                    message = self.queue[i]
                    self.queue.remove(message)
                    self.controller.mark_message_delivered(message)
                    return "message marked as delivered"
            raise HTTPError(400, "Unable to find message with id: %s" % id)
        else:
            raise HTTPError(400, "Required format: delivered?id=<message id>")

    @cherrypy.expose
    def outbox(self):
        """
        Grabs all the items in our outgoing queue.  Caller should send them off.
        """
        return json.dumps([message.as_json() for message in self.queue])
        

