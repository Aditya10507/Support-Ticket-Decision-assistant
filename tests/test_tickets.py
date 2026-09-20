# Test ticket data shape
from src.api import TicketRequest

# Ticket must have a message
def test_ticket_has_message():
    # Make a ticket with text
    t = TicketRequest(message="My box arrived broken")
    # Text should stay the same
    assert t.message == "My box arrived broken"
