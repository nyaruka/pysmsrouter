
from datetime import datetime
import uuid
from Queue import Queue
from threading import Thread
from urllib2 import urlopen
from urllib import urlencode
import time
import json
import sys
import traceback
from threading import Lock

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
            body = response.read()
            response = json.loads(body)

            # are there responses to send?
            if 'responses' in response:
                for message in response['responses']:
                    # add it to our outgoing queue
                    controller.add_outgoing_message(message['backend'],
                                                    None,
                                                    message['contact'],
                                                    message['text'],
                                                    id=message['id'])

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
            self.threads = int(config.get("main", "threads"))
        else:
            self.threads = 1

        self.receive_url = config.get("main", "receive_url")
        self.delivered_url = config.get("main", "delivered_url")

        self.outbox_url = config.get("main", "outbox_url")

        self.backends = {}
        self.config = config

        # latest messages that have been sent
        self.out = []
        self.out_lock = Lock()

    def register_backend(self, name, backend):
        self.backends[name] = backend

    def get_recent_messages(self):
        return list(self.out)

    def check_outbox(self):
        """
        Checks our outbox URL to see if there are any messages to send.
        """
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
            
    def start(self):
        """
        Starts the controller.  In our case we spawn all our worker threads.
        """
        # start all our backends
        for backend in set(self.backends.values()):
            backend.start()

        # fire off our workers
        def do_work():
            while True:
                job = self.jobs.get()
                try:
                    job.work(self)
                except:
                    print "Error running job: %s" % sys.exc_info()[1]
                    traceback.print_exc()
                    time.sleep(1)
                    self.jobs.put(job)

                self.jobs.task_done()


        for i in range(self.threads):
            thread = Thread(target=do_work)
            thread.daemon = True
            thread.start()

        # closure for our outbox checking in an infinite loop
        def check_outbox_loop():
            while True:
                try:
                    self.check_outbox()
                except Exception, e:
                    print "Error checking outbox: %s" % e

                time.sleep(2)

        # start our thread for our outbox
        thread = Thread(target=check_outbox_loop)
        thread.daemon = True
        thread.start()

    def add_incoming_message(self, backend_id, sender, recipient, text):
        message = self.create_message(backend_id, sender, recipient, text, 'IN')
        self.jobs.put(ReceiveJob(message))
        return message

    def add_outgoing_message(self, backend_id, sender, recipient, text, id=None):
        if backend_id not in self.backends:
            return

        message = self.create_message(backend_id, sender, recipient, text, 'OUT', id)

        # if we have an id, see if we've already seen this message
        if id:
            try:
                self.out_lock.acquire()

                # check to see if we've already seen this item
                for out in self.out:
                    if str(out.id) == str(message.id):
                        return

                # if not, add it to our locked queue
                self.out.append(message)

                # keep it to 10,000 items or less
                if len(self.out) > 10000:
                    self.out.pop(0)

            finally:
                self.out_lock.release()

        self.backends[backend_id].send(message)
        return message

    def mark_message_delivered(self, message):
        self.add_job(DeliveredJob(message))

    def create_message(self, backend_id, sender, recipient, message, direction, id=None):
        message = Message(backend=backend_id, 
                          sender=sender, 
                          recipient=recipient, 
                          message=message, 
                          direction=direction, 
                          id=id)
        return message

    def add_job(self, job):
        self.jobs.put(job)
