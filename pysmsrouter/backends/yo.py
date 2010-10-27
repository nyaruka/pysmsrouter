#!/usr/bin/python

from urllib2 import urlopen
from urllib import urlencode
import cgi
from .backend import Backend
import cherrypy

class Yo(Backend):

    STATUS = 'ybs_autocreate_status'
    ERROR = 'ybs_autocreate_message'

    def register(self, name, controller, config):
        if config.has_option(name, 'endpoint'):
            self.path = config.get(name, 'endpoint')
        else:
            self.path = '/sms/yo/receive'

        self.account = config.get(name, 'account')
        self.authorization = config.get(name, 'authorization')
        self.url = config.get(name, 'url')

        if config.has_option(name, 'backup_url'):
            self.backup_url = config.get(name, 'backup_url')
        else:
            self.backup_url = None

        self.controller = controller

        controller.register_backend(name, self)

    def start(self):
        pass

    @cherrypy.expose
    def receive(self, msisdn=None, dest=None, message=None):
        """
        Called by the Django router when an incoming message is received.
        """
        if msisdn and dest and message:
            self.controller.add_incoming_message(self.name, msisdn, dest, message)
        else:
            raise Exception("Missing arguments")

    def send(self, message):
        """ 
        Sends the passed in message to the router.  First tries the primary URL, and if that fails
        then tries the secondary.

        All errors are propagated via Exceptions.
        """
        self.controller.add_job(YoSendJob(self, message))


class YoSendJob():
    def __init__(self, yo, message):
        self.yo = backend
        self.message = message

        def work(controller):
            params = {
                'ybsacctno': self.yo.account,
                'sysrid': '5',
                'method': 'acsendsms',
                'type': '1',
                'sms_content': self.message.message,
                'destinations': self.message.recipient,
                'ybs_autocreate_authorization': self.yo.authorization,
                'origin': self.message.sender
                }
            
            response = urlopen(YoRouter.URL, urlencode(params), 15)
            
            # if we got a 200 back, read the response
            if response.getcode() == 200:
                body = response.read()
                
                # the response is a url encoded body
                try:
                    resp = dict(cgi.parse_qsl(body))
                except:
                    raise Exception("Unable to parse body: %s" % body)
                
                # grab the status
                if YoRouter.STATUS in resp:
                    status = resp[YoRouter.STATUS]

                    # yay it worked, mark the message as delivered
                    if status == 'OK':
                        controller.mark_message_delivered(self.message)

                    # badness
                    else:
                        error = "Message not delivered."
                        if YoRouter.ERROR in resp:
                            error = resp[YoRouter.ERROR]
                            raise Exception("Error making delivery: %s" % error)
                        
                # no status in the response, assume badness
                else:
                    raise Exception("No delivery status returned")

            # non 200 response, badness
            else:
                raise Exception("Unable deliver message, got status code: %d" % response.getcode())

    
def main():
    class Controller():
        def add_path(self, path, method):
            pass
    controller = Controller()

if __name__ == "__main__":
    main()




