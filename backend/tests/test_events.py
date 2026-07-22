from app.core.events import EventBus


def test_publish_delivers_to_all_subscribers():
    bus = EventBus()
    seen = []
    bus.subscribe("document.classified", lambda e, p: seen.append(("a", p)))
    bus.subscribe("document.classified", lambda e, p: seen.append(("b", p)))
    delivered = bus.publish("document.classified", {"kind": "boq"})
    assert delivered == 2
    assert seen == [("a", {"kind": "boq"}), ("b", {"kind": "boq"})]


def test_failing_handler_does_not_break_others():
    bus = EventBus()
    seen = []

    def bad(event, payload):
        raise RuntimeError("boom")

    bus.subscribe("finding.created", bad)
    bus.subscribe("finding.created", lambda e, p: seen.append(p))
    delivered = bus.publish("finding.created", {"id": 1})
    assert delivered == 1
    assert seen == [{"id": 1}]


def test_publish_without_subscribers_is_noop():
    assert EventBus().publish("nobody.cares") == 0
