import unittest
import ConfigParser
import time
from .dummy import DummyController
from pysmsrouter.backends.backend import Backend

class ControllerTest(unittest.TestCase):

    def test_controller(self):
        controller = DummyController()

        conf = ConfigParser.SafeConfigParser()
        conf.add_section('main')
        conf.set('main', 'threads', '1')
        conf.set('main', 'receive_url', 'receive')
        conf.set('main', 'delivered_url', 'delivered')
        conf.set('main', 'outbox_url', 'outbox')

        # configure our controller
        controller.configure(conf)

        class TestSendJob():
            def __init__(self, backend, message):
                self.backend = backend
                self.message = message

            def work(self, controller):
                self.backend.jobbed.append(self.message)
                controller.mark_message_delivered(self.message)

        # our dummy backend
        class TestBackend(Backend):
            def __init__(self):
                self.sent = []
                self.jobbed = []
                self.controller = None
            
            def register(self, name, controller, config):
                self.name = name
                self.controller = controller
                self.controller.register_backend(name, self)

            def send(self, message):
                # add it to our sent queue, this is for validation by our unit test
                self.sent.append(message)
                self.controller.add_job(TestSendJob(self, message))

        backend = TestBackend()
        backend.register('test', controller, conf)

        # overload our check outbox, we have it always send the same message
        def check_outbox(self):
            for i in range(200):
                self.add_outgoing_message('test',
                                          None,
                                          '250788383383',
                                          'test message',
                                          id='%d' % i)

        # monkey patch our check_outbox
        DummyController.check_outbox = check_outbox

        delivered = []
        def mark_message_delivered(self, message):
            delivered.append(message)

        DummyController.mark_message_delivered = mark_message_delivered

        # start everythign up
        controller.start()

        # sleep a few seconds
        time.sleep(2)

        self.assertEquals(200, len(backend.sent))

        # assert all our messages were sent (in order)
        for i in range(200):
            self.assertEquals(i, int(backend.sent[i].id))

        # wait a bit longer, make sure none of these are duplicated on the next call to check_outbox
        time.sleep(2)
        self.assertEquals(200, len(backend.sent))

        # by now all our messages should have been jobbed as well
        self.assertEquals(200, len(backend.jobbed))

        # check that they are in order
        for i in range(200):
            self.assertEquals(i, int(backend.jobbed[i].id))

        # and that they were all marked as delivered
        self.assertEquals(200, len(delivered))

        for i in range(200):
            self.assertEquals(i, int(delivered[i].id))
