class Backend():

    def register(self, name, controller, config):
        controller.register_backend(name, self)

    def send(self, sender, recipient, message):
        raise Exception("This backend does not support sending messages.")

    def receive(self, request):
        raise Exception("This backend does not support receiving messages.")
