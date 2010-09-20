
PySMS Router
=============

This package provides a very basic server for handling and routing of SMS messages from multiple sources to a single HTTP endpoint.

Backends
--------

Backends represent different ways of sending and receiping SMS messages.  An example backend may read messages straight from a GSM modem, others may interact with Kannel or particular aggregators.  Two backends are included by default.

yo
~~~
This interacts with Uganda's Yo SMS aggregator.

mailbox
~~~~~~~~
This provides a simple HTTP interface for inserting messages to be sent, listing them, and marking them as sent.  It is primarily used as an interface to the relay package which acts relays messages from sms-tools via HTTP.

