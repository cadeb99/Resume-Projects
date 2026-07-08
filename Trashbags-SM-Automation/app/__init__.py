"""Instagram DM automation — a small, robust proof of concept.

Each module maps to one of the project requirements:

    config        - Meta app credentials + backup-app switch (Req 1)
    main          - webhook server, fast ack, background processing (Req 2)
    ai            - Claude reply from product info, with latency fallback (Req 3)
    instagram     - send DMs with retry, verify webhook signatures (Req 4)
    takeover      - detect when a human should step in (Req 5)
    notifier      - alert the business owner (Req 5, 7)
    database      - log every message, reply, and error (Req 6)
"""
