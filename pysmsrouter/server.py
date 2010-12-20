import cherrypy
from cherrypy import HTTPError
import ConfigParser
import json
from urllib2 import urlopen
from urllib import urlencode

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
            backend.register(backend_name, self.controller, conf)

        # add our 'backends' controller
        self.backends = Backends(self.controller)

        # save our configuration
        self.conf = conf

    def start(self):
        # start our controller
        self.controller.start()
        
        port = int(self.conf.get("main", "port"))

        config = { 'global': { 'server.socket_host': '0.0.0.0', 'server.socket_port':  port } }

        # and start cherry py
        cherrypy.quickstart(self, config=config)

    @cherrypy.expose
    def send(self, id=None, backend=None, recipient=None, text=None):
        if backend and recipient and text:
            message = self.controller.add_outgoing_message(backend, backend, recipient, text, id=id)
            return json.dumps(message.as_json())
        else:
            raise HTTPError(400, 
                            "Request format: /send?backend=<backend>&recipient=<phone>&sender=<phone>&message=<msg>")

    @cherrypy.expose
    def index(self):
        return "SMS Router"

class Backends():
    def __init__(self, controller):
        self.controller = controller
        self.backends = controller.backends

        # add each backend to our dict, this exposes each as /backends/<backend name>
        for key in self.backends:
            self.__dict__[key] = self.backends[key]

    @cherrypy.expose
    def index(self):
        html = "<html><body><h2>backends</h2><ul>"
        for backend in self.backends:
            html += "<li>" + str(backend) + "</li>"
        html += "</ul>"

        messages = self.controller.get_recent_messages()
        messages.sort(key=lambda msg: msg.created)
        messages.reverse()

        html += "<h2>recent outgoing messages</h2>"
        html += "<table width='100%' border='1'><thead><tr><th>backend</th><th>time</th><th>recipient</th><th>message</th></tr></thead>"
        for message in messages:
            html += "<tr>"
            html += "<td width=100>" + message.backend + "</td>"
            html += "<td width=100>" + str(message.created) + "</td>"
            html += "<td width=100>" + message.recipient + "</td>"
            html += "<td><code>" + message.message + "</code></td>"
            html += "</td>"
        html += "</table>"

        html += "</body></html>"
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
