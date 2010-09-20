import cherrypy
from cherrypy import HTTPError
import ConfigParser
import json

class Server:

    def configure(self, config=None):
        """
        Configures our server.
        """
        conf = ConfigParser.SafeConfigParser()
        conf.read(config)

        # build our controller
        controller_type = conf.get("main", "controller")
        self.controller = get_class(controller_type)()
        self.controller.configure(conf)

        # read in our backends
        backend_names = conf.get("main", "backends").split(",")
        for backend_name in backend_names:
            backend_type = conf.get(backend_name, "type")
            backend = get_class(backend_type)()

            self.controller.add_backend(backend_name, backend)

        # add our 'backends' controller
        self.backends = Backends(self.controller.backends)

    def start(self):
        # start our controller
        self.controller.start()

        # and start cherry py
        cherrypy.quickstart(self)

    @cherrypy.expose
    def send(self, id=None, backend=None, sender=None, recipient=None, message=None):
        if backend and recipient and sender and message:
            message = self.controller.add_outgoing_message(backend, sender, recipient, message)
            return json.dumps(message.as_json())
        else:
            raise HTTPError(400, 
                            "Request format: /send?backend=<backend>&recipient=<phone>&sender=<phone>&message=<msg>")

    @cherrypy.expose
    def index(self):
        return "SMS Router"

class Backends():
    def __init__(self, backends):
        self.backends = backends

        # add each backend to our dict, this exposes each as /backends/<backend name>
        for key in self.backends:
            self.__dict__[key] = backends[key]

    @cherrypy.expose
    def index(self):
        html = "<html><body><ul>"
        for backend in self.backends:
            html += "<li>" + str(backend) + "</li>"
        html += "</li></body></html>"
        return html

def get_class(kls):
    if not kls:
        return None

    try:
        parts = kls.split('.')
        module = ".".join(parts[:-1])
        m = __import__( module )
        for comp in parts[1:]:
            m = getattr(m, comp)            
        return m
    except Exception as e:
        print "Error building class from path: %s" % kls
        raise e
