class Backend():

    def send(sender, recipient, message):
        raise Exception("This backend does not support sending messages.")

    def receive(request):
        raise Exception("This backend does not support receiving messages.")

    def get_outbox():
        raise Exception("This backend does not have an outbox.")
