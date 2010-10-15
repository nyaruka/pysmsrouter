
from datetime import datetime
import uuid
from Queue import Queue
from threading import Thread
from urllib2 import urlopen
from urllib import urlencode
import time
import json

class Message():
    """
    Represents a message in the system.  Incoming and outgoing messages end
    up in the same place.
    """

    def __init__(self, backend=None, sender=None, recipient=None, message=None, 
                 direction=None, sent=None, id=None):
        self.backend = backend
        self.sender = sender
        self.recipient = recipient
        self.message = message
        self.direction = direction
        self.sent = sent
        self.created = datetime.now()

        if not id:
            self.id = str(uuid.uuid1())
        else:
            self.id = id

    def as_json(self):
        return dict(id=self.id,
                    backend=self.backend,
                    sender=self.sender,
                    recipient=self.recipient,
                    message=self.message,
                    direction=self.direction,
                    sent=self.sent,
                    created=self.created.isoformat())

class ReceiveJob():
    def __init__(self, message):
        self.message = message

    def work(self, controller):
        msg = self.message

        params = {
            'backend': msg.backend,
            'sender': msg.sender,
            'message': msg.message
        }

        response = urlopen(controller.receive_url + urlencode(params))

        if response.getcode() == 200:
            print "message: %s sent" % msg.id
        else:
            raise Exception("Unable to send message, got status: %s" % response.getcode())


class DeliveredJob():
    def __init__(self, message):
        self.message = message

    def work(self, controller):
        msg = self.message
        
        params = {
            'backend': msg.backend,
            'message_id': msg.id
        }

        response = urlopen(controller.delivered_url + urlencode(params))

        if response.getcode() == 200:
            print "message delivery sent for: %s " % msg.id
        else:
            raise Exception("Unable to send message delivery, got status: %s" % response.getcode())

class DummyController():
    """
    A very naive implementation of a controller, uses an in memory queue.  Not recommended
    for production use.
    """

    def __init__(self):
        self.jobs = Queue()

    def configure(self, config):
        if config.has_option("main", "threads"):
            self.threads = config.get("main", "threads")
        else:
            self.threads = 1

        self.receive_url = config.get("main", "receive_url")
        self.delivered_url = config.get("main", "delivered_url")

        self.outbox_url = config.get("main", "outbox_url")

        self.backends = {}
        self.config = config

    def add_backend(self, name, backend):
        self.backends[name] = backend
        backend.configure(name, self, self.config)
            
    def start(self):
        """
        Starts the controller.  In our case we spawn all our worker threads.
        """
        # start all our backends
        for backend in self.backends:
            self.backends[backend].start()

        # fire off our workers
        def do_work():
            while True:
                job = self.jobs.get()
                try:
                    job.work(self)
                except Exception, e:
                    print "Error running job: %s" % e
                    time.sleep(1)
                    self.jobs.put(job)

                self.jobs.task_done()


        # checks our outbox over and over for new messages to send out
        def check_outbox():
            while True:
                try:
                    response = urlopen(self.outbox_url)
                    if response.getcode() == 200:
                        content = json.loads(response.read())
                        # for each message in our outbox
                        for message in content['outbox']:
                            # add it to our outgoing queue
                            self.add_outgoing_message(message['backend'],
                                                      None,
                                                      message['contact'],
                                                      message['text'],
                                                      id=message['id'])
                            
                    else:
                        raise Exception("Unable to send message, got status: %s" % response.getcode())
                except Exception, e:
                    print "Error checking outbox: %s" % e

                time.sleep(5)

        for i in range(self.threads):
            thread = Thread(target=do_work)
            thread.daemon = True
            thread.start()

        # start our thread for our outbox
        thread = Thread(target=check_outbox)
        thread.daemon = True
        thread.start()

    def add_incoming_message(self, backend_id, sender, recipient, text):
        message = self.create_message(backend_id, sender, recipient, text, 'IN')
        self.jobs.put(ReceiveJob(message))
        return message

    def add_outgoing_message(self, backend_id, sender, recipient, text, id=None):
        if backend_id not in self.backends:
            raise Exception("Unknown backend '%s'" % backend_id)

        message = self.create_message(backend_id, sender, recipient, text, 'OUT', id)
        self.backends[backend_id].send(message)
        return message

    def mark_message_delivered(self, message):
        self.add_job(DeliveredJob(message))

    def create_message(self, backend_id, sender, recipient, message, direction):
        message = Message(backend=backend_id, 
                          sender=sender, 
                          recipient=recipient, 
                          message=message, 
                          direction=direction, 
                          id=id)
        return message

    def add_job(self, job):
        self.jobs.put(job)
