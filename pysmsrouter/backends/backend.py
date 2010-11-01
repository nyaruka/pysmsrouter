import cherrypy
from cherrypy import HTTPError
import json

class Backend():

    def register(self, name, controller, config):
        self.name = name
        controller.register_backend(name, self)

    def send(self, sender, recipient, message):
        raise Exception("This backend does not support sending messages.")

    @cherrypy.expose
    def receive(self, sender=None, message=None):
        """
        Called when a message is received, we add it as an incoming message.
        """
        if sender and message:
            message = self.controller.add_incoming_message(self.name,
                                                           sender,
                                                           self.name,
                                                           message)
            return json.dumps(message.as_json())
        else:
            raise HTTPError(400, "Required format: receive?sender=<sender>&message=<msg>")

