#!/usr/bin/python

from urllib2 import urlopen
from urllib import urlencode
import cgi
from .backend import Backend
from django_sms_router.models import Message

class Mailbox(Backend):
    """
    The relay backend just acts as a relay for some other backend.  It's purpose is to queue
    outgoing messages
    """

    def __init__(self, name, controller, **args):
        self.name = name
        self.controller = controller

    def receive(self, request):
        """
        Called when a message is received, we add it as an incoming message.
        """
        import django.forms as forms

        class IncomingForm(forms.Form):
            sender = forms.CharField(min_length=12, max_length=20, required=True)
            message = forms.CharField(max_length=160, required=True)

        form = IncomingForm(request.GET)

        if form.is_valid():
            self.controller.add_incoming_message(self.name,
                                                 form.cleaned_data['sender'],
                                                 self.name,
                                                 form.cleaned_data['message'])
        else:
            raise Exception(str(form.errors))

    def send(self, sender, recipient, message):
        """ 
        Called when someone wants to send a message off.  We add the message as an outgoing
        message.
        """
        message = self.controller.add_outgoing_message(self.name, sender, recipient, message, True)
        return message

    def get_outbox(self):
        """
        Grabs all the items in our outgoing queue.  Caller should send them off.
        """
        outgoing = []
        message = self.controller.pop_outgoing_message(self.name)
        while not message is None:
            outgoing.append(message)
            message = self.controller.pop_outgoing_message(self.name)

        return outgoing
        

